import json

import vertexai
from google.cloud import aiplatform, translate
from google.oauth2.service_account import Credentials
from vertexai.language_models import TextGenerationModel

project = "lingo-406201"
location = "asia-northeast1"

QUESTION_OPTIONS_AND_INSTRUCTIONS = """
请从以下选项中选择正确的答案：
第一个选项：(A)
第二个选项：(B)
第三个选项：(C)
第四个选项：(D)

注意：当输出正确答案时，只需要输出选项的字母标识，不需要带括号。
"""


def get_tran_api_service_account_info(secrets):
    # 由于private_key含有大量的换行符号，所以单独存储
    service_account_info = json.loads(
        secrets["Google"]["GOOGLE_APPLICATION_CREDENTIALS"]
    )
    service_account_info["private_key"] = secrets["Google"]["private_key"]
    return service_account_info


def get_translation_client(secrets):
    service_account_info = get_tran_api_service_account_info(secrets)
    # 创建凭据
    credentials = Credentials.from_service_account_info(service_account_info)
    # 使用凭据初始化客户端
    return translate.TranslationServiceClient(credentials=credentials)


def google_translate(text: str, client, target_language_code: str = "zh-CN"):
    """Translating Text."""
    if text is None or text == "":
        return text  # type: ignore

    # Must be 'us-central1' or 'global'.
    parent = f"projects/{project}/locations/global"

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


def init_vertex(secrets):
    # 完成认证及初始化
    service_account_info = get_tran_api_service_account_info(secrets)
    # 创建凭据
    credentials = Credentials.from_service_account_info(service_account_info)
    aiplatform.init(
        # your Google Cloud Project ID or number
        # environment default used is not set
        project=project,
        # the Vertex AI region you will use
        # defaults to us-central1
        location=location,
        # Google Cloud Storage bucket in same region as location
        # used to stage artifacts
        # staging_bucket="gs://my_staging_bucket",
        # custom google.auth.credentials.Credentials
        # environment default credentials used if not set
        credentials=credentials,
        # customer managed encryption key resource name
        # will be applied to all Vertex AI resources if set
        # encryption_spec_key_name=my_encryption_key_name,
        # the name of the experiment to use to track
        # logged metrics and parameters
        experiment="lingo-experiment",
        # description of the experiment above
        experiment_description="云端使用vertex ai",
    )
    vertexai.init(project=project, location=location)


def generate_text(
    prompt,
    temperature,
    top_p,
    top_k=40,
    # 增加随机性
    candidate_count=1,
    max_output_tokens=1024,
):
    parameters = {
        "candidate_count": candidate_count,
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
    }
    model = TextGenerationModel.from_pretrained("text-bison")
    response = model.predict(
        prompt,
        **parameters,
    )
    return response.text


def generate_word_memory_tip(word):
    """
    生成单词记忆提示的函数。

    参数：
    word (str)：需要生成记忆提示的单词。

    返回值：
    str：生成的记忆提示文本。
    """
    parameters = {
        "candidate_count": 1,
        "max_output_tokens": 120,
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 40,
    }
    model = TextGenerationModel.from_pretrained("text-bison")
    response = model.predict(
        f"""您是一名英语单词记忆专家，擅长根据单词特点指导记忆方法。请您为以下单词提供记忆提示，
备注：
1. 不要单独再显示单词、词性、释义；
2. 有必要时，请使用换行符；

输出"markdown"格式。

单词："{word}"
""",
        **parameters,
    )
    return response.text


def generate_english_topics(target, category, level, n=5):
    parameters = {
        "candidate_count": 1,
        "max_output_tokens": 512,
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 40,
    }
    model = TextGenerationModel.from_pretrained("text-bison")
    response = model.predict(
        f"""在指定领域内，生成{n}个相关的话题，用英语输出。
学生当前英语水平：CEFR 分级 {level}
领域：{category}
目标：{target}
要求：
1. 话题要广泛；
2. 话题要贴近学生的实际生活，让学生有话可说；
3. 话题要有一定的开放性，让学生有充分的发挥空间；
4. 避免过于简单或复杂的话题；
5. 避免过于敏感或有争议的话题；
6. 话题的用词要根据学生的英语水平进行选择，以确保学生能够理解。
""",
        **parameters,
    )
    # 输出列表
    return response.text.splitlines()


def generate_short_discussion(topic, level):
    parameters = {
        "candidate_count": 1,
        "max_output_tokens": 1024,
        "temperature": 0.8,
        "top_p": 0.8,
        "top_k": 40,
    }
    model = TextGenerationModel.from_pretrained("text-bison")
    response = model.predict(
        f"""You are a student with CEFR English level {level}. Please complete the following topic discussion, no less than 150 words, no more than 300 words. No less than three sentences.
    topic:{topic}

    Require:
    1. The language used should be appropriate for the students' current level of proficiency.
    2. Start a discussion around the topic
    3. Express ideas clearly and make the discussion logical.
    4. Correct grammar and smooth wording""",
        **parameters,
    )
    return response.text


def generate_word_test(word, level):
    parameters = {
        "candidate_count": 1,
        "max_output_tokens": 1024,
        "temperature": 0.9,
        "top_p": 0.8,
        "top_k": 40,
    }
    model = TextGenerationModel.from_pretrained("text-bison")
    response = model.predict(
        f"""您是一名英语老师，精通设计出题考核学生是否掌握单词释义。为以下单词出题考察学生是否理解单词词义：
    单词:{word}
    学生当前水平:CEFR {level}

    要求：
    - 题目、选项要与学生当前水平相适应。
    - 问题应该清晰明确，让学生能理解题意。
    - 只有四个选项，并且只有唯一正确答案。
    - 选项应该合理，与问题相关。选项可以是同义词、反义词、近义词、同类此、异类词等。
    - 答案应该是唯一正确的，并且问题与选项保持一致。
    - 选项之间应该没有重叠，具有一定的逻辑关系，选项应该能够引导学生思考，并帮助他们找到正确答案。
    - 答案应随机分布，不要集中在某个选项。
    - 解释应该详细，说明答案是正确的理由。
    - 输出内容包括：\"question\"、\"options、\"answer\"、\"explanation\"。
    - 以json格式输出。
    {QUESTION_OPTIONS_AND_INSTRUCTIONS}
    """,
        **parameters,
    )
    return json.loads(response.text.replace("```json", "").replace("```", ""))


def remove_empty_lines(text):
    lines = text.split("\n")
    non_empty_lines = [line for line in lines if line.strip() != ""]
    text_without_empty_lines = "\n".join(non_empty_lines)
    return text_without_empty_lines


def generate_dialogue(style, scene, topic, level):
    parameters = {
        "candidate_count": 1,
        "max_output_tokens": 1024,
        "temperature": 0.8,
        "top_p": 0.8,
        "top_k": 40,
    }
    model = TextGenerationModel.from_pretrained("text-bison")
    prompt = f"""请生成一段英语对话材料，用于模拟{style}英语听力考试。对话场景是{scene}，主题是{topic}。\
    要求：\
    1. 难度适应于英语能力水平为CEFR {level}的学生。\
    2. 对话应使用口语化的词汇、句子、语法结构和表达方式。\
    3. 二人对话形式，每人至少三句话。\
    4. 使用英语输出。"""
    response = model.predict(prompt, **parameters)
    return remove_empty_lines(response.text)
