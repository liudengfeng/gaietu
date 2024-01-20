import json
import threading
import time
from collections import deque
from typing import Callable, List
from datetime import datetime
import streamlit as st
from faker import Faker
from vertexai.preview.generative_models import (
    GenerationConfig,
    GenerativeModel,
    Part,
    ResponseBlockedError,
)
import pytz
from mypylib.google_cloud_configuration import DEFAULT_SAFETY_SETTINGS


MAX_CALLS = 10
PER_SECONDS = 60
shanghai_tz = pytz.timezone("Asia/Shanghai")


@st.cache_resource
def load_vertex_model(model_name):
    return GenerativeModel(model_name)


@st.cache_resource
class ModelRateLimiter:
    def __init__(self, max_calls, per_seconds):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.calls = {}
        self.lock = threading.Lock()
        # self.records = {}

    def _allow_call(self, model_name):
        with self.lock:
            now = time.time()
            if model_name not in self.calls:
                self.calls[model_name] = deque()
            while (
                self.calls[model_name]
                and now - self.calls[model_name][0] > self.per_seconds
            ):
                self.calls[model_name].popleft()
            if len(self.calls[model_name]) < self.max_calls:
                self.calls[model_name].append(now)
                return True
            else:
                return False

    def call_func(self, model_name, func, *args, **kwargs):
        # start_time = time.time()  # 记录开始时间
        while not self._allow_call(model_name):
            time.sleep(0.2)
        result = func(*args, **kwargs)
        # end_time = time.time()  # 记录结束时间
        # elapsed_time = end_time - start_time  # 计算用时
        # now = datetime.now(pytz.utc).astimezone(shanghai_tz)  # 获取当前时间并转换为上海时区
        # current_time = now.strftime("%Y-%m-%d %H:%M:%S")  # 获取当前时间并转换为字符串格式
        # self.records[model_name] = self.records.get(model_name, []) + [
        #     f"{current_time}: {elapsed_time:.2f}s"
        # ]  # 记录用时
        return result


# if "user_name" not in st.session_state:
#     fake = Faker("zh_CN")
#     st.session_state.user_name = fake.name()


def display_generated_content_and_update_token(
    item_name: str,
    model_name: str,
    model_method: Callable,
    contents: List[Part],
    generation_config: GenerationConfig,
    stream: bool,
    placeholder,
):
    responses = st.session_state.rate_limiter.call_func(
        model_name,
        model_method,
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
            except (IndexError, ValueError, ResponseBlockedError) as e:
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
    model_name: str,
    model_method: Callable,
    contents: List[Part],
    generation_config: GenerationConfig,
    stream: bool,
    parser: Callable,
):
    responses = st.session_state.rate_limiter.call_func(
        model_name,
        model_method,
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
Your task is to find the top 4 image IDs that best explain the meaning of a word in a step-by-step process:

Step 1: Image IDs are numbered from 0 to n in the order of input.

Step 2: Images are scored for their explanatory power, with a minimum of 0 and a maximum of 1.0, to form a scoring dictionary. The higher the score, the better the image can explain the meaning of the word.

Step 3: For each image, each of the following conditions is analyzed to determine whether it is met. If met, 0.1 points are added for each item, and the scoring dictionary is updated.

- Image clarity and readability are most important. Users should be able to easily understand the information conveyed by the image.
- The image should accurately reflect the meaning of the word, avoiding misleading or confusing content.
- The image should be vivid and imaginative, able to attract user attention and interest, thereby promoting understanding and memorization of the word.
- The theme of the image should be relevant to the meaning of the word, helping users understand the specific meaning of the word.
- The composition of the image should be reasonable, highlighting the key content of the word.

Step 4: The scoring dictionary is analyzed to remove image IDs that contain pornographic, violent, or drug-related content or have a score of less than 0.6.

Step 5: The top 4 image IDs with the highest scores are selected. If the number of images that meet the conditions is less than 4, we will select all the image IDs that meet the conditions.

Output: A Python list format.

word:{word}
"""


def select_best_images_for_word(model_name, model, word, images: List[Part]):
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
        model_name,
        model.generate_content,
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


def generate_word_test(model_name, model, word, level):
    prompt = WORD_TEST_PROMPT_TEMPLATE.format(word=word, level=level)
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.4, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "单词理解考题",
        model_name,
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: json.loads(x.replace("```python", "").replace("```", "")),
    )


SCENARIO_TEMPLATE = """
为"{}"模拟12个场景列表
"""


def generate_scenarios(model, subject):
    prompt = SCENARIO_TEMPLATE.format(subject)
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.75, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "生成场景",
        "gemini-pro",
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: [line for line in x.strip().splitlines() if line],
    )


# DIALOGUE_TEMPLATE = """
# 参考以下中文说明，模拟一段地道美国人的英语对话：
# - 模拟纯正的英语对话，不要使用中式英语和中文思维方式，也不要使用中文
# - 对话双方：男孩：{boy_name} 和女孩：{girl_name}
# - 对话只有两人，不要有其他人参与
# - 场景：{scenario}
# - 情节： {plot}
# - 难度：{difficulty}
# - 字数：如果难度为初级，字数在200-300字左右；如果难度为中级，字数在300-500字左右；如果难度为高级，字数在500-1000字左右。
# - 难度反应受众语言能力，对话文字材料要与受众语言能力相适应，保证练习者能够理解和掌握内容
# - 根据难度调整用词、语法结构、表达方式
# - 对于初级难度，使用简单的词汇和语法结构，避免使用过于复杂的表达方式
# - 对于中级难度，使用稍微复杂的词汇和语法结构
# - 对于高级难度，使用更复杂的词汇和语法结构，但要注意保持流畅性和可理解性
# - 输出结果只允许二人对话材料，或者旁白，但旁白整体需要用括号标注，且单独成行
# - 每人发言结束时才能使用换行符
# - 输出结果不要使用非必要的格式标注，如加黑等等
# """

DIALOGUE_TEMPLATE = """
您精通CEFR英语能力分级，全面掌握各级词汇列表。参考以下中文说明，模拟一段地道美国人的英语对话：
- 模拟纯正的英语对话，不要使用中式英语和中文思维方式，也不要使用中文
- 对话双方：男孩：{boy_name} 和女孩：{girl_name} 
- 对话只有两人，不要有其他人参与
- 场景：{scenario} 
- 情节：{plot}
- 难度：CEFR {difficulty}
- 字数：如果难度为A级，字数在200-300字左右；如果难度为B级，字数在300-500字左右；如果难度为C级，字数在500-1000字左右。
- 难度反应受众语言能力，对话文字材料要与受众语言能力相适应，保证练习者能够理解和掌握内容
- 根据难度调整用词、语法结构、表达方式
- 对话用词需要在 CEFR {difficulty} 以下（包括）单词列表范围内
- 对于A级难度，使用简单的词汇和语法结构，避免使用过于复杂的表达方式
- 对于B级难度，使用稍微复杂的词汇和语法结构
- 对于C级难度，使用更复杂的词汇和语法结构，但要注意保持流畅性和可理解性
- 输出结果只允许二人对话材料，或者旁白，但旁白整体需要用括号标注，且单独成行
- 每人发言结束时才能使用换行符
- 输出结果不要使用非必要的格式标注，如加黑等等
"""


def generate_dialogue(model, boy_name, girl_name, scenario, plot, difficulty):
    prompt = DIALOGUE_TEMPLATE.format(
        boy_name=boy_name,
        girl_name=girl_name,
        scenario=scenario,
        plot=plot,
        difficulty=difficulty,
    )
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.75, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "生成对话",
        "gemini-pro",
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: [line for line in x.strip().splitlines() if line],
    )


ONE_SUMMARY_TEMPLATE = """使用中文简体一句话概要以下文本
文本：{text}。"""


def summarize_in_one_sentence(model, text):
    # 使用模型的 summarize 方法来生成文本的一句话中文概要
    prompt = ONE_SUMMARY_TEMPLATE.format(text=text)
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.75, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "一句话概述",
        "gemini-pro",
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )


LISTENING_TEST_TEMPLATE = """为了考察学生听力水平，根据学生语言水平，结合以下对话材料，出{number}道英语单选测试题：
语言水平：{level}
要求：
- 测试题必须结合学生当前的语言水平
- 与对话相关
- 题干与选项要相关，逻辑清晰
- 每道题四个选项，只有唯一正确答案
- 四个选项前依次使用A、B、C、D标识，用"."与选项文本分隔
- 随机分布正确答案，不要集中某一个标识
- 输出题干、选项列表、答案[只需要标识字符]、解释、相关句子

每一道题以字典形式表达，结果为列表，输出JSON格式。

对话：{dialogue}"""


def generate_listening_test(model, level, dialogue, number=5):
    prompt = LISTENING_TEST_TEMPLATE.format(
        level=level, dialogue=dialogue, number=number
    )
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.2, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "听力测试",
        "gemini-pro",
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: json.loads(x.replace("```json", "").replace("```", "")),
    )


READING_ARTICLE_TEMPLATE = """
您是专业的英语老师，全面掌握CEFR分级词汇表。您会准备专业的英语阅读材料来提高学生阅读理解能力。参考以下中文简体提示，生成一篇地道的英文文章：
- 体裁：{genre}
- 内容：{content}
- 情节：{plot}
- CEFR 分级：{level}
- 字数：如果难度为A级，字数在200-300字左右；如果难度为B级，字数在300-500字左右；如果难度为C级，字数在500-1000字左右。
- 文章内容要与提示内容相关
- 使用英语输出，不要使用中文
- 文章整体要求：内容准确、结构清晰、语言规范、表达生动。如果体裁是议论文，要求观点鲜明和论据充分；对于一篇文学作品，最重要的是情感的表达和艺术性。
- 难度反应受众语言能力，文章内容要与受众语言能力相适应，保证练习者能够理解和掌握内容
- 文章要求语法正确、用词准确、表达流畅
- 根据CEFR分级词汇表，文章用词需要在CEFR {level} 以下（包括）单词列表范围内
- 输出文本不要使用非必要的格式标注，如加黑等等
"""


def generate_reading_comprehension_article(model, genre, content, plot, level):
    prompt = READING_ARTICLE_TEMPLATE.format(
        genre=genre, content=content, plot=plot, level=level
    )
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.8, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "阅读文章",
        "gemini-pro",
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )


READING_COMPREHENSION_TEST_TEMPLATE = """
您是专业的英语老师，全面掌握CEFR分级词汇表。参考以下中文简体提示，为文章生成相关阅读理解测试题：
- 题目类型：{question_type}
- 题目数量：{number}
- CEFR 分级：{level}
- 使用英语输出，不要使用中文
- 题目与选项用词需要在CEFR {level} 以下（包括）单词列表范围内
- 题干要与文章和选项要相关，逻辑清晰
- 选择题要输出题干、选项列表、答案[只需要标识字符]、解释
- 单项选择题，每道题四个选项，只有唯一正确答案
- 多选题，每道题四个选项，至少有两个选项是正确答案
- 四个选项前依次使用A、B、C、D标识，用"."与选项文本分隔
- 随机分布正确答案，不要集中某一个标识
- 填空题、判断题输出题干、答案、解释

每一道题以字典形式表达，结果为列表，输出JSON格式。

文章：{article}
"""


def generate_reading_comprehension_test(model, question_type, number, level, article):
    prompt = READING_ARTICLE_TEMPLATE.format(
        question_type=question_type, number=number, level=level, article=article
    )
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.5, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "阅读测试",
        "gemini-pro",
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: json.loads(x.replace("```json", "").replace("```", "")),
    )
