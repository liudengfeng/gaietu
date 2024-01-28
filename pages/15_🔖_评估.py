import streamlit as st
from datetime import datetime, timedelta
import pytz
import re
from mypylib.azure_pronunciation_assessment import adjust_display_by_reference_text
from mypylib.constants import CEFR_LEVEL_MAPS, CEFR_LEVEL_TOPIC
from mypylib.google_ai import generate_pronunciation_assessment_text, load_vertex_model
from streamlit_mic_recorder import mic_recorder
from mypylib.st_helper import (
    TOEKN_HELP_INFO,
    check_access,
    check_and_force_logout,
    configure_google_apis,
    format_token_count,
    on_page_to,
    process_dialogue_text,
    pronunciation_assessment_for,
    view_pronunciation_assessment_legend,
    view_word_assessment,
)

# region 配置

st.set_page_config(
    page_title="能力评估",
    page_icon=":bookmark:",
    layout="wide",
)

check_access(False)
on_page_to("能力评估")
configure_google_apis()

menu_items = ["发音评估", "口语能力", "写作评估"]
menu_emojis = ["🔊", "🗣️", "✍️"]
menu_opts = [f"{e} {i}" for i, e in zip(menu_items, menu_emojis)]
menu = st.sidebar.selectbox("菜单", menu_opts, help="选择你要练习的项目")

st.sidebar.divider()
sidebar_status = st.sidebar.empty()
check_and_force_logout(sidebar_status)

sidebar_status.markdown(
    f"""令牌：{st.session_state.current_token_count} 累计：{format_token_count(st.session_state.total_token_count)}""",
    help=TOEKN_HELP_INFO,
)

if "text_model" not in st.session_state:
    st.session_state["text_model"] = load_vertex_model("gemini-pro")

# endregion


# region 函数


@st.cache_data(ttl=60 * 60 * 24, show_spinner="AI正在生成发音评估文本，请稍候...")
def generate_pronunciation_assessment_text_for(scenario_category, difficulty):
    return generate_pronunciation_assessment_text(
        st.session_state["text_model"], scenario_category, difficulty
    )


# endregion

# region 发音评估

if menu and menu.endswith("发音评估"):
    difficulty = st.sidebar.selectbox(
        "CEFR等级",
        list(CEFR_LEVEL_MAPS.keys()),
        key="listening-difficulty",
        index=0,
        format_func=lambda x: f"{x}({CEFR_LEVEL_MAPS[x]})",
        placeholder="请选择CEFR等级",
    )
    st.subheader("发音评估", divider="rainbow", anchor="发音评估")
    scenario_category = st.selectbox(
        "选择场景类别",
        CEFR_LEVEL_TOPIC[difficulty],
        index=0,
        key="scenario_category",
        placeholder="请选择场景类别",
    )
    pa_cols = st.columns(8)
    pa_refresh_btn = pa_cols[0].button(
        "刷新[:arrows_counterclockwise:]",
        key="refresh_pronunciation_assessment_text",
        help="点击按钮，生成发音评估文本",
    )
    audio_key = "pa-mic-recorder"
    audio_session_output_key = f"{audio_key}-output"
    with pa_cols[1]:
        audio_info = mic_recorder(
            start_prompt="录音[⏸️]",
            stop_prompt="停止[🔴]",
            key=audio_key,
        )
    pa_pro_btn = pa_cols[2].button(
        "评估[🔖]",
        disabled=not audio_info,
        key="pa-evaluation-btn",
        help="✨ 点击按钮，开始发音评估。",
    )
    # 左侧显示发音评估文本
    # 右侧显示评估内容
    content_cols = st.columns([4, 4, 2])
    with content_cols[2]:
        view_pronunciation_assessment_legend()

    if "pa-text" not in st.session_state:
        st.session_state["pa-text"] = ""
    if "pa-assessment" not in st.session_state:
        st.session_state["pa-assessment"] = {}

    if pa_refresh_btn:
        st.session_state["pa-text"] = generate_pronunciation_assessment_text_for(
            scenario_category, difficulty
        )

    content_cols[0].markdown(st.session_state["pa-text"], unsafe_allow_html=True)

    if pa_pro_btn and audio_info is not None:
        # 去掉发言者的名字
        reference_text = process_dialogue_text(st.session_state["pa-text"])

        start = datetime.now(pytz.UTC)
        st.session_state["pa-assessment"] = pronunciation_assessment_for(
            audio_info,
            reference_text,
        )
        words = st.session_state["pa-assessment"]["recognized_words"]
        adjusted = adjust_display_by_reference_text(st.session_state["pa-text"], words)
        # end = datetime.now(pytz.UTC)
        with content_cols[1]:
            view_word_assessment(adjusted)


# endregion

# region 口语评估

if menu and menu.endswith("口语能力"):
    pass

# endregion

# region 写作评估

if menu and menu.endswith("写作评估"):
    pass

# endregion
