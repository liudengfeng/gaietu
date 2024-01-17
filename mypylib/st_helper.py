from collections import OrderedDict
import logging
import time
from datetime import datetime, timedelta

import pytz
import streamlit as st
import vertexai
from azure.storage.blob import BlobServiceClient
from google.cloud import firestore, translate
from google.oauth2.service_account import Credentials
from vertexai.preview.generative_models import GenerativeModel, Image

from mypylib.db_model import LearningTime

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
from .word_utils import get_word_image_urls, load_image_bytes_from_url

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


def google_translate(text: str, target_language_code: str = "zh-CN"):
    """Translating Text."""
    if text is None or text == "":
        return text  # type: ignore

    # Location must be 'us-central1' or 'global'.
    parent = f"projects/{PROJECT_ID}/locations/global"

    client = st.session_state.google_translate_client
    # Detail on supported types can be found here:
    # https://cloud.google.com/translate/docs/supported-formats
    response = client.translate_text(
        request={
            "parent": parent,
            "contents": [text],
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
    return res[0]


# region 显示


def format_token_count(count):
    return f"{count / 1000:.1f}k" if count >= 1000 else str(count)


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


def view_md_badges(d: dict, badge_maps: OrderedDict):
    cols = st.columns(len(badge_maps.keys()))
    for i, t in enumerate(badge_maps.keys()):
        num = f"{d.get(t,0):3d}"
        body = f"""{badge_maps[t][1]}({num})"""
        cols[i].markdown(
            f""":{badge_maps[t][0]}[{body}]""",
            help=f"✨ {badge_maps[t][2]}",
        )


# endregion

# region 单词
WORD_COUNT_BADGE_MAPS = OrderedDict(
    {
        "总字数": ("green", "总字数", "文本中不重复的单词数量", "success"),
        "A1": ("orange", "A1", "CEFR A1 单词数量", "warning"),
        "A2": ("grey", "A2", "CEFR A1 单词数量", "secondary"),
        "B1": ("red", "B1", "CEFR B1 单词数量", "danger"),
        "B2": ("violet", "B2", "CEFR B2 单词数量", "info"),
        "C1": ("blue", "C1", "CEFR C1 单词数量", "light"),
        "C2": ("rainbow", "C2", "CEFR C2 单词数量", "dark"),
        "未分级": ("green", "未分级", "未分级单词数量", "dark"),
    }
)


@st.cache_resource(show_spinner="提取简版词典单词信息...", ttl=60 * 60 * 24)  # 缓存有效期为24小时
def get_mini_dict_doc(word):
    db = st.session_state.dbi.db
    collection = db.collection("mini_dict")
    w = word.replace("/", " or ")
    # 从 Firestore 获取数据
    doc = collection.document(w).get()

    if doc.exists:
        return doc.to_dict()
    else:
        return {}


def get_and_save_word_image_urls(word: str):
    image_urls = get_word_image_urls(word, st.secrets["SERPER_KEY"])
    # 保存 image_urls 到数据库
    st.session_state.dbi.db.collection("mini_dict").document(word).set(
        {"image_urls": image_urls}, merge=True
    )


def select_word_image_indices(word: str):
    # 查找 image_urls
    image_urls = get_mini_dict_doc(word).get("image_urls", [])
    model = load_vertex_model("gemini-pro-vision")
    if len(image_urls) == 0:
        image_urls = get_word_image_urls(word, st.secrets["SERPER_KEY"])

    images = []
    n = len(image_urls)
    for i, url in enumerate(image_urls):
        try:
            image_bytes = load_image_bytes_from_url(url)
            images.append(Image.from_bytes(image_bytes))
        except Exception as e:
            logger.error(f"加载单词{word}第{i+1}张图片时出错:{str(e)}")
            continue

    # 生成 image_indices
    image_indices = select_best_images_for_word(
        "gemini-pro-vision", model, word, images
    )

    # 检查 indices 是否为列表且列表中的每个元素是否都是整数
    if not isinstance(image_indices, list) or not all(
        isinstance(i, int) for i in image_indices
    ):
        msg = f"{word} 序号必须是一个列表，且列表中的每个元素都必须是整数，但是得到的类型是 {type(image_indices)} 或 {[(type(i), i) for i in image_indices]}"
        logger.error(msg)
        # 使用默认值
        image_indices = list(range(n))[:4]
    else:
        # 剔除不合格的序号
        image_indices = [i for i in image_indices if i < n]

    # 如果清单为空，则触发异常
    if not image_indices:
        image_indices = list(range(n))[:4]

    st.session_state.dbi.update_image_indices(word, image_indices)

    return image_indices


@st.cache_data(ttl=timedelta(hours=24), max_entries=10000, show_spinner="获取单词图片网址...")
def select_word_image_urls(word: str):
    word_info = get_mini_dict_doc(word)
    image_indices = word_info.get("image_indices", [])
    if image_indices:
        return [word_info["image_urls"][i] for i in image_indices]
    image_indices = select_word_image_indices(word)
    db = st.session_state.dbi.db
    collection = db.collection("mini_dict")
    w = word.replace("/", " or ")
    # 从 Firestore 获取数据
    doc = collection.document(w).get()
    urls = doc.to_dict()["image_urls"]
    return [urls[i] for i in image_indices]


# endregion

# region 学习记录
# 学习记录
WORD_IDX_MAPS = {
    "闪卡记忆": "flashcard-idx",
    "拼图游戏": "puzzle-idx",
    "词意测试": "word-test-idx",
}

WORD_NUM_MAPS = {
    "闪卡记忆": "flashcard-words-num",
    "拼图游戏": "puzzle-words-num",
    "词意测试": "test-word-num",
}

WORD_MAPS = {
    "闪卡记忆": "flashcard-words",
    "拼图游戏": "puzzle-words",
    "词意测试": "test-words",
}


def create_learning_records(item):
    num_word = len(st.session_state[WORD_MAPS[item]])
    for i in range(num_word):
        # idx = st.session_state[WORD_IDX_MAPS[item]]
        record = LearningTime(
            phone_number=st.session_state.dbi.cache["user_info"]["phone_number"],
            project=f"词汇-{item}",
            content=st.session_state[WORD_MAPS[item]][i],
        )
        st.session_state["learning-time"][item].append(record)


def handle_learning_record(direction):
    item = st.session_state["current-page"]
    if len(st.session_state["learning-time"][item]) == 0:
        create_learning_records(item)

    def decorator(func):
        def wrapper(*args, **kwargs):
            # 执行原函数
            result = func(*args, **kwargs)
            idx = st.session_state[WORD_IDX_MAPS[item]]
            # 获取当前单词的学习记录
            current_record = st.session_state["learning-time"][item][idx]
            # 开始记录
            current_record.start()

            # 根据 direction 参数来计算上一个单词的索引
            prev_idx = idx - 1 if direction == "next" else idx + 1
            # 如果下一个单词有效
            if 0 <= prev_idx < len(st.session_state["learning-time"][item]):
                # 获取下一个单词的学习记录
                prev_record = st.session_state["learning-time"][item][prev_idx]
                # 结束此前单词的学习记录
                prev_record.end()

            return result

        return wrapper

    return decorator


def save_and_clear_learning_records(item):
    current_time = time.time()

    # 如果 "last_save_time" 字典不存在，创建它
    if "last_save_time" not in st.session_state:
        st.session_state["last_save_time"] = {}

    # 如果这个项目的最后保存时间不存在，或者当前时间与最后保存时间的间隔超过 10 分钟
    if (
        item not in st.session_state["last_save_time"]
        or current_time - st.session_state["last_save_time"][item] > 10 * 60
    ):
        if "learning-time" not in st.session_state:
            return
        # 如果有学习记录
        if len(st.session_state["learning-time"][item]) >= 1:
            # 结束所有学习记录
            for r in st.session_state["learning-time"][item]:
                r.end()
            records = st.session_state["learning-time"][item]
            # 统计时长大于0的记录
            n = len([r for r in records if r.duration > 0])
            # 保存学习记录到数据库
            st.session_state.dbi.save_learning_time(records)
            # 清空学习记录
            st.session_state["learning-time"][item] = []

            st.toast(f"自动存储`{item}` {n:04}条学习记录")

        # 更新这个项目的最后保存时间
        st.session_state["last_save_time"][item] = current_time


def save_and_clear_all_learning_records():
    """
    保存并清除所有学习记录。
    """
    for k in WORD_IDX_MAPS.keys():
        save_and_clear_learning_records(k)


# endregion
