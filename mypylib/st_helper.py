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

# region 用户相关


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


@st.cache_data(ttl=60 * 60 * 24, show_spinner="正在进行发音评估，请稍候...")
def pronunciation_assessment_for(audio_info: dict, reference_text: str):
    return pronunciation_assessment_from_stream(
        audio_info, st.secrets, None, reference_text
    )


@st.cache_data(ttl=60 * 60 * 24, show_spinner="正在进行口语能力评估，请稍候...")
def oral_ability_assessment_for(audio_info: dict, topic: str):
    return pronunciation_assessment_from_stream(audio_info, st.secrets, topic)


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
    if idx:
        result = d[idx].get(score_key, {})
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


def pronunciation_assessment_word_format(word):
    error_type = word.error_type
    accuracy_score = round(word.accuracy_score)
    if error_type == "Mispronunciation":
        return annotation(word.word, label=str(accuracy_score), background="#d5d507ce")
    if error_type == "Omission":
        return annotation(f"[{word.word}]", color="white", background="#4a4943b7")
    if error_type == "Insertion":
        return annotation(word.word, border="2px dashed red")
    if word.is_unexpected_break:
        return annotation(
            f"{word.word}", label=str(accuracy_score), background="#FFC0CB"
        )
    if word.is_missing_break:
        return annotation(
            f"{word.word}", label=str(accuracy_score), background="#f2f2f2"
        )
    if word.is_monotone:
        return annotation(
            f"{word.word}",
            color="white",
            label=str(accuracy_score),
            background="#ac1882ce",
        )
    return f"{word.word}"


def view_word_assessment(words):
    res = []
    for word in words:
        if isinstance(word, str):
            res.append(word)
        else:
            res.append(pronunciation_assessment_word_format(word))
        res.append(" ")
    annotated_text(*res)


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


def view_pronunciation_assessment_legend():
    annotated_text(annotation("w1", "发音错误", background="#d5d507ce"))
    annotated_text(annotation("[w2]", "遗漏", color="white", background="#4a4943b7"))
    annotated_text(annotation("w3", "插入内容", border="2px dashed red"))
    annotated_text(annotation("w4", "意外中断", background="#FFC0CB"))
    annotated_text(annotation("w5", "缺少停顿", background="#f2f2f2"))
    annotated_text(annotation("w6", "发音单调", color="white", background="#ac1882ce"))


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
