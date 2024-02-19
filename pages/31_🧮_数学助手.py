import logging
import mimetypes
import tempfile
from pathlib import Path
from vertexai.preview.generative_models import GenerationConfig, Part
import streamlit as st
from moviepy.editor import VideoFileClip

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


def process_files_and_prompt(uploaded_files, prompt):
    # 没有案例
    contents_info = []
    if uploaded_files is not None:
        for m in uploaded_files:
            contents_info.append(_process_media(m))
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
st.markdown(
    "请上传所需的多媒体文件，并在下方的文本框中输入您的提示词。完成后，请点击 `提交` 按钮以启动模型。如果您已添加示例，它们也将一同提交。"
)
uploaded_files = st.file_uploader(
    "插入多媒体文件【点击`Browse files`按钮，从本地上传文件】",
    accept_multiple_files=True,
    key="uploaded_files",
    type=["png", "jpg", "mkv", "mov", "mp4", "webm"],
    help="""
支持的格式
- 图片：PNG、JPG
- 视频：
- 您可以上传视频，支持以下格式：MKV、MOV、MP4、WEBM（最大 7MB）
- 该模型将分析长达 2 分钟的视频。 请注意，它将处理从视频中获取的一组不连续的图像帧。
""",
)

prompt = st.text_area(
    "您的提示词",
    key="user_prompt_key",
    placeholder="请输入关于多媒体的提示词，例如：'描述这张风景图片'",
    max_chars=12288,
    height=300,
)
status = st.empty()
tab0_btn_cols = st.columns([1, 1, 1, 7])
# help="模型可以接受多个输入，以用作示例来了解您想要的输出。添加这些样本有助于模型识别模式，并将指定图片和响应之间的关系应用于新样本。这也称为少量样本学习。示例之间，添加'<>'符号用于分隔。"
cls_btn = tab0_btn_cols[0].button(
    ":wastebasket:",
    help="✨ 清空提示词",
    key="clear_prompt",
    on_click=clear_prompt,
    args=("user_prompt_key",),
)
view_all_btn = tab0_btn_cols[1].button(
    ":eyes:", help="✨ 查看全部样本", key="view_example-2"
)
submitted = tab0_btn_cols[2].button("提交")

response_container = st.container()

if view_all_btn:
    response_container.empty()
    contents = process_files_and_prompt(uploaded_files, prompt)
    response_container.subheader(
        f":clipboard: :blue[完整提示词（{len(contents)}）]",
        divider="rainbow",
        anchor=False,
    )
    view_example(contents, response_container)

if submitted:
    if uploaded_files is None or len(uploaded_files) == 0:  # type: ignore
        status.warning("您是否忘记了上传图片或视频？")
    if not prompt:
        status.error("请添加提示词")
        st.stop()
    contents = process_files_and_prompt(uploaded_files, prompt)
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
