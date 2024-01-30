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
from typing import List, Union

import requests
import spacy
from azure.storage.blob import BlobClient, BlobServiceClient, ContainerClient
from PIL import Image
from pydub import AudioSegment

from .azure_speech import synthesize_speech_to_file

CURRENT_CWD: Path = Path(__file__).parent.parent


def get_word_cefr_map(name, fp):
    assert name in ("us", "uk"), "只支持`US、UK`二种发音。"
    with open(os.path.join(fp, f"{name}_cefr.json"), "r") as f:
        return json.load(f)


def remove_trailing_punctuation(s: str) -> str:
    """
    Removes trailing punctuation from a string.

    Args:
        s (str): The input string.

    Returns:
        str: The input string with trailing punctuation removed.
    """
    chinese_punctuation = "！？｡。＂＃＄％＆＇（）＊＋，－／：；＜＝＞＠［＼］＾＿｀｛｜｝～｟｠｢｣､、〃》「」『』【】〔〕〖〗〘〙〚〛〜〝〞〟〰〾〿–—‘’‛“”„‟…‧﹏."
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


def audio_autoplay_elem(data: Union[bytes, str], fmt="mp3"):
    audio_type = "audio/mp3" if fmt == "mp3" else "audio/wav"
    # 如果 data 是字符串，假定它是一个文件路径，并从文件中读取音频数据
    if isinstance(data, str):
        with open(data, "rb") as f:
            data = f.read()

    b64 = base64.b64encode(data).decode()

    # 生成一个随机的 ID
    audio_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return f"""\
    <audio id="{audio_id}" autoplay>\
        <source src="data:{audio_type};base64,{b64}" type="{audio_type}">\
        Your browser does not support the audio element.\
    </audio>\
    <script>\
        var audio = document.querySelector('#{audio_id}');\
        audio.load();\
        audio.play();\
    </script>\
                """


def get_mini_dict():
    fp = os.path.join(CURRENT_CWD, "resource", "dictionary", "mini_dict.json")
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


def get_cefr_level(word, mini_dict):
    if word in mini_dict:
        return mini_dict[word]["level"]
    return None


def count_words_and_get_levels(
    text, mini_dict, percentage=False, exclude_persons=False
):
    level_words = get_cefr_vocabulary_list([text], mini_dict, exclude_persons)
    # 初始化字典
    levels = defaultdict(int)
    # 遍历分级词汇列表
    for level, words in level_words.items():
        # 增加对应级别的计数
        levels[level] = len(words)

    total_words = sum(len(words) for words in level_words.values())

    if percentage:
        for level in levels:
            levels[level] = (
                f"{levels[level]} ({levels[level] / total_words * 100:.2f}%)"
            )

    # 返回总字数和字典
    return total_words, dict(levels)


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


def get_cefr_vocabulary_list(texts: List[str], mini_dict: dict, exclude_persons=False):
    assert isinstance(texts, list), "texts must be a list of strings"
    model_name = "en_core_web_sm"
    nlp = spacy.load(model_name)
    cefr_vocabulary = {}
    for text in texts:
        doc = nlp(text)
        if exclude_persons:
            tokens = [token for token in doc if token.ent_type_ != "PERSON"]
        else:
            tokens = doc
        lemmatized_words = [token.lemma_ for token in tokens if token.is_alpha]
        for lemma in lemmatized_words:
            cefr_level = get_cefr_level(lemma, mini_dict)
            if cefr_level is None:
                cefr_level = "未分级"
            if cefr_level not in cefr_vocabulary:
                cefr_vocabulary[cefr_level] = set()
            cefr_vocabulary[cefr_level].add(lemma)

    return cefr_vocabulary
