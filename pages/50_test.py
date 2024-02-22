import base64
import logging
from operator import itemgetter
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate
import streamlit as st

from langchain_community.callbacks import StreamlitCallbackHandler

# from langchain.callbacks import StreamlitCallbackHandler
from langchain.prompts import PromptTemplate
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import MathpixPDFLoader, WebBaseLoader
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.vectorstores import FAISS
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_google_vertexai import (
    ChatVertexAI,
    HarmBlockThreshold,
    HarmCategory,
    VertexAI,
)
from langchain_core.runnables import RunnableLambda

from vertexai.preview.generative_models import Image
import json
from menu import menu
from mypylib.st_helper import add_exercises_to_db, check_access, configure_google_apis
from mypylib.st_setting import general_config

logger = logging.getLogger("streamlit")
CURRENT_CWD: Path = Path(__file__).parent.parent
IMAGE_DIR: Path = CURRENT_CWD / "resource/multimodal"


st.set_page_config(
    page_title="人工智能",
    page_icon=":toolbox:",
    layout="wide",
)
menu()
check_access(False)
configure_google_apis()
general_config()
add_exercises_to_db()


# region 函数


def parse_or_fix(text: str, config: RunnableConfig):
    fixing_chain = (
        ChatPromptTemplate.from_template(
            "Fix the following text:\n\n```text\n{input}\n```\nError: {error}"
            " Don't narrate, just respond with the fixed data."
        )
        | ChatVertexAI(model_name="gemini-pro")
        | StrOutputParser()
    )
    for _ in range(3):
        try:
            return json.loads(text)
        except Exception as e:
            text = fixing_chain.invoke({"input": text, "error": e}, config)
    return "Failed to parse"


def image_to_dict(image_path):
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    image_message = {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}"
        },
    }

    return image_message


# endregion


# llm = VertexAI(model_name="gemini-pro-vision")
# llm = VertexAI(model_name="gemini-pro")

# st_cb = StreamlitCallbackHandler(st.container(), expand_new_thoughts=False)

question = """The cafeteria had 23 apples.
If they used 20 to make lunch and bought 6 more, how many apples do they have?"""

context = """Answer questions showing the full math and reasoning.
Follow the pattern in the example.
"""

one_shot_exemplar = """Example Q: Roger has 5 tennis balls. He buys 2 more cans of tennis balls.
Each can has 3 tennis balls. How many tennis balls does he have now?
A: Roger started with 5 balls. 2 cans of 3 tennis balls
each is 6 tennis balls. 5 + 6 = 11.
The answer is 11.

Q: """


if st.button("执行"):
    # text_message = {
    #     "type": "text",
    #     "text": "What is shown in this image?",
    # }
    # img_path = IMAGE_DIR / "math/高中/定积分.png"
    # i = Image.load_from_file(str(img_path))
    # st.image(str(img_path), caption="定积分", use_column_width=True)
    # message = HumanMessage(content=[text_message, image_to_dict(str(img_path))])
    # output = llm([message])
    # planner = (
    #     PromptTemplate.from_template(context + one_shot_exemplar + " {input}")
    #     # | VertexAI(model_name="gemini-pro", callbacks=[st_cb])
    #     | VertexAI(model_name="gemini-pro")
    #     | StrOutputParser()
    #     | {"base_response": RunnablePassthrough()}
    # )

    # answer_1 = (
    #     PromptTemplate.from_template("{base_response} A: 33")
    #     | VertexAI(
    #         model_name="gemini-pro",
    #         temperature=0,
    #         max_output_tokens=400,
    #         # callbacks=[st_cb],
    #     )
    #     | StrOutputParser()
    # )

    # answer_2 = (
    #     PromptTemplate.from_template("{base_response} A:")
    #     | VertexAI(
    #         model_name="gemini-pro",
    #         temperature=0.1,
    #         max_output_tokens=400,
    #         # callbacks=[st_cb],
    #     )
    #     | StrOutputParser()
    # )

    # answer_3 = (
    #     PromptTemplate.from_template("{base_response} A:")
    #     | VertexAI(
    #         model_name="gemini-pro",
    #         temperature=0.7,
    #         max_output_tokens=400,
    #         # callbacks=[st_cb],
    #     )
    #     | StrOutputParser()
    # )

    # final_responder = (
    #     PromptTemplate.from_template(
    #         "Output all the final results in this markdown format: Result 1: {results_1} \n Result 2:{results_2} \n Result 3: {results_3}"
    #     )
    #     # | VertexAI(model_name="gemini-pro", max_output_tokens=1024, callbacks=[st_cb])
    #     | VertexAI(model_name="gemini-pro", max_output_tokens=1024)
    #     | StrOutputParser()
    # )

    # chain = (
    #     planner
    #     | {
    #         "results_1": answer_1,
    #         "results_2": answer_2,
    #         "results_3": answer_3,
    #         "original_response": itemgetter("base_response"),
    #     }
    #     | final_responder
    # )

    # answers = chain.invoke({"input": question})

    with StreamlitCallbackHandler(st.container(), expand_new_thoughts=False) as st_cb:
        output = RunnableLambda(parse_or_fix).invoke(
            "{foo: bar}", {"tags": ["my-tag"], "callbacks": [st_cb]}
        )
        st.write(output)
        st.write(st_cb)
