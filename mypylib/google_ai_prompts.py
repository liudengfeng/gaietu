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

- Content (Total: 40 points)
    - Consistency between the theme of the title and the content of the article (Total: 10 points):
        - Completely conforms to the meaning of the question, understands and answers the question accurately, score: 10.
        - Basically meets the meaning of the question, but there are a few deviations from the question or missing key points. Score: 5-8.
        - Deviates from the meaning of the question and fails to answer the question completely, score: 0-4.
    - Complete content (Total: 10 points):
        - Covers all key points and has substantial content. Score: 10.
        - A few key points are missing, but the content is basically complete. Score: 5-8.
        - Missing important points and incomplete content, score: 0-4.
    - Clear point of view (Total: 10 points):
        - The point is clear and the argument is sufficient. Score: 10.
        - The point of view is basically clear, but the argument is insufficient. Score: 5-8.
        - Vague views and insufficient arguments, score: 0-4.
    - Logic (Total: 10 points):
        - Clear thinking, reasonable structure, rigorous logic, score: 10.
        - The ideas are basically clear, the structure is slightly loose, and the logic occasionally has flaws. Score: 5-8.
        - The ideas are confusing, the structure is unreasonable, and there are many logical errors. Score: 0-4.
- Language (Total: 30 points)
    - Vocabulary (Total: 10 points):
        - Rich vocabulary, appropriate use, no obvious errors, score: 10.
        - Vocabulary basically meets the requirements. Occasionally there are errors. Score: 5-8.
        - Poor vocabulary and many errors, which affects understanding. Score: 0-4.
    - Grammar (Total: 10 points):
        - The grammar is accurate, the sentence structure is complete, and there are no obvious errors. Score: 10.
        - Grammar is basically accurate, with occasional errors, which do not affect understanding. Score: 5-8.
        - There are many grammatical errors, which affect understanding. Score: 0-4.
    - Fluency (Total: 10 points):
        - The sentences are fluent, the expression is natural, and it is easy to understand. Score: 10.
        - The sentence structure is a bit stiff and the expression is not natural enough. Score: 5-8.
        - The sentences are not fluent and the expression is unnatural, which affects understanding. Score: 0-4.
- Structure (Total: 20 points)
    - Paragraph division (Total: 10 points):
        - The paragraphs are reasonably divided and hierarchical. Score: 10.
        - The division of paragraphs is not reasonable enough, but the hierarchy is basically clear. Score: 5-8.
        - The division of paragraphs is unreasonable and the hierarchy is confusing. Score: 0-4.
    - Connection means (Total: 10 points):
        - The cohesion means are rich, used appropriately, and the whole text is coherent. Score: 10.
        - The connection methods basically meet the requirements, with occasional stiffness. Score: 5-8.
        - Lack of cohesion means, the whole text is incoherent, affecting understanding, score: 0-4.
- Others (Total: 10 points)
    - Innovation (Total: 5 points):
        - Novel and creative ideas, score: 5.
        - The viewpoint is basically novel and has a certain degree of creativity. Score: 3-4.
        - The ideas lack new ideas and have no obvious creativity. Score: 0-2.
    - Language style (Total: 5 points):
        - The language style is vivid and contagious. Score: 5.
        - The language style is basically vivid and has a certain appeal. Score: 3-4.
        - The language style is bland and lacks appeal. Score: 0-2.

Step by step:
- For each criterion, allocate scores based on the comprehensive grading rubric provided.
- Compile scoring records, each record should be a dictionary with keys representing the specific criterion, the corresponding score, and a brief justification (in Markdown format). The output should be a list of these dictionaries.
- Furnish a comprehensive evaluation (in Markdown format) of the composition, highlighting its merits and identifying areas that require enhancement.
- Ultimately, form a dictionary that includes the review and a list of scoring records.
- Output in JSON.

composition:

{composition}
"""
