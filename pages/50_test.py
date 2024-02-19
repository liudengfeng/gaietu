import logging

import streamlit as st
from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI, HarmBlockThreshold, HarmCategory

logger = logging.getLogger("streamlit")


llm = ChatVertexAI(
    model="gemini-pro-vision",
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
