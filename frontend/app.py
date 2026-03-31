import streamlit as st
import requests
import os
import html
from datetime import datetime
import re

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="MVP", page_icon=":)", layout="wide")

# css
st.markdown(
    """
    <style>
    .chat-container {
        display: flex;
        flex-direction: column;
        height: 70vh;
        border: 1px solid #ccc;
        padding: 10px;
        overflow-y: auto;
        background-color: #f8f9fa;
        border-radius: 10px;
    }
    .chat-msg {
        padding: 8px 12px;
        margin: 5px;
        border-radius: 12px;
        max-width: 60%;
        word-wrap: break-word;
    }
    .user-msg { background-color: #e0e0e0; align-self: flex-end; text-align: right; }
    .bot-msg { background-color: #d0eaff; align-self: flex-start; text-align: left; }
    .timestamp { font-size: 10px; color: gray; margin-top: 2px; }
    .input-container { display: flex; margin-top: 10px; }
    .csv-upload-box { border: 2px dashed #aaa; border-radius: 8px; width: 50px; height: 50px;
        text-align: center; font-size: 30px; cursor: pointer; line-height: 40px; margin-right: 10px; color: #666;}
    .send-button { background-color: #007bff; color: white; border-radius: 50%; width: 45px; height: 45px;
        text-align: center; line-height: 45px; font-size: 20px; cursor: pointer; margin-left: 5px; border: none;}
    </style>
    """,
    unsafe_allow_html=True,
)

# title
st.markdown("<h1 style='text-align: center;'>Chatbot</h1>", unsafe_allow_html=True)


# states
if "messages" not in st.session_state:
    st.session_state.messages = []

if "show_upload" not in st.session_state:
    st.session_state.show_upload = False
    
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None


# chat verlauf
chat_container = st.container()
with chat_container:
    chat_html = '<div class="chat-container">'
    for msg in st.session_state.messages:
        content = html.escape(msg["content"]).replace("\n", "<br>")
        ts = msg.get("time", "")

        if msg["role"] == "user":
            chat_html += f'<div class="chat-msg user-msg">{content}<div class="timestamp">{ts}</div></div>'
        else:
            clean_content = re.sub(r"<.*?>", "", content).strip()
            chat_html += f'<div class="chat-msg bot-msg">{clean_content}<div class="timestamp">{ts}</div></div>'

    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)



# input bereich unter chat verlauf
with st.form(key="chat_form", clear_on_submit=True):
    cols = st.columns([8,1, 1])

    # TEXT INPUT
    with cols[0]:
        user_input = st.text_input("Type your message...", key="input")

    # SEND BUTTON
    with cols[1]:
        send = st.form_submit_button("➡️")

    # ATTACH BUTTON
    with cols[2]:
        attach_clicked = st.form_submit_button("📎")
        if attach_clicked:
            st.session_state.show_upload = not st.session_state.show_upload

# UPLOAD-BEREICH
if st.session_state.show_upload:
    uploaded = st.file_uploader(
        "Upload CSV",
        type=["csv"],
        key="file_uploader",
        label_visibility="collapsed"  # optional, damit Label minimal ist
    )

    if uploaded:
        # Wenn schon eine Datei existiert -> automatisch ersetzen
        st.session_state.uploaded_file = uploaded
        st.success(f"Datei '{uploaded.name}' hochgeladen!")
    



# sending logik
if send and (user_input or st.session_state.uploaded_file):

    timestamp = datetime.now().strftime("%H:%M")

    # usertext
    if user_input:
        st.session_state.messages.append(
            {"role": "user", "content": user_input, "time": timestamp}
        )

    # scvanzeige im chat
    if st.session_state.uploaded_file:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": f"CSV: {st.session_state.uploaded_file.name}",
                "time": timestamp,
            }
        )

    # payload
    payload = {"message": user_input}

    if st.session_state.uploaded_file:
        st.session_state.uploaded_file.seek(0)
        payload["file_name"] = st.session_state.uploaded_file.name
        payload["file_content"] = st.session_state.uploaded_file.read().decode("utf-8")

    try:
        response = requests.post(f"{API_URL}/chat", json=payload, timeout=30)
        raw_response = response.json().get("response", "No response") #daten in json
        bot_response = re.sub(r"<.*?>", "", raw_response).strip()
    except Exception as e:
        bot_response = f"Could not reach the backend: {e}"

    # BOT MESSAGE
    bot_time = datetime.now().strftime("%H:%M")
    st.session_state.messages.append(
        {"role": "bot", "content": bot_response, "time": bot_time}
    )

    # reset 
    st.session_state.uploaded_file = None
    st.session_state.show_upload = False

    st.rerun()