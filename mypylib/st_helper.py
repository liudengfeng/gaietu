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
from annotated_text import annotated_text, annotation
from azure.storage.blob import BlobServiceClient
from google.cloud import firestore, translate
from google.oauth2.service_account import Credentials
from vertexai.preview.generative_models import GenerativeModel, Image

from .azure_pronunciation_assessment import (
    get_syllable_durations_and_offsets,
    pronunciation_assessment_from_stream,
)
from .azure_speech import synthesize_speech
from .db_interface import DbInterface
from .google_ai import (
    MAX_CALLS,
    PER_SECONDS,
    ModelRateLimiter,
    load_vertex_model,
    select_best_images_for_word,
)
from .google_cloud_configuration import (
    LOCATION,
    PROJECT_ID,
    get_google_service_account_info,
    google_configure,
)
from .word_utils import (
    audio_autoplay_elem,
    get_mini_dict,
    get_word_image_urls,
    load_image_bytes_from_url,
)

logger = logging.getLogger("streamlit")


TOEKN_HELP_INFO = "✨ 对于 Gemini 模型，一个令牌约相当于 4 个字符。100 个词元约为 60-80 个英语单词。"


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


def check_and_force_logout(status):
    """
    检查并强制退出用户重复登录。

    Args:
        st (object): Streamlit 模块。
        status (object): Streamlit 状态元素，用于显示错误信息。

    Returns:
        None
    """
    if "session_id" in st.session_state.dbi.cache.get("user_info", {}):
        dbi = st.session_state.dbi
        # 存在会话id，说明用户已经登录
        phone_number = dbi.cache["user_info"]["phone_number"]
        # 获取除最后一个登录事件外的所有未退出的登录事件
        active_sessions = dbi.get_active_sessions()
        for session in active_sessions:
            if session["session_id"] == dbi.cache.get("user_info", {}).get(
                "session_id", ""
            ):
                # 如果 st.session_state 中的会话ID在需要强制退出的列表中，处理强制退出
                dbi.force_logout_session(phone_number, session["session_id"])
                st.session_state.clear()
                status.error("您的账号在其他设备上登录，您已被强制退出。")
                st.stop()


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


def check_access(is_admin_page):
    if "dbi" not in st.session_state:
        st.session_state["dbi"] = DbInterface(get_firestore_client())

    if not st.session_state.dbi.is_logged_in():
        st.error("您尚未登录。请点击屏幕左侧的 `Home` 菜单进行登录。")
        st.stop()

    if (
        is_admin_page
        and st.session_state.dbi.cache.get("user_info", {}).get("user_role") != "管理员"
    ):
        st.error("您没有权限访问此页面。此页面仅供系统管理员使用。")
        st.stop()


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
            st.session_state[
                "total_token_count"
            ] = st.session_state.dbi.get_token_count()
    else:
        st.warning("非云端环境，无法使用 Google AI", icon="⚠️")


def google_translate(text, target_language_code: str = "zh-CN", is_list: bool = False):
    """Translating Text."""
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
    return res if is_list else res[0]


@st.cache_data(ttl=60 * 60 * 24)  # 缓存有效期为24小时
def translate_text(text: str, target_language_code, is_list: bool = False):
    return google_translate(text, target_language_code, is_list)


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


def view_stream_response(responses, placeholder):
    """
    Concatenates the text from the given responses and displays it in a placeholder.

    Args:
        responses (list): A list of response chunks.
        placeholder: The placeholder where the concatenated text will be displayed.
    """
    full_response = ""
    for chunk in responses:
        try:
            full_response += chunk.text
        except (IndexError, ValueError) as e:
            st.write(chunk)
            st.error(e)
            # pass
        time.sleep(0.05)
        # Add a blinking cursor to simulate typing
        placeholder.markdown(full_response + "▌")
    placeholder.markdown(full_response)


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

    # 播放音频
    auto_html = audio_autoplay_elem(audio_bytes, fmt="wav")
    components.html(auto_html)

    for (
        accumulated_text,
        duration,
        _,
        _,
    ) in get_syllable_durations_and_offsets(words):
        # 更新文本
        elem.markdown(accumulated_text + "▌")
        # # 暂停一会儿，以便我们可以看到文本的动态更新
        # sleep_duration = offset - previous_offset
        # time.sleep(sleep_duration)  # 暂停的时间等于当前偏移量和上一次偏移量的差值
        # previous_offset = offset
        time.sleep(duration)  # 暂停的时间等于当前音节的持续时间

    elem.markdown(accumulated_text)
    st.rerun()


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
        "completeness_score": ("red", "完整性评分", "语音的完整性，按发音单词与输入引用文本的比率计算。", "danger"),
        "prosody_score": (
            "rainbow",
            "韵律评分",
            "给定语音的韵律。韵律指示给定语音的性质，包括重音、语调、语速和节奏。",
            "info",
        ),
    }
)


# 判断是否为旁白
def is_aside(text):
    return re.match(r"^\(.*\)$", text) is not None


@st.cache_data(max_entries=10000, ttl=60 * 60 * 24, show_spinner=False)
def get_synthesis_speech(text, voice):
    result = synthesize_speech(
        text,
        st.secrets["Microsoft"]["SPEECH_KEY"],
        st.secrets["Microsoft"]["SPEECH_REGION"],
        voice,
    )
    return {"audio_data": result.audio_data, "audio_duration": result.audio_duration}


@st.cache_resource
def load_mini_dict():
    return get_mini_dict()


@st.cache_resource(show_spinner="提取简版词典单词信息...", ttl=60 * 60 * 24)  # 缓存有效期为24小时
def get_mini_dict_doc(word):
    w = word.replace("/", " or ")
    mini_dict = load_mini_dict()
    return mini_dict.get(w, {})


@st.cache_data(ttl=timedelta(hours=24), max_entries=10000, show_spinner="获取单词图片网址...")
def select_word_image_urls(word: str):
    mini_dict_doc = get_mini_dict_doc(word)
    return mini_dict_doc.get("image_urls", [])


@st.cache_data(ttl=60 * 60 * 24, show_spinner="正在进行发音评估，请稍候...")
def pronunciation_assessment_for(audio_info: dict, reference_text: str):
    return pronunciation_assessment_from_stream(
        audio_info, st.secrets, None, reference_text
    )


def process_dialogue_text(reference_text):
    # 去掉加黑等标注
    reference_text = reference_text.replace("**", "")
    # 去掉对话者名字
    reference_text = re.sub(r"^\w+(\s\w+)*:\s", "", reference_text, flags=re.MULTILINE)
    # 去掉空行
    reference_text = re.sub("\n\\s*\n*", "\n", reference_text)
    return reference_text.strip()


def pronunciation_assessment_word_format(word):
    error_type = word.error_type
    if error_type is None:
        return f"{word.word}"
    if error_type == "Mispronunciation":
        accuracy_score = round(word.accuracy_score)
        return annotation(word.word, label=str(accuracy_score), background="yellow")
    if error_type == "Omission":
        return annotation(f"[{word.word}]", background="#4a4943b7")
    if error_type == "Insertion":
        return annotation(word.word, border="2px dashed red")
    if word.is_unexpected_break:
        return annotation(f"{word.word}", background="#FFC0CB")
    if word.is_missing_break:
        return annotation(f"{word.word}", background="#f2f2f2")
    if word.is_monotone:
        return annotation(
            f"{word.word}", color="white", background="rgba(128, 0, 128, 200)"
        )
    return f"{word.word}"


def view_word_assessment(words):
    res = []
    for word in words:
        res.append(pronunciation_assessment_word_format(word))
        res.append(" ")
    annotated_text(*res)


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


def on_page_to(this_page: str = ""):
    """
    检查页面是否发生变化，如果发生变化，保存并清除所有学习记录。
    """
    # 在会话状态中设置上一页
    if "previous-page" not in st.session_state:
        st.session_state["previous-page"] = None

    if "current-page" not in st.session_state:
        st.session_state["current-page"] = None

    if "learning-record" not in st.session_state:
        st.session_state["learning-record"] = []

    # 如果当前页和上一页不同，保存上一页的学习时长
    if st.session_state["current-page"] != this_page:
        if st.session_state["previous-page"] is not None:
            # 当转移页面时，关闭未关闭的学习记录
            end_and_save_learning_records()

        # 更新上一页为当前页
        st.session_state["previous-page"] = st.session_state["current-page"]

    st.session_state["current-page"] = this_page

    # logger.info(
    #     f"上一页：{st.session_state['previous-page']} 当前页：{st.session_state['current-page']}"
    # )


# endregion
