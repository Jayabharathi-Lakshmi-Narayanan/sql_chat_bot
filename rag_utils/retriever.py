# D:\jb\chat_with_mysql\rag_utils\retriever.py

from langchain_community.vectorstores.faiss import FAISS
from langchain_community.embeddings.huggingface import HuggingFaceEmbeddings
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(BASE_DIR, "..", "config", "faiss_index")


def retrieve_relevant_schema(question: str, index_path=INDEX_PATH, k=3) -> str:
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    db = FAISS.load_local(
        index_path, embedding_model, allow_dangerous_deserialization=True
    )
    docs = db.similarity_search(question, k=k)
    return "\n\n".join([doc.page_content for doc in docs])
