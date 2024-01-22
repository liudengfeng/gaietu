import base64
import hashlib
import io
import json
import os
import random
import re
import string
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import Union

import requests
from azure.storage.blob import BlobClient, BlobServiceClient, ContainerClient
from gtts import gTTS
from PIL import Image

from .azure_speech import synthesize_speech_to_file

CURRENT_CWD: Path = Path(__file__).parent.parent


def get_unique_words(
    word_file_path: str, include_phrases: bool, cate: str = "all"
) -> list:
    # 加载 JSON 文件
    with open(word_file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 合并所有的单词并去除重复的单词
    unique_words = set()
    for c, word_list in data.items():
        if cate != "all" and cate not in c:
            continue
        for word in word_list:
            # 根据 include_phrases 参数决定是否添加单词
            if include_phrases or " " not in word:
                unique_words.add(word)

    # 将结果转换为列表
    unique_words = list(unique_words)

    return unique_words


def remove_trailing_punctuation(s: str) -> str:
    """
    Removes trailing punctuation from a string.

    Args:
        s (str): The input string.

    Returns:
        str: The input string with trailing punctuation removed.
    """
    chinese_punctuation = (
        "！？｡。＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～｟｠｢｣､、〃》「」『』【】〔〕〖〗〘〙〚〛〜〝〞〟〰〾〿–—‘’‛“”„‟…‧﹏."
    )
    all_punctuation = string.punctuation + chinese_punctuation
    return s.rstrip(all_punctuation)


def hash_word(word: str):
    # 创建一个md5哈希对象
    hasher = hashlib.md5()

    # 更新哈希对象的状态
    # 注意，我们需要将字符串转换为字节串，因为哈希函数只接受字节串
    hasher.update(word.encode("utf-8"))

    # 获取哈希值
    hash_value = hasher.hexdigest()

    return hash_value


def get_word_cefr_map(name, fp):
    assert name in ("us", "uk"), "只支持`US、UK`二种发音。"
    with open(os.path.join(fp, f"{name}_cefr.json"), "r") as f:
        return json.load(f)


def audio_autoplay_elem(data: Union[bytes, str], controls: bool = False, fmt="mp3"):
    audio_type = "audio/mp3" if fmt == "mp3" else "audio/wav"

    # 如果 data 是字符串，假定它是一个文件路径，并从文件中读取音频数据
    if isinstance(data, str):
        with open(data, "rb") as f:
            data = f.read()

    b64 = base64.b64encode(data).decode()
    if controls:
        return f"""\
<audio controls autoplay>\
    <source src="data:{audio_type};base64,{b64}" type="{audio_type}">\
    Your browser does not support the audio element.\
</audio>\
<script>\
    var audio = document.querySelector('audio');\
    audio.load();\
    audio.play();\
</script>\
            """
    else:
        return f"""\
<audio autoplay>\
    <source src="data:{audio_type};base64,{b64}" type="{audio_type}">\
    Your browser does not support the audio element.\
</audio>\
<script>\
    var audio = document.querySelector('audio');\
    audio.load();\
    audio.play();\
</script>\
            """


def gtts_autoplay_elem(text: str, lang: str, tld: str):
    tts = gTTS(text, lang=lang, tld=tld)
    io = BytesIO()
    tts.write_to_fp(io)
    b64 = base64.b64encode(io.getvalue()).decode()
    return f"""\
        <audio controls autoplay>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """


def get_lowest_cefr_level(word):
    """
    Get the lowest CEFR level of a given word.

    Parameters:
    word (str): The word to check the CEFR level for.

    Returns:
    str or None: The lowest CEFR level of the word, or None if the word is not found in the CEFR dictionary.
    """
    fp = os.path.join(
        CURRENT_CWD, "resource", "dictionary", "word_lists_by_edition_grade.json"
    )
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    with open(fp, "r") as f:
        cefr = json.load(f)
    for level in levels:
        level_flag = f"1-CEFR-{level}"
        if word in cefr[level_flag]:
            return level
    return None


def count_words_and_get_levels(text, percentage=False):
    """
    统计文本中的单词数量并获取每个单词的最低 CEFR 等级。

    参数：
    text (str)：要处理的文本。
    percentage (bool)：是否将结果转换为百分比形式。

    返回值：
    tuple：包含两个元素的元组，第一个元素是文本中的单词数量，第二个元素是一个字典，包含每个等级的单词数量。

    示例：
    >>> count_words_and_get_levels("Hello world! This is a test.")
    (5, {'未定义': 5})
    """

    # 移除所有标点符号并转换为小写
    text = re.sub(r"[^\w\s]", "", text).lower()

    # 获取所有唯一的单词
    words = set(text.split())

    # 初始化字典
    levels = defaultdict(int)

    # 遍历所有的单词
    for word in words:
        # 获取单词的最低 CEFR 等级
        level = get_lowest_cefr_level(word)

        # 如果单词没有 CEFR 等级，将等级设置为 "未定义"
        if level is None:
            level = "未分级"

        # 将等级添加到字典中
        levels[level] += 1

    total_words = len(words)
    if percentage:
        for level in levels:
            levels[
                level
            ] = f"{levels[level]} ({levels[level] / total_words * 100:.2f}%)"

    # 返回总字数和字典
    return total_words, dict(levels)


def sample_words(level, n):
    """
    Generate a random sample of words from a specific CEFR level.

    Args:
        level (str): The CEFR level of the words. Must be one of ["A1", "A2", "B1", "B2", "C1", "C2"].
        n (int): The number of words to sample.

    Returns:
        list: A list of randomly sampled words from the specified CEFR level.
    """
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    assert level in levels, f"level must be one of {levels}"
    fp = os.path.join(
        CURRENT_CWD, "resource", "dictionary", "word_lists_by_edition_grade.json"
    )
    with open(fp, "r") as f:
        cefr = json.load(f)
    level_flag = f"1-CEFR-{level}"
    return random.sample(cefr[level_flag], n)


def get_or_create_and_return_audio_data(word: str, style: str, secrets: dict):
    # 生成单词的哈希值
    hash_value = hash_word(word)

    # 生成单词的语音文件名
    filename = f"e{hash_value}.mp3"

    # 创建 BlobServiceClient 对象，用于连接到 Blob 服务
    blob_service_client = BlobServiceClient.from_connection_string(
        secrets["Microsoft"]["AZURE_STORAGE_CONNECTION_STRING"]
    )

    # 创建 ContainerClient 对象，用于连接到容器
    container_client = blob_service_client.get_container_client("word-voices")

    # 创建 BlobClient 对象，用于操作 Blob
    blob_client = container_client.get_blob_client(f"{style}/{filename}")

    # 如果 Blob 不存在，则调用 Azure 的语音合成服务生成语音文件，并上传到 Blob
    if not blob_client.exists():
        # 生成语音文件
        synthesize_speech_to_file(
            word,
            filename,
            secrets["Microsoft"]["SPEECH_KEY"],
            secrets["Microsoft"]["SPEECH_REGION"],
            style,  # type: ignore
        )

        # 上传文件到 Blob
        with open(filename, "rb") as data:
            blob_client.upload_blob(data)

    # 读取 Blob 的内容
    audio_data = blob_client.download_blob().readall()

    return audio_data


def _normalize_english_word(word):
    """规范化单词"""
    word = word.strip()
    # 当"/"在单词中以" or "代替
    if "/" in word:
        word = word.replace("/", " or ")
    return word


def get_word_image_urls(word, api_key):
    url = "https://google.serper.dev/images"
    w = _normalize_english_word(word)
    # q = f"Pictures that visually explain the meaning of the word '{w}' (pictures with only words and no explanation are excluded)'"
    payload = json.dumps({"q": w})
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

    response = requests.request("POST", url, headers=headers, data=payload)
    data_dict = json.loads(response.text)
    # 使用缩略图确保可正确下载图像
    return [img["thumbnailUrl"] for img in data_dict["images"]]


def load_image_bytes_from_url(img_url: str) -> bytes:
    response = requests.get(img_url)
    img = Image.open(io.BytesIO(response.content))

    # 如果图像是 GIF，将其转换为 PNG
    if img.format == "GIF":
        # 创建一个新的 RGBA 图像以保存 GIF 图像的每一帧
        png_img = Image.new("RGBA", img.size)
        # 将 GIF 图像的第一帧复制到新图像中
        png_img.paste(img)
        img = png_img

    # 将图像转换为字节
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr = img_byte_arr.getvalue()

    return img_byte_arr
