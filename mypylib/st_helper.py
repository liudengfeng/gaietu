import logging
import random
import re
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import List

import azure.cognitiveservices.speech as speechsdk
import pytz
import streamlit as st
import streamlit.components.v1 as components
import vertexai
from azure.cognitiveservices.speech import (
    ResultReason,
    SpeechSynthesisCancellationDetails,
)

# from annotated_text import annotated_text, annotation
from azure.storage.blob import BlobServiceClient
from google.cloud import firestore, translate
from google.oauth2.service_account import Credentials
from vertexai.preview.generative_models import GenerativeModel, Image

from mypylib.constants import USD_TO_CNY_EXCHANGE_RATE
from mypylib.utils import calculate_audio_duration

from .azure_pronunciation_assessment import (
    get_syllable_durations_and_offsets,
    pronunciation_assessment_from_stream,
)
from .azure_speech import synthesize_speech
from .db_interface import DbInterface
from .google_ai import MAX_CALLS, PER_SECONDS, ModelRateLimiter
from .google_cloud_configuration import (
    LOCATION,
    PROJECT_ID,
    get_google_service_account_info,
    google_configure,
)
from .html_constants import TIPPY_JS
from .html_fmt import pronunciation_assessment_word_format
from .word_utils import (
    audio_autoplay_elem,
    get_mini_dict,
    get_word_image_urls,
    load_image_bytes_from_url,
)

logger = logging.getLogger("streamlit")

# 发音评估(韵律、语法、词汇、主题)
RATE_PER_HOUR = 0.3
# 实时和批处理合成: $15/每 100 万 字符
# 长音频制作： 每 100 万个字符 $100
MIN_RATE_PER_MILLION_CHARS = 15
MAX_RATE_PER_MILLION_CHARS = 100
# Google 翻译费率 per million characters
RATE_PER_MILLION_CHARS = 25

TOEKN_HELP_INFO = (
    "✨ 对于 Gemini 模型，一个令牌约相当于 4 个字符。100 个词元约为 60-80 个英语单词。"
)

# region 通用函数


def setup_logger(logger, level="INFO"):
    # 设置日志的时间戳为 Asia/Shanghai 时区
    formatter = logging.Formatter("%(asctime)s - %(message)s")
    formatter.converter = lambda *args: datetime.now(
        tz=pytz.timezone("Asia/Shanghai")
    ).timetuple()
    for handler in logger.handlers:
        handler.setFormatter(formatter)
        handler.setLevel(logging.getLevelName(level))


setup_logger(logger)


def count_non_none(lst):
    return len(list(filter(lambda x: x is not None, lst)))


def is_answer_correct(user_answer, standard_answer):
    # 如果用户没有选择答案，直接返回 False
    if user_answer is None:
        return False

    # 创建一个字典，将选项序号映射到字母
    answer_dict = {0: "A", 1: "B", 2: "C", 3: "D"}

    # 检查用户答案是否是一个整数
    if isinstance(user_answer, int):
        # 获取用户的答案对应的字母
        user_answer = answer_dict.get(user_answer, "")
    else:
        # 移除用户答案中的非字母字符，并只取第一个字符
        user_answer = "".join(filter(str.isalpha, user_answer))[0]

    # 移除标准答案中的非字母字符，并只取第一个字符
    standard_answer = "".join(filter(str.isalpha, standard_answer))[0]

    # 比较用户的答案和标准答案
    return user_answer == standard_answer


# endregion

# region 时间相关


def get_current_monday():
    """
    使用会话缓存的用户时区信息，返回当前日期的周一日期。

    Returns:
        datetime.date: 当前日期的周一日期。
    """
    # 获取用户时区
    user_timezone = st.session_state.dbi.cache["user_info"]["timezone"]

    # 获取当前日期和时间
    now = datetime.now(pytz.timezone(user_timezone))

    # 获取今天是周几（0 是周一，6 是周日）
    weekday = now.weekday()

    # 获取当前周的周一
    monday = now.date() - timedelta(days=weekday)

    return monday


# endregion

# region 用户相关


def check_access(is_admin_page):
    if "dbi" not in st.session_state:
        st.session_state["dbi"] = DbInterface(get_firestore_client())

    if not st.session_state.dbi.is_logged_in():
        st.error("您尚未登录。请点击屏幕左侧 🏠 主页 菜单进行登录。")
        st.stop()

    if (
        is_admin_page
        and st.session_state.dbi.cache.get("user_info", {}).get("user_role") != "管理员"
    ):
        st.error("您没有权限访问此页面。此页面仅供系统管理员使用。")
        st.stop()


# endregion

# region Google


@st.cache_resource
def get_translation_client():
    service_account_info = get_google_service_account_info(st.secrets)
    # 创建凭据
    credentials = Credentials.from_service_account_info(service_account_info)
    # 使用凭据初始化客户端
    return translate.TranslationServiceClient(credentials=credentials)


@st.cache_resource
def get_firestore_client():
    service_account_info = get_google_service_account_info(st.secrets)
    # 创建凭据
    credentials = Credentials.from_service_account_info(service_account_info)
    # 使用凭据初始化客户端
    return firestore.Client(credentials=credentials, project=PROJECT_ID)


def configure_google_apis():
    # 配置 AI 服务
    if st.secrets["env"] in ["streamlit", "azure"]:
        if "inited_google_ai" not in st.session_state:
            google_configure(st.secrets)
            # vertexai.init(project=PROJECT_ID, location=LOCATION)
            st.session_state["inited_google_ai"] = True

        if "rate_limiter" not in st.session_state:
            st.session_state.rate_limiter = ModelRateLimiter(MAX_CALLS, PER_SECONDS)

        if "google_translate_client" not in st.session_state:
            st.session_state["google_translate_client"] = get_translation_client()

        # 配置 token 计数器
        if "current_token_count" not in st.session_state:
            st.session_state["current_token_count"] = 0

        if "total_token_count" not in st.session_state:
            st.session_state["total_token_count"] = (
                st.session_state.dbi.get_token_count()
            )
    else:
        st.warning("非云端环境，无法使用 Google AI", icon="⚠️")


def google_translate(
    item_name, text, target_language_code: str = "zh-CN", is_list: bool = False
):
    """Translating Text."""
    # Cloud Translation 会按字符数统计用量，即使一个字符为多字节也是如此。空白字符也需要付费。
    # LLM $25 per million characters $20 per million characters
    if is_list:
        if not isinstance(text, list):
            raise ValueError("Expected a list of strings, but got a single string.")
        if not all(isinstance(i, str) for i in text):
            raise ValueError("All elements in the list should be strings.")
    else:
        if not isinstance(text, str):
            raise ValueError("Expected a string, but got a different type.")

    if not text or text == "":
        return text  # type: ignore

    # 计算字符数
    char_count = len("".join(text)) if is_list else len(text)
    # 计算费用
    cost = (char_count / 1000000) * RATE_PER_MILLION_CHARS * USD_TO_CNY_EXCHANGE_RATE

    # Location must be 'us-central1' or 'global'.
    parent = f"projects/{PROJECT_ID}/locations/global"

    client = st.session_state.google_translate_client
    # Detail on supported types can be found here:
    # https://cloud.google.com/translate/docs/supported-formats
    response = client.translate_text(
        request={
            "parent": parent,
            "contents": text if is_list else [text],
            "mime_type": "text/plain",  # mime types: text/plain, text/html
            "source_language_code": "en-US",
            "target_language_code": target_language_code,
        }
    )

    res = []
    # Display the translation for each input text provided
    for translation in response.translations:
        res.append(translation.translated_text.encode("utf8").decode("utf8"))
    # google translate api 返回一个结果
    usage = {
        "service_name": "Google 翻译",
        "char_count": char_count,
        "cost": cost,
        "item_name": item_name,
        "timestamp": datetime.now(pytz.UTC),
    }
    st.session_state.dbi.add_usage_to_cache(usage)
    # logger.info(f"翻译费用：{cost:.4f}元，字符数：{char_count}")
    return res if is_list else res[0]


@st.cache_data(ttl=60 * 60 * 24)  # 缓存有效期为24小时
def translate_text(item_name, text: str, target_language_code, is_list: bool = False):
    return google_translate(item_name, text, target_language_code, is_list)


# endregion


# region Azure
@st.cache_resource
def get_blob_service_client():
    # container_name = "word-images"
    connect_str = st.secrets["Microsoft"]["AZURE_STORAGE_CONNECTION_STRING"]
    # 创建 BlobServiceClient 对象
    return BlobServiceClient.from_connection_string(connect_str)


@st.cache_resource
def get_blob_container_client(container_name):
    # 创建 BlobServiceClient 对象
    blob_service_client = get_blob_service_client()
    # 获取 ContainerClient 对象
    return blob_service_client.get_container_client(container_name)


# endregion

# region 播放显示


def format_token_count(count):
    if count >= 1000000000:
        return f"{count / 1000000000:.2f}B"
    elif count >= 1000000:
        return f"{count / 1000000:.2f}M"
    elif count >= 1000:
        return f"{count / 1000:.2f}K"
    else:
        return str(count)


def update_and_display_progress(
    current_value: int, total_value: int, progress_bar, message=""
):
    """
    更新并显示进度条。

    Args:
        current_value (int): 当前值。
        total_value (int): 总值。
        progress_bar: Streamlit progress bar object.

    Returns:
        None
    """
    # 计算进度
    progress = current_value / total_value

    # 显示进度百分比
    text = f"{progress:.2%} {message}"

    # 更新进度条的值
    progress_bar.progress(progress, text)


def view_md_badges(
    container, d: dict, badge_maps: OrderedDict, decimal_places: int = 2
):
    cols = container.columns(len(badge_maps.keys()))
    for i, t in enumerate(badge_maps.keys()):
        n = d.get(t, None)
        if n is None:
            num = "0"
        elif isinstance(n, int):
            num = f"{n:3d}"
        elif isinstance(n, float):
            num = f"{n:.{decimal_places}f}"
        else:
            num = n
        body = f"""{badge_maps[t][1]}[{num}]"""
        cols[i].markdown(
            f""":{badge_maps[t][0]}[{body}]""",
            help=f"✨ {badge_maps[t][2]}",
        )


def autoplay_audio_and_display_text(
    elem, audio_bytes: bytes, words: List[speechsdk.PronunciationAssessmentWordResult]
):
    """
    自动播放音频并显示文本。

    Args:
        elem: 显示文本的元素。
        audio_bytes: 音频文件的字节数据。
        words: 包含发音评估单词结果的列表。

    Returns:
        None
    """
    auto_html = audio_autoplay_elem(audio_bytes, fmt="wav")
    components.html(auto_html)

    start_time = time.perf_counter()
    for i, (accumulated_text, duration, offset, _) in enumerate(
        get_syllable_durations_and_offsets(words)
    ):
        elem.markdown(accumulated_text + "▌")
        time.sleep(duration)
        while time.perf_counter() - start_time < offset:
            time.sleep(0.01)
    elem.markdown(accumulated_text)
    # time.sleep(1)
    # st.rerun()


def update_sidebar_status(sidebar_status):
    sidebar_status.markdown(
        f"""令牌：{st.session_state.current_token_count} 累计：{format_token_count(st.session_state.total_token_count)}""",
        help=TOEKN_HELP_INFO,
    )


# endregion

# region 单词与发音评估

WORD_COUNT_BADGE_MAPS = OrderedDict(
    {
        "单词总量": ("green", "单词总量", "文本中不重复的单词数量", "success"),
        "A1": ("orange", "A1", "CEFR A1 单词数量", "warning"),
        "A2": ("grey", "A2", "CEFR A1 单词数量", "secondary"),
        "B1": ("red", "B1", "CEFR B1 单词数量", "danger"),
        "B2": ("violet", "B2", "CEFR B2 单词数量", "info"),
        "C1": ("blue", "C1", "CEFR C1 单词数量", "light"),
        "C2": ("rainbow", "C2", "CEFR C2 单词数量", "dark"),
        "未分级": ("green", "未分级", "未分级单词数量", "dark"),
    }
)

PRONUNCIATION_SCORE_BADGE_MAPS = OrderedDict(
    {
        "pronunciation_score": (
            "green",
            "综合评分",
            "表示给定语音发音质量的总体分数。这是由 AccuracyScore、FluencyScore、CompletenessScore (如果适用)、ProsodyScore (如果适用)加权聚合而成。",
            "success",
        ),
        "accuracy_score": (
            "orange",
            "准确性评分",
            "语音的发音准确性。准确性表示音素与母语说话人的发音的匹配程度。字词和全文的准确性得分是由音素级的准确度得分汇总而来。",
            "warning",
        ),
        "fluency_score": (
            "grey",
            "流畅性评分",
            "给定语音的流畅性。流畅性表示语音与母语说话人在单词间的停顿上有多接近。",
            "secondary",
        ),
        "completeness_score": (
            "red",
            "完整性评分",
            "语音的完整性，按发音单词与输入引用文本的比率计算。",
            "danger",
        ),
        "prosody_score": (
            "rainbow",
            "韵律评分",
            "给定语音的韵律。韵律指示给定语音的性质，包括重音、语调、语速和节奏。",
            "info",
        ),
    }
)

ORAL_ABILITY_SCORE_BADGE_MAPS = OrderedDict(
    {
        "content_score": (
            "green",
            "口语能力",
            "表示学生口语能力的总体分数。由词汇得分、语法得分和主题得分的简单平均得出。"
            "success",
        ),
        "vocabulary_score": (
            "rainbow",
            "词汇分数",
            "词汇运用能力的熟练程度是通过说话者有效地使用单词来评估的，即在特定语境中使用某单词以表达观点是否恰当。",
            "warning",
        ),
        "grammar_score": (
            "blue",
            "语法分数",
            "正确使用语法的熟练程度。语法错误是通过将适当的语法使用水平与词汇结合进行评估的。",
            "secondary",
        ),
        "topic_score": (
            "orange",
            "主题分数",
            "对主题的理解和参与程度，它提供有关说话人有效表达其思考和想法的能力以及参与主题的能力的见解。",
            "danger",
        ),
    }
)


# 判断是否为旁白
def is_aside(text):
    return re.match(r"^\(.*\)$", text) is not None


@st.cache_data(max_entries=10000, ttl=60 * 60 * 24, show_spinner=False)
def get_synthesis_speech(text, voice):
    # 首先处理text，删除text中的空白行
    text = re.sub("\n\\s*\n*", "\n", text)
    is_free = True
    try:
        result = synthesize_speech(
            text,
            st.secrets["Microsoft"]["F0_SPEECH_KEY"],
            st.secrets["Microsoft"]["F0_SPEECH_REGION"],
            voice,
        )
        if result.reason == ResultReason.Canceled:
            cancellation_details = SpeechSynthesisCancellationDetails(result)
            logger.error(f"Speech synthesis canceled: {cancellation_details.reason}")
            logger.error(f"Error details: {cancellation_details.error_details}")
    except Exception as e:
        is_free = False
        result = synthesize_speech(
            text,
            st.secrets["Microsoft"]["SPEECH_KEY"],
            st.secrets["Microsoft"]["SPEECH_REGION"],
            voice,
        )

    if is_free:
        cost0 = 0.0
        cost1 = 0.0
    else:
        cost0 = (
            (len(text) / 1000000)
            * MIN_RATE_PER_MILLION_CHARS
            * USD_TO_CNY_EXCHANGE_RATE
        )
        cost1 = (
            (len(text) / 1000000)
            * MAX_RATE_PER_MILLION_CHARS
            * USD_TO_CNY_EXCHANGE_RATE
        )

    # 实时和批处理合成: $15/每 100 万 字符
    # 长音频制作： 每 100 万个字符 $100
    char_count = len(text)
    cost = (
        (char_count / 1000000) * MAX_RATE_PER_MILLION_CHARS * USD_TO_CNY_EXCHANGE_RATE
    )
    usage = {
        "service_name": "微软语音服务",
        "char_count": char_count,
        "cost": cost,
        "cost0": cost0,
        "cost1": cost1,
        "item_name": "语音合成",
        "timestamp": datetime.now(pytz.UTC),
    }
    st.session_state.dbi.add_usage_to_cache(usage)
    # logger.info(f"语音合成费用：{cost:.4f}元，字符数：{char_count}")
    # free_flag = "免费" if is_free else "付费"
    # logger.info(
    #     f"语音合成费用：{cost0:.4f}元，字符数：{char_count}，是否免费：{free_flag}，费用1：{cost1:.4f}元"
    # )
    return {"audio_data": result.audio_data, "audio_duration": result.audio_duration}


@st.cache_resource
def load_mini_dict():
    return get_mini_dict()


@st.cache_resource(
    show_spinner="提取简版词典单词信息...", ttl=60 * 60 * 24
)  # 缓存有效期为24小时
def get_mini_dict_doc(word):
    w = word.replace("/", " or ")
    mini_dict = load_mini_dict()
    return mini_dict.get(w, {})


@st.cache_data(
    ttl=timedelta(hours=24), max_entries=10000, show_spinner="获取单词图片网址..."
)
def select_word_image_urls(word: str):
    mini_dict_doc = get_mini_dict_doc(word)
    return mini_dict_doc.get("image_urls", [])


def pronunciation_assessment_with_cost(
    audio_info: dict, topic: str, reference_text: str
):
    # $0.30 /小时/功能
    duration = calculate_audio_duration(
        audio_info["bytes"], audio_info["sample_rate"], audio_info["sample_width"]
    )
    cost = (duration / 3600) * RATE_PER_HOUR * USD_TO_CNY_EXCHANGE_RATE
    is_oral = topic is not None
    usage = {
        "service_name": "微软语音服务",
        "item_name": "口语能力评估" if is_oral else "发音评估",
        "duration": duration,
        "cost": cost,
        "timestamp": datetime.now(pytz.UTC),
    }
    st.session_state.dbi.add_usage_to_cache(usage)
    # logger.info(f"发音评估费用：{cost:.4f}元，时长：{duration:.2f}秒")
    return pronunciation_assessment_from_stream(
        audio_info, st.secrets, topic, reference_text
    )


@st.cache_data(ttl=60 * 60 * 24, show_spinner="正在进行发音评估，请稍候...")
def pronunciation_assessment_for(audio_info: dict, reference_text: str):
    return pronunciation_assessment_with_cost(audio_info, None, reference_text)


@st.cache_data(ttl=60 * 60 * 24, show_spinner="正在进行口语能力评估，请稍候...")
def oral_ability_assessment_for(audio_info: dict, topic: str):
    return pronunciation_assessment_with_cost(audio_info, topic, None)


def display_assessment_score(
    container, maps, assessment_key, score_key="pronunciation_result", idx=None
):
    """
    Display the assessment score for a given assessment key.

    Parameters:
    container (object): The container object to display the score.
    maps (dict): A dictionary containing mappings for the score.
    assessment_key (str): The key to retrieve the assessment from st.session_state.
    score_key (str, optional): The key to retrieve the score from the assessment. Defaults to "pronunciation_result".
    """
    if assessment_key not in st.session_state:
        return
    d = st.session_state[assessment_key]
    if idx is not None:
        result = d.get(idx, {}).get(score_key, {})
    else:
        result = d.get(score_key, {})
    if not result:
        return
    view_md_badges(container, result, maps, 0)


def process_dialogue_text(reference_text):
    # 去掉加黑等标注
    reference_text = reference_text.replace("**", "")
    # 去掉对话者名字
    reference_text = re.sub(r"^\w+(\s\w+)*:\s", "", reference_text, flags=re.MULTILINE)
    # 去掉空行
    reference_text = re.sub("\n\\s*\n*", "\n", reference_text)
    return reference_text.strip()


# def pronunciation_assessment_word_format(word):
#     error_type = word.error_type
#     accuracy_score = round(word.accuracy_score)
#     if error_type == "Mispronunciation":
#         return annotation(word.word, label=str(accuracy_score), background="#d5d507ce")
#     if error_type == "Omission":
#         return annotation(f"[{word.word}]", color="white", background="#4a4943b7")
#     if error_type == "Insertion":
#         return annotation(word.word, border="2px dashed red")
#     if word.is_unexpected_break:
#         return annotation(
#             f"{word.word}", label=str(accuracy_score), background="#FFC0CB"
#         )
#     if word.is_missing_break:
#         return annotation(
#             f"{word.word}", label=str(accuracy_score), background="#f2f2f2"
#         )
#     if word.is_monotone:
#         return annotation(
#             f"{word.word}",
#             color="white",
#             label=str(accuracy_score),
#             background="#ac1882ce",
#         )
#     return f"{word.word}"


# def view_word_assessment(words):
#     res = []
#     for word in words:
#         if isinstance(word, str):
#             res.append(word)
#         else:
#             res.append(pronunciation_assessment_word_format(word))
#         res.append(" ")
#     annotated_text(*res)


def view_word_assessment(words):
    result = ""
    for word in words:
        result += pronunciation_assessment_word_format(word)
    st.markdown(result + TIPPY_JS, unsafe_allow_html=True)


def _word_to_text(word):
    error_type = word.error_type
    accuracy_score = round(word.accuracy_score)
    if error_type == "Mispronunciation":
        return f"{word.word} | {accuracy_score}"
    if error_type == "Omission":
        return f"[{word.word}]"
    if error_type == "Insertion":
        return f"{word.word}"
    if word.is_unexpected_break:
        return f"{word.word} | {accuracy_score}"
    if word.is_missing_break:
        return f"{word.word} | {accuracy_score}"
    if word.is_monotone:
        return f"{word.word} | {accuracy_score}"
    return f"{word.word}"


# TODO:废弃或使用 单词数量调整
def left_paragraph_aligned_text(text1, words):
    """
    将文本1的每个段落首行与words首行对齐（为文本1补齐空行）。

    Args:
        text1 (str): 原始文本。
        words (list): 要插入文本中的单词列表。

    Returns:
        str: 处理后的文本。
    """

    # 将文本1分割成段落
    paragraphs1 = text1.split("\n\n")

    if len(words) == 0:
        return paragraphs1

    # 处理单词
    res = []
    for word in words:
        if isinstance(word, str):
            res.append(word)
        else:
            res.append(_word_to_text(word))
        res.append(" ")
    text2 = "".join(res)

    # 将文本2分割成段落
    paragraphs2 = text2.split("\n\n")

    # 计算每个段落的行数
    lines1 = [len(p.split("\n")) for p in paragraphs1]
    lines2 = [len(p.split("\n")) for p in paragraphs2]

    # 添加空白行
    for i in range(min(len(lines1), len(lines2))):
        diff = lines2[i] - lines1[i]
        if diff > 0:
            paragraphs1[i] += "\n" * diff

    return paragraphs1


# endregion

# region 学习记录


def process_learning_record(record, key):
    if len(st.session_state["learning-record"]) > 0:
        st.session_state["learning-record"][-1].end()

    st.session_state["learning-record"].append(record)
    record.start()
    st.session_state[key] += 1


def end_and_save_learning_records():
    """
    结束并保存学习记录。

    关闭未关闭的学习记录，并将其添加到缓存中。
    """
    for r in st.session_state.get("learning-record", []):
        # logger.info(f"关闭：{r.project} {r.content}")
        r.end()
        st.session_state.dbi.add_record_to_cache(r)
    st.session_state["learning-record"] = []


# def on_project_changed(this_page: str = ""):
#     """
#     检查页面是否发生变化，如果发生变化，保存并清除所有学习记录。
#     """
#     # 在会话状态中设置上一页
#     if "previous-page" not in st.session_state:
#         st.session_state["previous-page"] = None

#     if "current-page" not in st.session_state:
#         st.session_state["current-page"] = None

#     if "learning-record" not in st.session_state:
#         st.session_state["learning-record"] = []

#     # 如果当前页和上一页不同，保存上一页的学习时长
#     if st.session_state["current-page"] != this_page:
#         if st.session_state["previous-page"] is not None:
#             # 当转移页面时，关闭未关闭的学习记录
#             end_and_save_learning_records()

#         # 更新上一页为当前页
#         st.session_state["previous-page"] = st.session_state["current-page"]

#     st.session_state["current-page"] = this_page

#     # logger.info(
#     #     f"上一页：{st.session_state['previous-page']} 当前页：{st.session_state['current-page']}"
#     # )


# endregion


# region 个人记录


def end_and_save_exercises():
    """
    结束并保存学习记录。

    关闭未关闭的学习记录，并将其添加到缓存中。
    """
    key = "exercises"
    for r in st.session_state.get(key, []):
        # logger.info(f"关闭：{r.project} {r.content}")
        r.end()
        st.session_state.dbi.add_to_dbcache(r)
    st.session_state[key] = []


def start_project(project_name):
    # 记录项目开始的时间
    st.session_state["project-timer"][project_name] = {"start_time": datetime.now()}


def end_project(project_name):
    # 记录项目结束的时间
    end_time = datetime.now()
    st.session_state["project-timer"][project_name]["end_time"] = end_time

    # 计算项目的持续时间
    start_time = st.session_state["project-timer"][project_name]["start_time"]
    duration = end_time - start_time

    # 如果项目已经有持续时间，那么将新的持续时间添加到旧的持续时间上
    if "duration" in st.session_state["project-timer"][project_name]:
        st.session_state["project-timer"][project_name]["duration"] += duration
    else:
        st.session_state["project-timer"][project_name]["duration"] = duration


def on_project_changed(new_project: str = ""):
    """
    检查项目是否发生变化，如果发生变化，结束当前项目并开始新的项目。
    """
    if "project-timer" not in st.session_state:
        st.session_state["project-timer"] = {}

    timer = st.session_state["project-timer"]
    if "current_project" in st.session_state and st.session_state["current_project"] in timer:
        # 结束当前项目
        end_project(st.session_state["current_project"])

    # 开始新的项目
    start_project(new_project)

    # 更新当前项目
    st.session_state["current_project"] = new_project

    logger.info(f"{timer}")


# endregion
