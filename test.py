import streamlit as st
from streamlit_mic_recorder import mic_recorder
from mypylib.azure_pronunciation_assessment import (
    get_syllable_durations_and_offsets,
    pronunciation_assessment_from_stream,
    # pronunciation_assessment_with_content_assessment_from_stream,
)
from mypylib.utils import calculate_audio_duration
from mypylib.word_utils import audio_autoplay_elem
import streamlit.components.v1 as components
import time


st.set_page_config(
    page_title="测试",
    page_icon=":bust_in_silhouette:",
    layout="wide",
)

content_assessment = st.checkbox("是否进行内容评估", True, key="show_code")

topic = st.text_input("Topic", "Describe your favorite animal")

reference_text = st.text_area(
    "Reference text",
    "My favorite animal is the cat. Cats are independent, playful, and affectionate creatures. They are also very clean and low-maintenance. I love the way they purr and rub against me. I also love how they can be so playful and mischievous at times. I think cats make great companions. ",
)

cols = st.columns(8)

audio_key = "mic_recorder"
audio_session_output_key = f"{audio_key}_output"

if "pronunciation_assessment" not in st.session_state:
    st.session_state["pronunciation_assessment"] = None


with cols[0]:
    audio_info = mic_recorder(start_prompt="录音[⏸️]", stop_prompt="停止[🔴]", key=audio_key)

ps_btn = cols[1].button("评分[▶️]", disabled=not audio_info, key="ps_btn")
play_btn = cols[2].button("回放[▶️]", disabled=not audio_info, key="play_btn")
err_btn = cols[3].button("错误[▶️]", disabled=not audio_info, key="err_btn")


if ps_btn:
    st.session_state["pronunciation_assessment"] = pronunciation_assessment_from_stream(
        audio_info,
        st.secrets,
        topic if content_assessment else None,
        reference_text,
        language="en-US",
    )
    st.write(st.session_state["pronunciation_assessment"])

if audio_info and play_btn:
    auto_html = audio_autoplay_elem(audio_info["bytes"], fmt="wav")
    components.html(auto_html)

    duration = calculate_audio_duration(
        audio_info["bytes"], audio_info["sample_rate"], audio_info["sample_width"]
    )
    st.write(f"duration: {duration}")
    time.sleep(duration)

    # st.write(output)


if err_btn:
    # 打印得分
    st.write(st.session_state["pronunciation_assessment"]["error_counts"])
    if content_assessment:
        st.write(st.session_state["pronunciation_assessment"]["content_result"])
    words = st.session_state["pronunciation_assessment"]["recognized_words"]
    for w in words:
        st.write(w.word, w.error_type)
