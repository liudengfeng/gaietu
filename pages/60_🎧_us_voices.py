import logging
from pathlib import Path

import streamlit as st
from menu import menu

from mypylib.st_helper import (
    add_exercises_to_db,
    on_project_changed,
    setup_logger,
)

# 创建或获取logger对象
logger = logging.getLogger("streamlit")
setup_logger(logger)

CURRENT_CWD: Path = Path(__file__).parent.parent
VOICES_DIR = CURRENT_CWD / "resource/us_voices"
# Initialize st.session_state.role to None
if "role" not in st.session_state:
    st.session_state.role = None

st.set_page_config(
    page_title="美音示例",
    page_icon=":headphones:",
    layout="wide",
)

menu()
on_project_changed("Home")
add_exercises_to_db()

# region 美音示例
st.subheader(":headphones: 美式语音示例", divider="rainbow", anchor="美音示例")
with st.expander(":headphones: 美式语音示例", expanded=False):
    st.markdown(
        """
        以下是美式发音示例，点击按钮即可播放音频。
        演示文本英文内容：
        My name is Li Ming. I am from China. I am a student at Peking University. I am majoring in computer science. I am interested in artificial intelligence and machine learning. I am excited to be here today and I look forward to meeting all of you.
        演示文本中文翻译：
        我叫李明，来自中国。我在北京大学学习，主修计算机科学。我对人工智能和机器学习非常感兴趣。我很高兴今天能来到这里，期待与大家见面。
        """
    )
    wav_files = list(VOICES_DIR.glob("*.wav"))
    cols = st.columns(2)
    # 在每列中添加音频文件
    for i, wav_file in enumerate(wav_files):
        # 获取文件名（不包括扩展名）
        file_name = wav_file.stem
        # 在列中添加文本和音频
        cols[i % 2].markdown(file_name)
        cols[i % 2].audio(str(wav_file))

# endregion
