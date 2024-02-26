import base64
import json
import logging
import mimetypes
import os
import tempfile
from datetime import timedelta
from operator import itemgetter
from pathlib import Path

# from langchain.callbacks import StreamlitCallbackHandler
from typing import List, Tuple

import streamlit as st
from langchain.agents import AgentExecutor, BaseMultiActionAgent, Tool
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.chains import LLMMathChain
from langchain.utilities.tavily_search import TavilySearchAPIWrapper
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_google_vertexai import (
    ChatVertexAI,
    HarmBlockThreshold,
    HarmCategory,
    VertexAI,
)
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


def _format_chat_history(chat_history: List[Tuple[str, str]]):
    buffer = []
    for human, ai in chat_history:
        buffer.append(HumanMessage(content=human))
        buffer.append(AIMessage(content=ai))
    return buffer


class AgentInput(BaseModel):
    input: str
    chat_history: List[Tuple[str, str]] = Field(
        ..., extra={"widget": {"type": "chat", "input": "input", "output": "output"}}
    )


if st.button("执行"):
    llm = ChatVertexAI(
        model_name="gemini-pro-vision",
        temperature=0.0,
        max_retries=1,
        convert_system_message_to_human=True,
    )
    # Create the tool
    search = TavilySearchAPIWrapper()
    description = """"A search engine optimized for comprehensive, accurate, \
    and trusted results. Useful for when you need to answer questions \
    about current events or about recent information. \
    Input should be a search query. \
    If the user is asking about something that you don't know about, \
    you should probably use this tool to see if that can provide any information."""
    tavily_tool = TavilySearchResults(api_wrapper=search, description=description)

    tools = [tavily_tool]

    prompt = ChatPromptTemplate.from_messages(
        [
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    llm_with_tools = llm.bind(functions=tools)

    agent = (
        {
            "input": lambda x: x["input"],
            "chat_history": lambda x: _format_chat_history(x["chat_history"]),
            "agent_scratchpad": lambda x: format_to_openai_function_messages(
                x["intermediate_steps"]
            ),
        }
        | prompt
        | llm_with_tools
        | OpenAIFunctionsAgentOutputParser()
    )

    agent_executor = AgentExecutor.from_agent_and_tools(
        agent=agent, tools=tools, verbose=True
    ).with_types(input_type=AgentInput)
    st.markdown(agent_executor.invoke(text))

if st.button("graph", key="wiki"):
    from langchain_community.tools import WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper

    api_wrapper = WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=100)
    tool = WikipediaQueryRun(api_wrapper=api_wrapper)
    st.markdown(tool.run({"query": "langchain"}))
