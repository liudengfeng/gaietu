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

if "writing-ai-assitant" not in st.session_state:
    st.session_state["writing-ai-assitant"] = ""

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

- Read through the article and identify any spelling errors in the words. This primarily includes errors such as misspelled words.
- Please note that this task does not include correcting capitalization errors at the beginning of sentences. If such errors are encountered, they should be ignored and no changes should be made.
- In the event that the article is devoid of spelling errors, yield an empty dictionary.
- For each correction, three steps need to be completed: 1. Deletion of the error, marked with ~~. 2. Addition of the correction, marked with <ins> </ins>. 3. Addition of the explanation for the correction to the "explanations" list. If the correction involves adding a word, delete the word that is in the wrong context first, then add the corrected phrase. 
- Output a dictionary with "corrected" (the corrected text) and "explanations" (the list of explanations) as keys.
- Finally, output the dictionary in JSON format.

Examples:

The original text: 'It help us to learn new things and to develop our skills. It also help us to get a good job and to make a differents in the world.'
The output dictionary should include the following keys:
- corrected: "It ~~help~~ <ins>helps</ins> us to learn new things and to develop our skills. It also ~~help~~ <ins>helps</ins> us to get a good job and to make a ~~differents~~ <ins>difference</ins> in the world."
- explanations: ["The word 'help' should be replaced with 'helps' when the subject is singular.", "The word 'help' should be replaced with 'helps' when the subject is singular.", "The word 'differents' is a misspelling and should be replaced with 'difference'."]

The original text: 'I am going two the store two bye some bred, milk, and egs.'
The output dictionary should include the following keys:
- corrected: "I am going ~~two~~ <ins>to</ins> the store ~~two~~ <ins>to</ins> ~~bye~~ <ins>buy</ins> some ~~bred~~ <ins>bread</ins>, milk, and ~~egs~~ <ins>eggs</ins>."
- explanations: ["The word 'two' is a number and should be replaced with 'to' when used as a preposition.", "The word 'bye' is a farewell expression and should be replaced with 'buy' when referring to purchasing something.", "The word 'bred' is a past tense of breed and should be replaced with 'bread' when referring to the food.", "The word 'egs' is a misspelling and should be replaced with 'eggs'."]

The original text: 'i am going two the store.'
The output dictionary should include the following keys:
- corrected: "i am going ~~two~~ <ins>to</ins> the store."
- explanations: ["The word 'two' is a number and should be replaced with 'to' when used as a preposition."]

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


ARTICLE_POLISH_TEMPLATE = """\
作为英文写作指导者，你的主要任务是检查并纠正以下"文章"中的任何拼写错误。

按步骤完成以下操作：

- 仔细阅读文章，找出任何拼写错误。这主要包括像拼写错误这样的错误。
- 请注意，这个任务不包括在句子开头纠正大写错误。如果遇到这样的错误，应忽略它们，不做任何改变。
- 如果文章没有拼写错误，返回一个空字典。
- 对于每个修正，需要完成三个步骤：1. 删除错误，用~~标记。2. 添加修正，用<ins> </ins>标记。3. 将修正的解释添加到"explanations"列表中。如果修正涉及添加单词，先删除错误的上下文中的单词，然后添加修正的短语。
- 输出一个字典，其中"corrected"（修正后的文本）和"explanations"（解释列表）作为键。
- 最后，以JSON格式输出字典。

示例：

原文：'It help us to learn new things and to develop our skills. It also help us to get a good job and to make a differents in the world.'
输出的字典应包括以下键：
- corrected: "It ~~help~~ <ins>helps</ins> us to learn new things and to develop our skills. It also ~~help~~ <ins>helps</ins> us to get a good job and to make a ~~differents~~ <ins>difference</ins> in the world."
- explanations: ["The word 'help' should be replaced with 'helps' when the subject is singular.", "The word 'help' should be replaced with 'helps' when the subject is singular.", "The word 'differents' is a misspelling and should be replaced with 'difference'."]

文章:{article}
"""

ARTICLE_POLISH_CONFIG = {"max_output_tokens": 2048, "temperature": 0.75}


@st.cache_data(ttl=60 * 60 * 12, show_spinner="正在润色文章...")
def polish_article(article):
    # 检查 article 是否为英文文本 [字符数量少容易被错判]
    detected_language = detect(article)
    if detected_language in ["zh-cn", "ja"]:
        return {
            "corrected": f"The anticipated language is English, however, {detected_language} was detected",
            "explanations": [],
            "error_type": "LanguageError",
        }

    prompt = ARTICLE_POLISH_TEMPLATE.format(article=article)
    contents = [prompt]
    contents_info = [
        {"mime_type": "text", "part": Part.from_text(content), "duration": None}
        for content in contents
    ]
    model = st.session_state["text-model"]
    result = parse_generated_content_and_update_token(
        "写作练习-文章润色",
        "gemini-pro",
        model.generate_content,
        contents_info,
        GenerationConfig(**ARTICLE_POLISH_CONFIG),
        stream=False,
        parser=partial(parse_json_string, prefix="```json", suffix="```"),
    )
    result["error_type"] = "WordError"
    result["character_count"] = (
        f"{len(article)} / {len(remove_markup(result['corrected']))} characters corrected"
    )
    return result


LOGIC_STRUCTURE_TEMPLATE = """\
As an AI English writing assistant, your main task is to ensure that the "article" has a clear structure, a logical sequence, and uses appropriate conjunctions or transition words to represent the logical relationship between different parts.
Please proceed as follows:
- Check the logic and structure of the article, ensure clear viewpoints and sufficient arguments, and ensure clear logical relationships between paragraphs based on the theme of the article.
- If there are no areas for improvement in terms of logic and structure in the article, return an empty dictionary. Otherwise, provide a revised version of the manuscript and a detailed explanation of all corrections, both in Markdown format as a single text, using 'corrected' and 'explanation' as the keys in the dictionary.
- Finally, output the result in JSON format.

Article:{article}
"""

LOGIC_STRUCTURE_CONFIG = {"max_output_tokens": 2048, "temperature": 0.45}


@st.cache_data(ttl=60 * 60 * 12, show_spinner="正在检查、修正文章逻辑结构...")
def logic_article(article):
    # 检查 article 是否为英文文本 [字符数量少容易被错判]
    detected_language = detect(article)
    if detected_language in ["zh-cn", "ja"]:
        return {
            "corrected": f"The anticipated language is English, however, {detected_language} was detected",
            "explanations": [],
            "error_type": "LanguageError",
        }

    prompt = LOGIC_STRUCTURE_TEMPLATE.format(article=article)
    contents = [prompt]
    contents_info = [
        {"mime_type": "text", "part": Part.from_text(content), "duration": None}
        for content in contents
    ]
    model = st.session_state["text-model"]
    result = parse_generated_content_and_update_token(
        "写作练习-逻辑结构",
        "gemini-pro",
        model.generate_content,
        contents_info,
        GenerationConfig(**LOGIC_STRUCTURE_CONFIG),
        stream=False,
        parser=partial(parse_json_string, prefix="```json", suffix="```"),
    )
    result["error_type"] = "LogicError"
    result["character_count"] = (
        f"{len(article)} / {len(result['corrected'])} characters corrected"
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
        if prompt := st.chat_input("寻求 AI 写作助手的支持。"):
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
            st.session_state["writing-ai-assitant"] = (
                f"""您的问题：
                
                {prompt}

                'AI回复：
                
                {st.session_state["writing-chat"].history[-1].parts[0].text}"""
            )
            update_sidebar_status(sidebar_status)
    ai_tip_container.markdown(st.session_state["writing-ai-assitant"])


rfh_btn = w_btn_cols[0].button(
    "刷新[:arrows_counterclockwise:]",
    key="writing-refresh",
    help="✨ 点击按钮，开始新一轮练习。",
)

clr_btn = w_btn_cols[1].button(
    "清除[:wastebasket:]", key="writing-clear", help="✨ 点击按钮，清除写作练习内容。"
)

grm_btn = w_btn_cols[2].button(
    "语法[:triangular_ruler:]", key="grammar", help="✨ 点击按钮，检查语法错误。"
)

wrd_btn = w_btn_cols[3].button(
    "单词[:abc:]", key="word", help="✨ 点击按钮，检查单词拼写错误。"
)

plh_btn = w_btn_cols[4].button(
    "润色[:art:]", key="polish", help="✨ 点击按钮，提高词汇量和句式多样性。"
)

lgc_btn = w_btn_cols[5].button(
    "逻辑[:brain:]", key="logic", help="✨ 点击按钮，改善文章结构和逻辑。"
)

rvn_btn = w_btn_cols[6].button(
    "修正[:wrench:]", key="revision", help="✨ 点击按钮，接受AI修正建议。"
)

if rfh_btn:
    suggestions.empty()
    ai_tip_container.empty()
    initialize_writing_chat()
    st.rerun()

if clr_btn:
    pass

if grm_btn:
    suggestions.empty()
    result = check_grammar(st.session_state["writing-text"])
    html = display_grammar_errors(result)
    suggestions.markdown(html + TIPPY_JS, unsafe_allow_html=True)
    update_sidebar_status(sidebar_status)

if wrd_btn:
    suggestions.empty()
    result = check_spelling(st.session_state["writing-text"])
    html = display_word_spell_errors(result)
    suggestions.markdown(html + TIPPY_JS, unsafe_allow_html=True)

if plh_btn:
    pass

if lgc_btn:
    suggestions.empty()
    result = logic_article(st.session_state["writing-text"])
    if not result:
        suggestions.write("很好，文章的结构和逻辑已经很完善了。👏👏👏")
    else:
        suggestions.markdown("修正文稿如下：")
        suggestions.markdown(result["corrected"], unsafe_allow_html=True)
        suggestions.divider()
        suggestions.write("解释如下：")
        suggestions.write(result["explanation"])

if rvn_btn:
    result = check_grammar(st.session_state["writing-text"])
    if result["error_type"] == "LanguageError":
        content = remove_markup(result["corrected"])
        st.session_state["writing-content"] = content
        st.rerun()


# endregion
