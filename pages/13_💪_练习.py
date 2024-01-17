import json
import logging
import random
from pathlib import Path

import streamlit as st

from mypylib.constants import CEFR_LEVEL_MAPS, NAMES, TOPICS
from mypylib.google_ai import (
    generate_dialogue,
    generate_scenarios,
    load_vertex_model,
    summarize_in_one_sentence,
)
from mypylib.st_helper import (
    TOEKN_HELP_INFO,
    check_access,
    check_and_force_logout,
    configure_google_apis,
    format_token_count,
    save_and_clear_all_learning_records,
    setup_logger,
)
from mypylib.word_utils import count_words_and_get_levels

# region 配置

CURRENT_CWD: Path = Path(__file__).parent.parent
VOICES_FP = CURRENT_CWD / "resource" / "voices.json"

# 创建或获取logger对象
logger = logging.getLogger("streamlit")
setup_logger(logger)

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

    @st.cache_data(ttl=60 * 60 * 24, show_spinner="正在加载场景类别，请稍候...")
    def generate_scenarios_for(category: str):
        return generate_scenarios(st.session_state["text_model"], category)

    @st.cache_data(ttl=60 * 60 * 24, show_spinner="正在生成模拟场景，请稍候...")
    def generate_dialogue_for(selected_scenario, interesting_plot, difficulty):
        boy_name = random.choice(NAMES["en-US"]["male"])
        girl_name = random.choice(NAMES["en-US"]["female"])
        scenario = selected_scenario.split(".")[1]
        return generate_dialogue(
            st.session_state["text_model"],
            boy_name,
            girl_name,
            scenario,
            interesting_plot if interesting_plot else "",
            difficulty,
        )

    @st.cache_data(ttl=60 * 60 * 24, show_spinner="正在生成对话概要，请稍候...")
    def summarize_in_one_sentence_for(dialogue: str):
        return summarize_in_one_sentence(st.session_state["text_model"], dialogue)

    sidebar_status.markdown(
        f"""令牌：{st.session_state.current_token_count} 累计：{format_token_count(st.session_state.total_token_count)}""",
        help=TOEKN_HELP_INFO,
    )

    tabs = st.tabs(["配置场景", "开始练习"])

    if "stage" not in st.session_state:
        st.session_state.stage = 0

    def set_state(i):
        st.session_state.stage = i

    with tabs[0]:
        st.subheader("配置场景", divider="rainbow", anchor="配置场景")
        steps = ["1. 场景类别", "2. 选择场景", "3. 添加情节", "4. 设置难度", "5. 预览场景"]
        sub_tabs = st.tabs(steps)
        with sub_tabs[0]:
            scenario_category = st.selectbox(
                "场景类别",
                ["日常生活", "职场沟通", "学术研究"],
                index=None,
                on_change=set_state,
                args=(1,),
                key="scenario_category",
                placeholder="请选择场景类别",
            )
            # logger.info(f"{st.session_state.stage=}")
        with sub_tabs[1]:
            if st.session_state.stage == 1:
                selected_scenario = st.selectbox(
                    "选择场景",
                    generate_scenarios_for(scenario_category),
                    key="selected_scenario",
                    index=None,
                    on_change=set_state,
                    args=(2,),
                    placeholder="请选择您感兴趣的场景",
                )
        with sub_tabs[2]:
            if st.session_state.stage == 2:
                ignore = st.checkbox("添加情节", key="add_interesting_plot")
                if ignore:
                    st.session_state.stage = 3
                interesting_plot = st.text_area(
                    "添加一些有趣的情节【可选】",
                    height=200,
                    key="interesting_plot",
                    on_change=set_state,
                    args=(3,),
                    placeholder="""您可以在这里添加一些有趣的情节。比如：
- 同事问了一个非常奇怪的问题，让你忍俊不禁。
- 同事在工作中犯了一个错误，但他能够及时发现并改正。
- 同事在工作中遇到
                """,
                )
        with sub_tabs[3]:
            if st.session_state.stage == 3:
                difficulty = st.selectbox(
                    "难度",
                    ["初级", "中级", "高级"],
                    key="difficulty",
                    index=None,
                    on_change=set_state,
                    args=(4,),
                    placeholder="请选择您感兴趣的场景",
                )
        with sub_tabs[4]:
            if st.session_state.stage == 4:
                dialogue = generate_dialogue_for(
                    selected_scenario, interesting_plot, difficulty
                )
                summarize = summarize_in_one_sentence_for(dialogue)
                st.markdown(f"**{summarize}**")
                st.divider()
                total_words, level_dict = count_words_and_get_levels(dialogue)
                markdown_text = f"总字数：{total_words}\n\n"
                for level, count in level_dict.items():
                    markdown_text += f"- {level}：{count}\n"
                st.markdown(markdown_text)
                st.divider()

                for d in dialogue:
                    st.markdown(d)

    with tabs[1]:
        st.subheader("选择难度", divider="rainbow", anchor="选择难度")
        st.write("🚧 敬请期待")
