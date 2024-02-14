import streamlit as st

words = [
    "apple",
    "banana",
    "cherry",
    "dragonfruit",
    "elderberry",
    "fig",
    "grape",
    "honeydew",
    "ice cream",
    "jackfruit",
    "kiwi",
    "lemon",
    "mango",
    "nectarine",
    "orange",
    "pineapple",
    "quince",
    "raspberry",
    "strawberry",
    "tangerine",
    "umbrella fruit",
    "vanilla",
    "watermelon",
    "xigua",
    "yellow passionfruit",
    "zucchini",
    "fruit salad",
    "berry smoothie",
    "caramel apple",
    "dried figs",
]

if "source_words" not in st.session_state:
    st.session_state["source_words"] = words.copy()

if "target_words" not in st.session_state:
    st.session_state["target_words"] = [None] * len(words)


def move_words_between_containers(source_container, target_container):
    n = len(words)
    group_size = 6
    for j in range(0, n, group_size):
        src_cols = source_container.columns(group_size)
        for i in range(j, min(j + group_size, n)):
            if st.session_state["source_words"][i] is not None:
                if src_cols[i % group_size].button(
                    st.session_state["source_words"][i],
                    key=f"word-src-{i}",
                    help="✨ 点击选择移动单词。",
                    use_container_width=True,
                ):
                    st.session_state["target_words"].append(
                        st.session_state["source_words"][i]
                    )
                    st.session_state["source_words"].remove(
                        st.session_state["source_words"][i]
                    )
                    st.rerun()

    n = len(st.session_state["target_words"])
    for j in range(0, n, group_size):
        tgt_cols = target_container.columns(group_size)
        for i in range(j, min(j + group_size, n)):
            if tgt_cols[i % group_size].button(
                st.session_state["target_words"][i],
                key=f"word-tgt-{i}",
                help="✨ 点击选择移动单词。",
                use_container_width=True,
            ):
                st.session_state["source_words"].append(
                    st.session_state["target_words"][i]
                )
                st.session_state["target_words"].remove(
                    st.session_state["target_words"][i]
                )
                st.rerun()


source_container = st.container()
st.divider()
target_container = st.container()

move_words_between_containers(source_container, target_container)
