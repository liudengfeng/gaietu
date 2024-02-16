import streamlit as st
import logging

logger = logging.getLogger("streamlit")


def init_words_between_containers(words):
    st.session_state["source-container-words"] = words.copy()
    st.session_state["target-container-words"] = []


def move_words_between_containers(
    source_container, target_container, words, is_char=False
):
    """
    Move words between two containers.

    Args:
        source_container: The container from which words are moved.
        target_container: The container to which words are moved.
        words: The list of words to be moved.
        is_char: A boolean indicating whether the words are characters.

    Returns:
        None
    """

    if "source-container-words" not in st.session_state:
        st.session_state["source-container-words"] = words.copy()

    if "target-container-words" not in st.session_state:
        st.session_state["target-container-words"] = []

    group_size = 36 if is_char else 6
    n = len(st.session_state["source-container-words"])
    src_cols = source_container.columns(group_size)
    for i in range(n):
        if src_cols[i % group_size].button(
            st.session_state["source-container-words"][i],
            key=f"word-src-{i}",
            help="✨ 点击按钮将单词移动到目标位置。",
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
            help="✨ 点击按钮将单词移动回目标位置。",
            # use_container_width=True,
        ):
            tw = st.session_state["target-container-words"][i]
            st.session_state["source-container-words"].append(tw)
            st.session_state["target-container-words"].remove(tw)
            st.rerun()
