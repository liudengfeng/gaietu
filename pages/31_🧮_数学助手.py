import io
import logging
import mimetypes
import tempfile
from pathlib import Path

import streamlit as st
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

sidebar_status = st.sidebar.empty()


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
            container.image(p["part"].inline_data.data, width=300)
        elif mime_type.startswith("video"):
            container.video(p["part"].inline_data.data)


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
st.markdown("✨ 请上传清晰、正面、未旋转的数学试题图片，然后点击 `提交` 按钮开始解答。")
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
)
status = st.empty()
tab0_btn_cols = st.columns([1, 1, 1, 1, 6])
cls_btn = tab0_btn_cols[0].button(
    "清除[:wastebasket:]",
    help="✨ 清空提示词",
    key="clear_prompt",
    on_click=clear_prompt,
    args=("user_prompt_key",),
)
fix_btn = tab0_btn_cols[1].button(
    "修复[:wrench:]", help="✨ 点击按钮，修复从图片提取的试题文本", key="fix_button-2"
)
submitted = tab0_btn_cols[2].button(
    "提交[:heavy_check_mark:]", key="submit_button", help="✨ 点击提交"
)

response_container = st.container()

if fix_btn:
    if uploaded_file is not None:
        pass

if submitted:
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

# endregion

with st.expander(":bulb: 如何编辑数学公式？", expanded=False):
    st.subheader("数学公式编辑")
    demo_cols = st.columns(2)
    math_text = demo_cols[0].text_input("输入数学公式", value="$x^2 + y^2 = z^2$")
    demo_cols[1].markdown(math_text)

    st.subheader("数学公式演示")
    table = """
| 名称 | LaTeX 代码 | Markdown 代码 | 示例 |
| --- | --- | --- | --- |
| 加号 | `+` | `+` | a+b |
| 减号 | `-` | `-` | a−b |
| 乘号 | `\times` | `\times` | a×b |
| 除号 | `/` | `/` | a/b |
| 等号 | `=` | `=` | a=b |
| 大于号 | `>` | `>` | a>b |
| 小于号 | `<` | `<` | a<b |
| 大于等于号 | `\ge` | `\ge` | a≥b |
| 小于等于号 | `\le` | `\le` | a≤b |
| 不等于号 | `\neq` | `\neq` | a≠b |
| 正方形 | `\sqrt{x}` | `\sqrt{x}` | √x |
| 立方根 | `\sqrt[3]{x}` | `\sqrt[3]{x}` | ∛x |
| 平方 | `x^2` | `x^2` | x² |
| 立方 | `x^3` | `x^3` | x³ |
| 分数 | `\frac{a}{b}` | `\frac{a}{b}` | a/b |
| 求和 | `\sum_{i=1}^n a_i` | `\sum_{i=1}^n a_i` | ∑aᵢ |
| 积分 | `\int_a^b f(x) dx` | `\int_a^b f(x) dx` | ∫f(x)dx |
| 箭头 | `\rightarrow` | `\rightarrow` | a→b |
| 向量 | `\vec{a}` | `\vec{a}` | a |
| 矩阵 | `\begin{pmatrix} a & b \\ c & d \end{pmatrix}` | `\begin{pmatrix} a & b \\ c & d \end{pmatrix}` | (a c b d) |
"""
    st.markdown(table)

    url = "https://jupyterbook.org/en/stable/content/math.html"
    st.markdown(f"更多数学公式编辑，请参考 [Jupyter Book]( {url} )。")
