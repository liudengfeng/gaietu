import json
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, List

import pytz
import streamlit as st
import yaml
from faker import Faker
from vertexai.preview.generative_models import (
    GenerationConfig,
    GenerativeModel,
    Part,
    ResponseBlockedError,
)

from .constants import from_chinese_to_english_topic
from .google_ai_prompts import (
    MULTIPLE_CHOICE_QUESTION,
    READING_COMPREHENSION_FILL_IN_THE_BLANK_QUESTION,
    READING_COMPREHENSION_LOGIC_QUESTION,
    SINGLE_CHOICE_QUESTION,
)
from .google_cloud_configuration import DEFAULT_SAFETY_SETTINGS

MAX_CALLS = 10
PER_SECONDS = 60
shanghai_tz = pytz.timezone("Asia/Shanghai")


QUESTION_TYPE_GUIDELINES = {
    "single_choice": SINGLE_CHOICE_QUESTION,
    "multiple_choice": MULTIPLE_CHOICE_QUESTION,
    "reading_comprehension_logic": READING_COMPREHENSION_LOGIC_QUESTION,
    "reading_comprehension_fill_in_the_blank": READING_COMPREHENSION_FILL_IN_THE_BLANK_QUESTION,
}


def parse_json_string(s, prefix="```python", suffix="```"):
    # 删除换行符
    s = s.replace("\n", "")

    # 删除前缀和后缀
    s = s.replace(prefix, "").replace(suffix, "")

    # 解析 JSON
    d = json.loads(s)

    return d


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
As a professional English teacher, you have a thorough understanding of the CEFR English proficiency levels and a comprehensive knowledge of the vocabulary list for each level. You also understand the sequential relationship between numbers. Your task is to create a question to assess students' understanding of English vocabulary. Please follow the requirements below:
- avoiding Chinglish or Chinese.
- The target audience of the question is students whose English language ability has reached the {level} level of the CEFR standard;
- CEFR Level: {level}
- Output in English, do not use Chinese
- The vocabulary used in the questions and options should be within (including) the word list of CEFR {level}

{guidelines}

Output in JSON format, without using list or Markdown formatting.

Word: {word}
"""


def generate_word_test(model_name, model, word, level):
    prompt = WORD_TEST_PROMPT_TEMPLATE.format(
        word=word, level=level, guidelines=SINGLE_CHOICE_QUESTION
    )
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.1, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "单词理解考题",
        model_name,
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: json.loads(x),
    )


SCENARIO_TEMPLATE = """
为以下场景模拟12个不同的子场景列表：

场景：
{}

要求：
- 子场景只需要概要，不需要具体内容；
- 使用中文简体；
- 每个场景以数字序号开头，并用". "分隔。编号从1开始；
- 不使用markdown格式标注，如加黑等；
"""


def generate_scenarios(model, subject):
    prompt = SCENARIO_TEMPLATE.format(subject)
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.8, top_p=1.0
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


DIALOGUE_TEMPLATE = """
You have mastered the CEFR English proficiency levels and have a comprehensive grasp of the vocabulary list for each level. Please refer to the following instructions to simulate a dialogue in authentic American English:
- Simulate a dialogue in authentic American English, avoiding Chinglish or Chinese.
- Dialogues should be conducted entirely in English, without the use of Chinese or a mixture of Chinese and English.
- The participants in the dialogue should be: Boy: {boy_name} and Girl: {girl_name}.
- The dialogue should only involve these two participants and should not include others.
- Scenario: {scenario}.
- Plot: {plot}.
- Difficulty: CEFR {difficulty}.
- Word count: Approximately 200-300 words for level A; 300-500 words for level B; 500-1000 words for level C.
- The content of the dialogue should reflect the language ability of the audience to ensure that learners can understand and master it.
- Adjust vocabulary, grammatical structures, and expressions according to the difficulty level.
- The vocabulary used in the dialogue should be within the CEFR {difficulty} or lower word list.
- Level A should use simple vocabulary and grammatical structures, avoiding complex expressions.
- Level B can use slightly more complex vocabulary and grammatical structures.
- Level C can use more complex vocabulary and grammatical structures, but must maintain fluency and comprehensibility.
- The output should only include dialogue material or narration. Narration should be marked with parentheses and must be in a separate line and in English.
- A line break should only be used at the end of each person's speech.
- The output should not use unnecessary formatting, such as bolding.
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
        max_output_tokens=2048, temperature=0.5, top_p=1.0
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
You are a professional English teacher with a comprehensive mastery of the CEFR graded vocabulary list. You will prepare professional English reading materials to enhance students' reading comprehension skills. Refer to the following prompts to generate an authentic English article:
- Genre: {genre}
- Content: {content}
- Plot: {plot}
- CEFR Level: {level}
- Word Count: If the difficulty is Level A, the word count should be around 200-300 words; if Level B, around 300-500 words; if Level C, around 500-1000 words.
- The article content should be relevant to the prompt content
- Use English for output, do not use Chinese
- Overall requirements for the article: accurate content, clear structure, standard language, and vivid expression. If the genre is argumentative, the viewpoints should be distinct and the arguments sufficient; for a literary work, the most important thing is the expression of emotion and artistry.
- The difficulty reflects the audience's language ability, the article content should adapt to the audience's language ability, ensuring that the exerciser can understand and master the content
- The article should have correct grammar, accurate word usage, and smooth expression
- The vocabulary used in the article should primarily adhere to the CEFR level specified or below. Any usage of words beyond the specified level should be strictly necessary and should not exceed 5% of the total word count in the article. If there are suitable alternatives within the specified level or below, they should be used instead.
- Do not use unnecessary formatting marks in the output text, such as bolding, etc.
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
        "阅读理解文章",
        "gemini-pro",
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )


READING_COMPREHENSION_TEST_TEMPLATE = """
You are a professional English teacher with a comprehensive grasp of the CEFR vocabulary list. Refer to the following prompts to generate relevant reading comprehension test questions for the article:
- Question type: {question_type}
- Number of questions: {number}
- CEFR Level: {level}
- Output in English, do not use Chinese
- The vocabulary used in the questions and options should be within (including) the word list of CEFR {level}

{guidelines}

All the questions are compiled into a Python list. This list is then output in JSON format.

Article: {article}
"""


def generate_reading_comprehension_test(model, question_type, number, level, article):
    guidelines = QUESTION_TYPE_GUIDELINES.get(question_type, "")
    prompt = READING_COMPREHENSION_TEST_TEMPLATE.format(
        question_type=question_type,
        number=number,
        level=level,
        article=article,
        guidelines=guidelines,
    )
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.2, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "阅读理解测试",
        "gemini-pro",
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=parse_json_string,
    )


PRONUNCIATION_ASSESSMENT_TEMPLATE = """
"Please prepare a personal statement as an English speaking test candidate according to the following instructions:
- Language: Authentic English, leaning towards colloquial.
- Level: CEFR {level}.
- Ability Requirements: {ability}. 
- The description of abilities may be quite broad, you just need to elaborate on related details to demonstrate your capabilities.
- Personal Information: You may reasonably fabricate personal information for the purpose of the statement. Avoid using placeholders such as '[your name]'.
- Text content: The statement should be consistent with the above scenario or task and should match your English proficiency level.
- Vocabulary: Should be consistent with the CEFR English level
- Word count: Should be between 100 and 200 words
- Output format: Should be a personal statement. Any narration should be marked with parentheses and must be on a separate line.
- Language norms: The output content should be entirely in English, avoiding mixing English and Chinese or using Chinese in the narration."
"""


def generate_pronunciation_assessment_text(model, ability, level):
    scenario = from_chinese_to_english_topic(level, ability)
    prompt = PRONUNCIATION_ASSESSMENT_TEMPLATE.format(scenario=scenario, level=level)
    contents = [Part.from_text(prompt)]
    generation_config = GenerationConfig(
        max_output_tokens=500, temperature=0.9, top_p=1.0
    )
    return parse_generated_content_and_update_token(
        "发音评估材料",
        "gemini-pro",
        model.generate_content,
        contents,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )
