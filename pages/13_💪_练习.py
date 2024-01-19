import io
import json
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from mypylib.constants import CEFR_LEVEL_MAPS, NAMES, SCENARIO_MAPS, TOPICS
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
    end_and_save_learning_records,
    format_token_count,
    get_synthesis_speech,
    is_answer_correct,
    on_page_to,
    setup_logger,
    translate_text,
    view_md_badges,
)
from mypylib.utils import combine_audio_data
from mypylib.word_utils import audio_autoplay_elem, count_words_and_get_levels

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

# endregion

# region 函数

# region 听力练习


def display_dialogue_summary(container, dialogue, summarize):
    container.markdown("**对话概要**")
    container.markdown(f"{summarize}")
    dialogue_text = " ".join(dialogue)
    total_words, level_dict = count_words_and_get_levels(dialogue_text, True)
    container.markdown(f"**字数统计：{len(dialogue_text.split())}字**")
    level_dict.update({"单词总量": total_words})
    view_md_badges(container, level_dict, WORD_COUNT_BADGE_MAPS)
    container.markdown("**对话内容**")
    for d in dialogue:
        container.markdown(d)


# endregion


def create_learning_record(
    project,
    difficulty,
    words,
):
    record = LearningTime(
        phone_number=st.session_state.dbi.cache["user_info"]["phone_number"],
        project=project,
        content=difficulty,
        word_count=words,
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


def get_and_combine_audio_data():
    dialogue = st.session_state.conversation_scene
    audio_list = []
    for i, sentence in enumerate(dialogue):
        voice_style = m_voice_style if i % 2 == 0 else fm_voice_style
        result = get_synthesis_speech(sentence, voice_style[0])
        audio_list.append(result["audio_data"])
    return combine_audio_data(audio_list)


def autoplay_audio_and_display_dialogue(content_cols):
    dialogue = st.session_state.conversation_scene
    audio_list = []
    duration_list = []
    for i, sentence in enumerate(dialogue):
        voice_style = m_voice_style if i % 2 == 0 else fm_voice_style
        result = get_synthesis_speech(sentence, voice_style[0])
        audio_list.append(result["audio_data"])
        duration_list.append(result["audio_duration"])

    # 创建一个空的插槽
    slot_1 = content_cols[0].empty()
    slot_2 = content_cols[1].empty()
    # 如果需要显示中文，那么翻译文本
    if st.session_state.get("ls-display-state", "英文") != "英文":
        cns = translate_text(dialogue, "zh-CN", True)
    total = 0
    # 播放音频并同步显示文本
    for i, duration in enumerate(duration_list):
        # 检查 session state 的值
        if st.session_state.get("ls-display-state", "英文") == "英文":
            # 显示英文
            slot_1.markdown(dialogue[i])
        elif st.session_state.get("ls-display-state", "中文") == "中文":
            # 显示中文
            slot_2.markdown(cns[i])
        else:
            # 同时显示英文和中文
            slot_1.markdown(dialogue[i])
            slot_2.markdown(cns[i])
        # 播放音频
        audio_html = audio_autoplay_elem(audio_list[i], fmt="wav")
        components.html(audio_html)
        # st.markdown(audio_html, unsafe_allow_html=True)
        # 等待音频播放完毕
        t = duration.total_seconds() + 0.2
        total += t
        time.sleep(t)
    return total


def process_and_play_dialogue(content_cols, m_voice_style, fm_voice_style, difficulty):
    dialogue = st.session_state.conversation_scene
    cns = translate_text(dialogue, "zh-CN", True)
    idx = st.session_state["ls-idx"]
    sentence = dialogue[idx]
    voice_style = m_voice_style if idx % 2 == 0 else fm_voice_style
    result = get_synthesis_speech(sentence, voice_style[0])

    if st.session_state["ls-display-state"] == "英文":
        content_cols[0].markdown("英文")
        content_cols[0].markdown(sentence)
    elif st.session_state["ls-display-state"] == "中文":
        # cn = translate_text(sentence, "zh-CN")
        content_cols[1].markdown("中文")
        content_cols[1].markdown(cns[idx])
    else:
        content_cols[0].markdown("英文")
        content_cols[0].markdown(sentence)
        # cn = translate_text(sentence, "zh-CN")
        content_cols[1].markdown("中文")
        content_cols[1].markdown(cns[idx])

    # content_cols[0].audio(result["audio_data"], format="audio/wav")

    audio_html = audio_autoplay_elem(result["audio_data"], fmt="wav")
    components.html(audio_html)
    # st.markdown(audio_html, unsafe_allow_html=True)
    time.sleep(result["audio_duration"].total_seconds())

    # 记录学习时长
    if len(st.session_state["learning-record"]) > 0:
        st.session_state["learning-record"][-1].end()

    word_count = len(sentence.split())
    record = create_learning_record("听说练习", difficulty, word_count)
    record.start()

    st.session_state["learning-times"] += 1


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

    if st.session_state["ls-test-display-state"] == "语音":
        question_audio = get_synthesis_speech(question, m_voice_style[0])
        audio_html = audio_autoplay_elem(question_audio["audio_data"], fmt="wav")
        components.html(audio_html)
        # container.markdown(audio_html, unsafe_allow_html=True)
        time.sleep(question_audio["audio_duration"].total_seconds())
    else:
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

# region 会话状态

if "m_voices" not in st.session_state and "fm_voices" not in st.session_state:
    with open(VOICES_FP, "r", encoding="utf-8") as f:
        voices = json.load(f)["en-US"]
    st.session_state["m_voices"] = [v for v in voices if v[1] == "Male"]
    st.session_state["fm_voices"] = [v for v in voices if v[1] == "Female"]

if "conversation_scene" not in st.session_state:
    st.session_state["conversation_scene"] = []

if "summarize_in_one" not in st.session_state:
    st.session_state["summarize_in_one"] = ""

if "learning-times" not in st.session_state:
    st.session_state["learning-times"] = 0

if "listening-test" not in st.session_state:
    st.session_state["listening-test"] = []

if "listening-test-idx" not in st.session_state:
    st.session_state["listening-test-idx"] = -1

if "listening-test-answer" not in st.session_state:
    st.session_state["listening-test-answer"] = []

if "ls-test-display-state" not in st.session_state:
    st.session_state["ls-test-display-state"] = "文本"

# endregion

if menu is not None and menu.endswith("听说练习"):
    m_voice_style = st.sidebar.selectbox(
        "合成男声风格",
        st.session_state["m_voices"],
        # on_change=on_voice_changed,
        help="✨ 选择您喜欢的合成男声语音风格",
        format_func=lambda x: f"{x[2]}",  # type: ignore
    )
    fm_voice_style = st.sidebar.selectbox(
        "合成女声风格",
        st.session_state["fm_voices"],
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

    # region "配置场景"

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
            st.info("第一步：点击下拉框选定场景类别", icon="🚨")
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
            st.info(
                "第二步：点击下拉框，选择您感兴趣的场景。如果您希望AI重新生成场景，只需点击'刷新'按钮。请注意，这个过程可能需要6-12秒。",
                icon="🚨",
            )
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
                    index=0,
                    on_change=set_state,
                    args=(2,),
                    placeholder="请选择您感兴趣的场景",
                )

        with sub_tabs[2]:
            st.info("第三步：可选。可在文本框内添加一些有趣的情节以丰富听力练习材料。如果您想跳过这一步，可以选择'跳过'。", icon="🚨")
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
- 同事问了一个非常奇怪的问题，让您忍俊不禁。
- 同事在工作中犯了一个错误，但他能够及时发现并改正。
- 同事在工作中遇到
                """,
                )

        with sub_tabs[3]:
            st.info("第四步：点击下拉框选择难度，帮助AI生成相应的对话练习。这个过程可能需要6-12秒。感谢您的耐心等待...", icon="🚨")
            if st.session_state.stage == 3 or interesting_plot is not None or ignore:
                difficulty = st.selectbox(
                    "难度",
                    ["初级", "中级", "高级"],
                    key="difficulty",
                    index=0,
                    on_change=set_state,
                    args=(4,),
                    placeholder="请选择难度",
                )

        with sub_tabs[4]:
            st.info(
                """在完成所有步骤后，您可以在此处生成并查看详细的对话场景。生成对话场景后，您可以切换到最上方的 "开始练习" 标签页，开始进行听力和口语练习。""",
                icon="🚨",
            )
            if selected_scenario is None or difficulty is None:
                st.warning("您需要先完成之前的所有步骤")
                st.stop()

            session_cols = st.columns(8)

            container = st.container()

            gen_btn = session_cols[0].button(
                "刷新[:arrows_counterclockwise:]",
                key="generate-dialogue",
                help="✨ 点击按钮，生成对话场景。",
            )

            if gen_btn:
                container.empty()
                # 学习次数重置为0
                st.session_state["learning-times"] = 0

                dialogue = generate_dialogue_for(
                    selected_scenario, interesting_plot, difficulty
                )
                summarize = summarize_in_one_sentence_for(dialogue)

                display_dialogue_summary(container, dialogue, summarize)

                st.session_state.conversation_scene = dialogue
                st.session_state.summarize_in_one = summarize

            elif len(st.session_state.conversation_scene) > 0:
                display_dialogue_summary(
                    container,
                    st.session_state.conversation_scene,
                    st.session_state.summarize_in_one,
                )

    # endregion

    # region "听说练习"

    with tabs[1]:
        st.subheader("听说练习", divider="rainbow", anchor="听说练习")
        st.markdown(
            """
您可以通过反复播放和跟读每条对话样例来提升您的听力和口语技能。点击`全文`可以一次性收听整个对话。另外，您可以通过点击左侧的按钮调整合成语音的风格，以更好地适应您的听力习惯。      
"""
        )

        if "ls-display-state" not in st.session_state:
            st.session_state["ls-display-state"] = "全部"

        if len(st.session_state.conversation_scene) == 0:
            st.warning("请先配置场景")
            st.stop()

        if "ls-idx" not in st.session_state:
            st.session_state["ls-idx"] = -1

        ls_btn_cols = st.columns(8)
        st.divider()

        refresh_btn = ls_btn_cols[0].button(
            "刷新[:arrows_counterclockwise:]",
            key="ls-refresh",
            help="✨ 点击按钮，从头开始练习。",
        )
        display_status_button = ls_btn_cols[1].button(
            "切换[:recycle:]",
            key="ls-mask",
            help="✨ 点击按钮可以在中英对照、只显示英文和只显示中文三种显示状态之间切换。初始状态为中英对照。",
        )
        prev_btn = ls_btn_cols[2].button(
            "上一[:leftwards_arrow_with_hook:]",
            key="ls-prev",
            help="✨ 点击按钮，切换到上一轮对话。",
            on_click=on_prev_btn_click,
            args=("ls-idx",),
            disabled=st.session_state["ls-idx"] < 0,
        )
        next_btn = ls_btn_cols[3].button(
            "下一[:arrow_right_hook:]",
            key="ls-next",
            help="✨ 点击按钮，切换到下一轮对话。",
            on_click=on_next_btn_click,
            args=("ls-idx",),
            disabled=len(st.session_state.conversation_scene) == 0
            or (st.session_state["ls-idx"] != -1 and st.session_state["ls-idx"] == len(st.session_state.conversation_scene) - 1),  # type: ignore
        )
        lsi_btn = ls_btn_cols[4].button(
            "全文[:headphones:]",
            key="ls-lsi",
            help="✨ 点击按钮，收听整个对话。",
            disabled=len(st.session_state.conversation_scene) == 0,
        )

        content_cols = st.columns(2)

        if refresh_btn:
            st.session_state["ls-idx"] = -1
            st.session_state["learning-times"] = 0
            end_and_save_learning_records()

        if display_status_button:
            if st.session_state["ls-display-state"] == "全部":
                st.session_state["ls-display-state"] = "英文"
            elif st.session_state["ls-display-state"] == "英文":
                st.session_state["ls-display-state"] = "中文"
            else:
                st.session_state["ls-display-state"] = "全部"

        if prev_btn:
            process_and_play_dialogue(
                content_cols, m_voice_style, fm_voice_style, difficulty
            )

        if next_btn:
            process_and_play_dialogue(
                content_cols, m_voice_style, fm_voice_style, difficulty
            )

        if lsi_btn:
            total = autoplay_audio_and_display_dialogue(content_cols)
            st.session_state["learning-times"] = len(
                st.session_state.conversation_scene
            )
            dialogue_text = " ".join(st.session_state.conversation_scene)
            word_count = len(dialogue_text.split())
            record = LearningTime(
                phone_number=st.session_state.dbi.cache["user_info"]["phone_number"],
                project="听说练习",
                content=difficulty,
                duration=total,
                word_count=word_count,
            )
            st.session_state.dbi.add_record_to_cache(record)

    # endregion

    # region "听力测验"

    with tabs[2]:
        st.subheader("听力测验(五道题)", divider="rainbow", anchor="听力测验")

        if len(st.session_state.conversation_scene) == 0:
            st.warning("请先配置场景")
            st.stop()

        if st.session_state["learning-times"] == 0:
            st.warning("请先完成听说练习")
            st.stop()

        ls_text_btn_cols = st.columns(8)

        st.divider()

        refresh_test_btn = ls_text_btn_cols[0].button(
            "刷新[:arrows_counterclockwise:]",
            key="ls-test-refresh",
            help="✨ 点击按钮，生成听力测试题。",
        )
        display_test_btn = ls_text_btn_cols[1].button(
            "切换[:recycle:]",
            key="ls-test-mask",
            help="✨ 此状态切换按钮允许您选择测试题目的展示方式：以文本形式展示或以语音形式播放。初始状态为以文本形式展示测试题目。",
        )
        prev_test_btn = ls_text_btn_cols[2].button(
            "上一[:leftwards_arrow_with_hook:]",
            key="ls-test-prev",
            help="✨ 点击按钮，切换到上一道听力测试题。",
            on_click=on_prev_btn_click,
            args=("listening-test-idx",),
            disabled=st.session_state["listening-test-idx"] <= 0,
        )
        next_test_btn = ls_text_btn_cols[3].button(
            "下一[:arrow_right_hook:]",
            key="ls-test-next",
            help="✨ 点击按钮，切换到下一道听力测试题。",
            on_click=on_next_btn_click,
            args=("listening-test-idx",),
            disabled=len(st.session_state["listening-test"]) == 0
            or st.session_state["listening-test-idx"] == len(st.session_state["listening-test"]) - 1,  # type: ignore
        )
        rpl_test_btn = ls_text_btn_cols[4].button(
            "重放[:headphones:]",
            key="ls-test-replay",
            help="✨ 点击此按钮，可以重新播放当前测试题目的语音。",
            disabled=len(st.session_state["listening-test"]) == 0
            or st.session_state["listening-test-idx"] == -1
            or st.session_state["ls-test-display-state"] == "文本",  # type: ignore
        )
        sumbit_test_btn = ls_text_btn_cols[5].button(
            "检查[:mag:]",
            key="submit-listening-test",
            disabled=st.session_state["listening-test-idx"] == -1
            or len(st.session_state["listening-test-answer"]) == 0,
            help="✨ 至少完成一道测试题后，才可点击按钮，检查听力测验得分。",
        )

        container = st.container()

        if refresh_test_btn:
            end_and_save_learning_records()
            st.session_state["listening-test"] = generate_listening_test_for(
                difficulty, st.session_state.conversation_scene
            )
            st.session_state["listening-test-idx"] = -1
            st.session_state["listening-test-answer"] = [None] * len(
                st.session_state.conversation_scene
            )
            # 更新
            st.rerun()

        if display_test_btn:
            if st.session_state["ls-test-display-state"] == "文本":
                st.session_state["ls-test-display-state"] = "语音"
            else:
                st.session_state["ls-test-display-state"] = "文本"

        if rpl_test_btn:
            if st.session_state["ls-test-display-state"] == "文本":
                st.warning("请先切换到语音模式")
                st.stop()

            idx = st.session_state["listening-test-idx"]
            test = st.session_state["listening-test"][idx]
            question = test["question"]
            question_audio = get_synthesis_speech(question, m_voice_style[0])
            audio_html = audio_autoplay_elem(question_audio["audio_data"], fmt="wav")
            # st.markdown(audio_html, unsafe_allow_html=True)
            components.html(audio_html)
            time.sleep(question_audio["audio_duration"].total_seconds())

            # 添加一个学习时间记录
            record = LearningTime(
                phone_number=st.session_state.dbi.cache["user_info"]["phone_number"],
                project="听力测验",
                content=difficulty,
                word_count=len(question.split()),
                duration=question_audio["audio_duration"].total_seconds(),
            )
            st.session_state.dbi.add_record_to_cache(record)

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

    # endregion
