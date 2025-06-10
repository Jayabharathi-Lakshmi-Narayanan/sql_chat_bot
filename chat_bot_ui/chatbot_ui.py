import streamlit as st
import requests

BACKEND_URL = "http://127.0.0.1:8000/chat/"  # Django backend endpoint

st.set_page_config(page_title="SQL Chatbot", layout="centered")
st.title("SQL Chatbot")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Chat form for input
with st.form("chat_form"):
    user_question = st.text_input("Your Question:")
    submitted = st.form_submit_button("Send")

    if submitted and user_question.strip():
        payload = {
            "question": user_question,
            "chat_history": st.session_state.chat_history,
        }

        with st.spinner("Thinking..."):
            try:
                response = requests.post(BACKEND_URL, json=payload)
                response.raise_for_status()
                data = response.json()

                st.session_state.chat_history.append(
                    {
                        "user": user_question,
                        "bot": data.get("answer", "No explanation provided."),
                        "sql": data.get("sql", ""),
                        "raw_results": data.get("raw_results", "No results."),
                    }
                )
            except Exception as e:
                st.error(f"❌ Error communicating with backend: {e}")

# Display chat history
st.divider()
for chat in reversed(st.session_state.chat_history):
    st.markdown(f"**🧑 User:** {chat['user']}")
    st.markdown(f"**🤖 Bot:** {chat['bot']}")

    if chat.get("sql"):
        st.subheader("🧾 Generated SQL Query")
        st.code(chat["sql"], language="sql")

    if chat.get("raw_results"):
        st.subheader("📊 Raw SQL Results")
        if isinstance(chat["raw_results"], (dict, list)):
            st.json(chat["raw_results"])
        else:
            st.text(chat["raw_results"])

    st.markdown("---")
