import json
import re
from datetime import datetime, timedelta

import pytz
import streamlit as st
from streamlit_mic_recorder import mic_recorder

from mypylib.azure_pronunciation_assessment import adjust_display_by_reference_text
from mypylib.constants import CEFR_LEVEL_MAPS, CEFR_LEVEL_TOPIC, VOICES_FP
from mypylib.google_ai import generate_pronunciation_assessment_text, load_vertex_model
from mypylib.nivo_charts import gen_radar
from mypylib.st_helper import (
    TOEKN_HELP_INFO,
    autoplay_audio_and_display_text,
    check_access,
    check_and_force_logout,
    configure_google_apis,
    display_pronunciation_result,
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

if "m_voices" not in st.session_state and "fm_voices" not in st.session_state:
    with open(VOICES_FP, "r", encoding="utf-8") as f:
        voices = json.load(f)["en-US"]
    st.session_state["m_voices"] = [v for v in voices if v[1] == "Male"]
    st.session_state["fm_voices"] = [v for v in voices if v[1] == "Female"]

# endregion


# region 函数


@st.cache_data(ttl=60 * 60 * 24, show_spinner="AI正在生成发音评估文本，请稍候...")
def generate_pronunciation_assessment_text_for(scenario_category, difficulty):
    return generate_pronunciation_assessment_text(
        st.session_state["text_model"], scenario_category, difficulty
    )


def display_pronunciation_assessment_words(container, text_key, assessment_key):
    # 去掉 ** 加黑标记
    text = st.session_state[text_key].replace("**", "")
    words = st.session_state[assessment_key].get("recognized_words", [])
    container.markdown("##### 评估结果")
    if len(words) == 0:
        return
    adjusted = adjust_display_by_reference_text(text, words)
    with container:
        view_word_assessment(adjusted)


def view_radar(score_key, item_maps):
    # 雷达图
    data_tb = {
        key: st.session_state.get(score_key, {})
        .get("pronunciation_result", {})
        .get(key, 0)
        for key in item_maps.keys()
    }
    gen_radar(data_tb, item_maps, 320)


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

    voice_gender = st.sidebar.radio("选择合成声音的性别", ("男性", "女性"), index=0)

    if voice_gender == "男性":
        voice_style_options = st.session_state["m_voices"]
    else:
        voice_style_options = st.session_state["fm_voices"]

    voice_style = st.sidebar.selectbox(
        "合成声音风格",
        voice_style_options,
        help="✨ 选择您喜欢的语音风格",
        format_func=lambda x: f"{x[2]}",  # type: ignore
    )

    st.subheader("发音评估", divider="rainbow", anchor="发音评估")
    st.markdown(
        "在选择了 CEFR 等级和发音评估的场景类别之后，点击 '刷新[🔄]' 按钮来生成用于发音评估的文本。然后，点击 '录音[⏸️]' 按钮，按照生成的文本进行朗读。完成朗读后，点击 '评估[🔖]' 按钮，系统将对你的发音进行评估，并生成发音评估报告。"
    )
    scenario_category = st.selectbox(
        "选择场景类别",
        CEFR_LEVEL_TOPIC[difficulty],
        index=0,
        key="scenario_category",
        placeholder="请选择场景类别",
    )

    pa_report_container = st.container(border=True)
    replay_text_placeholder = st.empty()
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
    play_btn = pa_cols[3].button(
        "回放[▶️]",
        disabled=not audio_info,
        key="pa-play-btn",
        help="✨ 点击按钮，播放您的跟读录音。",
    )
    # 左侧显示发音评估文本
    # 右侧显示评估内容
    content_cols = st.columns([6, 6, 2])
    pa_text_container = content_cols[0].container(border=True)
    pa_words_container = content_cols[1].container(border=True)
    legend_container = content_cols[2].container(border=True)

    with legend_container:
        st.markdown("##### 图例")
        view_pronunciation_assessment_legend()

    if "pa-text" not in st.session_state:
        st.session_state["pa-text"] = ""
    if "pa-assessment" not in st.session_state:
        st.session_state["pa-assessment"] = {}

    if pa_refresh_btn:
        st.session_state["pa-text"] = generate_pronunciation_assessment_text_for(
            scenario_category, difficulty
        )
    pa_text_container.markdown("##### 评估文本")
    pa_text_container.markdown(st.session_state["pa-text"], unsafe_allow_html=True)

    if pa_pro_btn and audio_info is not None:
        # 去掉发言者的名字
        reference_text = process_dialogue_text(st.session_state["pa-text"])

        start = datetime.now(pytz.UTC)
        st.session_state["pa-assessment"] = pronunciation_assessment_for(
            audio_info,
            reference_text,
        )

    if play_btn and audio_info and st.session_state["pa-assessment"]:
        autoplay_audio_and_display_text(
            replay_text_placeholder,
            audio_info["bytes"],
            st.session_state["pa-assessment"]["recognized_words"],
        )

    display_pronunciation_result(
        pa_report_container,
        "pa-assessment",
    )

    display_pronunciation_assessment_words(
        pa_words_container,
        "pa-text",
        "pa-assessment",
    )

    with st.expander("查看发音评估雷达图", expanded=False):
        item_maps = {
            "pronunciation_score": "发音总评分",
            "accuracy_score": "准确性评分",
            "completeness_score": "完整性评分",
            "fluency_score": "流畅性评分",
            "prosody_score": "韵律分数",
        }
        view_radar("pa-assessment", item_maps)

# endregion

# region 口语评估

if menu and menu.endswith("口语能力"):
    pass

# endregion

# region 写作评估

if menu and menu.endswith("写作评估"):
    pass

# endregion
