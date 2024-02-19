import logging

import streamlit as st
from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI, HarmBlockThreshold, HarmCategory

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

llm = ChatVertexAI(
    model_name="gemini-pro-vision",
)

# example
message = HumanMessage(
    content=[
        {
            "type": "text",
            "text": "What's in this image?",
        },  # You can optionally provide text parts
        {"type": "image_url", "image_url": "https://picsum.photos/seed/picsum/200/300"},
    ]
)


if st.button("Generate"):
    result = llm.invoke([message])
    st.write(result)
