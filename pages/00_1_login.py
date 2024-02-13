from pathlib import Path
import streamlit as st
import firebase_admin

from firebase_admin import credentials, auth

CURRENT_CWD: Path = Path(__file__).parent.parent

cred = credentials.Certificate(CURRENT_CWD / ".streamlit" / "serviceAccountKey.json")
default_app = firebase_admin.initialize_app(cred)


def app():
    st.title("Login")
    choice = st.radio("Login or Register", ("Login", "Register"))
    if choice == "Login":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            try:
                user = auth.get_user_by_email(email)
                st.success("Logged in")
            except:
                st.error("Invalid credentials")
