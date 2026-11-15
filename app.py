"""Streamlit user interface."""
import os
import requests
import streamlit as st

API = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
st.title("RAG Demo")
st.caption("Upload documents, then ask grounded questions.")
file = st.file_uploader("Choose PDF, TXT or Markdown", type=["pdf", "txt", "md"])
if st.button("Index document", disabled=file is None):
    try:
        response = requests.post(f"{API}/ingest",
                                 files={"file": (file.name, file.getvalue())}, timeout=300)
        response.raise_for_status()
        st.success(f"Indexed {response.json()['chunks_indexed']} chunks.")
    except (requests.RequestException, ValueError, KeyError) as exc:
        st.error(f"Indexing failed: {exc}")

question = st.text_input("Ask a question")
if st.button("Ask", disabled=not question.strip()):
    try:
        response = requests.post(f"{API}/query", json={"question": question}, timeout=240)
        response.raise_for_status()
        result = response.json()
        st.write(result["answer"])
        st.write("Retrieved sources:", result["sources"])
    except (requests.RequestException, ValueError, KeyError) as exc:
        st.error(f"Query failed: {exc}")
