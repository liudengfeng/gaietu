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
import pytz
import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from menu import menu
from mypylib.constants import CEFR_LEVEL_MAPS

# from mypylib.db_model import LearningTime
from mypylib.google_ai import generate_word_tests, load_vertex_model, pick_a_phrase
from mypylib.personalized_task import calculate_sampling_probabilities
from mypylib.st_helper import (  # end_and_save_learning_records,
    add_exercises_to_db,
    check_access,
    configure_google_apis,
    count_non_none,
    get_mini_dict_doc,
    get_synthesis_speech,
    is_answer_correct,
    on_project_changed,
    select_word_image_urls,
    setup_logger,
    update_and_display_progress,
    update_sidebar_status,
)
from mypylib.st_utils import (
    init_words_between_containers,
    move_words_between_containers,
)
from mypylib.word_utils import (
    audio_autoplay_elem,
    is_phrase_combination_description,
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
menu()
check_access(False)
configure_google_apis()
sidebar_status = st.sidebar.empty()
user_tz = st.session_state.dbi.cache["user_info"]["timezone"]

menu_names = ["闪卡记忆", "拼图游戏", "看图猜词", "词意测试", "词库管理"]
menu_emoji = [
    "📚",
    "🧩",
    "🖼️",
    "📝",
    "🗂️",
]
menu_opts = [e + " " + n for e, n in zip(menu_emoji, menu_names)]


def on_menu_change():
    item = st.session_state["word_dict_menu"].split(" ", 1)[1]


item_menu: str = st.sidebar.selectbox(
    "菜单",
    menu_opts,
    index=0,
    key="word_dict_menu",
    on_change=on_menu_change,
    help="在这里选择你想要进行的操作。",
)  # type: ignore

st.sidebar.divider()

# endregion

# region 通用

# streamlit中各页都是相对当前根目录

CURRENT_CWD: Path = Path(__file__).parent.parent
DICT_DIR = CURRENT_CWD / "resource/dictionary"
VIDEO_DIR = CURRENT_CWD / "resource/video_tip"


# endregion

# region 通用函数


@st.cache_data(show_spinner="提取词典...", ttl=timedelta(days=1))  # 缓存有效期为24小时
def load_word_dict():
    with open(
        DICT_DIR / "word_lists_by_edition_grade.json", "r", encoding="utf-8"
    ) as f:
        return json.load(f)


# 使用手机号码防止缓存冲突
@st.cache_data(show_spinner="单词概率抽样...", ttl=timedelta(days=1))  # 缓存有效期为24小时
def get_sampled_word(phone_number, words, num_words):
    """
    从给定的单词列表中根据概率进行抽样，返回抽样结果。

    Args:
        phone_number (str): 手机号码。
        words (list): 单词列表。
        num_words (int): 抽样的单词数量。

    Returns:
        list: 抽样结果，包含抽样的单词列表。

    """
    word_duration_stats = st.session_state.dbi.generate_word_duration_stats(
        phone_number, "exercises"
    )
    word_pass_stats = st.session_state.dbi.generate_word_pass_stats(
        phone_number, "performances"
    )
    duration_records = [
        (word, duration) for word, duration in word_duration_stats.items()
    ]
    pass_records = [
        (word, d["passed"], d["failed"]) for word, d in word_pass_stats.items()
    ]
    probabilities = calculate_sampling_probabilities(
        words, duration_records, pass_records
    )
    # 根据概率进行抽样
    words = list(probabilities.keys())
    probs = list(probabilities.values())
    return random.choices(words, weights=probs, k=num_words)


def generate_page_words(
    word_lib_name, num_words, key, exclude_slash=False, from_today_learned=False
):
    # 根据from_today_learned参数决定从哪里获取单词
    # 集合转换为列表
    if from_today_learned:
        words = list(st.session_state["today-learned"])
    else:
        words = list(st.session_state.word_dict[word_lib_name])

    # logger.info(f"单词库名称：{word_lib_name} 单词：{words}")

    if from_today_learned and len(words) == 0:
        st.error("今天没有学习记录，请先进行闪卡记忆。")
        st.stop()

    if exclude_slash:
        words = [word for word in words if "/" not in word]

    phone_number = st.session_state.dbi.cache["user_info"]["phone_number"]
    n = min(num_words, len(words))
    word_lib = get_sampled_word(phone_number, words, n * 10)
    # 随机选择单词
    st.session_state[key] = random.sample(word_lib, n)
    if not from_today_learned:
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


@st.cache_data(
    ttl=timedelta(hours=24), max_entries=10000, show_spinner="获取单词信息..."
)
def get_word_info(word):
    return st.session_state.dbi.find_word(word)


@st.cache_data(
    ttl=timedelta(hours=24),
    max_entries=10000,
    show_spinner="AI正在生成单词理解测试题...",
)
def generate_word_tests_for(words, level):
    model_name = "gemini-pro"
    model = load_vertex_model(model_name)
    return generate_word_tests(model_name, model, words, level)


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
        try:
            img = Image.open(BytesIO(response.content))

            # 调整图片尺寸
            new_size = (400, 400)
            img = img.resize(new_size)
            # 显示图片
            col.image(img, use_column_width=True, caption=caption[i])
        except Exception:
            continue


# endregion

# region 闪卡状态

# 获取用户时区的当前日期
now = datetime.now(pytz.timezone(user_tz)).date()

if "flashcard-words" not in st.session_state:
    st.session_state["flashcard-words"] = []

if (
    "today-learned" not in st.session_state
    or "today-learned-date" not in st.session_state
):
    # 如果today-learned或其创建日期不存在，创建它们
    st.session_state["today-learned"] = set()
    st.session_state["today-learned-date"] = now
else:
    # 如果today-learned和其创建日期都存在，检查创建日期是否是今天
    if st.session_state["today-learned-date"] != now:
        # 如果不是今天，清空today-learned并更新创建日期
        st.session_state["today-learned"] = set()
        st.session_state["today-learned-date"] = now

if "flashcard-word-info" not in st.session_state:
    st.session_state["flashcard-word-info"] = {}

if "flashcard_display_state" not in st.session_state:
    st.session_state["flashcard_display_state"] = "全部"

# 初始化单词的索引
if "flashcard-idx" not in st.session_state:
    st.session_state["flashcard-idx"] = -1

# endregion

# region 闪卡辅助函数

if "word-learning-times" not in st.session_state:
    st.session_state["word-learning-times"] = 0


def reset_flashcard_word(clear=True):
    # 恢复初始显示状态
    if clear:
        st.session_state["flashcard-words"] = []
    st.session_state.flashcard_display_state = "全部"
    st.session_state["flashcard-idx"] = -1


def on_prev_btn_click():
    st.session_state["flashcard-idx"] -= 1


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


def get_flashcard_project():
    idx = st.session_state["flashcard-idx"]
    words = st.session_state["flashcard-words"]
    project = "闪卡记忆"
    if idx == -1 or len(words) == 0:
        return f"单词练习-{project}"
    else:
        return f"单词练习-{project}-{words[idx]}"


def play_flashcard_word(voice_style, sleep=False):
    word = st.session_state["flashcard-words"][st.session_state["flashcard-idx"]]
    result = get_synthesis_speech(word, voice_style[0])
    t = result["audio_duration"].total_seconds()
    html = audio_autoplay_elem(result["audio_data"], fmt="mav")
    components.html(html)
    # 如果休眠，第二次重复时会播放二次
    if sleep:
        time.sleep(t)


def view_flash_word(container, view_detail=True, placeholder=None):
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
    if placeholder:
        display_word_images(word, placeholder)

    if view_detail:
        display_word_images(word, container)
        view_pos(container, word_info, word)


def auto_play_flash_word(voice_style):
    current_idx = st.session_state["flashcard-idx"]
    n = len(st.session_state["flashcard-words"])
    cols = st.columns([1, 1, 2, 1, 1])
    elem = cols[2].empty()
    placeholder = st.empty()
    for idx in range(n):
        start = time.time()
        st.session_state["flashcard-idx"] = idx

        word = st.session_state["flashcard-words"][idx]
        st.session_state["today-learned"].add(word)

        on_project_changed(get_flashcard_project())

        play_flashcard_word(voice_style, True)
        view_flash_word(elem, False, placeholder)

        time.sleep(max(3 - time.time() + start, 0))

    # 恢复闪卡记忆的索引
    st.session_state["flashcard-idx"] = current_idx


# endregion

# region 单词拼图状态

if "puzzle-idx" not in st.session_state:
    st.session_state["puzzle-idx"] = -1

if "puzzle-words" not in st.session_state:
    st.session_state["puzzle-words"] = []

if "puzzle_view_word" not in st.session_state:
    st.session_state["puzzle_view_word"] = []

if "puzzle_test_score" not in st.session_state:
    st.session_state["puzzle_test_score"] = {}

# endregion

# region 单词拼图辅助函数


def reset_puzzle_word():
    # 恢复初始显示状态
    st.session_state["puzzle-idx"] = -1
    st.session_state["puzzle_test_score"] = {}
    st.session_state.puzzle_answer = ""


def get_puzzle_project():
    idx = st.session_state["puzzle-idx"]
    word = st.session_state["puzzle-words"][idx]
    project = "单词拼图"
    if idx == -1:
        return f"单词练习-{project}"
    else:
        return f"单词练习-{project}-{word}"


def get_word_definition(word):
    word_info = get_word_info(word)
    definition = ""
    en = word_info.get("en-US", {})
    for k, v in en.items():
        definition += f"\n{k}\n"
        for d in v:
            definition += f'- {d["definition"]}\n'
    return definition


@st.cache_data(ttl=timedelta(hours=24), max_entries=10000)
def normalize_puzzle_word(word):
    # 挑选一个短语
    if is_phrase_combination_description(word):
        model = load_vertex_model("gemini-pro")
        return pick_a_phrase(model, word)
    return word


def prepare_puzzle():
    word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
    word = normalize_puzzle_word(word)
    # 打乱单词字符顺序
    ws = [w for w in word]
    random.shuffle(ws)
    st.session_state["puzzle_view_word"] = ws
    init_words_between_containers(ws)


def display_puzzle_translation():
    word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
    t_word = get_mini_dict_doc(word).get("translation", "")
    msg = f"中文提示：{t_word}"
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


def check_puzzle(puzzle_container):
    puzzle_container.empty()
    idx = st.session_state["puzzle-idx"]
    word = st.session_state["puzzle-words"][idx]
    answer = normalize_puzzle_word(word)
    if word not in st.session_state["flashcard-word-info"]:
        st.session_state["flashcard-word-info"][word] = get_word_info(word)
    msg = f'单词：{word}\t翻译：{st.session_state["flashcard-word-info"][word]["zh-CN"]["translation"]}'
    user_input = "".join(st.session_state["target-container-words"])
    if user_input == answer:
        st.balloons()
        st.session_state.puzzle_test_score[word] = True
    else:
        st.snow()
        puzzle_container.markdown(f"对不起，您回答错误。正确的单词应该为：{word}")
        st.session_state.puzzle_test_score[word] = False

    n = len(st.session_state["puzzle-words"])
    score = sum(st.session_state.puzzle_test_score.values()) / n * 100
    msg = f":red[您的得分：{score:.0f}%]\t{msg}"
    puzzle_container.markdown(msg)
    puzzle_container.divider()
    if idx == n - 1:
        d = {
            "item": "拼图游戏",
            "level": answer,
            # "phone_number": st.session_state.dbi.cache["user_info"]["phone_number"],
            "record_time": datetime.now(timezone.utc),
            "score": score,
            "word_results": st.session_state.puzzle_test_score,
        }
        st.session_state.dbi.add_documents_to_user_history("performances", [d])


def handle_puzzle():
    display_puzzle_translation()

    st.markdown("打乱的字符")
    src_container = st.container()
    st.markdown("您的拼图")
    tgt_container = st.container()
    words = st.session_state.puzzle_view_word
    move_words_between_containers(src_container, tgt_container, words, True)

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


def on_pic_radio_change(options, idx):
    # 保存用户答案
    current = st.session_state["pic_options"]
    st.session_state.user_pic_answer[idx] = options.index(current)


def view_pic_question(container):
    tests = st.session_state.pic_tests
    idx = st.session_state.pic_idx

    question = tests[idx]["question"]
    o_options = tests[idx]["options"]
    options = []
    for f, o in zip("ABC", o_options):
        options.append(f"{f}. {o}")

    image = Image.open(tests[idx]["image_fp"])  # type: ignore

    user_prev_answer_idx = st.session_state.user_pic_answer[idx]

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
        args=(options, idx),
    )


def check_pic_answer(container):
    score = 0
    word_results = {}
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

        user_answer_idx = st.session_state.user_pic_answer[idx]
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
        is_correct = options[user_answer_idx].strip().endswith(answer.strip())
        # 结果是单词
        word_results[answer] = is_correct
        if is_correct:
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
    d = {
        # "phone_number": st.session_state.dbi.cache["user_info"]["phone_number"],
        "item": "看图猜词",
        "level": st.session_state["pic-category"],
        "score": percentage,
        "record_time": datetime.now(timezone.utc),
        "word_results": word_results,
    }
    # st.session_state.dbi.save_daily_quiz_results(d)
    st.session_state.dbi.add_documents_to_user_history("performances", [d])


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


def get_word_test_project():
    idx = st.session_state["word-test-idx"]
    word = st.session_state["test-words"][idx]
    project = "词意测试"
    if idx == -1:
        return f"单词练习-{project}"
    else:
        return f"单词练习-{project}-{word}"


def check_word_test_answer(container, level):
    if count_non_none(st.session_state["user-answer"]) == 0:
        container.warning("您尚未答题。")
        container.stop()

    score = 0
    word_results = {}
    n = count_non_none(st.session_state["word-tests"])
    for idx, test in enumerate(st.session_state["word-tests"]):
        question = test["question"]
        options = test["options"]
        answer = test["answer"]
        explanation = test["explanation"]

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
        is_correct = is_answer_correct(user_answer_idx, answer)
        word_results[word] = is_correct
        msg = ""
        # 用户答案是选项序号，而提供的标准答案是A、B、C、D
        if is_correct:
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
    test_dict = {
        "item": "词意测试",
        "level": level,
        "score": percentage,
        "record_time": datetime.now(timezone.utc),
        # 记录单词测试情况
        "word_results": word_results,
    }
    # st.session_state.dbi.save_daily_quiz_results(test_dict)
    st.session_state.dbi.add_documents_to_user_history("performances", [test_dict])
    # container.divider()


def on_word_test_radio_change(idx, options):
    current = st.session_state["test_options"]
    # 转换为索引
    st.session_state["user-answer"][idx] = options.index(current)


def view_test_word(container):
    idx = st.session_state["word-test-idx"]
    test = st.session_state["word-tests"][idx]
    question = test["question"]
    options = test["options"]
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
    data = st.session_state.dbi.find_docs_with_category(word_lib)
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

add_exercises_to_db()

if item_menu and item_menu.endswith("闪卡记忆"):
    on_project_changed("单词练习-闪卡记忆")
    # region 侧边栏
    # 让用户选择语音风格
    pronunciation = st.sidebar.radio("发音标准", ("美式", "英式"))
    autoplay = st.sidebar.toggle(
        "自动音频", True, key="word-autoplay", help="✨ 选择是否自动播放单词音频。"
    )

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

    status_cols = st.columns(2)

    update_and_display_progress(
        (
            st.session_state["flashcard-idx"] + 1
            if st.session_state["flashcard-idx"] != -1
            else 0
        ),
        (
            len(st.session_state["flashcard-words"])
            if len(st.session_state["flashcard-words"]) != 0
            else 1
        ),
        status_cols[0],
        f'\t 当前单词：{st.session_state["flashcard-words"][st.session_state["flashcard-idx"]] if st.session_state["flashcard-idx"] != -1 else ""}',
    )

    btn_cols = st.columns(8)

    refresh_btn = btn_cols[0].button(
        "刷新[:arrows_counterclockwise:]",
        key="flashcard-refresh",
        on_click=generate_page_words,
        args=(word_lib, num_word, "flashcard-words"),
        help="✨ 点击按钮，从词库中抽取单词，重新开始闪卡记忆游戏。",
    )
    display_status_button = btn_cols[1].button(
        "切换[:recycle:]",
        key="flashcard-mask",
        help="✨ 点击按钮，可以在中英对照、只显示英文和只显示中文三种显示状态之间切换。初始状态为中英对照。",
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
        "重放[:sound:]",
        key="flashcard-play",
        help="✨ 重新播放单词发音",
        disabled=len(st.session_state["flashcard-words"]) == 0,
    )
    auto_play_btn = btn_cols[5].button(
        "轮播[:arrow_forward:]",
        key="flashcard-auto-play",
        help="✨ 单词自动轮播",
        disabled=len(st.session_state["flashcard-words"]) == 0,
    )
    add_btn = btn_cols[6].button(
        "添加[:heavy_plus_sign:]",
        key="flashcard-add",
        help="✨ 将当前单词添加到个人词库",
        disabled=st.session_state["flashcard-idx"] == -1 or "个人词库" in word_lib,  # type: ignore
    )
    del_btn = btn_cols[7].button(
        "删除[:heavy_minus_sign:]",
        key="flashcard-del",
        help="✨ 将当前单词从个人词库中删除",
        disabled=st.session_state["flashcard-idx"] == -1,
    )

    container = st.container()

    if refresh_btn:
        on_project_changed("Home")
        reset_flashcard_word(False)
        st.rerun()

    if display_status_button:
        on_project_changed("Home")
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

        on_project_changed(get_flashcard_project())

        # 添加当天学习的单词
        idx = st.session_state["flashcard-idx"]
        word = st.session_state["flashcard-words"][idx]
        st.session_state["today-learned"].add(word)

        view_flash_word(container)
        if autoplay:
            play_flashcard_word(voice_style)

    if next_btn:
        if len(st.session_state["flashcard-words"]) == 0:
            st.warning("请先点击`🔄`按钮生成记忆闪卡。")
            st.stop()

        on_project_changed(get_flashcard_project())

        # 添加当天学习的单词
        idx = st.session_state["flashcard-idx"]
        word = st.session_state["flashcard-words"][idx]
        st.session_state["today-learned"].add(word)

        view_flash_word(container)

        if autoplay:
            play_flashcard_word(voice_style)

    if play_btn:
        on_project_changed(get_flashcard_project())
        play_flashcard_word(voice_style)

    if add_btn:
        on_project_changed("Home")
        word = st.session_state["flashcard-words"][st.session_state["flashcard-idx"]]
        st.session_state.dbi.add_words_to_personal_dictionary([word])
        st.toast(f"添加单词：{word} 到个人词库。")

    if del_btn:
        on_project_changed("Home")
        word = st.session_state["flashcard-words"][st.session_state["flashcard-idx"]]
        st.session_state.dbi.remove_words_from_personal_dictionary([word])
        st.toast(f"从个人词库中删除单词：{word}。")

    if auto_play_btn:
        with container:
            auto_play_flash_word(voice_style)


# endregion

# region 单词拼图

elif item_menu and item_menu.endswith("拼图游戏"):
    on_project_changed("单词练习-单词拼图")
    # region 边栏
    # include_cb = st.sidebar.checkbox(
    #     "是否包含个人词库？",
    #     key="include-personal-dictionary",
    #     value=False,
    #     on_change=on_include_cb_change,
    # )
    # 在侧边栏添加一个选项卡让用户选择一个单词列表
    # word_lib = st.sidebar.selectbox(
    #     "词库",
    #     sorted(list(st.session_state.word_dict.keys())),
    #     key="puzzle-selected",
    #     on_change=reset_puzzle_word,
    #     format_func=word_lib_format_func,
    #     help="✨ 选择一个词库，用于生成单词拼图。",
    # )

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
        "✨ 单词拼图是一种寓教于乐的语言学习工具，它要求玩家根据乱序的字母和相关提示，拼凑出正确的单词。这种游戏的单词来源于当天所学的词汇，旨在通过重复和实践来加深记忆。通过这种方式，玩家可以在提升词汇量、拼写技巧的同时，也锻炼了他们的问题解决能力。参考：[Cambridge Dictionary](https://dictionary.cambridge.org/)"
    )

    update_and_display_progress(
        (
            st.session_state["puzzle-idx"] + 1
            if st.session_state["puzzle-idx"] != -1
            else 0
        ),
        (
            len(st.session_state["puzzle-words"])
            if len(st.session_state["puzzle-words"]) != 0
            else 1
        ),
        st.empty(),
    )

    puzzle_cols = st.columns(8)
    puzzle_container = st.container()
    refresh_btn = puzzle_cols[0].button(
        "刷新[:arrows_counterclockwise:]",
        key="puzzle-refresh",
        help="✨ 点击按钮，将从词库中抽取单词，开始或重新开始单词拼图游戏。",
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
    chk_btn = puzzle_cols[3].button(
        "检查[:mag:]",
        help="✨ 点击按钮，检查您的答案是否正确。",
        disabled=st.session_state["puzzle-idx"] == -1,
    )
    add_btn = puzzle_cols[4].button(
        "添加[:heavy_plus_sign:]",
        key="puzzle-add",
        help="✨ 将当前单词添加到个人词库",
        disabled=st.session_state["puzzle-idx"] == -1,  # type: ignore
    )
    del_btn = puzzle_cols[5].button(
        "删除[:heavy_minus_sign:]",
        key="puzzle-del",
        help="✨ 将当前单词从个人词库中删除",
        disabled=st.session_state["puzzle-idx"] == -1,
    )

    if refresh_btn:
        on_project_changed("Home")
        generate_page_words(None, num_word, "puzzle-words", True, True)
        reset_puzzle_word()
        st.rerun()

    if prev_btn:
        prepare_puzzle()
        on_project_changed(get_puzzle_project())

    if next_btn:
        prepare_puzzle()
        on_project_changed(get_puzzle_project())

    if chk_btn:
        on_project_changed("Home")
        check_puzzle(puzzle_container)

    if add_btn:
        on_project_changed("Home")
        word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
        st.session_state.dbi.add_words_to_personal_dictionary([word])
        st.toast(f"添加单词：{word} 到个人词库。")

    if del_btn:
        on_project_changed("Home")
        word = st.session_state["puzzle-words"][st.session_state["puzzle-idx"]]
        st.session_state.dbi.remove_words_from_personal_dictionary([word])
        st.toast(f"从个人词库中删除单词：{word}。")

    if st.session_state["puzzle-idx"] != -1:
        on_project_changed(get_puzzle_project())
        handle_puzzle()

# endregion

# region 图片测词

elif item_menu and item_menu.endswith("看图猜词"):
    on_project_changed("单词练习-看图猜词")
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

    container = st.container()

    if refresh_btn:
        on_project_changed("Home")
        n = len(st.session_state.pic_tests)
        st.session_state.user_pic_answer = [None] * n

    if sumbit_pic_btn:
        on_project_changed("单词练习-看图猜词-检查答案")
        if count_non_none(st.session_state.user_pic_answer) == 0:
            st.warning("您尚未答题。")
            st.stop()
        container.empty()
        if count_non_none(st.session_state.user_pic_answer) != count_non_none(
            st.session_state.pic_tests
        ):
            container.warning("您尚未完成全部测试题目。")
        check_pic_answer(container)
    elif st.session_state.pic_idx != -1:
        idx = st.session_state.pic_idx
        answer = st.session_state.pic_tests[idx]["answer"]
        on_project_changed(f"单词练习-看图猜词-{answer}")
        view_pic_question(container)


# endregion

# region 词意测试

elif item_menu and item_menu.endswith("词意测试"):
    on_project_changed("单词练习-词意测试")
    update_sidebar_status(sidebar_status)
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
    st.markdown(
        """✨ 英语单词理解测试是一种选择题形式的测试，提供一个英语单词和四个选项，要求选出正确的词义。"""
    )

    if "text-model" not in st.session_state:
        st.session_state["text-model"] = load_vertex_model("gemini-pro")

    cols = st.columns(2)
    update_and_display_progress(
        (
            st.session_state["word-test-idx"] + 1
            if st.session_state["word-test-idx"] != -1
            else 0
        ),
        (
            len(st.session_state["test-words"])
            if len(st.session_state["test-words"]) != 0
            else 1
        ),
        cols[0].empty(),
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
        or st.session_state["word-test-idx"] != len(st.session_state["word-tests"]) - 1,
        help="✨ 只有在完成最后一道测试题后，才可以点击按钮提交，显示测验得分。",
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
        on_project_changed(get_word_test_project())

    if next_test_btn:
        on_project_changed(get_word_test_project())
        logger.info(st.session_state["test-words"])

    if refresh_btn:
        on_project_changed("Home")
        reset_test_words()
        st.session_state["user-answer"] = [None] * test_num  # type: ignore
        generate_page_words(word_lib, test_num, "test-words", True, True)
        st.session_state["word-tests"] = generate_word_tests_for(
            st.session_state["test-words"], level
        )
        st.rerun()

    if (
        st.session_state["word-test-idx"] != -1
        and len(st.session_state["word-tests"]) >= 1
        and not sumbit_test_btn
    ):
        on_project_changed(get_word_test_project())
        view_test_word(container)

    if sumbit_test_btn:
        on_project_changed(get_word_test_project())
        container.empty()
        if count_non_none(st.session_state["user-answer"]) != count_non_none(
            st.session_state["word-tests"]
        ):
            container.warning("您尚未完成测试。")
        check_word_test_answer(container, level)

    if add_btn:
        on_project_changed("Home")
        word = st.session_state["test-words"][st.session_state["word-test-idx"]]
        st.session_state.dbi.add_words_to_personal_dictionary([word])
        st.toast(f"添加单词：{word} 到个人词库。")

    if del_btn:
        on_project_changed("Home")
        word = st.session_state["test-words"][st.session_state["word-test-idx"]]
        st.session_state.dbi.remove_words_from_personal_dictionary([word])
        st.toast(f"从个人词库中删除单词：{word}。")

# endregion

# region 个人词库

elif item_menu and item_menu.endswith("词库管理"):
    on_project_changed("Home")
    # 基准词库不包含个人词库
    add_personal_dictionary(False)
    word_lib = st.sidebar.selectbox(
        "词库",
        sorted(list(st.session_state.word_dict.keys())),
        index=0,
        key="lib-selected",
        format_func=word_lib_format_func,
        help="✨ 选择一个基准词库，用于生成个人词库。",
    )  # type: ignore

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

    view_selected_list = word_lib.split("-", 1)[1]
    base_placeholder.text(f"基础词库({view_selected_list})")

    base_lib_df = gen_base_lib(view_selected_list)

    lib_df = get_my_word_lib()

    mylib_placeholder.text(
        f"可删列表（{0 if lib_df.empty else lib_df.shape[0]}） 个单词",
        help="在这里删除你的个人词库中的单词（显示的是最近10分钟的缓存数据）",
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
            # logger.info(f"已添加到个人词库中：{to_add}。")

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
            # logger.info(f"从个人词库中已经删除：{to_del}。")

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
