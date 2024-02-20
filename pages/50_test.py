import base64
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
from mypylib.st_setting import general_config
from langchain_community.document_loaders import WebBaseLoader

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
general_config()
add_exercises_to_db()


# region 函数


def image_to_dict(image_path):
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    image_message = {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        },
    }

    return image_message


# endregion


llm = ChatVertexAI(model_name="gemini-pro-vision")


if st.button("执行"):
    text_message = {
        "type": "text",
        "text": "What is shown in this image?",
    }
    img_path = IMAGE_DIR / "math/高中/定积分.png"
    i = Image.load_from_file(str(img_path))
    st.image(str(img_path), caption="定积分", use_column_width=True)
    message = HumanMessage(content=[text_message, image_to_dict(str(img_path))])
    output = llm([message])

    loader = WebBaseLoader("https://docs.smith.langchain.com")
    docs = loader.load()
    
    st.write(output.content)
