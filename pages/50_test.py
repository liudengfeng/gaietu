import base64
import json
import logging
import mimetypes
import os
import tempfile
from operator import itemgetter
from pathlib import Path

import streamlit as st

# from langchain.callbacks import StreamlitCallbackHandler
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.callbacks import StreamlitCallbackHandler
from langchain_community.document_loaders import MathpixPDFLoader, WebBaseLoader
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnableConfig, RunnableLambda
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


def parse_or_fix(text: str, config: RunnableConfig):
    fixing_chain = (
        ChatPromptTemplate.from_template(
            "Fix the following text:\n\n```text\n{input}\n```\nError: {error}"
            " Don't narrate, just respond with the fixed data."
        )
        | ChatVertexAI(model_name="gemini-pro")
        | StrOutputParser()
    )
    for _ in range(3):
        try:
            return json.loads(text)
        except Exception as e:
            text = fixing_chain.invoke({"input": text, "error": e}, config)
    return "Failed to parse"


EXTRACT_TEST_QUESTION_PROMPT = """从图片中提取数学题文本，不包含示意图、插图。
使用 $ 或 $$ 来正确标识变量和数学表达式。
如果内容以表格形式呈现，应使用 Markdown 中的 HTML 表格语法进行编写。
输出 Markdown 代码。
"""


def image_to_dict(uploaded_file):
    image_bytes = uploaded_file.getvalue()
    mime_type = uploaded_file.type
    # mime_type = mimetypes.guess_type(uploaded_file.name)[0]
    st.warning(f"mime_type: {mime_type}")
    if mime_type == "image/jpeg":
        data_url = (
            f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        )
    elif mime_type == "image/png":
        data_url = (
            f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        )
    else:
        raise ValueError("Unsupported file type")

    image_message = {
        "type": "image_url",
        "image_url": {"url": data_url},
    }
    return image_message


def image_to_file(uploaded_file):
    # 获取图片数据
    image_bytes = uploaded_file.getvalue()

    # 获取文件的 MIME 类型
    mime_type = uploaded_file.type

    # 根据 MIME 类型获取文件扩展名
    ext = mimetypes.guess_extension(mime_type)

    # 创建一个临时文件，使用正确的文件扩展名
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)

    # 将图片数据写入临时文件
    temp_file.write(image_bytes)
    temp_file.close()

    # 返回临时文件的路径
    image_message = {
        "type": "image_url",
        "image_url": {"url": temp_file.name},
    }
    return image_message


# endregion


# llm = VertexAI(model_name="gemini-pro-vision")
# llm = VertexAI(model_name="gemini-pro")

# st_cb = StreamlitCallbackHandler(st.container(), expand_new_thoughts=False)

question = """The cafeteria had 23 apples.
If they used 20 to make lunch and bought 6 more, how many apples do they have?"""

context = """Answer questions showing the full math and reasoning.
Follow the pattern in the example.
"""

one_shot_exemplar = """Example Q: Roger has 5 tennis balls. He buys 2 more cans of tennis balls.
Each can has 3 tennis balls. How many tennis balls does he have now?
A: Roger started with 5 balls. 2 cans of 3 tennis balls
each is 6 tennis balls. 5 + 6 = 11.
The answer is 11.

Q: """

uploaded_file = st.file_uploader(
    "上传数学试题图片【点击`Browse files`按钮，从本地上传文件】",
    accept_multiple_files=False,
    key="uploaded_file",
    type=["png", "jpg"],
    # on_change=create_math_chat,
    help="""
支持的格式
- 图片：PNG、JPG
""",
)

if st.button("执行"):
    # text_message = {
    #     "type": "text",
    #     "text": "What is shown in this image?",
    # }
    # img_path = IMAGE_DIR / "math/高中/定积分.png"
    # i = Image.load_from_file(str(img_path))
    # st.image(str(img_path), caption="定积分", use_column_width=True)
    # message = HumanMessage(content=[text_message, image_to_dict(str(img_path))])
    # output = llm([message])
    llm = ChatVertexAI(model_name="gemini-pro-vision", temperature=0.0)
    image_url = "https://picsum.photos/seed/picsum/300/300"
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": EXTRACT_TEST_QUESTION_PROMPT,
            },  # You can optionally provide text parts
            image_to_file(uploaded_file),
        ]
    )
    st.markdown(llm.invoke([message]).content)
