SINGLE_CHOICE_QUESTION = """
Single Choice Question Guidelines:
- The question should be clear, concise, and focused. It should accurately assess the knowledge or skills of the respondent, avoiding ambiguity, overly broad or difficult-to-understand phrasing.
- The options should include one correct answer and three plausible distractors, totaling to four options. The arrangement of options should be logical, avoiding any bias that could influence the respondent's choice.
- For a single-choice question, there should only be one correct answer. If two or more options could potentially be correct, the question needs to be restructured. The correct answer should be output as the identifier of the correct option, such as 'A', 'B', 'C', or 'D'. 
- The explanation should be detailed, clearly explaining why the correct answer is indeed correct.
- Each question should be output as a dictionary with 'question', 'options', 'answer', and 'explanation' as keys.
- The 'options' should be a list of strings, each string representing an option.
- Each option should be prefixed with a capital letter (A, B, C, D) followed by a '. '.
- Options should not include "All of the above" or similar choices, as this could lead to ambiguity and multiple correct answers.
- Questions should be grounded in generally accepted facts or consensus. Avoid formulating questions that are based on personal preferences, opinions, subjective circumstances, or feelings. If a question does involve personal preferences or subjective circumstances, it is essential to provide a clear context that transforms the preference or circumstance into a fact within the given situation.
"""

MULTIPLE_CHOICE_QUESTION = """
Multiple Choice Question Guidelines:
- Question should be clear, concise, and focused. Question should accurately assess students' knowledge or skills, avoiding ambiguous, too broad, or difficult-to-understand questions.
- Options should include at least two correct answers and several plausible distractors. The arrangement of options on the answer sheet should be reasonable, avoiding the influence of answer position on students' answers.
- The answer should include all correct options. There can be more than one answer for a multiple-choice question. If only one option is correct, the question is not designed reasonably. The answer should be output as a list of identifiers of the correct options, such as ['A', 'C'].
- Explanation should be detailed, clearly explaining why these answers are correct.
- Each question should be output as a dictionary with 'question', 'options', 'answer', and 'explanation' as keys.
- The 'options' should be a list of strings, each string representing an option.
- Each option should be prefixed with a capital letter (A, B, C, D) followed by a '. '.
"""

READING_COMPREHENSION_LOGIC_QUESTION = """
Reading Comprehension Logic Question Guidelines:
- The question stem should be related to the content of the article. The knowledge point or ability to be tested by the question stem must be reflected in the article.
- The question stem should be clear and concise. The question stem should be able to accurately test students' knowledge or abilities, avoiding ambiguous, too broad, or difficult-to-understand questions.
- Options should be comprehensive and reasonable. Options should cover all possible correct answers, and the arrangement of options on the answer sheet should be reasonable, avoiding the influence of answer position on students' answers.
- The answer should be the only correct one. There is only one answer for a reading comprehension logic question. If two or more options are correct, the question is not designed reasonably. The answer should be output as the identifier of the correct option, such as 'A'.
- Use the logical relationships in the article. The logical relationships in the article, such as cause and effect, progression, contrast, etc., can provide clues for designing reading comprehension logic questions.
- Use the factual information in the article. The factual information in the article, such as characters, events, time, place, etc., can also provide clues for designing reading comprehension logic questions.
- Use the viewpoints and attitudes in the article. The viewpoints and attitudes in the article can also provide clues for designing reading comprehension logic questions.
- Each question should be output as a dictionary with 'question', 'options', 'answer', and 'explanation' as keys.
"""

READING_COMPREHENSION_FILL_IN_THE_BLANK_QUESTION = """
Reading Comprehension Fill in the Blank Question Guidelines:
- Determine the position of the blank according to the context. The position of the blank should be able to test students' understanding of the context, avoiding too random positions.
- Determine the content of the blank according to the context. The content of the blank should be able to complete the meaning of the sentence or paragraph, avoiding too simple or too complex content.
- Determine the options for the blank according to the context. The options for the blank should conform to the meaning of the context, avoiding too vague or biased options.
- Each question should be output as a dictionary with 'question', 'answer', and 'explanation' as keys.
"""


ENGLISH_WRITING_SCORING_TEMPLATE = """
As an expert in English composition instruction, it is your duty to evaluate your students' writing assignments in accordance with the subsequent grading criteria.

# Grading Criteria

- Scoring Overview
    - Each criterion will be scored individually, based on specific circumstances.
    - The total score is 100 points, divided among various categories.
    - The detailed breakdown of scores for each category is as follows:

- Content (Total: 45 points)
    - Relevance to Theme (Total: 15 points):
        - Completely adheres to the assigned theme, explores it thoughtfully, and answers the prompt fully: 15 points.
        - Partially addresses the theme, may deviate slightly or miss minor points: 10-12 points.
        - Deviates significantly from the theme or fails to answer the prompt adequately: 0-8 points.
    - Completeness (Total: 10 points):
        - Covers all key points and provides substantial content relevant to the theme: 10 points.
        - Misses a few key points but maintains overall completeness: 7-9 points.
        - Lacks important points or content is incomplete: 0-6 points.
    - Clarity and Cohesion (Total: 10 points):
        - The point of view is clear, arguments are well-developed, and the essay flows smoothly: 10 points.
        - Point of view is somewhat clear, arguments might need improvement, and the essay has minor transitions: 7-9 points.
        - Vague views, underdeveloped arguments, and lack of clear transitions significantly hinder understanding: 0-6 points.
    - Body Restrictions (Total: 10 points):
        - Adheres to all specified body restrictions (e.g., number of paragraphs, specific points to cover): 10 points.
        - Minor deviations from or incomplete fulfillment of body restrictions: 7-9 points.
        - Significant deviations from or major inconsistencies with body restrictions: 0-6 points.
- Language (Total: 30 points)

    -Vocabulary (Total: 10 points):
        - Rich and varied vocabulary used appropriately: 10 points.
        - Meets vocabulary requirements with occasional errors: 7-9 points.
        - Poor vocabulary significantly affecting understanding: 0-6 points.
    - Grammar (Total: 10 points):
        - Grammatically accurate with no major errors: 10 points.
        - Occasional grammatical errors that do not impede understanding: 7-9 points.
        - Frequent grammatical errors affecting understanding: 0-6 points.
    - Fluency (Total: 10 points):
        - Sentences are clear, natural, and engaging: 10 points.
        - Minor awkwardness or stiffness in sentence structure or expression: 7-9 points.
        - Sentences lack fluency and clarity, negatively impacting understanding: 0-6 points.
- Structure (Total: 20 points)

    - Organization (Total: 10 points):
        - Logical and well-organized structure with clear introduction, body paragraphs, and conclusion: 10 points.
        - Somewhat organized structure but may lack clarity or transitions: 7-9 points.
        - Unorganized structure significantly impacting coherence and flow: 0-6 points.
    - Cohesion (Total: 10 points):
        - Effective use of transition words and phrases to connect ideas: 10 points.
        - Some awkward transitions but overall coherence maintained: 7-9 points.
        - Lack of clear transitions impacting understanding and flow: 0-6 points.
- Bonus (Total: 5 points)
    
    - Title (Total: 5 points):
        - Captivating and relevant to the content: 5 points.
        - Somewhat relevant or informative: 3-4 points.
        - Unclear or unrelated to the content: 0-2 points.

Step by step:
- For each sub-criterion under each main criterion, allocate scores based on the detailed grading rubric provided. Each sub-criterion should be scored separately, and the scores for the sub-criteria under a main criterion should be combined to form the total score for that main criterion.
- Compile scoring records, each record should be a dictionary with keys representing the specific criterion, the corresponding score, and a brief justification (in Markdown format). The output should be a list of these dictionaries.
- Furnish a comprehensive evaluation (in Markdown format) of the composition, highlighting its merits and identifying areas that require enhancement.
- Ultimately, form a dictionary that includes the review and a list of scoring records.
- Output in JSON.

composition:

{composition}
"""

CEFR_WRITING_EXAM_TEMPLATE = """
As a CEFR writing examiner, you are tasked with creating a test. Please note that you are the examiner, not the examinee, and your role is to set the questions, not to answer them. When designing the test, you should take into account the student's current level in all aspects, including the design of the background information, the formulation of the exam requirements, and the setting of the minimum word count.

The student's current level is: CEFR {student_level}
Topic: {exam_topic}

Requirements:
1. Design detailed background information based on the topic. The complexity of the background information should match the student's current level.
2. Propose at least three specific exam requirements. 
3. Set a minimum word count that is appropriate for the student's current level.
4. Output in an appropriate Markdown format.
"""
