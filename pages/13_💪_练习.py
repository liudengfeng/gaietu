import json
from pathlib import Path

import streamlit as st
from mypylib.google_ai import generate_scenarios, load_vertex_model

from mypylib.st_helper import (
    TOEKN_HELP_INFO,
    check_access,
    check_and_force_logout,
    configure_google_apis,
    format_token_count,
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

if "text_model" not in st.session_state:
    st.session_state["text_model"] = load_vertex_model("gemini-pro")

if menu.endswith("听说练习"):
    with open(VOICES_FP, "r", encoding="utf-8") as f:
        voices = json.load(f)["en-US"]

    m_voices = [v for v in voices if v[1] == "Male"]
    fm_voices = [v for v in voices if v[1] == "Female"]

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

    steps = ["配置场景", "选择难度", "选择语音风格", "开始练习"]

    @st.cache_data(ttl=60 * 60 * 24, show_spinner="正在加载场景，请稍候...")
    def generate_scenarios_for(category: str):
        return generate_scenarios(st.session_state["text_model"], category)

    sidebar_status.markdown(
        f"""令牌：{st.session_state.current_token_count} 累计：{format_token_count(st.session_state.total_token_count)}""",
        help=TOEKN_HELP_INFO,
    )

    tabs = st.tabs(steps)

    with tabs[0]:
        st.subheader("配置场景", divider="rainbow", anchor="配置场景")
        difficulty = st.selectbox("难度", ["初级", "中级", "高级"], key="difficulty")
        scenario_category = st.selectbox(
            "场景类别",
            ["日常生活", "职场沟通", "学术研究"],
            key="scenario_category",
            placeholder="请选择场景类别",
        )
        selected_scenario = st.selectbox(
            "选择场景",
            generate_scenarios_for(scenario_category),
            key="selected_scenario",
            placeholder="请选择您感兴趣的场景",
        )
        interesting_plot = st.text_area(
            "添加一些有趣的情节",
            height=200,
            key="interesting_plot",
            placeholder="""您可以在这里添加一些有趣的情节。比如：
- 同事问了一个非常奇怪的问题，让你忍俊不禁。
- 同事在工作中犯了一个错误，但他能够及时发现并改正。
- 同事在工作中遇到
            """,
        )

    with tabs[1]:
        st.subheader("选择难度", divider="rainbow", anchor="选择难度")
        st.write("🚧 敬请期待")
