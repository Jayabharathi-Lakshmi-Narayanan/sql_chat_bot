# SQL Chatbot with RAG + FAISS + LLM (Mistral)

<img src="image/work%20flow.png" width="600"/>

This project is an end-to-end intelligent chatbot system that enables natural language querying over a MySQL database using:

- Retrieval-Augmented Generation (RAG)
- FAISS-based schema indexing
- Mistral 7B via `llama.cpp`
- LangChain for orchestration
- SQL validation + result explanation
- Streamlit frontend + Django backend

---

## Tech Stack

| Layer         | Tool / Library                          |
| ------------- | --------------------------------------- |
| LLM           | `mistral-7b-instruct` (via `llama.cpp`) |
| Embeddings    | `HuggingFaceEmbeddings` (`MiniLM`)      |
| Vector Store  | `FAISS`                                 |
| Orchestration | `LangChain`                             |
| DB Layer      | `SQLAlchemy` + MySQL                    |
| Frontend      | `Streamlit`                             |
| Backend       | `Django` + REST                         |

---

## Setup Instructions

1. Environment Setup

```bash
git clone <your-repo>
cd project folder

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

2. Download Mistral LLM and Place the mistral-7b-instruct-v0.2.Q4_K_M.gguf model
   You can download it from HuggingFace: Mistral

3. Generate Rich Schema for RAG
   python rag_utils/show_schema.py
   This creates a rich metadata schema of your MySQL DB in:
   config/rich_metadata.txt

4. Chunk + Index Schema (FAISS)
   python rag_utils/index_builder.py
   This creates a faiss_index folder storing vectorized schema chunks.

5. Run
   python manage.py migrate
   python manage.py makemigrations
   python manage.py runserver
   cd chat_bot_ui/
   streamlit run chatbot_ui.py
