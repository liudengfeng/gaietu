import streamlit as st
import logging

logger = logging.getLogger("streamlit")


def move_words_between_containers(source_container, target_container, words):
    if "source-container-words" not in st.session_state:
        st.session_state["source-container-words"] = words.copy()

    if "target-container-words" not in st.session_state:
        st.session_state["target-container-words"] = []

    group_size = 6
    n = len(st.session_state["source-container-words"])
    src_cols = source_container.columns(group_size)
    for i in range(n):
        if src_cols[i % group_size].button(
            st.session_state["source-container-words"][i],
            key=f"word-src-{i}",
            help="✨ 点击按钮，将单词移动到目标位置。",
            # use_container_width=True,
        ):
            sw = st.session_state["source-container-words"][i]
            st.session_state["target-container-words"].append(sw)
            st.session_state["source-container-words"].remove(sw)
            # logger.info(f"{i} {sw}")
            st.rerun()

    tgt_cols = target_container.columns(group_size)
    for i in range(len(st.session_state["target-container-words"])):
        if tgt_cols[i % group_size].button(
            st.session_state["target-container-words"][i],
            key=f"word-tgt-{i}",
            help="✨ 点击按钮，将单词放回到目标位置。",
            # use_container_width=True,
        ):
            tw = st.session_state["target-container-words"][i]
            st.session_state["source-container-words"].append(tw)
            st.session_state["target-container-words"].remove(tw)
            st.rerun()
