import streamlit as st
from streamlit_mic_recorder import mic_recorder
from mypylib.azure_pronunciation_assessment import pronunciation_assessment_from_stream

reference_text = st.text_input("Reference text", "What's the weather like?")


audio_key = "mic_recorder"
audio = mic_recorder(start_prompt="录音[🔴]", stop_prompt="停止[⏹️]", key=audio_key)
audio_session_output_key = f"{audio_key}_output"


if audio:
    st.audio(audio["bytes"])

if st.session_state[audio_session_output_key]:
    st.audio(st.session_state[audio_session_output_key]["bytes"])
