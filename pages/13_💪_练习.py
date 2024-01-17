import json
from pathlib import Path

import streamlit as st

from mypylib.st_helper import (
    check_access,
    check_and_force_logout,
    configure_google_apis,
    save_and_clear_all_learning_records,
)
from mypylib.constants import CEFR_LEVEL_MAPS, NAMES, TOPICS

# region 配置

CURRENT_CWD: Path = Path(__file__).parent.parent
VOICES_FP = CURRENT_CWD / "resource" / "voices.json"

st.set_page_config(
    page_title="练习",
    page_icon=":muscle:",
    layout="wide",
)

check_access(False)
st.session_state["current-page"] = "练习"
save_and_clear_all_learning_records()
configure_google_apis()

# endregion
menu_emoji = [
    "🗣️",
    "📖",
    "✍️",
]
menu_names = ["听说练习", "阅读练习", "写作练习"]
menu_opts = [e + " " + n for e, n in zip(menu_emoji, menu_names)]
menu = st.sidebar.selectbox("菜单", menu_opts, help="请选择您要进行的练习项目")
st.sidebar.divider()
sidebar_status = st.sidebar.empty()
check_and_force_logout(sidebar_status)

if menu.endswith("听说练习"):
    with open(VOICES_FP, "r", encoding="utf-8") as f:
        voices = json.load(f)["en-US"]

    m_voices = [v for v in voices if v[1] == "Male"]
    fm_voices = [v for v in voices if v[1] == "Female"]

    st.sidebar.selectbox("模拟场景", ["日常生活", "职场沟通", "学术研究"])
    st.sidebar.selectbox("难度", ["初级", "中级", "高级"])

    m_voice_style = st.sidebar.selectbox(
        "合成男声风格",
        m_voices,
        # on_change=on_voice_changed,
        help="✨ 选择您喜欢的合成男声语音风格",
        format_func=lambda x: f"{x[2]}",  # type: ignore
    )
    fm_voice_style = st.sidebar.selectbox(
        "合成女声风格",
        fm_voices,
        # on_change=on_voice_changed,
        help="✨ 选择您喜欢的合成女声语音风格",
        format_func=lambda x: f"{x[2]}",  # type: ignore
    )
