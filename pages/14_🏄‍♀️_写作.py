import difflib
import logging
import spacy
import streamlit as st
from vertexai.preview.generative_models import Content, GenerationConfig, Part

from mypylib.google_ai import (
    display_generated_content_and_update_token,
    load_vertex_model,
    parse_generated_content_and_update_token,
    parse_json_string,
    to_contents_info,
)
from mypylib.html_constants import TIPPY_JS
from mypylib.st_helper import (
    check_access,
    check_and_force_logout,
    configure_google_apis,
    setup_logger,
    update_sidebar_status,
)

# region 配置

# 创建或获取logger对象


logger = logging.getLogger("streamlit")
setup_logger(logger)

st.set_page_config(
    page_title="写作练习",
    page_icon="🏄‍♀️",
    layout="wide",
)

check_access(False)
configure_google_apis()

sidebar_status = st.sidebar.empty()
check_and_force_logout(sidebar_status)

# endregion

# region 会话

if "text-model" not in st.session_state:
    st.session_state["text-model"] = load_vertex_model("gemini-pro")

# endregion

# region 边栏

# endregion


# region 函数


def initialize_writing_chat():
    model_name = "gemini-pro"
    model = load_vertex_model(model_name)
    history = [
        Content(
            role="user",
            parts=[
                Part.from_text(
                    "您是一名英语写作辅导老师，你的角色不仅是指导，更是激发学生的创作潜力。您需要耐心地引导学生，而不是直接给出完整的答案。通过提供提示和指导，帮助他们培养和提升写作技能。您的回复始终用英语，除非学生要求您使用中文回答。如果学生提出与写作无关的问题，您需要以婉转的方式引导他们回到主题。"
                )
            ],
        ),
        Content(role="model", parts=[Part.from_text("Alright, let's proceed.")]),
    ]
    st.session_state["writing-chat"] = model.start_chat(history=history)


GRAMMAR_CHECK_TEMPLATE = """\
You are an expert in English grammar, please strictly check the grammar of each sentence in the following text.\
Grammar Checking Process:
If a sentence has grammatical errors, it will be corrected and explanations will be provided. \
The check result of a sentence is a dictionary, which includes two keys: 'corrected' represents the corrected sentence, and 'explanations' is a list of explanations (strings) for each correction.\
If a sentence is grammatically correct, represent it with an empty list '{}';\
All sentence check results form a list. Output in JSON format.\

text:
"""

GRAMMAR_CHECK_CONFIG = (
    {"max_output_tokens": 256, "temperature": 0.2, "top_p": 0.95, "top_k": 40},
)


def check_grammar(paragraph):
    prompt = GRAMMAR_CHECK_TEMPLATE + paragraph
    contents = [prompt]
    contents_info = [
        {"mime_type": "text", "part": Part.from_text(content), "duration": None}
        for content in contents
    ]
    model = st.session_state["text-model"]
    return parse_generated_content_and_update_token(
        "写作练习-语法检查",
        "gemini-pro",
        model.generate_content,
        contents_info,
        GenerationConfig(**GRAMMAR_CHECK_CONFIG[0]),
        stream=False,
        parser=parse_json_string,
    )


# endregion

# region 主体

if "writing_chat_initialized" not in st.session_state:
    initialize_writing_chat()
    st.session_state["writing_chat_initialized"] = True

st.subheader("写作练习", divider="rainbow", anchor="写作练习")
st.markdown(
    "本写作练习旨在全面提升您的写作技巧和能力。我们提供多种场景的写作练习，以帮助您在各种实际情境中提升写作技巧。AI辅助功能将在您的写作过程中提供语法、词汇、主题和风格的评估或修正，甚至在需要时提供创作灵感。这是一个全面提升您的写作能力的过程，旨在让您在各种写作场景中都能自如应对。"
)

# 布局
w_cols = st.columns(3)
HEIGHT = 500

w_cols[0].markdown("<h5 style='color: blue;'>您的作文</h5>", unsafe_allow_html=True)
text = w_cols[0].text_area(
    "您的作文",
    max_chars=10000,
    height=HEIGHT,
    placeholder="在此输入您的作文",
    help="在此输入您的作文",
    label_visibility="collapsed",
)
w_cols[1].markdown("<h5 style='color: green;'>AI建议</h5>", unsafe_allow_html=True)
suggestions = w_cols[1].container(border=True, height=HEIGHT)
w_cols[2].markdown("<h5 style='color: red;'>AI助教</h5>", unsafe_allow_html=True)
ai_tip_container = w_cols[2].container(border=True, height=HEIGHT)

w_btn_cols = st.columns(8)

if w_btn_cols[0].button(
    "刷新[:arrows_counterclockwise:]",
    key="refresh",
    help="✨ 点击按钮，开始新一轮练习。",
):
    text = ""
    suggestions.empty()
    ai_tip_container.empty()
    initialize_writing_chat()


if w_btn_cols[1].button(
    "语法[:abc:]", key="grammar", help="✨ 点击按钮，开始语法检查。"
):
    suggestions.empty()
    nlp = spacy.load("en_core_web_sm")
    paragraphs = text.split("\n")
    paragraphs_check = []
    for paragraph in paragraphs:
        paragraphs_check.append(check_grammar(paragraph))
        suggestions.write(paragraphs_check)
        doc = nlp(paragraph)
        sentences = list(doc.sents)
        suggestions.write(sentences)

    # html = ""
    # for paragraph, check in zip(paragraphs, paragraphs_check):
    #     sentences = paragraph.split(".")
    #     doc = nlp(paragraph)
    #     sentences = list(doc.sents)
    #     for original, check_dict in zip(sentences, check):
    #         html += display_grammar_errors(
    #             original, check_dict["corrected"], check_dict["explanation"]
    #         )
    # # suggestions.markdown(html + TIPPY_JS, unsafe_allow_html=True)
    # update_sidebar_status(sidebar_status)


Assistant_Configuration = {
    "temperature": 0.2,
    "top_p": 1.0,
    "top_k": 32,
    "max_output_tokens": 1024,
}
config = GenerationConfig(**Assistant_Configuration)

if prompt := st.chat_input("从AI写作助教处获取支持"):
    contents_info = [
        {"mime_type": "text", "part": Part.from_text(prompt), "duration": None}
    ]
    display_generated_content_and_update_token(
        "AI写作助教",
        "gemini-pro",
        st.session_state["writing-chat"].send_message,
        contents_info,
        config,
        stream=True,
        placeholder=ai_tip_container.empty(),
    )
    update_sidebar_status(sidebar_status)

# endregion
