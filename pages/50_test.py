import base64
import json
import logging
import mimetypes
import os
import tempfile
from datetime import timedelta
from operator import itemgetter
from pathlib import Path

import streamlit as st
from langchain.agents import AgentExecutor, BaseMultiActionAgent, Tool
from langchain.chains import LLMMathChain

# from langchain.callbacks import StreamlitCallbackHandler
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.tools import StructuredTool
from langchain_community.callbacks import StreamlitCallbackHandler
from langchain_community.document_loaders import MathpixPDFLoader, WebBaseLoader
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.utilities import SerpAPIWrapper
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnableBranch, RunnableConfig, RunnableLambda
from langchain_experimental.llm_symbolic_math.base import LLMSymbolicMathChain
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


EXTRACT_TEST_QUESTION_PROMPT = """从图片中提取数学题文本，不包含示意图、插图。
使用 $ 或 $$ 来正确标识变量和数学表达式。
如果内容以表格形式呈现，应使用 Markdown 中的 HTML 表格语法进行编写。
输出 Markdown 代码。
"""


@st.cache_data(ttl=timedelta(hours=1))
def image_to_dict(uploaded_file):
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


def get_current_date():
    """
    Gets the current date (today), in the format YYYY-MM-DD
    """

    from datetime import datetime

    todays_date = datetime.today().strftime("%Y-%m-%d")

    return todays_date


# endregion


# region LCEL

# endregion

ANSWER_MATH_QUESTION_PROMPT = """
Let's think step by step. You are proficient in mathematics, calculate the math problems in the image step by step.
Use `$` or `$$` to correctly identify inline or block-level mathematical variables and formulas."""

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


text = st.text_input("输入问题")


def route(info):
    if "anthropic" in info["topic"].lower():
        logger.info("anthropic_chain")
        return anthropic_chain
    elif "langchain" in info["topic"].lower():
        logger.info("langchain_chain")
        return langchain_chain
    else:
        logger.info("general_chain")
        return general_chain


if st.button("执行"):
    model = ChatVertexAI(
        model_name="gemini-pro-vision",
        temperature=0.0,
        max_retries=1,
        convert_system_message_to_human=True,
    )
    chain = (
        PromptTemplate.from_template(
            """Given the user question below, classify it as either being about `LangChain`, `Anthropic`, or `Other`.

Do not respond with more than one word.

<question>
{question}
</question>

Classification:"""
        )
        | model
        | StrOutputParser()
    )
    langchain_chain = (
        PromptTemplate.from_template(
            """You are an expert in langchain. \
Always answer questions starting with "As Harrison Chase told me". \
Respond to the following question:

Question: {question}
Answer:"""
        )
        | model
    )
    anthropic_chain = (
        PromptTemplate.from_template(
            """You are an expert in anthropic. \
Always answer questions starting with "As Dario Amodei told me". \
Respond to the following question:

Question: {question}
Answer:"""
        )
        | model
    )
    general_chain = (
        PromptTemplate.from_template(
            """Respond to the following question:

Question: {question}
Answer:"""
        )
        | model
    )

    branch = RunnableBranch(
        (lambda x: "anthropic" in x["topic"].lower(), anthropic_chain),
        (lambda x: "langchain" in x["topic"].lower(), langchain_chain),
        general_chain,
    )
    full_chain = {"topic": chain, "question": lambda x: x["question"]} | branch
    # full_chain.invoke({"question": "how do I use Anthropic?"})

    st.markdown(full_chain.invoke({"question": text}))

if st.button("graph", key="wiki"):
    from langchain_community.tools import WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper

    api_wrapper = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=100)
    tool = WikipediaQueryRun(api_wrapper=api_wrapper)
    st.markdown(tool.run({"query": "langchain"}))
