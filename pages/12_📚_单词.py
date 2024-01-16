import json
import logging
import random
import re
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from io import BytesIO
from pathlib import Path
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from mypylib.constants import CEFR_LEVEL_MAPS
from mypylib.db_model import LearningRecord
from mypylib.google_ai import generate_word_test, load_vertex_model
from mypylib.st_helper import (
    TOEKN_HELP_INFO,
    check_access,
    check_and_force_logout,
    configure_google_apis,
    format_token_count,
    get_mini_dict_doc,
    select_word_image_urls,
    setup_logger,
    update_and_display_progress,
)
from mypylib.word_utils import (
    audio_autoplay_elem,
    get_or_create_and_return_audio_data,
    remove_trailing_punctuation,
)

# 创建或获取logger对象
logger = logging.getLogger("streamlit")
setup_logger(logger)

# region 页设置

st.set_page_config(
    page_title="单词",
    page_icon=":books:",
    layout="wide",
)

check_access(False)
configure_google_apis()
sidebar_status = st.sidebar.empty()
# 在页面加载时检查是否有需要强制退出的登录会话
check_and_force_logout(sidebar_status)

menu_names = ["闪卡记忆", "拼图游戏", "看图猜词", "词意测试", "词库管理"]
menu_emoji = [
    "📚",
    "🧩",
    "🖼️",
    "📝",
    "🗂️",
]
menu_opts = [e + " " + n for e, n in zip(menu_emoji, menu_names)]

if "current-page" not in st.session_state:
    st.session_state["current-page"] = menu_opts[0].split(" ", 1)[1]

# 学习记录
IDX_MAPS = {
    "闪卡记忆": "flashcard-idx",
    "拼图游戏": "puzzle-idx",
    "词意测试": "word-test-idx",
}

NUM_MAPS = {
    "闪卡记忆": "flashcard-words-num",
    "拼图游戏": "puzzle-words-num",
    "词意测试": "test-word-num",
}

WORD_MAPS = {
    "闪卡记忆": "flashcard-words",
    "拼图游戏": "puzzle-words",
    "词意测试": "test-words",
}

if "learning-records" not in st.session_state:
    d = {}
    for item in menu_names:
        d[item] = []
    st.session_state["learning-records"] = d


def save_and_clear_learning_records():
    item = st.session_state["current-page"]
    # 如果有学习记录
    if len(st.session_state["learning-records"][item]):
        # 结束所有学习记录
        for r in st.session_state["learning-records"][item]:
            r.end()
        # 保存学习记录到数据库
        st.session_state.dbi.save_records(st.session_state["learning-records"][item])
        # 清空学习记录
        st.session_state["learning-records"][item] = []


def create_learning_records():
    item = st.session_state["current-page"]
    num_word = len(st.session_state[WORD_MAPS[item]])
    for i in range(num_word):
        # idx = st.session_state[IDX_MAPS[item]]
        record = LearningRecord(
            phone_number=st.session_state.dbi.cache["user_info"]["phone_number"],
            project=f"词汇-{item}",
            content=st.session_state[WORD_MAPS[item]][i],
        )
        st.session_state["learning-records"][item].append(record)


def on_menu_change():
    item = st.session_state["current-page"]
    save_and_clear_learning_records()
    st.toast(f"存储`{item}`学习记录")
    # 更新当前页面
    st.session_state["current-page"] = st.session_state.word_dict_menu.split(" ", 1)[1]


menu = st.sidebar.selectbox(
    "菜单",
    menu_opts,
    key="word_dict_menu",
    on_change=on_menu_change,
    help="在这里选择你想要进行的操作。",
)

st.sidebar.divider()

# endregion

# region 通用

# streamlit中各页都是相对当前根目录

CURRENT_CWD: Path = Path(__file__).parent.parent
DICT_DIR = CURRENT_CWD / "resource/dictionary"
VIDEO_DIR = CURRENT_CWD / "resource/video_tip"

TIME_LIMIT = 10 * 60  # 10分钟
OP_THRESHOLD = 10000  # 操作阈值


# endregion

# region 通用函数


def count_non_none(lst):
    return len(list(filter(lambda x: x is not None, lst)))


def is_answer_correct(user_answer, standard_answer):
    # 如果用户没有选择答案，直接返回 False
    if user_answer is None:
        return False

    # 创建一个字典，将选项序号映射到字母
    answer_dict = {0: "A", 1: "B", 2: "C", 3: "D"}

    # 获取用户的答案对应的字母
    user_answer_letter = answer_dict.get(user_answer, "")

    # 移除标准答案中的非字母字符
    standard_answer = "".join(filter(str.isalpha, standard_answer))

    # 比较用户的答案和标准答案
    return user_answer_letter == standard_answer


@st.cache_data(show_spinner="提取词典...", ttl=60 * 60 * 24)  # 缓存有效期为24小时
def load_word_dict():
    with open(
        DICT_DIR / "word_lists_by_edition_grade.json", "r", encoding="utf-8"
    ) as f:
        return json.load(f)


def generate_page_words(word_lib_name, num_words, key, exclude_slash=False):
    # 获取选中的单词列表
    words = st.session_state.word_dict[word_lib_name]
    if exclude_slash:
        words = [word for word in words if "/" not in word]
    n = min(num_words, len(words))
    # 随机选择单词
    st.session_state[key] = random.sample(list(words), n)
    name = word_lib_name.split("-", maxsplit=1)[1]
    st.toast(f"当前单词列表名称：{name} 单词数量: {len(st.session_state[key])}")


def add_personal_dictionary(include):
    # 从集合中提取个人词库，添加到word_lists中
    personal_word_list = st.session_state.dbi.find_personal_dictionary()
    if include:
        if len(personal_word_list) > 0:
            st.session_state.word_dict["0-个人词库"] = personal_word_list
    else:
        if "0-个人词库" in st.session_state.word_dict:
            del st.session_state.word_dict["0-个人词库"]


@st.cache_data(ttl=timedelta(hours=24), max_entries=10000, show_spinner="获取单词信息...")
def get_word_info(word):
    return st.session_state.dbi.find_word(word)


def word_lib_format_func(word_lib_name):
    name = word_lib_name.split("-", maxsplit=1)[1]
    num = len(st.session_state.word_dict[word_lib_name])
    return f"{name} ({num})"


def on_include_cb_change():
    # st.write("on_include_cb_change", st.session_state["include-personal-dictionary"])
    # 更新个人词库
    add_personal_dictionary(st.session_state["include-personal-dictionary"])


def display_word_images(word, container):
    urls = select_word_image_urls(word)
    cols = container.columns(len(urls))
    caption = [f"图片 {i+1}" for i in range(len(urls))]

    for i, col in enumerate(cols):
        # 下载图片
        response = requests.get(urls[i])
        img = Image.open(BytesIO(response.content))

        # 调整图片尺寸
        new_size = (400, 400)
        img = img.resize(new_size)
        # 显示图片
        col.image(img, use_column_width=True, caption=caption[i])


def handle_learning_record(direction):
    item = st.session_state["current-page"]
    if len(st.session_state["learning-records"][item]) == 0:
        create_learning_records()

    def decorator(func):
        def wrapper(*args, **kwargs):
            # 执行原函数
            result = func(*args, **kwargs)
            idx = st.session_state[IDX_MAPS[item]]
            # 获取当前单词的学习记录
            current_record = st.session_state["learning-records"][item][idx]
            # 开始记录
            current_record.start()

            # 根据 direction 参数来计算上一个单词的索引
            prev_idx = idx - 1 if direction == "next" else idx + 1
            # 如果下一个单词有效
            if 0 <= prev_idx < len(st.session_state["learning-records"][item]):
                # 获取下一个单词的学习记录
                prev_record = st.session_state["learning-records"][item][prev_idx]
                # 结束此前单词的学习记录
                prev_record.end()

            return result

        return wrapper

    return decorator


# endregion

# region 闪卡状态

if "flashcard-words" not in st.session_state:
    st.session_state["flashcard-words"] = []

if "flashcard-word-info" not in st.session_state:
    st.session_state["flashcard-word-info"] = {}

if "flashcard_display_state" not in st.session_state:
    st.session_state["flashcard_display_state"] = "全部"

# 初始化单词的索引
if "flashcard-idx" not in st.session_state:
    st.session_state["flashcard-idx"] = -1

# endregion

# region 闪卡辅助函数


def reset_flashcard_word(clear=True):
    # 恢复初始显示状态
    if clear:
        st.session_state["flashcard-words"] = []
    st.session_state.flashcard_display_state = "全部"
    st.session_state["flashcard-idx"] = -1


@handle_learning_record("prev")
def on_prev_btn_click():
    st.session_state["flashcard-idx"] -= 1


@handle_learning_record("next")
def on_next_btn_click():
    # 记录当前单词的开始时间
    st.session_state["flashcard-idx"] += 1


template = """
##### 单词或短语：:rainbow[{word}]
- CEFR最低分级：:green[{cefr}]
- 翻译：:rainbow[{translation}]
- 美式音标：:blue[{us_written}]  
- 英式音标：:violet[{uk_written}]
"""


def _rainbow_word(example: str, word: str):
    pattern = r"\b" + word + r"\b"
    match = re.search(pattern, example)
    if match:
        return re.sub(pattern, f":rainbow[{word}]", example)
    pattern = r"\b" + word.capitalize() + r"\b"
    match = re.search(pattern, example)
    if match:
        return re.sub(pattern, f":rainbow[{word.capitalize()}]", example)
    return example


def _view_detail(container, detail, t_detail, word):
    d1 = remove_trailing_punctuation(detail["definition"])
    d2 = remove_trailing_punctuation(t_detail["definition"])
    e1 = detail["examples"]
    e2 = t_detail["examples"]
    num_elements = min(3, len(e1))
    # 随机选择元素
    content = ""
    indices = random.sample(range(len(e1)), num_elements)
    if st.session_state.flashcard_display_state == "全部":
        container.markdown(f"**:blue[definition：{d1}]**")
        container.markdown(f"**:violet[定义：{d2}]**")
        for i in indices:
            content += f"- {_rainbow_word(e1[i], word)}\n"
            content += f"- {e2[i]}\n"
    elif st.session_state.flashcard_display_state == "英文":
        container.markdown(f"**:blue[definition：{d1}]**")
        for i in indices:
            content += f"- {_rainbow_word(e1[i], word)}\n"
    else:
        # 只显示译文
        container.markdown(f"**:violet[定义：{d2}]**")
        for i in indices:
            content += f"- {e2[i]}\n"
    container.markdown(content)


def _view_pos(container, key, en, zh, word):
    container.markdown(f"**{key}**")
    for i in range(len(en)):
        _view_detail(container, en[i], zh[i], word)


def view_pos(container, word_info, word):
    en = word_info.get("en-US", {})
    zh = word_info.get("zh-CN", {})
    for key in en.keys():
        container.divider()
        _view_pos(container, key, en[key], zh[key], word)


@st.cache_data(ttl=timedelta(hours=12), max_entries=1000, show_spinner="获取音频元素...")
def get_audio_html(word, voice_style):
    """
    获取单词的音频HTML代码，可供浏览器内自动播放。

    参数：
    - word：要获取音频的单词（字符串）
    - voice_style：音频风格（字符串）

    返回值：
    - 音频的HTML代码（字符串）
    """
    audio_data = get_or_create_and_return_audio_data(word, voice_style[0], st.secrets)  # type: ignore
    return audio_autoplay_elem(audio_data)


def view_flash_word(container):
    """
    Display the flashcard word and its information.

    Args:
        container (object): The container to display the flashcard word and information.
        tip_placeholder (object): The placeholder to display the memory tip.

    Returns:
        None
    """

    word = st.session_state["flashcard-words"][st.session_state["flashcard-idx"]]
    if word not in st.session_state["flashcard-word-info"]:
        st.session_state["flashcard-word-info"][word] = get_word_info(word)

    word_info = st.session_state["flashcard-word-info"].get(word, {})
    if not word_info:
        st.error(f"没有该单词：“{word}”的信息。TODO：添加到单词库。")
        st.stop()

    v_word = word
    t_word = ""
    if st.session_state.flashcard_display_state == "中文":
        v_word = ""

    if st.session_state.flashcard_display_state != "英文":
        # t_word = word_info["zh-CN"].get("translation", "")
        t_word = get_mini_dict_doc(word).get("translation", "")

    md = template.format(
        word=v_word,
        # cefr=word_info.get("level", ""),
        cefr=get_mini_dict_doc(word).get("level", ""),
        us_written=word_info.get("us_written", ""),
        uk_written=word_info.get("uk_written", ""),
        translation=t_word,
    )

    container.divider()
    container.markdown(md)

    display_word_images(word, container)
    view_pos(container, word_info, word)


# endregion

# region 单词拼图状态

if "puzzle-idx" not in st.session_state:
    st.session_state["puzzle-idx"] = -1

if "puzzle-words" not in st.session_state:
    st.session_state["puzzle-words"] = []

# if "puzzle_answer_value" not in st.session_state:
#     st.session_state["puzzle_answer_value"] = ""

if "puzzle_view_word" not in st.session_state:
    st.session_state["puzzle_view_word"] = []

if "clicked_character" not in st.session_state:
    st.session_state["clicked_character"] = []

if "puzzle_test_score" not in st.session_state:
    st.session_state["puzzle_test_score"] = {}

# endregion

# region 单词拼图辅助函数


def reset_puzzle_word():
    # 恢复初始显示状态
    st.session_state["puzzle-idx"] = -1
    st.session_state["puzzle_view_word"] = []
    st.session_state["puzzle_test_score"] = {}
    # st.session_state.puzzle_answer_value = ""
    st.session_state.puzzle_answer = ""


def get_word_definition(word):
    word_info = get_word_info(word)
    definition = ""
    en = word_info.get("en-US", {})
    for k, v in en.items():
        definition += f"\n{k}\n"
        for d in v:
            definition += f'- {d["definition"]}\n'
    return definition


def prepare_puzzle():
    word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
    # 打乱单词字符顺序
    ws = [w for w in word]
    random.shuffle(ws)
    st.session_state.puzzle_view_word = ws
    st.session_state.clicked_character = [False] * len(ws)


def view_puzzle_word():
    ws = st.session_state.puzzle_view_word
    n = len(ws)
    cols = st.columns(36)
    button_placeholders = [cols[i].empty() for i in range(n)]
    for i in range(n):
        if button_placeholders[i].button(
            ws[i],
            key=f"btn_{i}",
            disabled=st.session_state.clicked_character[i],
            help="✨ 点击选择字符。",
            type="primary",
            use_container_width=True,
        ):
            # st.session_state.puzzle_answer_value += ws[i]
            st.session_state.puzzle_answer += ws[i]
            st.session_state.clicked_character[i] = True
            st.rerun()


def display_puzzle_translation():
    word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
    t_word = get_mini_dict_doc(word).get("translation", "")
    msg = f"中译文：{t_word}"
    st.markdown(msg)


def display_puzzle_definition():
    word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
    definition = get_word_definition(word)
    msg = f"{definition}"
    st.markdown(msg)


def on_prev_puzzle_btn_click():
    st.session_state["puzzle-idx"] -= 1
    # st.session_state.puzzle_answer_value = ""
    st.session_state.puzzle_answer = ""


def on_next_puzzle_btn_click():
    st.session_state["puzzle-idx"] += 1
    # st.session_state.puzzle_answer_value = ""
    st.session_state.puzzle_answer = ""


def handle_puzzle_input():
    # Use the get method since the keys won't be in session_state
    # on the first script run
    if st.session_state.get("retry"):
        st.session_state["puzzle_answer"] = ""

    user_input = st.text_input(
        "点击字符按钮或输入您的答案",
        placeholder="点击字符按钮或直接输入您的答案",
        key="puzzle_answer",
        label_visibility="collapsed",
    )

    puzzle_score = st.empty()
    sumbit_cols = st.columns(5)

    if sumbit_cols[0].button("重试[:repeat:]", key="retry", help="✨ 恢复初始状态，重新开始拼图游戏。"):
        prepare_puzzle()
        st.rerun()

    if sumbit_cols[1].button("检查[:mag:]", help="✨ 点击按钮，检查您的答案是否正确。"):
        word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
        if word not in st.session_state["flashcard-word-info"]:
            st.session_state["flashcard-word-info"][word] = get_word_info(word)

        msg = f'单词：{word}\t翻译：{st.session_state["flashcard-word-info"][word]["zh-CN"]["translation"]}'
        if user_input == word:
            st.balloons()
            st.session_state.puzzle_test_score[word] = True
        else:
            st.write(f"对不起，您回答错误。正确的单词应该为：{word}")
            st.session_state.puzzle_test_score[word] = False

        score = (
            sum(st.session_state.puzzle_test_score.values())
            / len(st.session_state["puzzle-words"])
            * 100
        )
        msg = f":red[您的得分：{score:.0f}%]\t{msg}"
        puzzle_score.markdown(msg)


def handle_puzzle():
    display_puzzle_translation()
    view_puzzle_word()
    handle_puzzle_input()

    word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
    st.divider()
    st.info("如果字符中包含空格，这可能表示该单词是一个复合词或短语。", icon="ℹ️")
    container = st.container()
    display_puzzle_definition()
    display_word_images(word, container)


# endregion

# region 图片测词辅助

if "pic_idx" not in st.session_state:
    st.session_state["pic_idx"] = -1


if "pic_tests" not in st.session_state:
    st.session_state["pic_tests"] = []

if "user_pic_answer" not in st.session_state:
    st.session_state["user_pic_answer"] = {}


def on_prev_pic_btn_click():
    st.session_state["pic_idx"] -= 1


def on_next_pic_btn_click():
    st.session_state["pic_idx"] += 1


PICTURE_CATEGORY_MAPS = {
    "animals": "动物",
    "animals-not-mammals": "非哺乳动物",
    "arts-and-crafts": "艺术与手工",
    "at-random": "随机",
    "at-work-and-school": "工作与学校",
    "boats-aircraft-and-trains": "船、飞机与火车",
    "buildings": "建筑物",
    "colours-shapes-and-patterns": "颜色、形状与图案",
    "computers-and-technology": "计算机与技术",
    "cooking-and-kitchen-equipment": "烹饪与厨房设备",
    "food-and-drink": "食物与饮料",
    "fruit-vegetables-herbs-and-spices": "水果、蔬菜、草药与香料",
    "furniture-and-household-equipment": "家具与家用设备",
    "gardens-and-farms": "花园与农场",
    "holidays-vacations": "假期与度假",
    "in-the-past": "过去",
    "in-town-and-shopping": "城镇与购物",
    "music": "音乐",
    "nature-and-weather": "自然与天气",
    "on-the-road": "在路上",
    "plants-trees-and-flowers": "植物、树木与花朵",
    "sports": "运动",
    "taking-care-of-yourself": "照顾自己",
    "the-body": "身体",
    "things-you-wear": "穿着",
    "tools-and-machines": "工具与机器",
    "toys-games-and-entertainment": "玩具、游戏与娱乐",
}


@st.cache_data
def get_pic_categories():
    pic_dir = CURRENT_CWD / "resource/quiz/images"
    return sorted([d.name for d in pic_dir.iterdir() if d.is_dir()])


@st.cache_data(ttl=timedelta(hours=24))
def load_pic_tests(category, num):
    pic_qa_path = CURRENT_CWD / "resource/quiz/quiz_image_qa.json"
    pic_qa = {}
    with open(pic_qa_path, "r", encoding="utf-8") as f:
        pic_qa = json.load(f)
    qa_filtered = [v for v in pic_qa if v["category"].startswith(category)]
    random.shuffle(qa_filtered)
    # 重置
    data = qa_filtered[:num]
    for d in data:
        random.shuffle(d["options"])
    return data


def pic_word_test_reset(category, num):
    st.session_state.user_pic_answer = {}
    st.session_state.pic_idx = -1
    data = load_pic_tests(category, num)
    st.session_state["pic_tests"] = data


def on_pic_radio_change(idx):
    # 保存用户答案
    current = st.session_state["pic_options"]
    st.session_state.user_pic_answer[idx] = current


def view_pic_question(container):
    tests = st.session_state.pic_tests
    idx = st.session_state.pic_idx

    question = tests[idx]["question"]
    o_options = tests[idx]["options"]
    options = []
    for f, o in zip("ABC", o_options):
        options.append(f"{f}. {o}")

    image = Image.open(tests[idx]["image_fp"])  # type: ignore

    user_prev_answer = st.session_state.user_pic_answer.get(idx, options[0])
    user_prev_answer_idx = options.index(user_prev_answer)

    st.divider()
    container.markdown(question)
    container.image(image, caption=tests[idx]["iamge_label"], width=400)  # type: ignore

    container.radio(
        "选项",
        options,
        index=user_prev_answer_idx,
        label_visibility="collapsed",
        key="pic_options",
        on_change=on_pic_radio_change,
        args=(idx,),
    )
    # 🎀
    # 兼顾 改变选项和默认二者的影响
    # on_change 选项变化时赋值
    # 没有赋值时使用 user_prev_answer
    st.session_state.user_pic_answer[idx] = user_prev_answer


def check_pic_answer(container):
    score = 0
    tests = st.session_state.pic_tests
    n = len(tests)
    for idx in range(n):
        question = tests[idx]["question"]
        o_options = tests[idx]["options"]
        options = []
        for f, o in zip("ABC", o_options):
            options.append(f"{f}. {o}")
        answer = tests[idx]["answer"]
        image = Image.open(tests[idx]["image_fp"])  # type: ignore

        user_answer = st.session_state.user_pic_answer.get(idx, options[0])
        user_answer_idx = options.index(user_answer)
        container.divider()
        container.markdown(question)
        container.image(image, caption=tests[idx]["iamge_label"], width=400)  # type: ignore
        container.radio(
            "选项",
            options,
            index=user_answer_idx,
            disabled=True,
            label_visibility="collapsed",
            key=f"pic_options_{idx}",
        )
        msg = ""
        if user_answer.strip().endswith(answer.strip()):
            score += 1
            msg = f"正确答案：{answer} :white_check_mark:"
        else:
            msg = f"正确答案：{answer} :x:"
        container.markdown(msg)
    percentage = score / n * 100
    if percentage >= 75:
        st.balloons()
    container.divider()
    container.markdown(f":red[得分：{percentage:.0f}%]")


# endregion

# region 单词测验辅助函数

# 单词序号

if "word-test-idx" not in st.session_state:
    st.session_state["word-test-idx"] = -1
# 用于测试的单词
if "test-words" not in st.session_state:
    st.session_state["test-words"] = []
# 单词理解测试题列表，按自然序号顺序存储测试题、选项、答案、解释字典
if "word-tests" not in st.session_state:
    st.session_state["word-tests"] = []
# 用户答案
if "user-answer" not in st.session_state:
    st.session_state["user-answer"] = []


def reset_test_words():
    st.session_state["word-test-idx"] = -1
    st.session_state["word-tests"] = []
    st.session_state["user-answer"] = []


def on_prev_test_btn_click():
    st.session_state["word-test-idx"] -= 1


def on_next_test_btn_click():
    st.session_state["word-test-idx"] += 1


def check_word_test_answer(container):
    if count_non_none(st.session_state["user-answer"]) == 0:
        container.warning("您尚未答题。")
        container.stop()

    score = 0
    n = count_non_none(st.session_state["word-tests"])
    for idx, test in enumerate(st.session_state["word-tests"]):
        question = test["问题"]
        options = test["选项"]
        answer = test["答案"]
        explanation = test["解释"]

        word = st.session_state["test-words"][idx]
        # 存储的是 None 或者 0、1、2、3
        user_answer_idx = st.session_state["user-answer"][idx]
        container.divider()
        container.markdown(question)
        container.radio(
            "选项",
            options,
            # horizontal=True,
            index=user_answer_idx,
            disabled=True,
            label_visibility="collapsed",
            key=f"test-options-{word}",
        )
        msg = ""
        # 用户答案是选项序号，而提供的标准答案是A、B、C、D
        if is_answer_correct(user_answer_idx, answer):
            score += 1
            msg = f"正确答案：{answer} :white_check_mark:"
        else:
            msg = f"正确答案：{answer} :x:"
        container.markdown(msg)
        container.markdown(f"解释：{explanation}")
    percentage = score / n * 100
    if percentage >= 75:
        container.balloons()
    container.divider()
    container.markdown(f":red[得分：{percentage:.0f}%]")
    # container.divider()


def on_word_test_radio_change(idx, options):
    current = st.session_state["test_options"]
    # 转换为索引
    st.session_state["user-answer"][idx] = options.index(current)


def view_test_word(container):
    idx = st.session_state["word-test-idx"]
    test = st.session_state["word-tests"][idx]
    question = test["问题"]
    options = test["选项"]
    user_answer_idx = st.session_state["user-answer"][idx]

    container.markdown(question)
    container.radio(
        "选项",
        options,
        index=user_answer_idx,
        label_visibility="collapsed",
        on_change=on_word_test_radio_change,
        args=(idx, options),
        key="test_options",
    )
    # 保存用户答案
    st.session_state["user-answer"][idx] = user_answer_idx
    # logger.info(f"用户答案：{st.session_state["user-answer"]}")


# endregion

# region 个人词库辅助


@st.cache_data(ttl=timedelta(hours=24), max_entries=100, show_spinner="获取基础词库...")
def gen_base_lib(word_lib):
    words = st.session_state.word_dict[word_lib]
    data = []
    for word in words:
        info = get_mini_dict_doc(word)
        data.append(
            {
                "单词": word,
                "CEFR最低分级": info.get("level", "") if info else "",
                "翻译": info.get("translation", "") if info else "",
            }
        )
    return pd.DataFrame.from_records(data)


def get_my_word_lib():
    # 返回实时的个人词库
    my_words = st.session_state.dbi.find_personal_dictionary()
    data = []
    for word in my_words:
        info = get_mini_dict_doc(word)
        data.append(
            {
                "单词": word,
                "CEFR最低分级": info.get("level", "") if info else "",
                "翻译": info.get("translation", "") if info else "",
            }
        )
    return pd.DataFrame.from_records(data)


# endregion

# region 加载数据

if "word_dict" not in st.session_state:
    d = load_word_dict().copy()
    # 注意要使用副本
    st.session_state["word_dict"] = {key: set(value) for key, value in d.items()}

with open(CURRENT_CWD / "resource/voices.json", "r", encoding="utf-8") as f:
    voice_style_options = json.load(f)

# endregion

# region 闪卡记忆

if menu and menu.endswith("闪卡记忆"):
    # region 侧边栏
    # 让用户选择语音风格
    pronunciation = st.sidebar.radio("请选择发音标准", ("美式", "英式"))
    style = "en-US" if pronunciation == "美式" else "en-GB"

    # 固定语音风格
    voice_style = voice_style_options[style][0]
    st.sidebar.info(f"语音风格：{voice_style[0]}({voice_style[1]})")
    st.sidebar.checkbox(
        "是否包含个人词库？",
        key="include-personal-dictionary",
        on_change=on_include_cb_change,
    )
    # 在侧边栏添加一个选项卡让用户选择一个单词列表
    word_lib = st.sidebar.selectbox(
        "词库",
        sorted(list(st.session_state.word_dict.keys())),
        key="flashcard-selected",
        on_change=reset_flashcard_word,
        format_func=word_lib_format_func,
        help="✨ 选择一个单词列表，用于生成闪卡单词。",
    )

    # 在侧边栏添加一个滑块让用户选择记忆的单词数量
    num_word = st.sidebar.slider(
        "单词数量",
        10,
        50,
        step=5,
        key="flashcard-words-num",
        on_change=reset_flashcard_word,
        help="✨ 请选择计划记忆的单词数量。",
    )
    # endregion

    st.subheader(":book: 闪卡记忆", divider="rainbow", anchor=False)
    st.markdown(
        """✨ 闪卡记忆是一种依赖视觉记忆的学习策略，通过展示与单词或短语含义相关的四幅图片，帮助用户建立和强化单词或短语与其含义之间的关联。这四幅图片的共同特性可以引导用户快速理解和记忆单词或短语的含义，从而提高记忆效率和效果。"""
    )

    update_and_display_progress(
        st.session_state["flashcard-idx"] + 1
        if st.session_state["flashcard-idx"] != -1
        else 0,
        len(st.session_state["flashcard-words"])
        if len(st.session_state["flashcard-words"]) != 0
        else 1,
        st.empty(),
        f'\t 当前单词：{st.session_state["flashcard-words"][st.session_state["flashcard-idx"]] if st.session_state["flashcard-idx"] != -1 else ""}',
    )

    btn_cols = st.columns(8)

    refresh_btn = btn_cols[0].button(
        "刷新[:arrows_counterclockwise:]",
        key="flashcard-refresh",
        on_click=generate_page_words,
        args=(word_lib, num_word, "flashcard-words"),
        help="✨ 点击按钮，从词库中抽取单词，开始或重新开始记忆闪卡游戏。",
    )
    display_status_button = btn_cols[1].button(
        "切换[:recycle:]",
        key="flashcard-mask",
        help="✨ 点击按钮可以在中英对照、只显示英文和只显示中文三种显示状态之间切换。初始状态为中英对照。",
    )
    prev_btn = btn_cols[2].button(
        "上一[:leftwards_arrow_with_hook:]",
        key="flashcard-prev",
        help="✨ 点击按钮，切换到上一个单词。",
        on_click=on_prev_btn_click,
        disabled=st.session_state["flashcard-idx"] < 0,
    )
    next_btn = btn_cols[3].button(
        "下一[:arrow_right_hook:]",
        key="flashcard-next",
        help="✨ 点击按钮，切换到下一个单词。",
        on_click=on_next_btn_click,
        disabled=len(st.session_state["flashcard-words"]) == 0
        or st.session_state["flashcard-idx"]
        == len(st.session_state["flashcard-words"]) - 1,  # type: ignore
    )
    play_btn = btn_cols[4].button(
        "播放[:sound:]",
        key="flashcard-play",
        help="✨ 聆听单词发音",
        disabled=st.session_state["flashcard-idx"] == -1,
    )
    add_btn = btn_cols[5].button(
        "添加[:heavy_plus_sign:]",
        key="flashcard-add",
        help="✨ 将当前单词添加到个人词库",
        disabled=st.session_state["flashcard-idx"] == -1 or "个人词库" in word_lib,  # type: ignore
    )
    del_btn = btn_cols[6].button(
        "删除[:heavy_minus_sign:]",
        key="flashcard-del",
        help="✨ 将当前单词从个人词库中删除",
        disabled=st.session_state["flashcard-idx"] == -1,
    )

    # 创建按钮
    if display_status_button:
        if st.session_state.flashcard_display_state == "全部":
            st.session_state.flashcard_display_state = "英文"
        elif st.session_state.flashcard_display_state == "英文":
            st.session_state.flashcard_display_state = "中文"
        else:
            st.session_state.flashcard_display_state = "全部"

    if prev_btn:
        if len(st.session_state["flashcard-words"]) == 0:
            st.warning("请先点击`🔄`按钮生成记忆闪卡。")
            st.stop()

    if next_btn:
        if len(st.session_state["flashcard-words"]) == 0:
            st.warning("请先点击`🔄`按钮生成记忆闪卡。")
            st.stop()

    if refresh_btn:
        reset_flashcard_word(False)
        save_and_clear_learning_records()
        # 新记录
        create_learning_records()
        st.rerun()

    if play_btn:
        item = st.session_state["current-page"]
        idx = st.session_state["flashcard-idx"]
        record = st.session_state["learning-records"][item][idx]
        record.start()
        word = st.session_state["flashcard-words"][idx]
        # 使用会话缓存，避免重复请求
        audio_html = get_audio_html(word, voice_style)
        components.html(audio_html)
        record.end()
        # logger.info(f"{record.duration:.2f} 秒")

    if add_btn:
        word = st.session_state["flashcard-words"][st.session_state["flashcard-idx"]]
        st.session_state.dbi.add_words_to_personal_dictionary([word])
        st.toast(f"添加单词：{word} 到个人词库。")

    if del_btn:
        word = st.session_state["flashcard-words"][st.session_state["flashcard-idx"]]
        st.session_state.dbi.delete_words_from_personal_dictionary([word])
        st.toast(f"从个人词库中删除单词：{word}。")

    if st.session_state["flashcard-idx"] != -1:
        view_flash_word(st.container())

# endregion

# region 单词拼图

elif menu and menu.endswith("拼图游戏"):
    # region 边栏
    include_cb = st.sidebar.checkbox(
        "是否包含个人词库？",
        key="include-personal-dictionary",
        value=False,
        on_change=on_include_cb_change,
    )
    # 在侧边栏添加一个选项卡让用户选择一个单词列表
    word_lib = st.sidebar.selectbox(
        "词库",
        sorted(list(st.session_state.word_dict.keys())),
        key="puzzle-selected",
        on_change=reset_puzzle_word,
        format_func=word_lib_format_func,
        help="✨ 选择一个词库，用于生成单词拼图。",
    )

    # 在侧边栏添加一个滑块让用户选择记忆的单词数量
    num_word = st.sidebar.slider(
        "单词数量",
        10,
        50,
        step=5,
        key="puzzle-words-num",
        on_change=reset_puzzle_word,
        help="✨ 单词拼图的数量。",
    )
    # endregion

    st.subheader(":jigsaw: 拼图游戏", divider="rainbow", anchor=False)
    st.markdown(
        "✨ 单词拼图是一种记忆单词的游戏，玩家需根据打乱的字母和提示信息拼出正确的单词，有助于提高词汇量、拼写能力和解决问题能力。参考：[Cambridge Dictionary](https://dictionary.cambridge.org/)"
    )

    update_and_display_progress(
        st.session_state["puzzle-idx"] + 1
        if st.session_state["puzzle-idx"] != -1
        else 0,
        len(st.session_state["puzzle-words"])
        if len(st.session_state["puzzle-words"]) != 0
        else 1,
        st.empty(),
    )

    puzzle_cols = st.columns(8)
    refresh_btn = puzzle_cols[0].button(
        "刷新[:arrows_counterclockwise:]",
        key="puzzle-refresh",
        help="✨ 点击按钮，将从词库中抽取单词，开始或重新开始单词拼图游戏。",
        on_click=generate_page_words,
        args=(word_lib, num_word, "puzzle-words", True),
    )
    prev_btn = puzzle_cols[1].button(
        "上一[:leftwards_arrow_with_hook:]",
        key="puzzle-prev",
        help="✨ 点击按钮，切换到上一单词拼图。",
        on_click=on_prev_puzzle_btn_click,
        disabled=st.session_state["puzzle-idx"] < 0,
    )
    next_btn = puzzle_cols[2].button(
        "下一[:arrow_right_hook:]",
        key="puzzle-next",
        help="✨ 点击按钮，切换到下一单词拼图。",
        on_click=on_next_puzzle_btn_click,
        disabled=len(st.session_state["puzzle-words"]) == 0
        or st.session_state["puzzle-idx"]
        == len(st.session_state["puzzle-words"]) - 1,  # type: ignore
    )
    add_btn = puzzle_cols[3].button(
        "添加[:heavy_plus_sign:]",
        key="puzzle-add",
        help="✨ 将当前单词添加到个人词库",
        disabled=st.session_state["puzzle-idx"] == -1 or "个人词库" in word_lib,  # type: ignore
    )
    del_btn = puzzle_cols[4].button(
        "删除[:heavy_minus_sign:]",
        key="puzzle-del",
        help="✨ 将当前单词从个人词库中删除",
        disabled=st.session_state["puzzle-idx"] == -1,
    )

    if refresh_btn:
        reset_puzzle_word()
        st.rerun()

    if prev_btn:
        prepare_puzzle()

    if next_btn:
        prepare_puzzle()

    if add_btn:
        word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
        st.session_state.dbi.add_words_to_personal_dictionary([word])
        st.toast(f"添加单词：{word} 到个人词库。")

    if del_btn:
        word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
        st.session_state.dbi.delete_words_from_personal_dictionary([word])
        st.toast(f"从个人词库中删除单词：{word}。")

    if st.session_state["puzzle-idx"] != -1:
        handle_puzzle()

# endregion

# region 图片测词

elif menu and menu.endswith("看图猜词"):
    # region 边栏
    category = st.sidebar.selectbox(
        "请选择图片类别以生成对应的看图猜词题目",
        get_pic_categories(),
        format_func=lambda x: PICTURE_CATEGORY_MAPS[x],
        key="pic-category",
    )
    pic_num = st.sidebar.number_input(
        "请选择您希望生成的看图猜词题目的数量",
        1,
        20,
        value=10,
        step=1,
        key="pic-num",
    )
    # endregion
    st.subheader(":frame_with_picture: 看图猜词", divider="rainbow", anchor=False)
    st.markdown(
        """✨ 看图猜词是一种记忆单词的方法，通过图片提示，用户需猜出对应的单词。数据来源：[Cambridge Dictionary](https://dictionary.cambridge.org/)

请注意，专业领域的单词可能较为生僻，对于不熟悉的领域，可能需要投入更多的精力。
        """
    )

    update_and_display_progress(
        st.session_state.pic_idx + 1 if st.session_state.pic_idx != -1 else 0,
        len(st.session_state.pic_tests) if len(st.session_state.pic_tests) != 0 else 1,
        st.empty(),
    )

    pic_word_test_btn_cols = st.columns(8)

    # 创建按钮
    refresh_btn = pic_word_test_btn_cols[0].button(
        "刷新[:arrows_counterclockwise:]",
        key="refresh-pic",
        help="✨ 点击按钮，将从题库中抽取测试题，开始或重新开始看图测词游戏。",
        on_click=pic_word_test_reset,
        args=(category, pic_num),
    )
    prev_pic_btn = pic_word_test_btn_cols[1].button(
        "上一[:leftwards_arrow_with_hook:]",
        help="✨ 点击按钮，切换到上一题。",
        on_click=on_prev_pic_btn_click,
        key="prev-pic",
        disabled=st.session_state.pic_idx < 0,
    )
    next_btn = pic_word_test_btn_cols[2].button(
        "下一[:arrow_right_hook:]",
        help="✨ 点击按钮，切换到下一题。",
        on_click=on_next_pic_btn_click,
        key="next-pic",
        disabled=len(st.session_state.pic_tests) == 0
        or st.session_state.pic_idx == len(st.session_state.pic_tests) - 1,
    )
    # 答题即可提交检查
    sumbit_pic_btn = pic_word_test_btn_cols[3].button(
        "提交[:mag:]",
        key="submit-pic",
        disabled=len(st.session_state.pic_tests) == 0
        or len(st.session_state.user_pic_answer) == 0,
        help="✨ 只有在完成至少一道测试题后，才能点击按钮查看测验得分。",
    )

    # add_btn = pic_word_test_btn_cols[4].button(
    #     "添加[:heavy_plus_sign:]",
    #     key="pic-add",
    #     help="✨ 将当前单词添加到个人词库",
    #     disabled=st.session_state.pic_idx == -1,
    # )
    # del_btn = pic_word_test_btn_cols[5].button(
    #     "删除[:heavy_minus_sign:]",
    #     key="pic-del",
    #     help="✨ 将当前单词从个人词库中删除",
    #     disabled=st.session_state.pic_idx == -1,
    # )

    container = st.container()
    if sumbit_pic_btn:
        if len(st.session_state.user_pic_answer) == 0:
            st.warning("您尚未答题。")
            st.stop()
        container.empty()
        if len(st.session_state.user_pic_answer) != len(st.session_state.pic_tests):
            container.warning("您尚未完成全部测试题目。")
        check_pic_answer(container)
    elif st.session_state.pic_idx != -1:
        view_pic_question(container)

    # if add_btn:
    #     tests = st.session_state.pic_tests
    #     idx = st.session_state.pic_idx
    #     word = tests[idx]["answer"]
    #     st.session_state.dbi.add_words_to_personal_dictionary([word])
    #     st.toast(f"添加单词：{word} 到个人词库。")

    # if del_btn:
    #     tests = st.session_state.pic_tests
    #     idx = st.session_state.pic_idx
    #     word = tests[idx]["answer"]
    #     st.session_state.dbi.delete_words_from_personal_dictionary([word])
    #     st.toast(f"从个人词库中删除单词：{word}。")

# endregion

# region 词意测试

elif menu and menu.endswith("词意测试"):
    sidebar_status.markdown(
        f"""令牌：{st.session_state.current_token_count} 累计：{format_token_count(st.session_state.total_token_count)}""",
        help=TOEKN_HELP_INFO,
    )
    # region 边栏
    level = st.sidebar.selectbox(
        "CEFR分级",
        CEFR_LEVEL_MAPS.keys(),
        key="test-word-level",
    )
    include_cb = st.sidebar.checkbox(
        "是否包含个人词库？",
        key="include-personal-dictionary",
        value=False,
        on_change=on_include_cb_change,
    )
    # 在侧边栏添加一个选项卡让用户选择一个单词列表
    word_lib = st.sidebar.selectbox(
        "词库",
        sorted(list(st.session_state.word_dict.keys())),
        key="test-word-selected",
        on_change=reset_test_words,
        format_func=word_lib_format_func,
        help="✨ 选择一个单词列表，用于生成单词词义理解测试题。",
    )
    test_num = st.sidebar.number_input(
        "试题数量",
        1,
        20,
        value=10,
        step=1,
        key="test-word-num",
        on_change=reset_test_words,
    )
    # endregion

    st.subheader(":pencil: 英语单词理解测试", divider="rainbow", anchor=False)
    st.markdown("""✨ 英语单词理解测试是一种选择题形式的测试，提供一个英语单词和四个选项，要求选出正确的词义。""")

    if "gemini-pro-model" not in st.session_state:
        st.session_state["gemini-pro-model"] = load_vertex_model("gemini-pro")

    update_and_display_progress(
        st.session_state["word-test-idx"] + 1
        if st.session_state["word-test-idx"] != -1
        else 0,
        len(st.session_state["test-words"])
        if len(st.session_state["test-words"]) != 0
        else 1,
        st.empty(),
        # message=st.session_state["test-words"][st.session_state["word-test-idx"]]
        # if st.session_state["word-test-idx"] != -1
        # else "",
    )

    test_btns = st.columns(8)

    refresh_btn = test_btns[0].button(
        "刷新[:arrows_counterclockwise:]",
        key="test-word-refresh",
        help="✨ 点击按钮，将从词库中抽取单词，开始或重新开始单词理解测试。",
    )
    prev_test_btn = test_btns[1].button(
        "上一[:leftwards_arrow_with_hook:]",
        key="prev-test-word",
        help="✨ 点击按钮，切换到上一题。",
        on_click=on_prev_test_btn_click,
        disabled=st.session_state["word-test-idx"] < 0,
    )
    next_test_btn = test_btns[2].button(
        "下一[:arrow_right_hook:]",
        key="next-test-word",
        help="✨ 点击按钮，切换到下一题。",
        on_click=on_next_test_btn_click,
        # 选择单词后才开始出题
        disabled=len(st.session_state["test-words"]) == 0
        or st.session_state["word-test-idx"] == len(st.session_state["test-words"]) - 1,
    )
    # 答题即可提交检查
    sumbit_test_btn = test_btns[3].button(
        "检查[:mag:]",
        key="submit-test-word",
        disabled=st.session_state["word-test-idx"] == -1
        or len(st.session_state["user-answer"]) == 0,
        help="✨ 至少完成一道测试题后，才可点击按钮，显示测验得分。",
    )
    add_btn = test_btns[4].button(
        "添加[:heavy_plus_sign:]",
        key="test-word-add",
        help="✨ 将当前单词添加到个人词库",
        disabled=st.session_state["word-test-idx"] == -1 or "个人词库" in word_lib,  # type: ignore
    )
    del_btn = test_btns[5].button(
        "删除[:heavy_minus_sign:]",
        key="test-word-del",
        help="✨ 将当前单词从个人词库中删除",
        disabled=st.session_state["word-test-idx"] == -1,
    )

    st.divider()
    container = st.container()

    if prev_test_btn:
        idx = st.session_state["word-test-idx"]
        if idx != -1:
            word = st.session_state["test-words"][idx]
            if not st.session_state["word-tests"][idx]:
                with st.spinner("AI🤖正在生成单词理解测试题，请稍候..."):
                    st.session_state["word-tests"][idx] = generate_word_test(
                        "gemini-pro",
                        st.session_state["gemini-pro-model"],
                        word,
                        level,
                    )

    if next_test_btn:
        idx = st.session_state["word-test-idx"]
        word = st.session_state["test-words"][idx]
        if not st.session_state["word-tests"][idx]:
            with st.spinner("AI🤖正在生成单词理解测试题，请稍候..."):
                st.session_state["word-tests"][idx] = generate_word_test(
                    "gemini-pro", st.session_state["gemini-pro-model"], word, level
                )

    if refresh_btn:
        reset_test_words()
        st.session_state["user-answer"] = [None] * test_num
        st.session_state["word-tests"] = [None] * test_num
        generate_page_words(word_lib, test_num, "test-words", True)
        st.rerun()

    if (
        st.session_state["word-test-idx"] != -1
        and st.session_state["word-tests"][st.session_state["word-test-idx"]]
        and not sumbit_test_btn
    ):
        view_test_word(container)

    if sumbit_test_btn:
        container.empty()
        if count_non_none(st.session_state["user-answer"]) != count_non_none(
            st.session_state["word-tests"]
        ):
            container.warning("您尚未完成测试。")
        check_word_test_answer(container)

    if add_btn:
        word = st.session_state["test-words"][st.session_state["word-test-idx"]]
        st.session_state.dbi.add_words_to_personal_dictionary([word])
        st.toast(f"添加单词：{word} 到个人词库。")

    if del_btn:
        word = st.session_state["test-words"][st.session_state["word-test-idx"]]
        st.session_state.dbi.delete_words_from_personal_dictionary([word])
        st.toast(f"从个人词库中删除单词：{word}。")

# endregion

# region 个人词库

elif menu and menu.endswith("词库管理"):
    # 基准词库不包含个人词库
    add_personal_dictionary(False)
    word_lib = st.sidebar.selectbox(
        "词库",
        sorted(list(st.session_state.word_dict.keys())),
        key="lib-selected",
        format_func=word_lib_format_func,
        help="✨ 选择一个基准词库，用于生成个人词库。",
    )

    st.subheader(":books: 词库管理", divider="rainbow", anchor=False)
    st.markdown(
        """✨ 词库分基础词库和个人词库两部分。基础词库包含常用单词，供所有用户使用。个人词库则是用户自定义的部分，用户可以根据自己的需求添加或删除单词，以便进行个性化的学习和复习。"""
    )
    status_elem = st.empty()

    lib_cols = st.columns(8)

    add_lib_btn = lib_cols[0].button(
        "添加[:heavy_plus_sign:]",
        key="add-lib-btn",
        help="✨ 点击按钮，将'基础词库'中选定单词添加到个人词库。",
    )
    del_lib_btn = lib_cols[1].button(
        "删除[:heavy_minus_sign:]",
        key="del-lib-btn",
        help="✨ 点击按钮，将'可删列表'中选定单词从'个人词库'中删除。",
    )
    view_lib_btn = lib_cols[2].button(
        "查看[:eye:]", key="view-lib-btn", help="✨ 点击按钮，查看'个人词库'最新数据。"
    )

    content_cols = st.columns(3)
    base_placeholder = content_cols[0].container()
    mylib_placeholder = content_cols[1].container()
    view_placeholder = content_cols[2].container()

    base_lib_df = gen_base_lib(word_lib)
    lib_df = get_my_word_lib()

    view_selected_list = word_lib.split("-", 1)[1]
    base_placeholder.text(f"基础词库({view_selected_list})")
    mylib_placeholder.text(
        f"可删列表（{0 if lib_df.empty else lib_df.shape[0]}） 个单词",
        help="在这里删除你的个人词库中的单词（显示的是最近1小时的缓存数据）",
    )

    base_placeholder.data_editor(
        base_lib_df,
        key="base_lib_edited_df",
        hide_index=True,
        disabled=["单词", "CEFR最低分级", "翻译"],
        num_rows="dynamic",
        height=500,
    )

    mylib_placeholder.data_editor(
        lib_df,
        key="my_word_lib",
        hide_index=True,
        disabled=["单词", "CEFR最低分级", "翻译"],
        num_rows="dynamic",
        height=500,
    )

    if add_lib_btn:
        if st.session_state.get("base_lib_edited_df", {}).get("deleted_rows", []):
            deleted_rows = st.session_state["base_lib_edited_df"]["deleted_rows"]
            to_add = []
            for idx in deleted_rows:
                word = base_lib_df.iloc[idx]["单词"]  # type: ignore
                to_add.append(word)
            st.session_state.dbi.add_words_to_personal_dictionary(to_add)
            logger.info(f"已添加到个人词库中：{to_add}。")

    if del_lib_btn:
        if del_lib_btn and st.session_state.get("my_word_lib", {}).get(
            "deleted_rows", []
        ):
            my_word_deleted_rows = st.session_state["my_word_lib"]["deleted_rows"]
            # st.write("删除的行号:\n", my_word_deleted_rows)
            to_del = []
            for idx in my_word_deleted_rows:
                word = lib_df.iloc[idx]["单词"]  # type: ignore
                to_del.append(word)
            st.session_state.dbi.remove_words_from_personal_dictionary(to_del)
            logger.info(f"从个人词库中已经删除：{to_del}。")

    if view_lib_btn:
        df = get_my_word_lib()
        view_placeholder.text(
            f"个人词库（{0 if df.empty else df.shape[0]}） 个单词",
            help="在这里查看你的个人词库所有单词（显示的最新数据）",
        )
        view_placeholder.dataframe(df, height=500)

    with st.expander(":bulb: 如何给个人词库添加一个或多个单词？", expanded=False):
        vfp = VIDEO_DIR / "单词" / "个人词库逐词添加.mp4"
        st.video(str(vfp))

    with st.expander(":bulb: 如何把一个基础词库整体添加到个人词库？", expanded=False):
        vfp = VIDEO_DIR / "单词" / "基础词库整体加入个人词库.mp4"
        st.video(str(vfp))

    with st.expander(":bulb: 如何从个人词库中删除一个或多个单词？", expanded=False):
        vfp = VIDEO_DIR / "单词" / "个人词库逐词删除.mp4"
        st.video(str(vfp))

    with st.expander(":bulb: 如何把个人词库中的单词全部删除？", expanded=False):
        vfp = VIDEO_DIR / "单词" / "删除个人词库.mp4"
        st.video(str(vfp))

    with st.expander(":bulb: 小提示", expanded=False):
        st.markdown(
            """
- 用户只能从基础词库中挑选单词添加到个人词库，而不能直接添加单词到个人词库。
- 词库`coca20000`包含了大量常用英语单词，可作为基础词库供用户参考。
- 基础词库的删除操作不会影响到基础词库本身的内容，只将基础词库删除部分单词添加到个人词库。
- 如需从基础词库中添加单词到个人词库，用户需在基础词库左侧的复选框中选择一行或多行，单击删除`图标 (delete)`或按键盘上的`删除键`，最后点击`添加[➕]`按钮，即可将选中的单词添加到个人词库。
- 如需将整个基础词库添加到个人词库，用户需在基础词库标题行的第一列进行全选，然后点击`添加[➕]`按钮，即可将所有单词添加到个人词库。
"""
        )

# endregion
