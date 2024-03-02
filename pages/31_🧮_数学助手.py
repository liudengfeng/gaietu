import base64
from functools import partial
import io
import logging
import mimetypes
import re
import tempfile
from datetime import timedelta
from pathlib import Path

import numpy as np
import streamlit as st
from langchain.callbacks import StreamlitCallbackHandler
from langchain.chains import ConversationChain, LLMMathChain
from langchain.memory import ChatMessageHistory, ConversationBufferMemory
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
)
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_experimental.llm_symbolic_math.base import LLMSymbolicMathChain
from langchain_google_vertexai import (
    ChatVertexAI,
    HarmBlockThreshold,
    HarmCategory,
    VertexAI,
)
from moviepy.editor import VideoFileClip
from vertexai.preview.generative_models import Content, GenerationConfig, Part, Image
from PIL import Image as PIL_Image
from menu import menu
from mypylib.google_ai import (
    display_generated_content_and_update_token,
    load_vertex_model,
    parse_generated_content_and_update_token,
    parse_json_string,
)
from mypylib.math import remove_text_keep_illustrations
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

if "math-illustration" not in st.session_state:
    st.session_state["math-illustration"] = None

if "math-question-prompt" not in st.session_state:
    st.session_state["math-question-prompt"] = ""

if "math-assistant-response" not in st.session_state:
    st.session_state["math-assistant-response"] = ""


def initialize_writing_chat():
    model_name = "gemini-pro"
    model = load_vertex_model(model_name)
    history = [
        Content(
            role="user",
            parts=[
                Part.from_text(
                    """作为一个精通Markdown数学语法的AI，你的任务是根据用户的请求，提供正确的数学变量或表达式的Markdown代码。如果用户提出与此无关的问题，你需要婉转地引导他们回到主题。"""
                )
            ],
        ),
        Content(role="model", parts=[Part.from_text("Alright, let's proceed.")]),
    ]
    st.session_state["AI-Formula-Assistant"] = model.start_chat(history=history)


# endregion

# region 提示词

CORRECTION_PROMPT_TEMPLATE = """
**现在已经更新了题目，你只需要参考图中的示意图或插图。**
修订后的题目：
...在此处输入修订后的题目...
"""

EXAMPLES = r"""
- 对于行内的变量代码，使用：$x$
- 对于行内的数学表达式，使用 `$x = y + z$`
- 对于数学公式块，使用：
$$
\begin{cases}
x + y = 10 \\
2x - y = 3
\end{cases}
$$
"""

EXTRACT_TEST_QUESTION_PROMPT = f"""
根据以下要求，从图片中提取数学问题的文本：
- 只提取试题的文本内容，不包括插图或附注。
- 所有的数学变量、表达式和数学公式都需要使用 `$` 或 `$$` 进行标注。
- 如果试题中的内容以表格形式呈现，应使用 Markdown 中的 HTML 表格语法进行编写。
- 项目列表应使用标准的 Markdown 格式进行编写。
- 输出 Markdown 代码。
- 只需要提取数学问题的文本，无需提供解题策略和具体答案。

Markdown数学变量、表达式、公式格式示例： 

{EXAMPLES}
"""


SOLUTION_THOUGHT_PROMPT = """你精通数学，你的任务是根据以下要求，为图片中的数学问题提供解题思路：
1. 你的受众是中国{grade}学生，你需要提供与他们能力匹配的解题方法。
2. 如果问题的难度或内容与指定年级的教学大纲不符，你需要以尊重和理解的态度，礼貌地向用户指出这一点。
3. 这是一道{question_type}题，你需要按照题型的标准范式进行解答。
4. 简要阐述解决问题的步骤和所采用的方法，列出必要的数学公式和计算流程，但无需进行详细的数值运算。
5. 使用`$`或`$$`来正确标识行内或块级的数学变量和公式。

**你不能提供具体的答案。**
"""

ANSWER_MATH_QUESTION_PROMPT = """你精通数学，你的任务是按照以下要求，分步解答图中的数学题：
1. 这是一道{question_type}题，你需要按照题型的标准范式进行解答。
2. 您的受众是中国{grade}学生，需要提供与其学习阶段相匹配的解题方法。
3. 使用`$`或`$$`来正确标识行内或块级数学变量及公式。
"""


# endregion


# region 函数
def reset_text_value(key, value=""):
    st.session_state[key] = value


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


@st.cache_data(ttl=timedelta(hours=1))
def create_temp_file_from_upload(uploaded_file):
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
    return temp_file.name


@st.cache_data(ttl=timedelta(hours=1))
def image_to_dict(uploaded_file):
    # 返回临时文件的路径
    image_message = {
        "type": "image_url",
        "image_url": {"url": create_temp_file_from_upload(uploaded_file)},
    }
    # logger.info(f"url: {temp_file.name}")
    return image_message


# @st.cache_data(ttl=timedelta(hours=1))
# def image_to_dict(uploaded_file):
#     # 获取图片数据
#     image_bytes = uploaded_file.getvalue()

#     # 返回临时文件的路径
#     image_message = {
#         "type": "image_url",
#         "image_url": {
#             "url": f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
#         },
#     }
#     return image_message

ANALYZE_IMAGE_COORDINATES_TEMPLATE = """
结合已经提取的文本和以下两幅图像，指出插图的 box 坐标。
方法介绍：
- 从原图中遮掩已经提取的文本部分。
- 参考分离的图片，分离的图片包含了插图，但可能错误保留了文本。
- 结合两幅图像，指出插图的 box 坐标，字典列表以JSON格式输出。


原图：
{original}

提取的文本：
{text}

分离的图片：
{image}

输出示例：
```json
[
    {
        "x": 0,
        "y": 0,
        "width": 100,
        "height": 100
    },
]
```       
"""


def analyze_coordinates_prompt(
    original_image_path, separated_image_path, extracted_text
):
    contents_info = []
    prompt = """
结合已经提取的文本和以下两幅图像，指出插图在原图中的 box 坐标。
方法介绍：
- 从原图中遮掩已经提取的文本部分。
- 参考分离的图片，分离的图片包含了插图，但可能错误保留了文本。
- 结合两幅图像，指出插图的 box 坐标，字典列表以JSON格式输出。

原图："""
    contents_info.append(
        {"mime_type": "text", "part": Part.from_text(prompt), "duration": None}
    )
    mime_type = mimetypes.guess_type(original_image_path)[0]
    contents_info.append(
        {
            "mime_type":mime_type,
            "part": Image.load_from_file(original_image_path),
            "duration": None,
        }
    )
    prompt = f"提取的文本：{extracted_text}\n\n分离的图片："
    contents_info.append(
        {"mime_type": "text", "part": Part.from_text(prompt), "duration": None}
    )
    mime_type = mimetypes.guess_type(separated_image_path)[0]
    contents_info.append(
        {
            "mime_type": mime_type,
            "part": Image.load_from_file(separated_image_path),
            "duration": None,
        }
    )
    prompt = """输出示例：
```json
[
    {
        "x": 0,
        "y": 0,
        "width": 100,
        "height": 100
    },
]
```  
"""
    contents_info.append(
        {"mime_type": "text", "part": Part.from_text(prompt), "duration": None}
    )
    return contents_info


def process_file_and_prompt(uploaded_file, prompt):
    # 没有案例
    contents_info = []
    if uploaded_file is not None:
        contents_info.append(_process_media(uploaded_file))
    contents_info.append(
        {"mime_type": "text", "part": Part.from_text(prompt), "duration": None}
    )
    return contents_info


def view_example(container, prompt):
    container.markdown("##### 提示词")
    container.markdown(prompt)


def get_prompt_templature(op, checked):
    if op == "提供解题思路":
        if not checked:
            return SOLUTION_THOUGHT_PROMPT.format(
                grade=grade, question_type=question_type
            )
        else:
            return (
                SOLUTION_THOUGHT_PROMPT.format(grade=grade, question_type=question_type)
                + "\n"
                + CORRECTION_PROMPT_TEMPLATE
            )
    elif op == "提取图中的试题":
        return EXTRACT_TEST_QUESTION_PROMPT
    elif op == "提供完整解答":
        if not checked:
            return ANSWER_MATH_QUESTION_PROMPT.format(
                grade=grade, question_type=question_type
            )
        else:
            return (
                ANSWER_MATH_QUESTION_PROMPT.format(
                    grade=grade, question_type=question_type
                )
                + "\n"
                + CORRECTION_PROMPT_TEMPLATE
            )
    elif op == "提供解题思路":
        if not checked:
            return SOLUTION_THOUGHT_PROMPT.format(
                grade=grade, question_type=question_type
            )
        else:
            return (
                SOLUTION_THOUGHT_PROMPT.format(grade=grade, question_type=question_type)
                + "\n"
                + CORRECTION_PROMPT_TEMPLATE
            )
    return ""


def replace_brackets_with_dollar(content):
    content = re.sub(r"\\\(", "$", content)
    content = re.sub(r"\\\)", "$", content)
    return content


def display_in_container(container, content, code_fmt=False):
    if not code_fmt:
        container.markdown(replace_brackets_with_dollar(content))
    else:
        container.code(replace_brackets_with_dollar(content), language="markdown")


def ensure_math_code_wrapped_with_dollar(math_code):
    if not (math_code.startswith("$") and math_code.endswith("$")):
        math_code = f"${math_code}$"
    return math_code


@st.cache_data(
    ttl=timedelta(hours=1), show_spinner="正在运行多模态模型，提取数学试题..."
)
def extract_math_question_text_for(uploaded_file, prompt):
    contents = process_file_and_prompt(uploaded_file, prompt)
    model_name = "gemini-1.0-pro-vision-001"
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


@st.cache_data(
    ttl=timedelta(hours=1), show_spinner="正在运行多模态模型，修正提取插图..."
)
def analyze_coordinates_for(original_image_path, separated_image_path, extracted_text):
    contents = analyze_coordinates_prompt(
        original_image_path, separated_image_path, extracted_text
    )
    model_name = "gemini-1.0-pro-vision-001"
    model = load_vertex_model(model_name)
    generation_config = GenerationConfig(
        temperature=0.0,
        top_p=1.0,
        top_k=32,
        max_output_tokens=2048,
    )
    return parse_generated_content_and_update_token(
        "多模态AI修正提取插图",
        model_name,
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=partial(parse_json_string, prefix="```json", suffix="```"),
    )


def generate_content_from_files_and_prompt(contents, placeholder):
    model_name = "gemini-1.0-pro-vision-001"
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


def gen_tip_for(question):
    Assistant_Configuration = {
        "temperature": 0.0,
        "top_k": 32,
        "top_p": 1.0,
        "max_output_tokens": 1024,
    }
    question = f"你精通 Markdown 数学公式语法。请专注于回答与 Markdown 数学公式相关的问题。如果用户的问题与此无关，以礼貌的方式引导他们提出相关问题。现在，请为以下问题提供 Markdown 数学公式代码（不需要化简）：{question}"
    assistant_config = GenerationConfig(**Assistant_Configuration)
    contents_info = [
        {"mime_type": "text", "part": Part.from_text(question), "duration": None}
    ]
    response = parse_generated_content_and_update_token(
        "AI Formula Assistant",
        "gemini-pro",
        st.session_state["AI-Formula-Assistant"].send_message,
        contents_info,
        assistant_config,
        stream=False,
    )
    return response.replace("```", "")


# endregion

# region langchain


def create_math_chat():
    # if uploaded_file is None:
    #     return
    st.session_state["math-assistant"] = ChatVertexAI(
        model_name="gemini-1.0-pro-vision-001",
        # convert_system_message_to_human=True,
        safety_settings={
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE
        },
    )


def extract_math_question(uploaded_file):
    st.session_state["math-question"] = extract_math_question_text_for(
        uploaded_file, EXTRACT_TEST_QUESTION_PROMPT
    )


def is_blank(image_path):
    # 使用 PIL 库打开图片
    image = PIL_Image.open(image_path)

    # 将图像转换为 numpy 数组
    img_array = np.array(image)

    # 检查所有像素值是否都相同
    return np.all(img_array == img_array[0, 0])


@st.cache_data(ttl=timedelta(hours=1), show_spinner=False)
def run_chain(prompt):
    uploaded_file = st.session_state["math-illustration"]
    text_message = {
        "type": "text",
        "text": prompt,
    }
    if uploaded_file is not None:
        message = HumanMessage(
            content=[
                text_message,
                image_to_dict(uploaded_file),
            ]
        )
    else:
        message = HumanMessage(content=[text_message])
    return st.session_state["math-assistant"].invoke(
        [message],
    )


# endregion


# region 主页

if "math-assistant" not in st.session_state:
    create_math_chat()

st.subheader(":bulb: :blue[数学解题助手]", divider="rainbow", anchor=False)

st.markdown("""✨ :red[请上传清晰、正面、未旋转的数学试题图片。]""")
elem_cols = st.columns([10, 1, 10])
uploaded_file = elem_cols[0].file_uploader(
    "上传数学试题图片【点击`Browse files`按钮，从本地上传文件】",
    accept_multiple_files=False,
    key="uploaded_file",
    type=["png", "jpg"],
    # on_change=get_math_question,
    help="""
支持的格式
- 图片：PNG、JPG
""",
)
grade_cols = elem_cols[2].columns(3)
grade = grade_cols[0].selectbox(
    "年级", ["小学", "初中", "高中", "大学"], key="grade", help="选择年级"
)
question_type = grade_cols[1].selectbox(
    "题型",
    ["选择题", "填空题", "计算题", "证明题", "判断题", "推理题", "解答题"],
    # index=None,
    key="question_type",
    help="选择题型",
)
operation = grade_cols[2].selectbox(
    "您的操作",
    ["提供解题思路", "提供完整解答"],
)
checked = grade_cols[0].checkbox(
    "是否修正试题", value=False, help="✨ 请勾选此项，如果您需要修正试题文本。"
)


question_cols = st.columns(2)

if uploaded_file is not None:
    question_cols[0].image(uploaded_file.getvalue(), "试题图片")
    extract_math_question(uploaded_file)
    question_cols[1].markdown("##### 试题文本")
    question_cols[1].markdown(st.session_state["math-question"])
    math_fp = create_temp_file_from_upload(uploaded_file)
    illustration = remove_text_keep_illustrations(math_fp, output_to_file=True)
    question_cols[1].markdown("##### 分离出的试题插图")
    if is_blank(illustration):
        question_cols[1].markdown("没有分离出的插图。")
        st.session_state["math-illustration"] = None
    else:
        st.session_state["math-illustration"] = illustration
        question_cols[1].image(st.session_state["math-illustration"], "试题插图")
else:
    st.session_state["math-illustration"] = None

prompt_cols = st.columns([1, 1])
prompt_cols[0].markdown("您的提示词")
prompt = prompt_cols[0].text_area(
    "您的提示词",
    # value=st.session_state["math-question-prompt"],
    key="user_prompt_key",
    placeholder="输入提示词或点击`模板`按钮选择提示词。",
    max_chars=12288,
    height=300,
    label_visibility="collapsed",
)

prompt_cols[1].markdown("显示验证", help="✨ 显示验证提示词中的数学公式")
view_prompt_container = prompt_cols[1].container(height=300)
view_prompt_container.markdown(prompt, unsafe_allow_html=True)

status = st.empty()
tab0_btn_cols = st.columns([1, 1, 1, 1, 1, 5])
cls_btn = tab0_btn_cols[0].button(
    "清除[:wastebasket:]",
    help="✨ 清空提示词",
    key="reset_text_value",
    on_click=reset_text_value,
    args=("user_prompt_key",),
)
demo_btn_1 = tab0_btn_cols[1].button(
    "模板[:eyes:]",
    key="demo_prompt_text",
    help="✨ 展示当前所应用的提示词模板",
    on_click=reset_text_value,
    args=("user_prompt_key", get_prompt_templature(operation, checked)),
)
ans_btn = tab0_btn_cols[2].button(
    "提交[:black_nib:]", key="generate_button", help="✨ 点击按钮，获取AI响应。"
)
fx_btn = tab0_btn_cols[3].button(
    "修复[:black_nib:]", key="fix_button", help="✨ 点击按钮，修复插图。"
)


response_container = st.container(height=300)
prompt_elem = st.empty()

if fx_btn:
    math_fp = create_temp_file_from_upload(uploaded_file)
    illustration = st.session_state["math-illustration"]
    text = st.session_state["math-question"]
    if is_blank(illustration):
        st.stop()
    boxes = analyze_coordinates_for(math_fp, illustration, text)
    # 使用解析的坐标列表显示插图
    for box in boxes:
        x, y, width, height = box["x"], box["y"], box["width"], box["height"]
        with st.empty():
            st.image(
                PIL_Image.open(math_fp).crop((x, y, x + width, y + height)),
                "修复后的插图",
            )


if cls_btn:
    pass


if ans_btn:
    # if uploaded_file is None:
    #     if operation == "提取图中的试题":
    #         status.error(
    #             "您是否需要从图像中提取试题文本？目前似乎还未接收到您上传的数学相关图片。请上传图片，以便 AI 能更准确地理解和回答您的问题。"
    #         )
    #         st.stop()
    if not prompt:
        status.error("请添加提示词")
        st.stop()
    response_container.empty()
    view_example(response_container, prompt)
    with st.spinner(f"正在运行多模态模型获取{operation}..."):
        response = run_chain(prompt)
    response_container.markdown("##### AI响应")
    response_container.markdown("###### 代码")
    display_in_container(response_container, response.content, True)
    response_container.markdown("###### 显示")
    display_in_container(response_container, response.content)
    update_sidebar_status(sidebar_status)

# endregion


# region 数学公式编辑
st.subheader("数学公式编辑演示", divider="rainbow", anchor="数学公式编辑")

demo_cols = st.columns([10, 1, 10])
demo_cols[0].markdown("在此输入包含数学公式的markdown格式文本")
MATH_VARIABLE_DEMO = "$x$"
FRACTION_DEMO = "$\\frac{a}{b}$"  # 分数，a/b
SUBSCRIPT_DEMO = "$a_{i}$"  # 下标，a_i
FORMULA_DEMO = "$a^2 + b^2 = c^2$"  # 公式，勾股定理
INTEGRAL_DEMO = r"$$\int_0^\infty \frac{1}{x^2}\,dx$$"  # 积分
DEMO = f"""\
#### 数学公式编辑演示
##### 行内数学公式
- 行内变量代码 ```{MATH_VARIABLE_DEMO}``` 显示：{MATH_VARIABLE_DEMO}
- 分数代码 ```{FRACTION_DEMO}``` 显示：{FRACTION_DEMO}
- 下标代码 ```{SUBSCRIPT_DEMO}``` 显示：{SUBSCRIPT_DEMO}
- 公式代码 ```{FORMULA_DEMO}``` 显示：{FORMULA_DEMO}
##### 块级数学公式
- 积分代码 ```{INTEGRAL_DEMO}``` 显示：{INTEGRAL_DEMO}
"""
math_text = demo_cols[0].text_area(
    "输入数学公式",
    label_visibility="collapsed",
    key="demo-math-text",
    height=300,
)


with demo_cols[2]:
    st.markdown("检查数学公式是否正确")
    ai_tip_container = st.container(border=True, height=300)
    with ai_tip_container:
        if math_prompt := st.chat_input("向AI提问数学公式的写法，比如：举例分数的写法"):
            if "AI-Formula-Assistant" not in st.session_state:
                initialize_writing_chat()
            math_code = gen_tip_for(math_prompt)
            st.code(
                f"{math_code}",
                language="markdown",
            )

        st.markdown(math_text, unsafe_allow_html=True)

edit_btn_cols = demo_cols[0].columns(4)

demo_btn = edit_btn_cols[0].button(
    "演示[:eyes:]",
    key="demo_math_text",
    help="✨ 演示数学公式",
    on_click=reset_text_value,
    args=("demo-math-text", DEMO),
)
cls_edit_btn = edit_btn_cols[1].button(
    "清除[:wastebasket:]",
    key="clear_math_text",
    help="✨ 清空数学公式",
    on_click=reset_text_value,
    args=("demo-math-text",),
)
code_btn = edit_btn_cols[2].button(
    "代码[:clipboard:]",
    key="code_math_text",
    help="✨ 点击按钮，将原始文本转换为Markdown格式的代码，并在右侧显示，以便复制。",
)

if cls_edit_btn:
    pass

if code_btn:
    st.code(f"{math_text}", language="markdown")

with st.expander(":bulb: 怎样有效利用数学助手？", expanded=False):
    st.markdown(
        """
- 提供清晰、正面、未旋转的数学试题图片，有助于模型更准确地识别数学公式和解答。
- 如果模型对分数的识别效果不好或从试题文本中提取的信息有误，修正文本中的问题后再尝试让模型进行解答。
- :warning: 虽然模型可以帮助解析数学问题，但它并不完美，不能替代人的判断和理解。
"""
    )

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
