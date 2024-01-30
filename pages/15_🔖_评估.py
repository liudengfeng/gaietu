import json
import re
from datetime import datetime, timedelta

import pytz
import streamlit as st
import streamlit.components.v1 as components
from streamlit_mic_recorder import mic_recorder

from mypylib.azure_pronunciation_assessment import (
    adjust_display_by_reference_text,
    read_audio_file,
)
from mypylib.constants import CEFR_LEVEL_MAPS, CEFR_LEVEL_TOPIC, VOICES_FP
from mypylib.db_model import LearningTime
from mypylib.google_ai import (
    generate_oral_ability_topics,
    generate_oral_statement_template,
    generate_pronunciation_assessment_text,
    load_vertex_model,
)
from mypylib.nivo_charts import gen_radar
from mypylib.st_helper import (
    ORAL_ABILITY_SCORE_BADGE_MAPS,
    PRONUNCIATION_SCORE_BADGE_MAPS,
    TOEKN_HELP_INFO,
    autoplay_audio_and_display_text,
    check_access,
    check_and_force_logout,
    configure_google_apis,
    display_assessment_score,
    format_token_count,
    get_synthesis_speech,
    # left_paragraph_aligned_text,
    on_page_to,
    oral_ability_assessment_for,
    process_dialogue_text,
    process_learning_record,
    pronunciation_assessment_for,
    view_pronunciation_assessment_legend,
    view_word_assessment,
)
from mypylib.utils import calculate_audio_duration
from mypylib.word_utils import audio_autoplay_elem

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

# region 发音评估会话

if "pa-learning-times" not in st.session_state:
    st.session_state["pa-learning-times"] = 0

if "pa-idx" not in st.session_state:
    st.session_state["pa-idx"] = -1

if "pa-text" not in st.session_state:
    st.session_state["pa-text"] = ""

if "pa-current-text" not in st.session_state:
    st.session_state["pa-current-text"] = ""

# 当前段落的发音评估结果
if "pa-assessment" not in st.session_state:
    st.session_state["pa-assessment"] = {}

# 以序号为键，每段落的发音评估结果为值的字典
if "pa-assessment-dict" not in st.session_state:
    st.session_state["pa-assessment-dict"] = {}

# endregion

# region 口语评估会话

if "oa-sample-text" not in st.session_state:
    st.session_state["oa-sample-text"] = ""

if "oa-topic-options" not in st.session_state:
    st.session_state["oa-topic-options"] = []

if "oa-assessment" not in st.session_state:
    st.session_state["oa-assessment"] = {}

# endregion

# region 函数


def on_scenario_category_changed():
    # 类别更改后，清空话题选项
    st.session_state["oa-topic-options"] = []


def on_prev_btn_click(key):
    st.session_state[key] -= 1


def on_next_btn_click(key):
    st.session_state[key] += 1


def create_learning_record(
    project,
    difficulty,
    selected_scenario,
    words,
):
    record = LearningTime(
        phone_number=st.session_state.dbi.cache["user_info"]["phone_number"],
        project=project,
        content=f"{difficulty}-{selected_scenario}",
        word_count=words,
    )
    return record


@st.cache_data(ttl=60 * 60 * 24, show_spinner="AI正在生成发音评估文本，请稍候...")
def generate_pronunciation_assessment_text_for(scenario_category, difficulty):
    return generate_pronunciation_assessment_text(
        st.session_state["text_model"], scenario_category, difficulty
    )


def display_pronunciation_assessment_words(container, text_key, assessment_key):
    container.markdown("##### 评估结果")
    idx = st.session_state["pa-idx"]
    words = st.session_state[assessment_key].get(idx, {}).get("recognized_words", [])
    # 去掉 ** 加黑标记
    text = st.session_state[text_key].replace("**", "")
    if len(words) == 0:
        return
    adjusted = adjust_display_by_reference_text(text, words)
    with container:
        view_word_assessment(adjusted)


def display_oral_pronunciation_assessment_results(container, assessment_key):
    container.markdown("##### 评估结果")
    words = st.session_state[assessment_key].get("recognized_words", [])
    if len(words) == 0:
        return
    with container:
        view_word_assessment(words)


def view_radar(score_dict, item_maps):
    # 雷达图
    data_tb = {
        key: score_dict.get("pronunciation_result", {}).get(key, 0)
        for key in item_maps.keys()
    }
    gen_radar(data_tb, item_maps, 320)


def play_synthesized_audio(text, voice_style, difficulty, selected_scenario):
    if not text:
        return
    style = voice_style[0]

    with st.spinner(f"使用 Azure 将文本合成语音..."):
        result = get_synthesis_speech(text, style)

    audio_html = audio_autoplay_elem(result["audio_data"], fmt="wav")
    components.html(audio_html)

    # 记录学习时长
    word_count = len(re.findall(r"\b\w+\b", text))
    record = create_learning_record(
        "发音评估", difficulty, selected_scenario, word_count
    )
    record.duration = result["audio_duration"].total_seconds()
    st.session_state.dbi.add_record_to_cache(record)


def display_assessment_text(pa_text_container):
    with pa_text_container:
        title = "评估文本"
        text = st.session_state["pa-text"]
        if text:
            idx = st.session_state["pa-idx"]
            words = []
            if idx == -1:
                words = st.session_state["pa-text"].split()
                title = f"评估全文（单词：{len(words)}）"
            else:
                words = st.session_state["pa-current-text"].split()
                title = f"评估段落（单词：{len(words)}）"

            st.markdown(f"##### {title}")

            if idx == -1:
                st.markdown(text, unsafe_allow_html=True)
            else:
                st.markdown(st.session_state["pa-current-text"], unsafe_allow_html=True)
        else:
            st.markdown(f"##### {title}")


# endregion

# region 口语能力函数


# def delete_recorded_audio(audio_obj, audio_key):
#     st.session_state[audio_key] = None
#     if audio_obj:
#         audio_obj.clear()  # 删除所有元素


@st.cache_data(ttl=60 * 60 * 24, show_spinner="AI正在生成口语讨论话题清单，请稍候...")
def generate_oral_ability_topics_for(difficulty, scenario_category):
    text = generate_oral_ability_topics(
        st.session_state["text_model"], scenario_category, difficulty, 5
    )
    return [line for line in text.splitlines() if line.strip()]


@st.cache_data(ttl=60 * 60 * 24, show_spinner="AI正在生成口语话题样例，请稍候...")
def generate_oral_statement_template_for(topic, difficulty):
    return generate_oral_statement_template(
        st.session_state["text_model"], topic, difficulty
    )


# endregion

# region 发音评估页面

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
    prev_btn = pa_cols[1].button(
        "上一[:leftwards_arrow_with_hook:]",
        key="ra-prev",
        help="✨ 点击按钮，切换到上一段落。",
        on_click=on_prev_btn_click,
        args=("pa-idx",),
        disabled=st.session_state["pa-idx"] < 0,
    )
    next_btn = pa_cols[2].button(
        "下一[:arrow_right_hook:]",
        key="ra-next",
        help="✨ 点击按钮，切换到下一段落。",
        on_click=on_next_btn_click,
        args=("pa-idx",),
        disabled=st.session_state["pa-idx"]
        == len(
            [line for line in st.session_state["pa-text"].splitlines() if line.strip()]
        )
        - 1,
    )
    synthetic_audio_replay_button = pa_cols[3].button(
        "收听[:headphones:]",
        key="pa-replay",
        help="✨ 点击按钮，收听文本的合成语音。",
        disabled=st.session_state["pa-current-text"] == ""
        or st.session_state["pa-idx"] == -1,
    )
    audio_key = "pa-mic-recorder"
    audio_session_output_key = f"{audio_key}_output"
    with pa_cols[4]:
        audio_info = mic_recorder(
            start_prompt="录音[⏸️]",
            stop_prompt="停止[🔴]",
            key=audio_key,
        )
    pa_pro_btn = pa_cols[5].button(
        "评估[🔖]",
        disabled=not audio_info or st.session_state["pa-current-text"] == "",
        key="pa-evaluation-btn",
        help="✨ 点击按钮，开始发音评估。",
    )
    audio_playback_button = pa_cols[6].button(
        "回放[▶️]",
        disabled=not audio_info or st.session_state["pa-current-text"] == "",
        key="pa-play-btn",
        help="✨ 点击按钮，播放您的跟读录音。",
    )
    # 左侧显示发音评估文本
    # 右侧显示评估内容6
    content_cols = st.columns([8, 8, 2])
    pa_text_container = content_cols[0].container(border=True)
    pa_words_container = content_cols[1].container(border=True)
    legend_container = content_cols[2].container(border=True)

    with legend_container:
        st.markdown("##### 图例")
        view_pronunciation_assessment_legend()

    if pa_refresh_btn:
        st.session_state["pa-text"] = generate_pronunciation_assessment_text_for(
            scenario_category, difficulty
        )
        st.session_state["pa-idx"] = -1
        st.session_state["pa-current-text"] = ""
        st.session_state["pa-assessment-dict"] = {}
        st.rerun()

    if prev_btn or next_btn:
        text = st.session_state["pa-text"]
        paragraphs = [line for line in text.splitlines() if line.strip()]
        st.session_state["pa-current-text"] = paragraphs[st.session_state["pa-idx"]]

    display_assessment_text(pa_text_container)

    if pa_pro_btn and audio_info is not None:
        # 去掉发言者的名字
        idx = st.session_state["pa-idx"]
        if idx == -1:
            st.error("不允许全文评估。请选择段落进行评估。")
            st.stop()

        reference_text = process_dialogue_text(st.session_state["pa-current-text"])

        st.session_state["pa-assessment"] = pronunciation_assessment_for(
            audio_info,
            reference_text,
        )
        st.session_state["pa-assessment-dict"][idx] = st.session_state["pa-assessment"]

        # # TODO:管理待处理任务列表
        # # 创建一个空的待处理任务列表
        # tasks = []
        # # 遍历发音评估结果
        # for word in st.session_state["pa-assessment"].get("recognized_words", []):
        #     # 如果单词的发音错误，将它添加到待处理任务列表中
        #     if word.get("error_type") == "Mispronunciation":
        #         tasks.append(word.word)

    if audio_playback_button and audio_info and st.session_state["pa-assessment"]:
        autoplay_audio_and_display_text(
            replay_text_placeholder,
            audio_info["bytes"],
            st.session_state["pa-assessment"]["recognized_words"],
        )

    if synthetic_audio_replay_button:
        play_synthesized_audio(
            st.session_state["pa-current-text"],
            voice_style,
            difficulty,
            scenario_category,
        )

    display_assessment_score(
        pa_report_container, PRONUNCIATION_SCORE_BADGE_MAPS, "pa-assessment"
    )

    display_pronunciation_assessment_words(
        pa_words_container,
        "pa-current-text",
        "pa-assessment-dict",
    )

    with st.expander("查看发音评估雷达图", expanded=False):
        radar_cols = st.columns(2)
        item_maps = {
            "pronunciation_score": "发音总评分",
            "accuracy_score": "准确性评分",
            "completeness_score": "完整性评分",
            "fluency_score": "流畅性评分",
            "prosody_score": "韵律分数",
        }
        with radar_cols[0]:
            st.markdown("当前段落的发音评估结果")
            view_radar(st.session_state["pa-assessment"], item_maps)

        # 开始至当前的平均值
        with radar_cols[1]:
            st.markdown("开始至当前段落的平均值")
            data = {"pronunciation_result": {key: 0.0 for key in item_maps.keys()}}
            idx = st.session_state["pa-idx"]

            # 计算截至当前的平均值
            for i in range(idx + 1):
                assessment = st.session_state["pa-assessment-dict"].get(i, {})
                for key in item_maps.keys():
                    data["pronunciation_result"][key] = data[
                        "pronunciation_result"
                    ].get(key, 0) + assessment.get("pronunciation_result", {}).get(
                        key, 0
                    )

            # 计算平均值
            if idx >= 0:
                for key in item_maps.keys():
                    data["pronunciation_result"][key] /= idx + 1

            view_radar(data, item_maps)

# endregion

# region 口语评估

if menu and menu.endswith("口语能力"):
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

    st.subheader("口语能力评估", divider="rainbow", anchor="口语能力评估")
    st.markdown(
        "选择 CEFR 等级和评估的场景类别，点击 '刷新[🔄]' 按钮，生成讨论话题清单。选择话题清单，点击 '录音[⏸️]' 或 `Browse files` 按钮，录制或上传关于此主题的讨论。准备就绪后，点击 '评估[🔖]' 按钮，系统将对你的口语能力进行评估，并生成评估报告。"
    )

    scenario_category = st.selectbox(
        "选择场景类别",
        CEFR_LEVEL_TOPIC[difficulty],
        index=0,
        key="scenario-category",
        placeholder="请选择场景类别",
        on_change=on_scenario_category_changed,
    )

    oa_topic = st.selectbox(
        "选择讨论话题",
        st.session_state["oa-topic-options"],
        # index=0,
        key="oa-topic",
        placeholder="请选择讨论话题",
    )

    oa_report_container = st.container(border=True)
    replay_text_placeholder = st.empty()
    status_placeholder = st.empty()
    oa_btn_cols = st.columns(8)

    oa_refresh_btn = oa_btn_cols[0].button(
        "刷新[:arrows_counterclockwise:]",
        key="refresh-oa-text",
        help="点击按钮，生成讨论主题清单。",
    )

    audio_session_output_key = "oa-audio"
    with oa_btn_cols[1]:
        st.session_state[audio_session_output_key] = mic_recorder(
            start_prompt="录音[⏸️]",
            stop_prompt="停止[🔴]",
        )

    oa_del_btn = oa_btn_cols[2].button(
        "删除[🗑️]",
        # disabled=not oa_audio_info,
        key="oa-delete-btn",
        help="✨ 点击按钮，删除已经录制的音频。",
    )

    oa_pro_btn = oa_btn_cols[3].button(
        "评估[🔖]",
        disabled=not oa_topic,
        key="oa-evaluation-btn",
        help="✨ 点击按钮，开始发音评估。",
    )

    audio_playback_button = oa_btn_cols[4].button(
        "回放[▶️]",
        disabled=not oa_topic,
        key="oa-play-btn",
        help="✨ 点击按钮，播放您的主题讨论录音。",
    )

    sample_button = oa_btn_cols[5].button(
        "样本[:page_facing_up:]",
        key="oa-sample",
        help="✨ 点击按钮，让AI为您生成话题讨论示例。",
        disabled=not st.session_state["oa-topic-options"] or not oa_topic,
    )

    synthetic_audio_replay_button = oa_btn_cols[6].button(
        "收听[:headphones:]",
        key="oa-replay",
        help="✨ 点击按钮，收听话题讨论示例文本的合成语音。",
        disabled=st.session_state["oa-sample-text"] == "",
    )

    tab0_col1, tab0_col2 = st.columns(2)
    audio_media_file = tab0_col1.file_uploader(
        "上传录制的音频【点击`Browse files`按钮，从本地上传文件】",
        accept_multiple_files=False,
        key="oa_media_file_key",
        type=["mp3", "wav"],
        help="""时长超过 15 秒，文字篇幅在 50 个字词(推荐)和 3 个句子以上。""",
    )

    content_cols = st.columns([16, 2])
    oa_words_container = content_cols[0].container(border=True)
    oa_legend_container = content_cols[1].container(border=True)

    with oa_legend_container:
        st.markdown("##### 图例")
        view_pronunciation_assessment_legend()

    if oa_refresh_btn:
        st.session_state["oa-topic-options"] = generate_oral_ability_topics_for(
            difficulty, scenario_category
        )
        st.rerun()

    if oa_del_btn:
        # 删除录制的音频
        st.session_state[audio_session_output_key] = None
        st.rerun()

    if oa_pro_btn:
        if not st.session_state[audio_session_output_key] and not audio_media_file:
            status_placeholder.error("请先录制音频或上传音频文件。")
            st.stop()
        if st.session_state[audio_session_output_key] is not None and audio_media_file:
            # 首先检查是否上传了音频文件同时录制了音频，如果是，则提示用户只能选择一种方式
            status_placeholder.error(
                "请注意，只能选择录制音频或上传音频文件中的一种方式进行评估。如果需要删除已经录制的音频，可以点击`删除[🗑️]`按钮。如果需要移除已上传的音频文件，可以在文件尾部点击`❌`标志。"
            )
            st.stop()

        # 判断是使用录制的音频还是上传的音频文件
        if audio_media_file is not None:
            audio = read_audio_file(audio_media_file)
        else:
            audio = st.session_state[audio_session_output_key]

        # 这里返回的是秒 float 类型
        audio["audio_duration"] = calculate_audio_duration(
            audio["bytes"], audio["sample_rate"], audio["sample_width"]
        )

        # 判断时长是否超过 15 秒
        if audio["audio_duration"] < 15:
            st.error(
                f"录制的音频时长必须至少为 15 秒。您当前的音频时长为：{audio['audio_duration']:.2f} 秒。"
            )
            st.stop()

        st.session_state["oa-assessment"] = oral_ability_assessment_for(
            audio,
            oa_topic,
        )

        # # TODO:管理待处理任务列表
        # # 创建一个空的待处理任务列表
        # tasks = []
        # # 遍历发音评估结果
        # for word in st.session_state["pa-assessment"].get("recognized_words", []):
        #     # 如果单词的发音错误，将它添加到待处理任务列表中
        #     if word.get("error_type") == "Mispronunciation":
        #         tasks.append(word.word)

    if sample_button:
        if not oa_topic:
            status_placeholder.error("请先选择话题。")
            st.stop()

        st.session_state["oa-sample-text"] = generate_oral_statement_template_for(
            oa_topic, difficulty
        )
        st.rerun()

    if audio_playback_button and st.session_state["oa-assessment"]:
        if not st.session_state[audio_session_output_key]:
            status_placeholder.error("请先录制音频或上传音频文件。")
            st.stop()

        if not st.session_state["oa-assessment"]:
            status_placeholder.error("请先进行发音评估。")
            st.stop()

        oa_audio_info = st.session_state[audio_session_output_key]
        autoplay_audio_and_display_text(
            replay_text_placeholder,
            oa_audio_info["bytes"],
            st.session_state["oa-assessment"]["recognized_words"],
        )

    if synthetic_audio_replay_button:
        play_synthesized_audio(
            st.session_state["oa-sample-text"],
            voice_style,
            difficulty,
            oa_topic,
        )

    display_assessment_score(
        oa_report_container,
        ORAL_ABILITY_SCORE_BADGE_MAPS,
        "oa-assessment",
        "content_result",
    )

    display_oral_pronunciation_assessment_results(
        oa_words_container,
        "oa-assessment",
    )

    with st.expander("查看口语能力评估雷达图", expanded=False):
        radar_cols = st.columns(2)
        item_maps = {
            "pronunciation_score": "发音总评分",
            "accuracy_score": "准确性评分",
            "completeness_score": "完整性评分",
            "fluency_score": "流畅性评分",
            "prosody_score": "韵律分数",
        }
        with radar_cols[0]:
            st.markdown("当前段落的发音评估结果")
            view_radar(st.session_state["pa-assessment"], item_maps)

        # 开始至当前的平均值
        with radar_cols[1]:
            st.markdown("开始至当前段落的平均值")
            data = {"pronunciation_result": {key: 0.0 for key in item_maps.keys()}}
            idx = st.session_state["pa-idx"]

            # 计算截至当前的平均值
            for i in range(idx + 1):
                assessment = st.session_state["pa-assessment-dict"].get(i, {})
                for key in item_maps.keys():
                    data["pronunciation_result"][key] = data[
                        "pronunciation_result"
                    ].get(key, 0) + assessment.get("pronunciation_result", {}).get(
                        key, 0
                    )

            # 计算平均值
            if idx >= 0:
                for key in item_maps.keys():
                    data["pronunciation_result"][key] /= idx + 1

            view_radar(data, item_maps)

# endregion

# region 写作评估

if menu and menu.endswith("写作评估"):
    pass

# endregion
