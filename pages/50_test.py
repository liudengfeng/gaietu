import logging

import streamlit as st
from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI, HarmBlockThreshold, HarmCategory
from langchain_google_vertexai import VertexAI
from menu import menu
from mypylib.st_helper import add_exercises_to_db, check_access, configure_google_apis

logger = logging.getLogger("streamlit")

st.set_page_config(
    page_title="人工智能",
    page_icon=":gemini:",
    layout="wide",
)
menu()
check_access(False)
configure_google_apis()
add_exercises_to_db()


model = VertexAI(model_name="gemini-pro")


if st.button("Generate"):
    message = "What are some of the pros and cons of Python as a programming language?"
    st.write(model.invoke(message))
