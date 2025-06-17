# --- sql_agent.py ---

import re
from collections import defaultdict
import sqlparse
from sqlparse.sql import IdentifierList, Identifier
from sqlparse.tokens import Keyword

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableMap
from langchain_community.utilities import SQLDatabase
from langchain_community.llms import LlamaCpp

from rag_utils.retriever import retrieve_relevant_schema

MODEL_PATH = r"D:\jb\Yakkaybot\yakkay_backend\mistral-7b-instruct-v0.2.Q4_K_M.gguf"


def create_llm(temperature=0.0, max_tokens=2048):
    return LlamaCpp(
        model_path=MODEL_PATH,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
        n_ctx=2048,
        verbose=False,
    )


def get_sql_agent(schema_text: str):
    prompt_template = """
You are a helpful data analyst. You are given the database schema below. Based on the schema and the user's question, generate a valid SQL query to answer the question.

<SCHEMA>
{schema}
</SCHEMA>

Conversation History:
{chat_history}

Now write only the SQL query. Do not add any other text.

Question: {question}
SQL Query:
""".strip()

    prompt = PromptTemplate.from_template(prompt_template)

    return (
        RunnableMap(
            {
                "schema": lambda x: schema_text,
                "chat_history": lambda x: x.get("chat_history", ""),
                "question": lambda x: x["question"],
            }
        )
        | prompt
        | create_llm()
    )


def clean_sql_output(response_text: str) -> str:
    return re.sub(
        r"^```(?:sql)?|```$", "", response_text.strip(), flags=re.IGNORECASE
    ).strip()


def dynamic_get_sql_response(user_question: str, chat_history: list):
    fallback = handle_fallback_question(user_question)
    if fallback:
        return {"text": fallback["answer"]}

    chat_history_str = trim_chat_history(chat_history)
    schema_chunk = retrieve_relevant_schema(user_question)
    agent = get_sql_agent(schema_chunk)
    response = agent.invoke(
        {
            "question": user_question,
            "chat_history": chat_history_str,
        }
    )

    response_text = response if isinstance(response, str) else str(response)
    cleaned_sql = clean_sql_output(response_text)
    return {"text": cleaned_sql}


def handle_fallback_question(question: str) -> dict | None:
    q = question.lower().strip()
    if "name of the database" in q or "which database" in q:
        try:
            from decouple import config

            db_name = config("DB_NAME", default="(unknown)")
            return {"answer": f"The database currently connected is `{db_name}`."}
        except ImportError:
            return {
                "answer": "Could not retrieve database name. Required module missing."
            }
    return None


def get_explanation_llm():
    prompt_template = """
You are a helpful assistant. Given the user's question and the raw SQL result, provide a clear explanation in simple language.

Question:
{question}

SQL Results:
{raw_results}

Explanation:
""".strip()

    prompt = PromptTemplate.from_template(prompt_template)

    return (
        RunnableMap(
            {
                "question": lambda x: x["question"],
                "raw_results": lambda x: x["raw_results"],
            }
        )
        | prompt
        | create_llm(temperature=0.7, max_tokens=1024)
    )


def run_sql_query(db: SQLDatabase, sql_query: str):
    try:
        return db.run(sql_query)
    except Exception as e:
        return f"SQL Execution Error: {str(e)}"


def trim_chat_history(chat_history: list, max_tokens: int = 1024) -> str:
    combined = ""
    for turn in reversed(chat_history):
        piece = ""
        if isinstance(turn, dict):
            piece = f"User: {turn.get('user', '')}\nBot: {turn.get('bot', '')}\n"
        else:
            piece = str(turn) + "\n"
        if len(combined) + len(piece) > max_tokens:
            break
        combined = piece + combined
    return combined.strip()


def parse_schema_to_dict(schema: str) -> dict:
    schema_dict = defaultdict(list)
    table_matches = re.findall(r"Table: (\w+)\n((?:- .+\n)+)", schema)
    for table_name, columns_block in table_matches:
        for line in columns_block.strip().splitlines():
            match = re.match(r"- (\w+)", line)
            if match:
                column_name = match.group(1)
                schema_dict[table_name].append(column_name)
    return dict(schema_dict)


def extract_tables_and_aliases(parsed):
    tables = {}
    from_seen = False
    for token in parsed.tokens:
        if token.is_group:
            tables.update(extract_tables_and_aliases(token))
        if token.ttype is Keyword and token.value.upper() in ("FROM", "JOIN"):
            from_seen = True
            continue
        if from_seen:
            if isinstance(token, IdentifierList):
                for identifier in token.get_identifiers():
                    real_name = identifier.get_real_name()
                    alias = identifier.get_alias() or real_name
                    tables[alias] = real_name
            elif isinstance(token, Identifier):
                real_name = token.get_real_name()
                alias = token.get_alias() or real_name
                tables[alias] = real_name
            from_seen = False
    return tables


def extract_column_references(parsed):
    columns = set()
    for token in parsed.tokens:
        if token.is_group:
            columns |= extract_column_references(token)
        elif isinstance(token, IdentifierList):
            for identifier in token.get_identifiers():
                columns.add(identifier.get_name())
        elif isinstance(token, Identifier):
            columns.add(token.get_name())
    return columns


def validate_sql_against_schema(sql_query: str, schema_dict: dict) -> list:
    errors = []
    parsed_statements = sqlparse.parse(sql_query)

    for parsed in parsed_statements:
        if parsed.get_type() != "SELECT":
            continue

        table_aliases = extract_tables_and_aliases(parsed)
        column_refs = extract_column_references(parsed)

        for alias, table in table_aliases.items():
            if table not in schema_dict:
                errors.append(f"Unknown table: {table}")

        for col in column_refs:
            if "." in col:
                alias, col_name = col.split(".", 1)
                table = table_aliases.get(alias)
                if not table or col_name not in schema_dict.get(table, []):
                    errors.append(f"Unknown column: {col}")
            else:
                found = any(
                    col in schema_dict.get(table, [])
                    for table in table_aliases.values()
                )
                if not found:
                    errors.append(f"Unknown or ambiguous column: {col}")

    return errors


def load_or_generate_metadata(path="config/rich_metadata.txt"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Metadata file not found at {path}. Please run `show_schema.py` to generate it."
        )
