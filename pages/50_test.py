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
        "url": "https://www.google.com/url?sa=i&url=https%3A%2F%2Fwww.jczhijia.com%2Fart%2F22718.html&psig=AOvVaw2G0NClgL5OB_NHY_leH6YK&ust=1708488102597000&source=images&cd=vfe&opi=89978449&ved=0CBIQjRxqFwoTCMDMsKWEuYQDFQAAAAAdAAAAABAE",
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
