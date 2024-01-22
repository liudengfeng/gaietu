import streamlit as st
from streamlit_mic_recorder import mic_recorder
from mypylib.azure_pronunciation_assessment import pronunciation_assessment_from_stream
from mypylib.word_utils import audio_autoplay_elem
import streamlit.components.v1 as components
import time


def calculate_audio_duration(
    audio_bytes: bytes, sample_rate: int, sample_width: int
) -> float:
    total_samples = len(audio_bytes) / sample_width
    duration = total_samples / sample_rate
    return duration


reference_text = st.text_input("Reference text", "What's the weather like?")

cols = st.columns(8)

audio_key = "mic_recorder"
audio_session_output_key = f"{audio_key}_output"

with cols[0]:
    audio_info = mic_recorder(start_prompt="录音[🔴]", stop_prompt="停止[⏹️]", key=audio_key)

play_btn = cols[1].button("回放[▶️]")

if audio_info and play_btn:
    auto_html = audio_autoplay_elem(audio_info["bytes"], fmt="wav")
    components.html(auto_html)

    duration = calculate_audio_duration(
        audio_info["bytes"], audio_info["sample_rate"], audio_info["sample_width"]
    )
    st.write(f"录音时长: {duration:.2f}秒")

if audio_info:
    st.audio(audio_info["bytes"], format="audio/wav")
