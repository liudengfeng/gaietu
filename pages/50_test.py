import logging
from pathlib import Path

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
from vertexai.preview.generative_models import Image
from menu import menu
from mypylib.st_helper import add_exercises_to_db, check_access, configure_google_apis

logger = logging.getLogger("streamlit")
CURRENT_CWD: Path = Path(__file__).parent.parent
IMAGE_DIR: Path = CURRENT_CWD / "resource/multimodal"


st.set_page_config(
    page_title="人工智能",
    page_icon=":toolbox:",
    layout="wide",
)
menu()
check_access(False)
configure_google_apis()
add_exercises_to_db()

img_path = IMAGE_DIR / "math/高中/定积分.png"
i = Image.load_from_file(str(img_path))
st.image(str(img_path), caption="定积分", use_column_width=True)

llm = ChatVertexAI(model_name="gemini-pro-vision")
image_message = {
    "type": "image_url",
    "image_url": {
        "url": "https://python.langchain.com/assets/images/cell-18-output-1-0c7fb8b94ff032d51bfe1880d8370104.png",
    },
}
text_message = {
    "type": "text",
    "text": "What is shown in this image?",
}
message = HumanMessage(content=[text_message, image_message])


if st.button("执行"):
    output = llm([message])
    st.write(output.content)
