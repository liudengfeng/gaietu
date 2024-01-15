import json
import threading
import time
from collections import deque
from typing import Callable, List

import streamlit as st
from faker import Faker
from vertexai.preview.generative_models import GenerationConfig, GenerativeModel, Part

from mypylib.google_cloud_configuration import DEFAULT_SAFETY_SETTINGS


MAX_CALLS = 10
PER_SECONDS = 60


@st.cache_resource
class RateLimiter:
    def __init__(self, max_calls, per_seconds):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.calls = deque()
        self.lock = threading.Lock()

    def _allow_call(self):
        with self.lock:
            now = time.time()
            while self.calls and now - self.calls[0] > self.per_seconds:
                self.calls.popleft()
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True
            else:
                return False

    def call_func(self, func, *args, **kwargs):
        while not self._allow_call():
            time.sleep(0.2)
        return func(*args, **kwargs)


# if "user_name" not in st.session_state:
#     fake = Faker("zh_CN")
#     st.session_state.user_name = fake.name()


def display_generated_content_and_update_token(
    item_name: str,
    model: GenerativeModel,
    contents: List[Part],
    generation_config: GenerationConfig,
    stream: bool,
    placeholder,
):
    responses = st.session_state.rate_limiter.call_func(
        model.generate_content,
        contents,
        generation_config=generation_config,
        safety_settings=DEFAULT_SAFETY_SETTINGS,
        stream=stream,
    )
    full_response = ""
    total_tokens = 0
    # 提取生成的内容
    if stream:
        for chunk in responses:
            try:
                full_response += chunk.text
                total_tokens += chunk._raw_response.usage_metadata.total_token_count
                # st.write(f"流式块 令牌数：{chunk._raw_response.usage_metadata}")
            except (IndexError, ValueError) as e:
                st.write(chunk)
                st.error(e)
            time.sleep(0.05)
            # Add a blinking cursor to simulate typing
            placeholder.markdown(full_response + "▌")
    else:
        full_response = responses.text
        total_tokens += responses._raw_response.usage_metadata.total_token_count
        # st.write(f"responses 令牌数：{responses._raw_response.usage_metadata}")

    placeholder.markdown(full_response)

    # 添加记录到数据库
    st.session_state.dbi.add_token_record(item_name, total_tokens)
    # 修改会话中的令牌数
    st.session_state.current_token_count = total_tokens
    st.session_state.total_token_count += total_tokens


def parse_generated_content_and_update_token(
    item_name: str,
    model: GenerativeModel,
    contents: List[Part],
    generation_config: GenerationConfig,
    stream: bool,
    parser: Callable,
):
    responses = st.session_state.rate_limiter.call_func(
        model.generate_content,
        contents,
        generation_config=generation_config,
        safety_settings=DEFAULT_SAFETY_SETTINGS,
        stream=stream,
    )
    full_response = ""
    total_tokens = 0
    # 提取生成的内容
    if stream:
        for chunk in responses:
            try:
                full_response += chunk.text
                total_tokens += chunk._raw_response.usage_metadata.total_token_count
            except (IndexError, ValueError) as e:
                st.write(chunk)
                st.error(e)
    else:
        full_response = responses.text
        total_tokens += responses._raw_response.usage_metadata.total_token_count

    # 添加记录到数据库
    st.session_state.dbi.add_token_record(item_name, total_tokens)
    # 修改会话中的令牌数
    st.session_state.current_token_count = total_tokens
    st.session_state.total_token_count += total_tokens
    return parser(full_response)


WORD_IMAGE_PROMPT_TEMPLATE = """
你的任务是分步找出最能解释单词含义的前4张图片编号：
第一步：图片按输入顺序从0开始编号；
第二步：按解释程度评分，最低0分，最高1.0，形成一个得分字典。评分越高，图片越能解释单词的含义；
第三步：对每一张照片逐项分析是否满足以下条件，如果满足，每项加0.1分，更新得分字典；
- 图片的清晰度和可读性是最重要的，用户应该能够轻松地理解图片所传达的信息。
- 图片应该准确地反映单词的含义，避免出现误导或混淆。
- 图片应该生动形象，能够引起用户的注意力和兴趣，从而促进对单词的理解和记忆。
- 图片的主题应该与单词的含义相关，能够帮助用户理解单词的具体含义。
- 图片的构图应该合理，能够突出单词的重点内容。
- 图片的色彩应该鲜明，能够引起用户的注意力。
第四步：分析得分字典，剔除包含色情、暴力、毒品等内容或者得分少于0.6的编号；
第五步：选择得分最高的前4张图像编号。如果满足条件的图像不足4张，我们将选择所有满足条件的图像编号。

输出python list格式。

单词：{word}
"""


def select_best_images_for_word(model, word, images: List[Part]):
    """
    为给定的单词选择最佳解释单词含义的图片。

    这个函数使用模型生成一个图片选择结果，然后返回最能解释给定单词含义的图片的序号列表。

    Args:
        word (str): 要解释的单词。
        images (List[Part]): 图片列表，每个元素都是一个Part对象，代表一张图片。
        model (GenerativeModel): 用于生成图片选择结果的模型。

    Returns:
        list: 以JSON格式输出的最佳图片序号列表。这些序号对应于输入的图片列表中的位置。如果没有合适的图片，则返回空列表。
    """
    prompt = WORD_IMAGE_PROMPT_TEMPLATE.format(word=word)
    contents = [Part.from_text(prompt)] + images
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.0, top_p=1, top_k=32
    )
    return parse_generated_content_and_update_token(
        "挑选图片",
        model,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: json.loads(x.replace("```python", "").replace("```", "")),
    )


WORD_TEST_PROMPT_TEMPLATE = """
你是一名专业英语老师，需要出题考察学生对英语词汇含义的理解，要求：
在出题时，要避免歧义，让题目具有明确性；
题干要清晰明了。题干要让学生能够准确理解题意；
单选题，每道题只有唯一正确的答案；
选项的排列顺序通常是随机的;
正确答案随机分布，不要总集中在某个选项；
选项与题干密切相关，且互不重复；
选项之间区分度高，不要造成困扰；
选项使用A、B、C、D标识，以"."与选项分离；
正确答案只需要输出字符标识；
针对的受众是英语语言能力为CEFR标准{level}的人群；
输出中不需要使用非必要的格式标注，如加黑等等；

输出键为"问题"、"选项"、"答案"、"解释"的字典，JSON格式。
注意：选项共四个，以python list格式输出。

单词：{word}
"""


def generate_word_test(model, word, level):
    prompt = WORD_TEST_PROMPT_TEMPLATE.format(word=word, level=level)
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.4, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "单词理解考题",
        model,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: json.loads(x.replace("```python", "").replace("```", "")),
    )
