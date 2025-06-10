import json
import logging
import os
from urllib.parse import quote_plus

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from langchain_community.utilities import SQLDatabase

from .sql_agent import (
    get_sql_agent,
    get_explanation_llm,
    run_sql_query,
    trim_chat_history,
    load_or_generate_metadata,
)

logger = logging.getLogger(__name__)

# Load DB config
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASSWORD", "Yakkay@123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "employeedb")

encoded_password = quote_plus(DB_PASS)
db_uri = f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
db = SQLDatabase.from_uri(db_uri)

# Load metadata and initialize chains
rich_schema = load_or_generate_metadata()
agent = get_sql_agent(rich_schema)
explanation_chain = get_explanation_llm()


def format_raw_results(raw_results):
    if not raw_results:
        return "No results found."
    if isinstance(raw_results, list):
        if len(raw_results) > 0 and isinstance(raw_results[0], tuple):
            return [
                {"value": row[0]} if len(row) == 1 else list(row) for row in raw_results
            ]
        return raw_results
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

        chat_history_str = trim_chat_history(chat_history, max_tokens=256)
        prompt_length = len(rich_schema) + len(chat_history_str) + len(user_question)
        logger.info(f"Prompt size: {prompt_length}")

        try:
            response = agent.invoke(
                {
                    "schema": rich_schema,
                    "chat_history": chat_history_str,
                    "question": user_question,
                }
            )

            sql_query = (
                response["text"].strip()
                if isinstance(response, dict) and "text" in response
                else str(response).strip()
            )

            raw_results = run_sql_query(db, sql_query)

        except Exception as e:
            logger.exception(f"Error generating or running SQL: {e}")
            return JsonResponse(
                {"error": "Failed to process your question."}, status=500
            )

        formatted_results = format_raw_results(raw_results)

        try:
            explanation_text = explanation_chain.invoke(
                {
                    "question": user_question,
                    "raw_results": json.dumps(formatted_results, indent=2)
                    if isinstance(formatted_results, (dict, list))
                    else formatted_results,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to generate explanation: {e}")
            explanation_text = "Explanation not available."

        return JsonResponse(
            {
                "question": user_question,
                "sql": sql_query,
                "raw_results": formatted_results,
                "answer": explanation_text,
            }
        )

    except json.JSONDecodeError:
        logger.warning("Invalid JSON received")
        return JsonResponse({"error": "Invalid JSON format"}, status=400)

    except Exception:
        logger.exception("Unexpected error in chat_view:")
        return JsonResponse({"error": "Internal Server Error"}, status=500)
