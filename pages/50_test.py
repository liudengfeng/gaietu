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

human = "Translate this sentence from English to Chinese. I love programming."
messages = [HumanMessage(content=human)]

chat = ChatVertexAI(
    model_name="gemini-pro",
    safety_settings={
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
    },
)


if st.button("Generate"):
    result = chat.generate([messages])
    st.write(result.generations[0][0].generation_info)
