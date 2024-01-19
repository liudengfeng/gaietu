import io
import json
import logging
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

from mypylib.constants import CEFR_LEVEL_MAPS, NAMES, TOPICS, SCENARIO_MAPS
from mypylib.db_model import LearningTime
from mypylib.google_ai import (
    generate_dialogue,
    generate_listening_test,
    generate_scenarios,
    load_vertex_model,
    summarize_in_one_sentence,
)
from mypylib.st_helper import (
    TOEKN_HELP_INFO,
    WORD_COUNT_BADGE_MAPS,
    check_access,
    check_and_force_logout,
    configure_google_apis,
    count_non_none,
    format_token_count,
    get_synthesis_speech,
    is_answer_correct,
    on_page_to,
    setup_logger,
    view_md_badges,
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
# save_and_clear_all_learning_records()
configure_google_apis()

# endregion
menu_emoji = [
    "🗣️",
    "📖",
    "✍️",
]
menu_names = ["听说练习", "阅读练习", "写作练习"]
menu_opts = [e + " " + n for e, n in zip(menu_emoji, menu_names)]


def on_menu_changed():
    item = menu_names[menu_opts.index(menu)]  # type: ignore
    on_page_to(item)


menu = st.sidebar.selectbox(
    "菜单", menu_opts, help="请选择您要进行的练习项目", on_change=on_menu_changed
)
st.sidebar.divider()
sidebar_status = st.sidebar.empty()
check_and_force_logout(sidebar_status)

if "text_model" not in st.session_state:
    st.session_state["text_model"] = load_vertex_model("gemini-pro")


# region 函数


def create_learning_record(
    project,
    words,
):
    record = LearningTime(
        phone_number=st.session_state.dbi.cache["user_info"]["phone_number"],
        project=project,
        content=words,
    )
    return record


@st.cache_data(ttl=60 * 60 * 24, show_spinner="正在生成听力测试题，请稍候...")
def generate_listening_test_for(difficulty: str, conversation: str):
    return generate_listening_test(
        st.session_state["text_model"], difficulty, conversation, 5
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


def on_prev_btn_click(key):
    st.session_state[key] -= 1


def on_next_btn_click(key):
    st.session_state[key] += 1


def on_word_test_radio_change(idx, options):
    current = st.session_state["listening-test-options"]
    # 转换为索引
    st.session_state["listening-test-answer"][idx] = options.index(current)


def view_listening_test(container):
    idx = st.session_state["listening-test-idx"]
    test = st.session_state["listening-test"][idx]
    question = test["question"]
    options = test["options"]
    user_answer_idx = st.session_state["listening-test-answer"][idx]

    container.markdown(question)
    container.radio(
        "选项",
        options,
        index=user_answer_idx,
        label_visibility="collapsed",
        on_change=on_word_test_radio_change,
        args=(idx, options),
        key="listening-test-options",
    )
    # 保存用户答案
    # st.session_state["listening-test-answer"][idx] = user_answer_idx


def check_listening_test_answer(container, level):
    score = 0
    n = count_non_none(st.session_state["listening-test"])
    for idx, test in enumerate(st.session_state["listening-test"]):
        question = test["question"]
        options = test["options"]
        answer = test["answer"]
        explanation = test["explanation"]
        related_sentence = test["related_sentence"]

        # 存储的是 None 或者 0、1、2、3
        user_answer_idx = st.session_state["listening-test-answer"][idx]
        container.divider()
        container.markdown(question)
        container.radio(
            "选项",
            options,
            # horizontal=True,
            index=user_answer_idx,
            disabled=True,
            label_visibility="collapsed",
            key=f"test-options-{idx}",
        )
        msg = ""
        # 用户答案是选项序号，而提供的标准答案是A、B、C、D
        if is_answer_correct(user_answer_idx, answer):
            score += 1
            msg = f"正确答案：{answer} :white_check_mark:"
        else:
            msg = f"正确答案：{answer} :x:"
        container.markdown(msg)
        container.markdown(f"解释：{explanation}")
        container.markdown(f"相关对话：{related_sentence}")
    percentage = score / n * 100
    if percentage >= 75:
        container.balloons()
    container.divider()
    container.markdown(f":red[得分：{percentage:.0f}%]")
    test_dict = {
        "phone_number": st.session_state.dbi.cache["user_info"]["phone_number"],
        "item": "听力测验",
        "level": level,
        "score": percentage,
        "record_time": datetime.now(timezone.utc),
    }
    st.session_state.dbi.save_daily_quiz_results(test_dict)


# endregion

if menu is not None and menu.endswith("听说练习"):
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

    sidebar_status.markdown(
        f"""令牌：{st.session_state.current_token_count} 累计：{format_token_count(st.session_state.total_token_count)}""",
        help=TOEKN_HELP_INFO,
    )

    tabs = st.tabs(["配置场景", "开始练习", "听力测验"])

    if "stage" not in st.session_state:
        st.session_state.stage = 0

    def set_state(i):
        st.session_state.stage = i

    # 对话变量
    if "conversation_scene" not in st.session_state:
        st.session_state.conversation_scene = []

    with tabs[0]:
        st.subheader("配置场景", divider="rainbow", anchor="配置场景")
        st.markdown("依次执行以下步骤，生成听说练习模拟场景。")
        steps = ["1. 场景类别", "2. 选择场景", "3. 添加情节", "4. 设置难度", "5. 预览场景"]
        sub_tabs = st.tabs(steps)
        scenario_category = None
        selected_scenario = None
        interesting_plot = None
        difficulty = None
        with sub_tabs[0]:
            # st.info("这是第一步：首次选定场景类别，AI会花6-12秒生成对应的场景列表。请耐心等待...", icon="🚨")
            st.info("第一步：选定场景类别", icon="🚨")
            scenario_category = st.selectbox(
                "场景类别",
                ["日常生活", "职场沟通", "学术研究", "旅行交通", "餐饮美食", "健康医疗", "购物消费", "娱乐休闲"],
                # index=None,
                index=0,
                on_change=set_state,
                args=(1,),
                key="scenario_category",
                placeholder="请选择场景类别",
            )
            # logger.info(f"{st.session_state.stage=}")
        with sub_tabs[1]:
            st.info("点击下拉框，选择您感兴趣的场景。如果你希望AI重新生成场景，只需点击'刷新'按钮。请注意，这个过程可能需要6-12秒。", icon="🚨")
            if st.session_state.stage == 1 or scenario_category is not None:
                if st.button("刷新[:arrows_counterclockwise:]", key="generate-scenarios"):
                    scenario_list = generate_scenarios_for(scenario_category)
                else:
                    scenario_list = SCENARIO_MAPS[scenario_category]
                # st.write(scenario_list)
                selected_scenario = st.selectbox(
                    "选择场景",
                    scenario_list,  # type: ignore
                    key="selected_scenario",
                    index=None,
                    on_change=set_state,
                    args=(2,),
                    placeholder="请选择您感兴趣的场景",
                )
        with sub_tabs[2]:
            st.info("可在文本框内添加一些有趣的情节以丰富听力练习材料。如果您想跳过这一步，可以选择'跳过'。", icon="🚨")
            ignore = st.toggle("跳过", key="add_interesting_plot", value=True)
            if ignore:
                st.session_state.stage = 3
            st.divider()
            if st.session_state.stage == 2 or selected_scenario is not None:
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
            st.info("点击下来框选择难度，帮助AI生成相应的对话练习。这个过程可能需要6-12秒。感谢您的耐心等待...", icon="🚨")
            if st.session_state.stage == 3 or interesting_plot is not None or ignore:
                difficulty = st.selectbox(
                    "难度",
                    ["初级", "中级", "高级"],
                    key="difficulty",
                    index=None,
                    on_change=set_state,
                    args=(4,),
                    placeholder="请选择难度",
                )
        with sub_tabs[4]:
            st.info("在完成所有步骤后，你可以在这里查看详细的对话场景。",icon="🚨")
            if selected_scenario is None:
                st.warning("您需要先完成之前的所有步骤")
                st.stop()
            if st.session_state.stage == 4 or difficulty is not None:
                dialogue = generate_dialogue_for(
                    selected_scenario, interesting_plot, difficulty
                )
                summarize = summarize_in_one_sentence_for(dialogue)
                st.markdown("**对话概要**")
                st.markdown(f"{summarize}")
                st.markdown("**字数统计**")
                dialogue_text = " ".join(dialogue)
                total_words, level_dict = count_words_and_get_levels(dialogue_text)
                level_dict.update({"总字数": total_words})
                view_md_badges(level_dict, WORD_COUNT_BADGE_MAPS)
                st.markdown("**对话内容**")
                for d in dialogue:
                    st.markdown(d)
                st.session_state.conversation_scene = dialogue

    with tabs[1]:
        if "learning-times" not in st.session_state:
            st.session_state["learning-times"] = 0

        st.subheader("听说练习", divider="rainbow", anchor="听说练习")

        if len(st.session_state.conversation_scene) == 0:
            st.warning("请先配置场景")
            st.stop()

        if "ls-idx" not in st.session_state:
            st.session_state["ls-idx"] = -1

        ls_btn_cols = st.columns(8)

        display_status_button = ls_btn_cols[0].button(
            "切换[:recycle:]",
            key="ls-mask",
            help="✨ 点击按钮可以在中英对照、只显示英文和只显示中文三种显示状态之间切换。初始状态为中英对照。",
        )
        prev_btn = ls_btn_cols[1].button(
            "上一[:leftwards_arrow_with_hook:]",
            key="ls-prev",
            help="✨ 点击按钮，切换到上一轮对话。",
            on_click=on_prev_btn_click,
            args=("ls-idx",),
            disabled=st.session_state["ls-idx"] < 0,
        )
        next_btn = ls_btn_cols[2].button(
            "下一[:arrow_right_hook:]",
            key="ls-next",
            help="✨ 点击按钮，切换到下一轮对话。",
            on_click=on_next_btn_click,
            args=("ls-idx",),
            disabled=len(st.session_state.conversation_scene) == 0
            or st.session_state["ls-idx"] == len(st.session_state.conversation_scene) - 1,  # type: ignore
        )

        content_cols = st.columns(2)

        if prev_btn:
            dialogue = st.session_state.conversation_scene
            idx = st.session_state["ls-idx"]
            sentence = dialogue[idx]
            voice_style: voices = m_voice_style if idx % 2 == 0 else fm_voice_style
            result = get_synthesis_speech(sentence, voice_style[0])
            content_cols[0].audio(result["audio_data"], format="audio/wav")
            content_cols[0].markdown(sentence)

            if len(st.session_state["learning-record"]) > 0:
                st.session_state["learning-record"][-1].end()
            word_count = len(sentence.split())
            record = create_learning_record("听说练习", f"单词数量：{word_count}")
            record.start()

            st.session_state["learning-times"] += 1

        if next_btn:
            dialogue = st.session_state.conversation_scene
            idx = st.session_state["ls-idx"]
            sentence = dialogue[idx]
            voice_style: voices = m_voice_style if idx % 2 == 0 else fm_voice_style
            result = get_synthesis_speech(sentence, voice_style[0])
            content_cols[0].audio(result["audio_data"], format="audio/wav")
            content_cols[0].markdown(sentence)

            if len(st.session_state["learning-record"]) > 0:
                st.session_state["learning-record"][-1].end()
            word_count = len(sentence.split())
            record = create_learning_record("听说练习", f"单词数量：{word_count}")
            record.start()

            st.session_state["learning-times"] += 1

    with tabs[2]:
        st.subheader("听力测验(五道题)", divider="rainbow", anchor="听力测验")

        if len(st.session_state.conversation_scene) == 0:
            st.warning("请先配置场景")
            st.stop()

        if st.session_state["learning-times"] == 0:
            st.warning("请先完成听说练习")
            st.stop()

        if "listening-test" not in st.session_state:
            st.session_state["listening-test"] = generate_listening_test_for(
                difficulty, st.session_state.conversation_scene
            )

        if "listening-test-idx" not in st.session_state:
            st.session_state["listening-test-idx"] = -1

        if "listening-test-answer" not in st.session_state:
            st.session_state["listening-test-answer"] = [None] * len(
                st.session_state.conversation_scene
            )

        ls_text_btn_cols = st.columns(8)

        st.divider()

        prev_btn = ls_text_btn_cols[0].button(
            "上一[:leftwards_arrow_with_hook:]",
            key="ls-test-prev",
            help="✨ 点击按钮，切换到上一道听力测试题。",
            on_click=on_prev_btn_click,
            args=("listening-test-idx",),
            disabled=st.session_state["listening-test-idx"] < 0,
        )
        next_btn = ls_text_btn_cols[1].button(
            "下一[:arrow_right_hook:]",
            key="ls-test-next",
            help="✨ 点击按钮，切换到下一道听力测试题。",
            on_click=on_next_btn_click,
            args=("listening-test-idx",),
            disabled=len(st.session_state["listening-test"]) == 0
            or st.session_state["listening-test-idx"] == len(st.session_state["listening-test"]) - 1,  # type: ignore
        )
        sumbit_test_btn = ls_text_btn_cols[2].button(
            "检查[:mag:]",
            key="submit-listening-test",
            disabled=st.session_state["listening-test-idx"] == -1
            or len(st.session_state["listening-test-answer"]) == 0,
            help="✨ 至少完成一道测试题后，才可点击按钮，检查听力测验得分。",
        )

        container = st.container()

        if st.session_state["listening-test-idx"] != -1 and not sumbit_test_btn:
            view_listening_test(container)

        if sumbit_test_btn:
            container.empty()

            if count_non_none(st.session_state["listening-test-answer"]) == 0:
                container.warning("您尚未答题。")
                container.stop()

            if count_non_none(
                st.session_state["listening-test-answer"]
            ) != count_non_none(st.session_state["listening-test"]):
                container.warning("您尚未完成测试。")

            check_listening_test_answer(container, difficulty)
