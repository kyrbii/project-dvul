import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.title("MVP")
msg = st.text_input("Send a message:")
if st.button("Send") and msg:
    resp = requests.post(f"{API_URL}/chat", json={"message": msg})
    st.write(resp.json().get("response"))
