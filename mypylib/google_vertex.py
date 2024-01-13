import streamlit as st
import vertexai
from vertexai.preview.language_models import TextGenerationModel

vertexai.init(
    project=st.secrets["Google"]["PROJECT_ID"],
    location=st.secrets["Google"]["LOCATION"],
)

# 屏蔽大部分
SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_LOW_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_LOW_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_LOW_AND_ABOVE"},
]


@st.cache_resource
def get_generation_model():
    model = TextGenerationModel.from_pretrained("text-bison")
    return model


@st.cache_resource
def get_chat_model():
    model = TextGenerationModel.from_pretrained("chat-bison")
    return model


def get_text_generation(st, prompt, **parameters):
    model = get_generation_model()
    response = model.predict(prompt=prompt, **parameters)
    output = response.text
    st.session_state.current_token_count = model.count_tokens(
        prompt + output
    ).total_billable_characters
    st.session_state.total_token_count += st.session_state.current_token_count
    return output


def generate_sub_scenes(theme_scene, st):
    prompt = f"""对以下场景，生成完整20个相关对话场景子类别，以python list格式输出。
场景：
{theme_scene}"""
    parameters = {
        "temperature": 0.9,
        "candidate_count": 1,
        "max_output_tokens": 1024,
    }
    output = get_text_generation(st, prompt, **parameters)
    return eval(output)
