import base64
from datetime import timedelta
import io
import logging
import mimetypes
import tempfile
from pathlib import Path

import streamlit as st
from langchain.chains import LLMMathChain
from langchain_core.messages import HumanMessage
from langchain_experimental.llm_symbolic_math.base import LLMSymbolicMathChain
from langchain_google_vertexai import ChatVertexAI, VertexAI
from moviepy.editor import VideoFileClip
from vertexai.preview.generative_models import GenerationConfig, Part

from menu import menu
from mypylib.google_ai import (
    display_generated_content_and_update_token,
    load_vertex_model,
    parse_generated_content_and_update_token,
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

# region 提示词

EXTRACT_TEST_QUESTION_PROMPT = """Extract the test question text from the image.
The layout according to the format in the picture. Add necessary blank lines to keep things nice.
Use $ or $$ to correctly identify mathematical formulas.
If the content is presented in a tabular format, it should be written using the HTML table syntax in Markdown.
Output in markdown."""

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
    st.markdown("##### 显示试题图片")
    for i, p in enumerate(examples):
        mime_type = p["mime_type"]
        if mime_type.startswith("text"):
            st.markdown(p["part"].text)
        elif mime_type.startswith("image"):
            # container.image(p["part"].inline_data.data, width=300)
            st.image(p["part"].inline_data.data)
        elif mime_type.startswith("video"):
            st.video(p["part"].inline_data.data)


@st.cache_data(
    ttl=timedelta(hours=1), show_spinner="正在运行多模态模型，提取数学试题..."
)
def extract_test_question_text_for(uploaded_file, prompt):
    contents = process_file_and_prompt(uploaded_file, prompt)
    model_name = "gemini-pro-vision"
    model = load_vertex_model(model_name)
    generation_config = GenerationConfig(
        temperature=0.0,
        top_p=1.0,
        top_k=32,
        max_output_tokens=2048,
    )
    return parse_generated_content_and_update_token(
        "多模态AI提取数学题文本",
        model_name,
        model.generate_content,
        contents,
        generation_config,
        stream=False,
    )


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
        "多模态AI解答数学题",
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

st.markdown("您的提示词")
prompt = st.text_area(
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

status = st.empty()
tab0_btn_cols = st.columns([1, 1, 1, 1, 6])
cls_btn = tab0_btn_cols[0].button(
    "清除[:wastebasket:]",
    help="✨ 清空提示词",
    key="clear_prompt",
)
qst_btn = tab0_btn_cols[1].button(
    "试题[:toolbox:]",
    help="✨ 点击按钮，将从图片中提取试题文本，并在右侧文本框中显示。",
    key="extract_text",
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
    if uploaded_file is None:
        status.warning("您是否忘记了上传图片或视频？")
        st.stop()
    contents = process_file_and_prompt(uploaded_file, EXTRACT_TEST_QUESTION_PROMPT)
    view_example_v0(contents)
    st.session_state["math-question"]
    st.session_state["math-question"] = extract_test_question_text_for(
        uploaded_file, EXTRACT_TEST_QUESTION_PROMPT
    )
    st.markdown("##### 试题markdown代码")
    st.code(f'{st.session_state["math-question"]}', language="markdown")
    st.markdown("##### 显示的试题文本")
    st.markdown(st.session_state["math-question"])
    update_sidebar_status(sidebar_status)

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
    llm_symbolic_math = LLMSymbolicMathChain.from_llm(llm)
    message = HumanMessage(content=[prompt, image_to_dict(uploaded_file)])
    # output = llm_math.invoke([message])
    output = llm_symbolic_math.invoke([message])
    st.markdown(output.content)

# endregion


# region 数学公式编辑
st.subheader("数学公式编辑演示", divider="rainbow", anchor="数学公式编辑")

demo_cols = st.columns([10, 1, 10])
demo_cols[0].markdown("在此输入包含数学公式的markdown格式文本")
MATH_VARIABLE_DEMO = "$x$"
FRACTION_DEMO = "$\\frac{a}{b}$"  # 分数，a/b
SUBSCRIPT_DEMO = "$a_{i}$"  # 下标，a_i
FORMULA_DEMO = "$a^2 + b^2 = c^2$"  # 公式，勾股定理
INTEGRAL_DEMO = "\int_0^\infty \frac{1}{x^2}\,dx"  # 积分
DEMO = f"""
#### 数学公式编辑演示
##### 行内数学公式
- 行内变量代码 ```{MATH_VARIABLE_DEMO}``` 显示效果：{MATH_VARIABLE_DEMO}
- 分数代码 ```{FRACTION_DEMO}``` 显示效果：{FRACTION_DEMO}
- 下标代码 ```{SUBSCRIPT_DEMO}``` 显示效果：{SUBSCRIPT_DEMO}
- 公式代码 ```{FORMULA_DEMO}``` 显示效果：{FORMULA_DEMO}
##### 块级数学公式
- 积分代码 ```{INTEGRAL_DEMO}``` 显示效果：{INTEGRAL_DEMO}
"""
math_text = demo_cols[0].text_area(
    "输入数学公式",
    value=DEMO,
    label_visibility="collapsed",
    key="demo-math_text",
    height=200,
)
# demo_cols[1].markdown("=>")
demo_cols[2].markdown("检查数学公式是否正确")
demo_cols[2].markdown(math_text)

edit_btn_cols = demo_cols[0].columns(4)
cls_edit_btn = edit_btn_cols[0].button("清除[:wastebasket:]", key="clear_math_text")
copy_btn = edit_btn_cols[1].button("复制[:clipboard:]", key="copy_math_text")
if cls_edit_btn:
    clear_prompt("demo-math_text")
    st.rerun()


with st.expander(":bulb: 如何编辑数学公式？", expanded=False):
    st.markdown("常用数学符号示例代码")
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
