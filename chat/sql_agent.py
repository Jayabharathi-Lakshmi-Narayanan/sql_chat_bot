import os
import re
import subprocess
from collections import defaultdict

from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableMap
from langchain_community.utilities import SQLDatabase
from langchain_community.llms import LlamaCpp

# Paths
METADATA_PATH = r"D:\jb\chat_with_mysql\config\rich_metadata.txt"
MODEL_PATH = r"D:\jb\Yakkaybot\yakkay_backend\mistral-7b-instruct-v0.2.Q4_K_M.gguf"


def load_or_generate_metadata():
    if not os.path.exists(METADATA_PATH):
        try:
            subprocess.run(["python", "config/show_schema.py"], check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError("Could not regenerate rich_metadata.txt") from e

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        return f.read()


def create_llm(temperature=0.0, max_tokens=2048):
    return LlamaCpp(
        model_path=MODEL_PATH,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=0.9,
        n_ctx=2048,
        verbose=False,
    )


def get_sql_agent(rich_schema):
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
                "schema": lambda x: rich_schema,
                "chat_history": lambda x: x.get("chat_history", ""),
                "question": lambda x: x["question"],
            }
        )
        | prompt
        | create_llm(temperature=0.0)
    )


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
        if isinstance(turn, dict):
            piece = f"User: {turn.get('user', '')}\nBot: {turn.get('bot', '')}\n"
        else:
            piece = str(turn) + "\n"
        if len(combined) + len(piece) > max_tokens:
            break
        combined = piece + combined
    return combined.strip()


# ✅ Utility to parse schema into structured format
def parse_schema_to_dict(schema: str) -> dict:
    schema_dict = defaultdict(list)
    table_matches = re.findall(r"Table: (\w+)\nColumns:\n((?:\s+- .+\n)+)", schema)
    for table_name, columns_block in table_matches:
        column_lines = columns_block.strip().splitlines()
        for line in column_lines:
            match = re.match(r"\s*-\s*(\w+)", line)
            if match:
                column_name = match.group(1)
                schema_dict[table_name].append(column_name)
    return dict(schema_dict)


# ✅ Validate generated SQL against schema
def validate_sql_against_schema(sql_query: str, schema_dict: dict) -> list:
    errors = []
    tables_in_query = re.findall(r"(?:from|join)\s+(\w+)", sql_query, re.IGNORECASE)
    tables = set(tables_in_query)

    for table in tables:
        if table not in schema_dict:
            errors.append(f"Unknown table: {table}")

    for table, columns in schema_dict.items():
        for col in re.findall(rf"{table}\.(\w+)", sql_query):
            if col not in columns:
                errors.append(f"Unknown column: {table}.{col}")

    return errors
