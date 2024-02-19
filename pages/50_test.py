import streamlit as st
import logging
from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI, HarmBlockThreshold, HarmCategory

logger = logging.getLogger("streamlit")


human = "Translate this sentence from English to French. I love programming."
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
