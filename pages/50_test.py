import logging

import streamlit as st
from langchain_community.document_loaders import MathpixPDFLoader
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_google_vertexai import (
    ChatVertexAI,
    HarmBlockThreshold,
    HarmCategory,
    VertexAI,
)
from menu import menu
from mypylib.st_helper import add_exercises_to_db, check_access, configure_google_apis

logger = logging.getLogger("streamlit")

st.set_page_config(
    page_title="人工智能",
    page_icon=":toolbox:",
    layout="wide",
)
menu()
check_access(False)
configure_google_apis()
add_exercises_to_db()


llm = ChatVertexAI(model_name="gemini-pro-vision")
image_message = {
    "type": "image_url",
    "image_url": {"url": "dog.png"},
}
text_message = {
    "type": "text",
    "text": "What is shown in this image?",
}
message = HumanMessage(content=[text_message, image_message])


if st.button("执行"):
    output = llm([message])
    st.write(output.content)
