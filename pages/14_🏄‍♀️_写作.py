import difflib
import logging
from functools import partial

import spacy
import streamlit as st
from langdetect import detect
from vertexai.preview.generative_models import Content, GenerationConfig, Part

from menu import help_page, return_home
from mypylib.google_ai import (
    display_generated_content_and_update_token,
    load_vertex_model,
    parse_generated_content_and_update_token,
    parse_json_string,
    to_contents_info,
)
from mypylib.html_constants import TIPPY_JS
from mypylib.html_fmt import (
    display_grammar_errors,
    display_word_spell_errors,
    remove_markup,
)
from mypylib.st_helper import (
    add_exercises_to_db,
    check_access,
    configure_google_apis,
    on_project_changed,
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
return_home()
help_page()
check_access(False)
configure_google_apis()
on_project_changed("写作练习")
add_exercises_to_db()
sidebar_status = st.sidebar.empty()

# endregion

# region 会话

if "text-model" not in st.session_state:
    st.session_state["text-model"] = load_vertex_model("gemini-pro")

if "writing-content" not in st.session_state:
    st.session_state["writing-content"] = ""

# Use the get method since the keys won't be in session_state on the first script run
if st.session_state.get("writing-clear"):
    st.session_state["writing-text"] = ""

# endregion

# region 边栏

# endregion


# region 函数


def clear_text(key):
    st.session_state[key] = ""


def initialize_writing_chat():
    model_name = "gemini-pro"
    model = load_vertex_model(model_name)
    history = [
        Content(
            role="user",
            parts=[
                Part.from_text(
                    "您是一名英语写作辅导老师，您的角色不仅是指导，更是激发学生的创作潜力。您需要耐心地引导学生，而不是直接给出完整的答案。通过提供提示和指导，帮助他们培养和提升写作技能。您的回复始终用英语，除非学生要求您使用中文回答。如果学生提出与写作无关的问题，您需要以婉转的方式引导他们回到主题。"
                )
            ],
        ),
        Content(role="model", parts=[Part.from_text("Alright, let's proceed.")]),
    ]
    st.session_state["writing-chat"] = model.start_chat(history=history)


GRAMMAR_CHECK_TEMPLATE = """\
As an English grammar expert, your primary task is to inspect and correct any grammatical errors in the following "Article".

Step by step, complete the following:
1. Identify all grammatical inaccuracies in the article, including errors in tense usage, noun forms, subject-verb agreement, use of prepositions and conjunctions, punctuation, and capitalization.Spelling errors that lead to incorrect word forms or parts of speech are considered related to grammar and should be corrected. Other spelling errors that do not affect the grammatical structure of the sentence are disregarded in this check.
2. In the event that the article is devoid of grammatical inaccuracies, yield an empty dictionary.
3. Rectify the identified grammatical inaccuracies based on the original text.
    - First, use `~~` to mark the segments that are to be removed from the original text. Then, use `<ins>` `</ins>` to indicate the additions.
    - Any modifications to the original text, including the addition of white space, punctuation, and changes in case, should be distinctly indicated using the above markers.
    - Please note that the preferred method of indicating corrections is to mark the entire word for deletion and then insert the corrected word. 
    - The "corrected" content should clearly articulate the modifications made from the original text.
4. Provide a corresponding explanation for each modification made, then compile these explanations into a list.
5. Output a dictionary with "corrected" (the corrected text) and "explanations" (the list of explanations) as keys.
6. Finally, output the dictionary in JSON format.

Examples:

The original text: 'I have many moeney in the past,I have not to work now.'
The output dictionary should include the following keys:
- corrected: "I ~~have~~ <ins>had</ins> many moeney in the past, so I ~~have not to~~ <ins>don't have to</ins> work now."
- explanations: ["The past tense of 'have' is 'had'.", "The phrase 'have not to' is used to express necessity or obligation. In this context, it should be replaced with 'don't have to' to convey the idea of not being required to work."]

The original text: 'She don't likes apples.'
The output dictionary should include the following keys:
- corrected: "She ~~don't likes~~ <ins>doesn't like</ins> apples."
- explanations: ["The correct form is 'doesn't like' when referring to third person singular."]   

The original text: 'she is a teacher.'
The output dictionary should include the following keys:
- corrected: "~~she~~ <ins>She</ins> is a teacher."
- explanations: ["The first word of a sentence should be capitalized."]

Article:{article}
"""


GRAMMAR_CHECK_CONFIG = {"max_output_tokens": 2048, "temperature": 0.0}


@st.cache_data(ttl=60 * 60 * 12, show_spinner="正在检查语法...")
def check_grammar(article):
    # 检查 article 是否为英文文本 [字符数量少容易被错判]
    detected_language = detect(article)
    if detected_language in ["zh-cn", "ja"]:
        return {
            "corrected": f"The anticipated language is English, however, {detected_language} was detected",
            "explanations": [],
            "error_type": "LanguageError",
        }

    prompt = GRAMMAR_CHECK_TEMPLATE.format(article=article)
    contents = [prompt]
    contents_info = [
        {"mime_type": "text", "part": Part.from_text(content), "duration": None}
        for content in contents
    ]
    model = st.session_state["text-model"]
    result = parse_generated_content_and_update_token(
        "写作练习-语法检查",
        "gemini-pro",
        model.generate_content,
        contents_info,
        GenerationConfig(**GRAMMAR_CHECK_CONFIG),
        stream=False,
        parser=partial(parse_json_string, prefix="```json", suffix="```"),
    )
    result["error_type"] = "GrammarError"
    result["character_count"] = (
        f"{len(article)} / {len(remove_markup(result['corrected']))} characters corrected"
    )
    return result


WORD_SPELL_CHECK_TEMPLATE = """\
As an English writing instructor, your primary task is to inspect and correct any spelling errors in the following "Article".

Step by step, complete the following:
1. Read through the article and correct any spelling errors in the words. This includes errors such as misspelled words, incorrect capitalization at the beginning of sentences, and other types of spelling mistakes.
2. In the event that the article is devoid of spelling errors, yield an empty dictionary.
3. Correct the identified spelling errors based on the original text.
    - First, use `~~` to strike through the words that need to be removed from the original text. Then, use `<ins>` `</ins>` to indicate the corrected words.
    - Please note that the preferred method of indicating corrections is to mark the entire word for deletion and then insert the corrected word. The strike-through and insertion indicators should always appear in pairs to represent a single spelling correction.
    - The "corrected" content should clearly articulate the modifications made from the original text.
4. Provide a corresponding explanation for each modification made, then compile these explanations into a list.
5. Output a dictionary with "corrected" (the corrected text) and "explanations" (the list of explanations) as keys.
6. Finally, output the dictionary in JSON format.

Example:

The original text: 'I am going two the store two bye some bred, milk, and egs.'
The output dictionary should include the following keys:
- corrected: "I am going ~~two~~ <ins>to</ins> the store ~~two~~ <ins>to</ins> ~~bye~~ <ins>buy</ins> some ~~bred~~ <ins>bread</ins>, milk, and ~~egs~~ <ins>eggs</ins>."
- explanations: ["The word 'two' is a number and should be replaced with 'to' when used as a preposition.", "The word 'bye' is a farewell expression and should be replaced with 'buy' when referring to purchasing something.", "The word 'bred' is a past tense of breed and should be replaced with 'bread' when referring to the food.", "The word 'egs' is a misspelling and should be replaced with 'eggs'."]

Article:{article}
"""


WORD_SPELL_CHECK_CONFIG = {"max_output_tokens": 2048, "temperature": 0.0}


@st.cache_data(ttl=60 * 60 * 12, show_spinner="正在检查单词拼写...")
def check_spelling(article):
    # 检查 article 是否为英文文本 [字符数量少容易被错判]
    detected_language = detect(article)
    if detected_language in ["zh-cn", "ja"]:
        return {
            "corrected": f"The anticipated language is English, however, {detected_language} was detected",
            "explanations": [],
            "error_type": "LanguageError",
        }

    prompt = WORD_SPELL_CHECK_TEMPLATE.format(article=article)
    contents = [prompt]
    contents_info = [
        {"mime_type": "text", "part": Part.from_text(content), "duration": None}
        for content in contents
    ]
    model = st.session_state["text-model"]
    result = parse_generated_content_and_update_token(
        "写作练习-检查单词拼写",
        "gemini-pro",
        model.generate_content,
        contents_info,
        GenerationConfig(**WORD_SPELL_CHECK_CONFIG),
        stream=False,
        parser=partial(parse_json_string, prefix="```json", suffix="```"),
    )
    result["error_type"] = "WordError"
    result["character_count"] = (
        f"{len(article)} / {len(remove_markup(result['corrected']))} characters corrected"
    )
    return result


# endregion

# region 主体

if "writing_chat_initialized" not in st.session_state:
    initialize_writing_chat()
    st.session_state["writing_chat_initialized"] = True

st.subheader("写作练习", divider="rainbow", anchor="写作练习")
st.markdown(
    "本写作练习旨在全面提升您的写作技巧和能力。我们提供多种场景的写作练习，以帮助您在各种实际情境中提升写作技巧。AI辅助功能将在您的写作过程中提供语法、词汇、主题和风格的评估或修正，甚至在需要时提供创作灵感。这是一个全面提升您的写作能力的过程，旨在让您在各种写作场景中都能自如应对。"
)

w_btn_cols = st.columns(8)

# 布局
w_cols = st.columns(3)
HEIGHT = 600

w_cols[0].markdown("<h5 style='color: blue;'>您的写作练习</h5>", unsafe_allow_html=True)

w_cols[0].text_area(
    "您的写作练习",
    max_chars=10000,
    value=st.session_state["writing-content"],
    key="writing-text",
    height=HEIGHT,
    placeholder="在此输入您的作文",
    help="在此输入您的作文",
    label_visibility="collapsed",
)
w_cols[1].markdown("<h5 style='color: green;'>AI建议</h5>", unsafe_allow_html=True)
suggestions = w_cols[1].container(border=True, height=HEIGHT)

Assistant_Configuration = {
    "temperature": 0.2,
    "top_p": 1.0,
    "top_k": 32,
    "max_output_tokens": 1024,
}
assistant_config = GenerationConfig(**Assistant_Configuration)
with w_cols[2]:
    st.markdown("<h5 style='color: purple;'>AI助教</h5>", unsafe_allow_html=True)
    ai_tip_container = st.container(border=True, height=HEIGHT)
    with ai_tip_container:
        if prompt := st.chat_input("输入请求，获取 AI 写作助手的支持。"):
            contents_info = [
                {"mime_type": "text", "part": Part.from_text(prompt), "duration": None}
            ]
            display_generated_content_and_update_token(
                "AI写作助教",
                "gemini-pro",
                st.session_state["writing-chat"].send_message,
                contents_info,
                assistant_config,
                stream=True,
                placeholder=ai_tip_container.empty(),
            )
            update_sidebar_status(sidebar_status)


if w_btn_cols[0].button(
    "刷新[:arrows_counterclockwise:]",
    key="writing-refresh",
    help="✨ 点击按钮，开始新一轮练习。",
):
    suggestions.empty()
    ai_tip_container.empty()
    initialize_writing_chat()
    st.rerun()

if w_btn_cols[1].button(
    "清除[:wastebasket:]", key="writing-clear", help="✨ 点击按钮，清除写作练习内容。"
):
    pass

if w_btn_cols[2].button(
    "语法[:triangular_ruler:]", key="grammar", help="✨ 点击按钮，检查语法错误。"
):
    suggestions.empty()
    result = check_grammar(st.session_state["writing-text"])
    html = display_grammar_errors(result)
    suggestions.markdown(html + TIPPY_JS, unsafe_allow_html=True)
    update_sidebar_status(sidebar_status)

if w_btn_cols[3].button(
    "单词[:abc:]", key="word", help="✨ 点击按钮，检查标点符号和拼写错误。"
):
    suggestions.empty()
    result = check_spelling(st.session_state["writing-text"])
    html = display_word_spell_errors(result)
    suggestions.markdown(html + TIPPY_JS, unsafe_allow_html=True)

if w_btn_cols[4].button(
    "润色[:art:]", key="polish", help="✨ 点击按钮，提高词汇量和句式多样性。"
):
    pass

if w_btn_cols[5].button(
    "逻辑[:brain:]", key="logic", help="✨ 点击按钮，改善文章结构和逻辑。"
):
    # 你的文本
    text = "<p>这是一段文本。</p>"

    # 使用 st.code 显示文本
    st.code(text, language="txt")

if w_btn_cols[6].button(
    "修正[:wrench:]", key="revision", help="✨ 点击按钮，接受AI修正建议。"
):
    result = check_grammar(st.session_state["writing-text"])
    if result["error_type"] == "LanguageError":
        content = remove_markup(result["corrected"])
        st.session_state["writing-content"] = content
        st.rerun()


# endregion
