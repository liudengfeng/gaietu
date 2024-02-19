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


model = VertexAI(model_name="gemini-pro")
template = """Question: {question}

Answer: Let's think step by step."""
prompt = PromptTemplate.from_template(template)

chain = prompt | model

question = """
I have five apples. I throw two away. I eat one. How many apples do I have left?
"""

if st.button("Generate"):
    st.write(chain.invoke({"question": question}))
