# views.py
import os
import json
import logging
from urllib.parse import quote_plus

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase

from .sql_agent import (
    dynamic_get_sql_response,
    get_explanation_llm,
    run_sql_query,
    parse_schema_to_dict,
    validate_sql_against_schema,
    load_or_generate_metadata,
)

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv(dotenv_path="D:/jb/chat_with_mysql/config/.env")

# DB config
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Yakkay@123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "employeedb")

# Build DB URI
encoded_password = quote_plus(DB_PASSWORD)
db_uri = f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
db = SQLDatabase.from_uri(db_uri)

# Preload schema and explanation chain
rich_schema = load_or_generate_metadata()
schema_dict = parse_schema_to_dict(rich_schema)
explanation_chain = get_explanation_llm()


def format_raw_results(raw_results):
    if not raw_results:
        return "No results found."
    if isinstance(raw_results, list):
        return [
            {"value": row[0]} if len(row) == 1 else list(row) for row in raw_results
        ]
    return str(raw_results)


@csrf_exempt
def chat_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST method allowed"}, status=405)

    if request.content_type != "application/json":
        return JsonResponse(
            {"error": "Content-Type must be application/json"}, status=415
        )

    try:
        data = json.loads(request.body)
        user_question = data.get("question", "").strip()
        chat_history = data.get("chat_history", [])

        if not user_question:
            return JsonResponse({"error": "Empty question"}, status=400)

        logger.info("User question received")
        response = dynamic_get_sql_response(user_question, chat_history)
        sql_query = (
            response["text"].strip()
            if isinstance(response, dict)
            else str(response).strip()
        )

        logger.debug("Generated SQL query")
        validation_errors = validate_sql_against_schema(sql_query, schema_dict)

        if validation_errors:
            return JsonResponse(
                {
                    "question": user_question,
                    "sql": sql_query,
                    "raw_results": [],
                    "answer": "SQL validation failed. Here is the generated SQL.",
                    "details": validation_errors,
                }
            )

        raw_results = run_sql_query(db, sql_query)
        formatted_results = format_raw_results(raw_results)

        try:
            explanation_text = explanation_chain.invoke(
                {
                    "question": user_question,
                    "raw_results": json.dumps(formatted_results, indent=2),
                }
            )
        except Exception as e:
            logger.warning(f"Explanation LLM failed: {e}")
            explanation_text = "Explanation not available."

        return JsonResponse(
            {
                "question": user_question,
                "sql": sql_query,
                "raw_results": formatted_results,
                "answer": explanation_text.get("text", "Explanation not available.")
                if isinstance(explanation_text, dict)
                else explanation_text or "Explanation not available.",
            }
        )

    except Exception:
        logger.exception("Unexpected error in chat_view:")
        return JsonResponse({"error": "Internal Server Error"}, status=500)
