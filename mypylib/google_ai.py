import json
import logging
import sys
import tempfile
import threading
import time
from collections import deque
from datetime import datetime
from functools import partial
from typing import Callable, List

import pytz
import requests
import streamlit as st
import yaml
from faker import Faker
from moviepy.editor import VideoFileClip
from vertexai.preview.generative_models import (
    GenerationConfig,
    GenerativeModel,
    Part,
    ResponseBlockedError,
)

from .constants import USD_TO_CNY_EXCHANGE_RATE, from_chinese_to_english_topic
from .google_ai_prompts import (
    ENGLISH_WRITING_SCORING_TEMPLATE,
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

logger = logging.getLogger("streamlit")


@st.cache_resource
def load_vertex_model(model_name):
    return GenerativeModel(model_name)


def download_file(url, local_filename):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)


def get_video_duration(video_path):
    clip = VideoFileClip(video_path)
    duration = clip.duration  # 获取视频时长，单位为秒
    return duration


def get_duration_from_url(url):
    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=True) as temp_file:
        # 下载视频文件
        download_file(url, temp_file.name)

        # 获取视频时长
        duration = get_video_duration(temp_file.name)

    return duration


def get_text_length_in_bytes(text):
    text_without_spaces = text.replace(" ", "")
    byte_string = text_without_spaces.encode("utf-8")
    return len(byte_string)


def calculate_gemini_pro_cost(
    image_count, video_seconds, input_characters, output_characters
):
    image_cost = 0.0025 * image_count
    video_cost = 0.002 * video_seconds
    input_text_cost = 0.00025 * (input_characters / 1000)
    output_text_cost = 0.0005 * (output_characters / 1000)
    # logger.info(
    #     f"{image_cost =:.6f},  {video_cost =:.6f},  {input_text_cost =:.6f},  {output_text_cost =:.6f}"
    # )
    total_cost = image_cost + video_cost + input_text_cost + output_text_cost

    return total_cost * USD_TO_CNY_EXCHANGE_RATE


def _calculate_input_cost_from_parts(contents_info: List[dict]):
    image_count = 0
    video_seconds = 0
    input_characters = 0

    for content in contents_info:
        if content["mime_type"].startswith("image"):
            image_count += 1
        elif content["mime_type"].startswith("video"):
            # 这里假设你有一个函数可以获取视频的时长
            video_seconds += content["duration"]
            # logger.info(f"{content['duration']=}")
        elif content["mime_type"].startswith("text"):
            input_characters += get_text_length_in_bytes(content["part"].text)

    return calculate_gemini_pro_cost(image_count, video_seconds, input_characters, 0)


def _calculate_output_cost(text):
    length_in_bytes = get_text_length_in_bytes(text)
    return calculate_gemini_pro_cost(0, 0, 0, length_in_bytes)


def calculate_total_cost_by_rule(contents_info: List[dict], full_response):
    """
    Calculate the total cost by rule based on the given contents information and full response.

    Args:
        contents_info (List[dict]): A list of dictionaries containing information about the contents.
        full_response: The full response object.

    Returns:
        float: The total cost calculated based on the input and output costs.
    """
    input_cost = _calculate_input_cost_from_parts(contents_info)
    output_cost = _calculate_output_cost(full_response)
    total_cost = input_cost + output_cost
    return total_cost


def calculate_cost_by_model(model_name, contents, full_response):
    """
    Calculate the cost of using a specific model for text generation.

    Args:
        model_name (str): The name of the model to be used.
        contents (str): The input text contents.
        full_response (str): The generated full response.

    Returns:
        float: The cost of using the model for text generation.
    """
    model = load_vertex_model(model_name)
    input_token_count = model.count_tokens(contents)
    output_token_count = model.count_tokens(full_response)
    return calculate_gemini_pro_cost(
        0,
        0,
        input_token_count.total_billable_characters,
        output_token_count.total_billable_characters,
    )


def parse_json_string(s, prefix="```python", suffix="```"):
    s = s.strip()  # 删除字符串两端的空白字符
    if s.startswith(prefix.upper()):
        s = s[len(prefix) :]  # 删除前缀
    if s.startswith(prefix.lower()):
        s = s[len(prefix) :]  # 删除前缀
    if s.endswith(suffix):
        s = s[: -len(suffix)]  # 删除后缀

    # 解析 JSON
    try:
        d = json.loads(s)
    except json.JSONDecodeError:
        logger.info(f"Failed to parse JSON string: {s}")
        raise

    return d


class ModelRateLimiter:
    def __init__(self, max_calls, per_seconds):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self.calls = {}
        self.lock = threading.Lock()

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
        while not self._allow_call(model_name):
            time.sleep(0.2)
        return func(*args, **kwargs)


# 在streamlit环境下使用装饰器
if "streamlit" in sys.modules:
    ModelRateLimiter = st.cache_resource(ModelRateLimiter)


# if "user_name" not in st.session_state:
#     fake = Faker("zh_CN")
#     st.session_state.user_name = fake.name()


def part_to_dict(part: Part, mime_type: str, duration=None):
    return {"part": part, "mime_type": mime_type, "duration": duration}


def to_contents_info(contents):
    contents_info = []
    for content in contents:
        if isinstance(content, str):
            contents_info.append({"part": Part.from_text(content), "mime_type": "text"})
        elif isinstance(content, dict):
            contents_info.append(content)
        else:
            raise TypeError(f"不支持的内容类型：{type(content)}")
    return contents_info


def display_generated_content_and_update_token(
    item_name: str,
    model_name: str,
    model_method: Callable,
    contents_info: List[dict],
    generation_config: GenerationConfig,
    stream: bool,
    placeholder,
):
    contents = [p["part"] for p in contents_info]
    start_time = time.time()  # 记录开始时间
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
            time.sleep(0.02)
            # Add a blinking cursor to simulate typing
            placeholder.markdown(full_response + "▌")
    else:
        full_response = responses.text
        total_tokens += responses._raw_response.usage_metadata.total_token_count
        # st.write(f"responses 令牌数：{responses._raw_response.usage_metadata}")

    placeholder.markdown(full_response)
    elapsed_time = time.time() - start_time  # 计算用时

    # 添加记录到数据库
    st.session_state.dbi.add_token_record(item_name, total_tokens)
    # 修改会话中的令牌数
    st.session_state.current_token_count = total_tokens
    st.session_state.total_token_count += total_tokens

    total_cost_1 = calculate_total_cost_by_rule(contents_info, full_response)
    total_cost_2 = calculate_cost_by_model(model_name, contents, full_response)
    # logger.info(f"{total_cost_1=:.4f}, {total_cost_2=:.4f}")

    usage = {
        "service_name": "Google AI",
        "item_name": item_name,
        "cost": total_cost_1,
        "total_cost_google": total_cost_2,
        "total_tokens": total_tokens,
        "model_name": model_name,
        "elapsed_time": elapsed_time,
        "timestamp": datetime.now(pytz.utc),
    }
    st.session_state.dbi.add_usage_to_cache(usage)
    # 保存到数据库


def parse_generated_content_and_update_token(
    item_name: str,
    model_name: str,
    model_method: Callable,
    contents_info: List[dict],
    generation_config: GenerationConfig,
    stream: bool,
    parser: Callable = lambda x: x,
):
    contents = [p["part"] for p in contents_info]
    start_time = time.time()  # 记录开始时间
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

    elapsed_time = time.time() - start_time  # 计算用时
    # 添加记录到数据库
    st.session_state.dbi.add_token_record(item_name, total_tokens)
    # 修改会话中的令牌数
    st.session_state.current_token_count = total_tokens
    st.session_state.total_token_count += total_tokens

    total_cost_1 = calculate_total_cost_by_rule(contents_info, full_response)
    total_cost_2 = calculate_cost_by_model(model_name, contents, full_response)
    # logger.info(f"{total_cost_1=:.4f}, {total_cost_2=:.4f}")

    usage = {
        "service_name": "Google AI",
        "item_name": item_name,
        "cost": total_cost_1,
        "total_cost_google": total_cost_2,
        "total_tokens": total_tokens,
        "model_name": model_name,
        "elapsed_time": elapsed_time,
        "timestamp": datetime.now(pytz.utc),
    }
    st.session_state.dbi.add_usage_to_cache(usage)

    return parser(full_response)


WORDS_TEST_PROMPT_TEMPLATE = """
As an experienced English teacher, you are tasked with creating an examination for the following words to assess students' understanding of their meanings.
- You possess an in-depth understanding of the vocabulary for each level of the Common European Framework of Reference for Languages (CEFR).
- You should have a thorough understanding of the sequence of numbers in English, such as knowing that each number has a unique successor and predecessor. For instance, the successor of "eighteen" is "nineteen", and the predecessor of "eleven" is "ten". This knowledge is necessary for creating questions related to numerical vocabulary.
- The target audience for the examination is students who have achieved the {level} proficiency level according to the CEFR standards. The complexity of the questions should not exceed their comprehension abilities.
- The examination questions and options should not contain any Chinese. However, Chinese can be used in the "explanations" section when necessary.
- Inspect and adjust the distribution of answers for these questions, ensuring they are randomly and evenly distributed. 

{guidelines}

- Create a list of dictionaries, each representing a test question for each word.
- Output the list in JSON format. Note that 'question', 'options', and 'answer' in the dictionary should not use Markdown formatting.

Words: {words}
"""


def generate_word_tests(model_name, model, words, level):
    # 确定单词为列表
    if not isinstance(words, list):
        raise TypeError("words must be a list of words")
    words = " , ".join(words)
    prompt = WORDS_TEST_PROMPT_TEMPLATE.format(
        words=words, level=level, guidelines=SINGLE_CHOICE_QUESTION
    )
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=8192, temperature=0.0, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "单词理解测试",
        model_name,
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=partial(parse_json_string, prefix="```json", suffix="```"),
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
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.8, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "生成场景",
        "gemini-pro",
        model.generate_content,
        contents_info,
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
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.5, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "生成对话",
        "gemini-pro",
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=lambda x: [line for line in x.strip().splitlines() if line],
    )


ONE_SUMMARY_TEMPLATE = """使用中文简体一句话概要以下文本
文本：{text}。"""


def summarize_in_one_sentence(model, text):
    # 使用模型的 summarize 方法来生成文本的一句话中文概要
    prompt = ONE_SUMMARY_TEMPLATE.format(text=text)
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.0, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "一句话概述",
        "gemini-pro",
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )


LISTENING_TEST_TEMPLATE = """为了考察学生听力水平，根据学生语言水平，结合以下对话材料，出{number}道英语单选测试题：
语言水平：{level}
要求：
- 测试题必须根据学生当前的语言水平设计。
- 测试题应与对话内容紧密相关。
- 题干与选项必须逻辑清晰，相关联。题目应提供充分的上下文，以避免产生歧义。
- 每道题应提供四个选项，其中只有一个是正确答案。
- 四个选项应以A、B、C、D标识，选项文本应以"."与标识分隔。
- 正确答案应在各选项中随机分布，避免偏向某一特定选项。
- 输出内容应包括题干、选项列表、答案（只需提供选项标识）、解析以及相关句子。

每一道题以字典形式表达，结果为列表，输出JSON格式。

对话：{dialogue}"""


def generate_listening_test(model, level, dialogue, number=5):
    prompt = LISTENING_TEST_TEMPLATE.format(
        level=level, dialogue=dialogue, number=number
    )
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.2, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "听力测试",
        "gemini-pro",
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=partial(parse_json_string, prefix="```json", suffix="```"),
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
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.8, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "阅读理解文章",
        "gemini-pro",
        model.generate_content,
        contents_info,
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
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=2048, temperature=0.0, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "阅读理解测试",
        "gemini-pro",
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=parse_json_string,
    )


PRONUNCIATION_ASSESSMENT_TEMPLATE = """
Please prepare a personal statement as an English speaking test candidate according to the following instructions:
- Language: Authentic English, leaning towards colloquial.
- Level: CEFR {level}.
- Ability Requirements: {ability}. 
- The description of abilities may be quite broad, you just need to elaborate on related details to demonstrate your capabilities.
- Personal Information: You may reasonably fabricate personal information for the purpose of the statement. Avoid using placeholders such as '[your name]'.
- Text content: The statement should be consistent with the above scenario or task and should match your English proficiency level.
- Vocabulary: Should be consistent with the CEFR English level
- Word count: The generated text should strictly adhere to the word count limit of between 100 and 200 words. 
- Output format: Should be a personal statement. Any narration should be marked with parentheses and must be on a separate line.
- Language norms: The output content should be entirely in English, avoiding mixing English and Chinese or using Chinese in the narration."
"""


def generate_pronunciation_assessment_text(model, ability, level):
    scenario = from_chinese_to_english_topic(level, ability)
    prompt = PRONUNCIATION_ASSESSMENT_TEMPLATE.format(ability=scenario, level=level)
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=500, temperature=0.9, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "发音评估材料",
        "gemini-pro",
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )


ORAL_ABILITY_TOPIC_TEMPLATE = """
As an English oral ability examiner, provide 5 topics for students to choose from to assess whether they meet the following ability requirements:
- Level: CEFR {level}.
- Ability Requirements: {ability}.
- Word count: Each topic should be within 30 words.
- Each topic should be a complete sentence, not a list of questions.
- Each topic should not exceed three questions.
- No need for detailed descriptions.
- Language: Please use English, do not use Simplified Chinese.
- Vocabulary: The vocabulary used in each topic must match the ability level of the students.
"""


def generate_oral_ability_topics(model, ability, level, number):
    scenario = from_chinese_to_english_topic(level, ability)
    prompt = ORAL_ABILITY_TOPIC_TEMPLATE.format(
        number=number, ability=scenario, level=level
    )
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=500, temperature=0.9, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "口语能力话题",
        "gemini-pro",
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )


ORAL_ABILITY_STATEMENT_TEMPLATE = """
As an examinee, you are required to make a statement on a given topic according to the following requirements:
- Level: CEFR {level}.
- Topic: {topic}.
- Word count: The statement should be within 100 to 200 words.
- Vocabulary and ability: Your statement should use vocabulary and demonstrate abilities that match the CEFR {level} level (slightly higher is also acceptable).
"""


def generate_oral_statement_template(model, topic, level):
    prompt = ORAL_ABILITY_STATEMENT_TEMPLATE.format(topic=topic, level=level)
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=256, temperature=0.5, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "口语陈述模板",
        "gemini-pro",
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )


EXTRACT_ONE_PHRASE_TEMPLATE = """
From the given phrase combinations, randomly select one.

For example:
- Given the phrase combinations "(be) concentrated around or in or on, etc.".
- You might randomly select and output: "(be) concentrated in".

Phrase combinations:
{phrase}
"""


def pick_a_phrase(model, phrase):
    """
    从模型中提取与给定短语相关的短语搭配。

    Args:
        model: 模型对象，用于生成短语搭配。
        phrase: 给定的短语。

    Returns:
        提取的短语搭配结果。
    """

    prompt = EXTRACT_ONE_PHRASE_TEMPLATE.format(phrase=phrase)
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=128, temperature=0.1, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "提取短语搭配",
        "gemini-pro",
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )


def generate_english_writing_assessment(model, composition):
    prompt = ENGLISH_WRITING_SCORING_TEMPLATE.format(composition=composition)
    contents = [prompt]
    generation_config = GenerationConfig(
        max_output_tokens=4096, temperature=0.1, top_p=1.0
    )
    contents_info = to_contents_info(contents)
    return parse_generated_content_and_update_token(
        "英语写作能力评估",
        "gemini-pro",
        model.generate_content,
        contents_info,
        generation_config,
        stream=False,
        parser=lambda x: x,
    )
