import json
import random
import time

import google.generativeai as palm
from google.api_core import retry

model = "models/text-bison-001"


@retry.Retry()
def generate_text(*args, **kwargs):
    return palm.generate_text(*args, **kwargs)


@retry.Retry()
def chat(*args, **kwargs):
    return palm.chat(*args, **kwargs)


vocabulary_comprehension_defaults = {
    "model": model,
    "temperature": 0.25,
    "candidate_count": 4,
    "top_k": 40,
    "top_p": 0.95,
    "max_output_tokens": 300,
    "stop_sequences": [],
    "safety_settings": [
        {"category": "HARM_CATEGORY_DEROGATORY", "threshold": 1},
        {"category": "HARM_CATEGORY_TOXICITY", "threshold": 1},
        {"category": "HARM_CATEGORY_VIOLENCE", "threshold": 2},
        {"category": "HARM_CATEGORY_SEXUAL", "threshold": 2},
        {"category": "HARM_CATEGORY_MEDICAL", "threshold": 2},
        {"category": "HARM_CATEGORY_DANGEROUS", "threshold": 2},
    ],
}

# 单词理解四选一出题模板
vocabulary_comprehension_template = """
Designing Effective Test Questions for English Word Assessment

Crafting effective test questions to assess students' grasp of English vocabulary is crucial for evaluating their language proficiency. Well-structured test questions should not only gauge students' understanding of word meanings but also their ability to apply these words appropriately in context.

Question Structure and Components

A comprehensive test question typically comprises the following components:
Stem: The stem, also known as the question prompt, presents the context or scenario in which the target word is used. It should be clear, concise, and engaging, providing students with the necessary information to make an informed decision.
Options: Four options are presented, each representing a possible answer to the question. The correct answer, labeled with the letter A, B, C, or D, should be the most appropriate choice based on the context and usage of the target word. The remaining options, known as distractors, should be plausible yet incorrect, allowing students to differentiate between the correct and incorrect choices.
Answer Key: The answer key clearly indicates the correct option (A, B, C, or D) that corresponds to the most appropriate answer.
Explanation: The explanation section provides a detailed justification for selecting the correct answer while explaining why the other options are incorrect. It should be clear, concise, and informative, helping students not only identify the correct answer but also understand the nuances of word usage.

Question Design Principles

To create effective test questions, consider the following principles:
Context Applicability: Ensure the chosen words and sentences resonate in real-life situations, avoiding contrived or unrealistic contexts. This facilitates the assessment of students' ability to apply words appropriately in practical settings.
Difficulty Balance: Maintain a moderate level of difficulty, avoiding questions that are either too easy or too complex. This can be achieved through pre-testing on students to gauge their understanding.
Clarity of Explanation: The explanation section should clearly elucidate the correctness of the chosen answer and the incorrectness of the other options. This helps students learn from their mistakes and improve their understanding of word usage.
Distractor Design: Craft distractors that share some resemblance to the correct answer, preventing students from selecting the right choice through mere pattern matching. This encourages a genuine understanding of word meanings.
Language Style Consistency: Maintain a consistent language style throughout the question stem, options, and explanation to avoid unnecessary confusion. This ensures clarity and focus on the target word's usage.
Logical Connection: Establish a clear logical connection between the question stem and the options. This allows students to make informed choices based on their understanding of the target word's meaning and usage.
Question Clarity: Ensure the question stem is clear, concise, and unambiguous. Avoid vague or confusing wording that may lead to misinterpretations.
Option Differentiation: The four options should be distinct and well-differentiated, allowing students to identify the correct answer with reasonable certainty. Avoid options that are too similar or overlap in meaning.
Vocabulary Level: Tailor the question's vocabulary level to align with students' current proficiency. Avoid using words that are too advanced or unfamiliar to the target audience.
Answer Randomization: To prevent students from relying on predictable patterns, the correct answer should be randomly distributed among the four options (A, B, C, or D) with equal probability.

Question Types

Test questions can be formulated from various perspectives, each focusing on a specific aspect of word usage:
Context Fill-in: Construct a sentence or paragraph with a missing word, asking students to insert the accurate term based on the context. This assesses students' ability to understand word meanings and apply them in context.
Synonyms or Antonyms: Provide a word and instruct students to choose a term with a similar or opposite meaning. This evaluates students' grasp of word relationships and their ability to discern subtle differences in meaning.
Fixed Collocations: Offer a word and prompt students to select another word frequently associated with it. This assesses students' knowledge of common word combinations and their ability to use language naturally.

Negative cases:

case 1:
The state is the capital of the country.
A. city
B. country
C. government
D. province
Reason:The question suffers from vague wording, making it challenging for students to accurately interpret the entity in question. Lack of context may lead students to guess the answer rather than make an informed choice.
Correction suggestions:Provide more context to enable students to make a more accurate choice. For example, describe some features or functions of the region to help students better understand the entity being referred to.

case 2:
The main reason for the delay was the bad weather. The delay was caused by the bad weather. The delay was due to the bad weather. The delay was because of the bad weather. Which sentence is grammatically correct?
A.
B.
C.
D.
Reason:All options are grammatically correct, and there isn't enough information or context provided to specify one option as a better choice. Students may feel confused as they cannot determine the criteria on which to base the correct answer.
Correction suggestions:Provide more guidance or context to help students make a more specific choice. For example, ask students to choose the option that most accurately expresses the reason for the delay or provide more information about the specific situation to assist students in making a more informed choice.

In each section, use single or double quotation marks as appropriate, without using HTML entity encoding.The final output should be a JSON object.

Examples:
"question": "The two countries have a corresponding relationship. What is the closest synonym for 'corresponding' in this context?",
"options": [
  "A. matching",
  "B. similar but not identical",
  "C. sharing common characteristics",
  "D. having opposite qualities"
],
"answer": "A",
"explanation": "The term 'corresponding' implies a matching relationship. 'Matching' is the closest synonym to 'corresponding.' Options B, C, and D are not the best fits as they convey different nuances of similarity or dissimilarity."

"question": "The smart boy got good grades in school. What is another word for 'smart'?"
"options": [
"A. dumb",
"B. clever",
"C. intelligent",
"D. stupid"
],
"answer": "C",
"explanation": "The word 'smart' is a synonym for 'intelligent.' Options A, B, and D are not synonyms for 'smart.'"

Current student level: CEFR {level}
Please design a question for the word: {word}
"""


def _gen_vocabulary_comprehension_test(word: str, level: str) -> str:
    """
    生成词汇理解测试的函数。

    Args:
    word: str，要测试的单词。
    level: str，CEFR分级表示的单词难度级别。

    Returns:
    dic，测试结果的JSON字符串解析为字典，键分别为："question", "options", "answer", and "explanation"。
    """
    prompt = vocabulary_comprehension_template.format(word=word, level=level)
    # get alternate model responses
    completion = generate_text(
        **vocabulary_comprehension_defaults,
        prompt=prompt,
    )
    candidates = completion.candidates
    result = random.choice(candidates)["output"]
    return json.loads(result.replace("```json", "").replace("```", ""))


def _is_valid_completion(value):
    # TODO:待总结
    keys = ["question", "options", "answer", "explanation"]
    is_valid = all([k in value for k in keys])
    # 四个选项除标签外不应重复
    opts = [opt.split(".", maxsplit=1)[1] for opt in value["options"]]
    is_valid &= len(set(opts)) == 4
    return is_valid


def gen_vocabulary_comprehension_test(word: str, level: str):
    n = 0
    max_try = 5
    while n < max_try:
        try:
            value = _gen_vocabulary_comprehension_test(word, level)
            if _is_valid_completion(value):
                return value
        except json.JSONDecodeError as e:
            # 未能解析为JSON，说明生成的结果无效
            pass
        except Exception as e:
            raise e
        n += 1
        time.sleep(0.5)


irregular_forms_of_a_word_defaults = {
    "model": model,
    "temperature": 0,
    "candidate_count": 1,
    "top_k": 40,
    "top_p": 0.9,
    "max_output_tokens": 400,
    "stop_sequences": [],
    "safety_settings": [
        {"category": "HARM_CATEGORY_DEROGATORY", "threshold": 1},
        {"category": "HARM_CATEGORY_TOXICITY", "threshold": 1},
        {"category": "HARM_CATEGORY_VIOLENCE", "threshold": 2},
        {"category": "HARM_CATEGORY_SEXUAL", "threshold": 2},
        {"category": "HARM_CATEGORY_MEDICAL", "threshold": 2},
        {"category": "HARM_CATEGORY_DANGEROUS", "threshold": 2},
    ],
}


def get_irregular_forms_of_a_word(word: str) -> dict:
    """
    获取单词的不规则变形。

    Args:
    word: str，要获取的单词。

    Returns:
    dic，单词的不规则变形，键分别为："noun", "adjective", "adverb", "verb"。
    """
    prompt = f"""Your are a professional dictionary and will not provide false information. You will answer all questions honestly and to the best of your ability.
To provide the irregular forms of a word, You will search for parts of speech of the word that are involved in the following steps and then check the irregular forms for each part of speech. You will follow these steps:
1. For nouns, if there is an irregular plural form, the key will be "plural" and the value will be the irregular plural form.
2. For adjectives or adverbs, the keys will be "comparative" and "superlative", and the values will be the comparative and superlative forms, respectively.
3. For verbs, the keys will be "past tense" and "past participle", and the values will be the irregular past tense and past participle forms, respectively.
You will store the irregular forms of each word in a dictionary, with the word's title as the key and the irregular form as the value. You will then merge all of the dictionaries of irregular forms into a single dictionary, with the part of speech as the key. Finally, output the dictionary in JSON format.

word:"{word}"

"""
    completion = generate_text(
        **irregular_forms_of_a_word_defaults,
        prompt=prompt,
    )
    return json.loads(completion.result.replace("```json", "").replace("```", ""))


def lemmatize(word: str):
    """
    Lemmatizes a word using a language model.

    Args:
        word (str): The word to be lemmatized.

    Returns:
        str: The lemmatized form of the word.
    """

    # 当输入的单词是短语时，不进行词形还原
    if len(word.split(" ")) > 1:
        return word
    defaults = {
        "model": model,
        "temperature": 0,
        "candidate_count": 1,
        "top_k": 40,
        "top_p": 0.95,
        "max_output_tokens": 50,
        "stop_sequences": [],
        "safety_settings": [
            {"category": "HARM_CATEGORY_DEROGATORY", "threshold": 1},
            {"category": "HARM_CATEGORY_TOXICITY", "threshold": 1},
            {"category": "HARM_CATEGORY_VIOLENCE", "threshold": 2},
            {"category": "HARM_CATEGORY_SEXUAL", "threshold": 2},
            {"category": "HARM_CATEGORY_MEDICAL", "threshold": 2},
            {"category": "HARM_CATEGORY_DANGEROUS", "threshold": 2},
        ],
    }
    prompt = f"""You are an expert in English vocabulary. Please answer honestly: What is the root of the following words?
word:{word}"""
    completion = generate_text(
        **defaults,
        prompt=prompt,
    )
    return completion.result


def lookup(word: str):
    """
    Looks up a word using a language model.

    Args:
        word (str): The word to be looked up.

    Returns:
        str: The definition of the word.
    """
    defaults = {
        "model": model,
        "temperature": 0.2,
        "candidate_count": 1,
        "top_k": 40,
        "top_p": 0.5,
        "max_output_tokens": 1024,
        "stop_sequences": [],
        "safety_settings": [
            {"category": "HARM_CATEGORY_DEROGATORY", "threshold": 1},
            {"category": "HARM_CATEGORY_TOXICITY", "threshold": 1},
            {"category": "HARM_CATEGORY_VIOLENCE", "threshold": 2},
            {"category": "HARM_CATEGORY_SEXUAL", "threshold": 2},
            {"category": "HARM_CATEGORY_MEDICAL", "threshold": 2},
            {"category": "HARM_CATEGORY_DANGEROUS", "threshold": 2},
        ],
    }
    prompt = f"""You are an English vocabulary expert, please answer honestly. Please provide the following word definitions and example dictionaries with part-of-speech as the key, content as &quot;meaning&quot;, and &quot;examples&quot; as the key. Use at least three examples and no more than five, and try to preserve the variety of examples. Output in json format.
word:{word}"""
    completion = generate_text(**defaults, prompt=prompt)
    return json.loads(completion.result.replace("```json", "").replace("```", ""))
