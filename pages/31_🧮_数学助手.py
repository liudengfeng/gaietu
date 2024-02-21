import base64
import io
import logging
import mimetypes
import tempfile
from pathlib import Path

import streamlit as st
from langchain.chains import LLMMathChain
from langchain_core.messages import HumanMessage
from langchain_google_vertexai import ChatVertexAI, VertexAI
from moviepy.editor import VideoFileClip
from vertexai.preview.generative_models import GenerationConfig, Part

from menu import menu
from mypylib.google_ai import (
    display_generated_content_and_update_token,
    load_vertex_model,
)
from mypylib.st_helper import (
    add_exercises_to_db,
    check_access,
    configure_google_apis,
    setup_logger,
    update_sidebar_status,
)
from mypylib.st_setting import general_config

logger = logging.getLogger("streamlit")
setup_logger(logger)

CURRENT_CWD: Path = Path(__file__).parent.parent
IMAGE_DIR: Path = CURRENT_CWD / "resource/multimodal"

st.set_page_config(
    page_title="数学解题助手",
    page_icon=":abacus:",
    layout="wide",
)
menu()
check_access(False)
configure_google_apis()
add_exercises_to_db()
general_config()
sidebar_status = st.sidebar.empty()

# region 会话状态
if "math-question" not in st.session_state:
    st.session_state["math-question"] = ""
# endregion


# region 函数
def clear_prompt(key):
    st.session_state[key] = ""


def _process_media(uploaded_file):
    # 用文件扩展名称形成 MIME 类型
    mime_type = mimetypes.guess_type(uploaded_file.name)[0]
    p = Part.from_data(data=uploaded_file.getvalue(), mime_type=mime_type)  # type: ignore

    duration = None
    if mime_type.startswith("video"):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_video_file:
            temp_video_file.write(uploaded_file.getvalue())
            temp_video_file.flush()
            clip = VideoFileClip(temp_video_file.name)
            duration = clip.duration  # 获取视频时长，单位为秒

    return {"mime_type": mime_type, "part": p, "duration": duration}


def image_to_dict(uploaded_file):
    image_message = {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{base64.b64encode(uploaded_file.getvalue()).decode('utf-8')}"
        },
    }
    return image_message


def process_file_and_prompt(uploaded_file, prompt):
    # 没有案例
    contents_info = []
    if uploaded_file is not None:
        contents_info.append(_process_media(uploaded_file))
    contents_info.append(
        {"mime_type": "text", "part": Part.from_text(prompt), "duration": None}
    )
    return contents_info


def view_example(examples, container):
    for i, p in enumerate(examples):
        mime_type = p["mime_type"]
        if mime_type.startswith("text"):
            container.markdown(p["part"].text)
        elif mime_type.startswith("image"):
            # container.image(p["part"].inline_data.data, width=300)
            container.image(p["part"].inline_data.data)
        elif mime_type.startswith("video"):
            container.video(p["part"].inline_data.data)


def view_example_v0(examples):
    for i, p in enumerate(examples):
        mime_type = p["mime_type"]
        if mime_type.startswith("text"):
            st.markdown(p["part"].text)
        elif mime_type.startswith("image"):
            # container.image(p["part"].inline_data.data, width=300)
            st.image(p["part"].inline_data.data)
        elif mime_type.startswith("video"):
            st.video(p["part"].inline_data.data)


def generate_content_from_files_and_prompt(contents, placeholder):
    model_name = "gemini-pro-vision"
    model = load_vertex_model(model_name)
    generation_config = GenerationConfig(
        temperature=0.0,
        top_p=1.0,
        top_k=32,
        max_output_tokens=2048,
    )
    display_generated_content_and_update_token(
        "多模态AI",
        model_name,
        model.generate_content,
        contents,
        generation_config,
        stream=True,
        placeholder=placeholder,
    )


# endregion

# region 主页
st.subheader(":bulb: :blue[数学解题助手]", divider="rainbow", anchor=False)


st.markdown(
    """✨ 请上传清晰、正面、未旋转的数学试题图片，然后点击 `提交` 按钮开始解答。
- 模型对分数的识别效果不好，这可能导致计算结果的不准确
- 在处理计算过程中，即使是最简单的计算也可能出现错误。
- 如果发现从试题文本中提取的信息有误，请首先修正文本中的问题，然后再让模型尝试进行解答。
- :warning: 模型只能帮助解析数学问题，但不能完全依赖。
"""
)
uploaded_file = st.file_uploader(
    "上传数学试题图片【点击`Browse files`按钮，从本地上传文件】",
    accept_multiple_files=False,
    key="uploaded_file",
    type=["png", "jpg"],
    help="""
支持的格式
- 图片：PNG、JPG
""",
)
content_cols = st.columns([2, 1])
content_cols[0].markdown("您的提示词")
content_cols[1].markdown("提取的试题文本")
prompt_container = content_cols[0].container(height=300)
question_container = content_cols[1].container(height=300)
prompt = prompt_container.text_area(
    "您的提示词",
    value="""您是数学专业老师，按照指示完成以下任务：
1. 提取图中的试题文本。
2. 分步做答，必要时指出知识点。

要求：
markdown格式，数学公式正确标记 $ 或 $$。""",
    key="user_prompt_key",
    placeholder="请输入提示词，例如：'您是一位优秀的数学老师，分步指导学生解答图中的试题。注意：请提供解题思路、解题知识点，并正确标识数学公式。'",
    max_chars=12288,
    height=300,
    label_visibility="collapsed",
)
question_container.markdown(st.session_state["math-question"])


status = st.empty()
tab0_btn_cols = st.columns([1, 1, 1, 1, 6])
cls_btn = tab0_btn_cols[0].button(
    "清除[:wastebasket:]",
    help="✨ 清空提示词",
    key="clear_prompt",
)
qst_btn = tab0_btn_cols[1].button(
    "文本[:mag:]", help="✨ 点击按钮，从图片提取试题文本", key="extract_text"
)
smt_btn = tab0_btn_cols[2].button(
    "提交[:heavy_check_mark:]", key="submit_button", help="✨ 点击提交"
)
test_btn = tab0_btn_cols[3].button(
    "测试[:heavy_check_mark:]", key="test_button", help="✨ 临时测试"
)

response_container = st.container()

if cls_btn:
    clear_prompt("user_prompt_key")
    st.session_state["math-question"] = ""
    st.rerun()

if qst_btn:
    if uploaded_file is not None:
        pass

if smt_btn:
    if uploaded_file is None:
        status.warning("您是否忘记了上传图片或视频？")
    if not prompt:
        status.error("请添加提示词")
        st.stop()
    contents = process_file_and_prompt(uploaded_file, prompt)
    response_container.empty()
    col1, col2 = response_container.columns([1, 1])
    view_example(contents, col1)
    with st.spinner(f"正在运行多模态模型..."):
        generate_content_from_files_and_prompt(
            contents,
            col2.empty(),
        )
    update_sidebar_status(sidebar_status)

if test_btn:
    contents = process_file_and_prompt(uploaded_file, prompt)
    view_example_v0(contents)
    # llm = VertexAI(temperature=0, model_name="gemini-pro-vision")
    llm = ChatVertexAI(
        temperature=0, top_p=0.5, top_k=20, model_name="gemini-pro-vision"
    )
    llm_math = LLMMathChain.from_llm(llm, verbose=True)
    message = HumanMessage(content=[prompt, image_to_dict(uploaded_file)])
    output = llm.invoke([message])
    st.markdown(output.content)

# endregion


# region 数学公式编辑
st.subheader("编辑数学公式", divider="rainbow", anchor="数学公式编辑")

demo_cols = st.columns(2)
demo_cols[0].markdown("在此输入数学公式文本")
math_text = demo_cols[0].text_input(
    "输入数学公式",
    value=r"$\int_0^\infty \frac{x^3}{e^x-1}\,dx = \frac{\pi^4}{15}$",
    label_visibility="collapsed",
)
demo_cols[1].markdown("检查数学公式是否正确")
demo_cols[1].markdown(math_text)

with st.expander(":bulb: 如何编辑数学公式？", expanded=False):
    st.markdown("常用的数学公式符号")
    # 创建一个列表，每一项包括名称、LaTeX 代码、Markdown 代码和示例
    math_symbols = [
        ["分数", "\\frac{a}{b}", "\\frac{a}{b}", "\\frac{a}{b}"],
        ["平方", "x^2", "x^2", "x^2"],
        ["立方", "x^3", "x^3", "x^3"],
        ["求和", "\\sum_{i=1}^n a_i", "\\sum_{i=1}^n a_i", "\\sum_{i=1}^n a_i"],
        ["积分", "\\int_a^b f(x) dx", "\\int_a^b f(x) dx", "\\int_a^b f(x) dx"],
    ]

    math_demo_cols = st.columns(4)
    math_demo_cols[0].markdown("名称")
    math_demo_cols[1].markdown("LaTeX")
    math_demo_cols[2].markdown("Markdown")
    math_demo_cols[3].markdown("显示效果")
    for symbol in math_symbols:
        math_demo_cols[0].markdown(symbol[0])
        math_demo_cols[1].text(symbol[1])
        math_demo_cols[2].text(symbol[2])
        math_demo_cols[3].markdown(f"${symbol[3]}$")

    url = "https://cloud.tencent.com/developer/article/2349331"
    st.markdown(f"更多数学公式编辑，请参考 [数学公式语法集]( {url} )。")

# endregion
