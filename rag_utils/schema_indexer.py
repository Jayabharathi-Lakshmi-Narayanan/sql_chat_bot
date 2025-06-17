# D:\jb\chat_with_mysql\rag_utils\schema_indexer.py

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.docstore.document import Document


def build_schema_index(schema_chunks: list[dict], index_path="faiss_index"):
    documents = [
        Document(page_content=chunk["content"], metadata={"table": chunk["table"]})
        for chunk in schema_chunks
    ]
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    db = FAISS.from_documents(documents, embedding_model)
    db.save_local(index_path)
