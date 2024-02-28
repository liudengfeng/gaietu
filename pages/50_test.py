import base64
import json
import logging
import mimetypes
import operator
import os
import re
import tempfile
from datetime import timedelta
from functools import partial
from operator import itemgetter
from pathlib import Path

# from langchain.callbacks import StreamlitCallbackHandler
from typing import Annotated, List, Sequence, Tuple, TypedDict

import streamlit as st
from langchain.agents import (
    AgentExecutor,
    AgentType,
    BaseMultiActionAgent,
    Tool,
    initialize_agent,
    load_tools,
    tool,
)
from langchain.agents.format_scratchpad import format_to_openai_function_messages
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers import OpenAIFunctionsAgentOutputParser
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain.chains import LLMMathChain
from langchain.prompts import MessagesPlaceholder
from langchain.tools import StructuredTool
from langchain.utilities.tavily_search import TavilySearchAPIWrapper
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    FunctionMessage,
    HumanMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_google_vertexai import (
    ChatVertexAI,
    HarmBlockThreshold,
    HarmCategory,
    VertexAI,
)
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolExecutor, ToolInvocation

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


# endregion


# region langchain


def _format_chat_history(chat_history: List[Tuple[str, str]]):
    buffer = []
    for human, ai in chat_history:
        buffer.append(HumanMessage(content=human))
        buffer.append(AIMessage(content=ai))
    return buffer


def get_current_date():
    """
    Gets the current date (today), in the format YYYY-MM-DD
    """

    from datetime import datetime

    todays_date = datetime.today().strftime("%Y-%m-%d")

    return todays_date


# endregion


# region 交互界面
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

# endregion


# region graph


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]


def initialize_app():
    model = ChatVertexAI(
        model_name="gemini-1.0-pro-vision-001",
        temperature=0.0,
        max_retries=1,
        streaming=True,
        convert_system_message_to_human=True,
    )
    # TODO：根据需要修改
    tools = [TavilySearchResults(max_results=1)]
    model = model.bind(tools=tools)
    tool_executor = ToolExecutor(tools)

    # Define the function that determines whether to continue or not
    def should_continue(state):
        messages = state["messages"]
        last_message = messages[-1]
        # If there is no function call, then we finish
        if "function_call" not in last_message.additional_kwargs:
            return "end"
        # Otherwise if there is, we continue
        else:
            return "continue"

    # Define the function that calls the model
    def call_model(state):
        messages = state["messages"]
        response = model.invoke(messages)
        # We return a list, because this will get added to the existing list
        return {"messages": [response]}

    # Define the function to execute tools
    def call_tool(state):
        tool_executor = st.session_state["tool_executor"]
        messages = state["messages"]
        # Based on the continue condition
        # we know the last message involves a function call
        last_message = messages[-1]
        # We construct an ToolInvocation from the function_call
        action = ToolInvocation(
            tool=last_message.additional_kwargs["function_call"]["name"],
            tool_input=json.loads(
                last_message.additional_kwargs["function_call"]["arguments"]
            ),
        )
        # We call the tool_executor and get back a response
        response = tool_executor.invoke(action)
        # We use the response to create a FunctionMessage
        function_message = FunctionMessage(content=str(response), name=action.tool)
        # We return a list, because this will get added to the existing list
        return {"messages": [function_message]}

    # Define a new graph
    workflow = StateGraph(AgentState)

    # Define the two nodes we will cycle between
    workflow.add_node("agent", call_model)
    workflow.add_node("action", call_tool)

    # Set the entrypoint as `agent`
    workflow.set_entry_point("agent")

    # We now add a conditional edge
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "action",
            "end": END,
        },
    )

    # We now add a normal edge from `tools` to `agent`.
    workflow.add_edge("action", "agent")

    # Finally, we compile it!
    app = workflow.compile()
    st.session_state["workflow"] = app


if "workflow" not in st.session_state:
    initialize_app()

# endregion


if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

btn_cols = st.columns(8)

if btn_cols[0].button("清空", key="clear"):
    st.session_state["chat_history"] = []

if btn_cols[1].button("执行", key="run"):
    model = ChatVertexAI(
        model_name="gemini-1.0-pro-vision-001",
        # model_name="gemini-pro",
        temperature=0.0,
        max_retries=1,
        streaming=True,
        convert_system_message_to_human=True,
    )

    # Function as tool is only supported for `gemini-pro` and `gemini-pro-001` models.
    llm_with_tools = model.bind(tools=tools)

    # Define a new graph
    workflow = StateGraph(AgentState)

    # Define the two nodes we will cycle between
    workflow.add_node("agent", call_model)
    workflow.add_node("action", call_tool)

    # Set the entrypoint as `agent`
    # This means that this node is the first one called
    workflow.set_entry_point("agent")

    # We now add a conditional edge
    workflow.add_conditional_edges(
        # First, we define the start node. We use `agent`.
        # This means these are the edges taken after the `agent` node is called.
        "agent",
        # Next, we pass in the function that will determine which node is called next.
        should_continue,
        # Finally we pass in a mapping.
        # The keys are strings, and the values are other nodes.
        # END is a special node marking that the graph should finish.
        # What will happen is we will call `should_continue`, and then the output of that
        # will be matched against the keys in this mapping.
        # Based on which one it matches, that node will then be called.
        {
            # If `tools`, then we call the tool node.
            "continue": "action",
            # Otherwise we finish.
            "end": END,
        },
    )

    # We now add a normal edge from `tools` to `agent`.
    # This means that after `tools` is called, `agent` node is called next.
    workflow.add_edge("action", "agent")

    # Finally, we compile it!
    # This compiles it into a LangChain Runnable,
    # meaning you can use it as you would any other runnable
    app = workflow.compile()

    # agent_executor = AgentExecutor.from_agent_and_tools(
    #     agent=agent, tools=tools, verbose=True
    # ).with_types(input_type=AgentInput)
    # agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    inputs = {"messages": [HumanMessage(content="what is the weather in sf")]}
    app.invoke(inputs)
    st.markdown(app.invoke(inputs))

if btn_cols[2].button("graph", key="graph"):
    app = st.session_state["workflow"]
    inputs = {"messages": [HumanMessage(content=text)]}
    result = app.stream(inputs)
    st.write_stream(result)

    # st.markdown(result.content)
