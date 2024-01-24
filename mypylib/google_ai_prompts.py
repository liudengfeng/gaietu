SINGLE_CHOICE_QUESTION = """
Single Choice Question Guidelines:
- The question should be clear, concise, and focused. It should accurately assess the knowledge or skills of the respondent, avoiding ambiguity, overly broad or difficult-to-understand phrasing.
- The options should include one correct answer and three plausible distractors, totaling to four options. The arrangement of options should be logical, avoiding any bias that could influence the respondent's choice.
- There should only be one correct answer for a single-choice question. If two or more options could be correct, the question needs to be redesigned. The correct answer should be output as the identifier of the correct option, such as 'A'.
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
