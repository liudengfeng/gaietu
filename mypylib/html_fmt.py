import difflib
import streamlit as st


def view_error_counts_legend(session_state_key: str, idx=None):
    if idx is not None:
        st.write(st.session_state[session_state_key].get(idx, {}))
        d = st.session_state[session_state_key].get(idx, {}).get("error_counts", {})
    else:
        d = st.session_state[session_state_key].get("error_counts", {})
    # TODO:删除
    st.write(d)
    st.markdown("##### 图例")
    n1 = d.get("Mispronunciation", 0)
    st.markdown(
        f"<span style='color: black; background-color: #F5F5DC; margin-right: 10px;'>{n1}</span> <span>发音错误</span>",
        help="✨ 说得不正确的字词。",
        unsafe_allow_html=True,
    )
    n2 = d.get("Omission", 0)
    st.markdown(
        f"<span style='color: white; background-color: #A9A9A9; margin-right: 10px;'>{n2}</span> <span>遗漏</span>",
        help="✨ 脚本中已提供，但未说出的字词。",
        unsafe_allow_html=True,
    )
    n3 = d.get("Insertion", 0)
    st.markdown(
        f'<span style="color: white; background-color: #800080; margin-right: 10px;">{n3}</span>'
        + "<span>插入内容</span>",
        help="✨ 不在脚本中但在录制中检测到的字词。",
        unsafe_allow_html=True,
    )
    n4 = d.get("UnexpectedBreak", 0)
    st.markdown(
        f'<span style="color: black; background-color: #FFC0CB; margin-right: 10px;">{n4}</span>'
        + "<span>意外中断</span>",
        help="✨ 同一句子中的单词之间未正确暂停。",
        unsafe_allow_html=True,
    )
    n5 = d.get("MissingBreak", 0)
    st.markdown(
        f'<span style="color: black; background-color: #D3D3D3; margin-right: 10px;">{n5}</span>'
        + "<span>缺少停顿</span>",
        help="✨ 当两个单词之间存在标点符号时，词之间缺少暂停。",
        unsafe_allow_html=True,
    )
    n6 = d.get("Monotone", 0)
    st.markdown(
        f'<span style="color: white; background-color: #800080; margin-right: 10px;">{n6}</span>'
        + "<span>发音单调</span>",
        help="✨ 这些单词正以平淡且不兴奋的语调阅读，没有任何节奏或表达。",
        unsafe_allow_html=True,
    )


def display_grammar_errors(original, corrected, explanations):
    if not explanations:  # 如果解释列表为空
        return " ".join(f"<span>{word}</span>" for word in corrected.split())

    diff = difflib.ndiff(original.split(), corrected.split())
    diff = list(diff)  # 生成列表

    result = []
    explanations_copy = explanations.copy()  # 创建副本

    for i in range(len(diff)):
        if diff[i][0] == "-":
            if explanations_copy:  # 检查副本是否为空
                explanation = (
                    explanations_copy.pop(0)
                    .replace("'", "&#39;")
                    .replace('"', "&quot;")
                )
            else:
                explanation = "No explanation available"  # 提供一个默认的解释
            result.append(
                f"<del style='color:red;text-decoration: line-through' title='{explanation}'>{diff[i][2:].lstrip()}</del>"
            )
            if i + 1 < len(diff) and diff[i + 1][0] == "+":
                result.append(
                    f"<ins style='color:blue;text-decoration: underline' title='{explanation}'>{diff[i + 1][2:].lstrip()}</ins>"
                )
        elif diff[i][0] == "+":
            if i == 0 or diff[i - 1][0] != "-":
                if explanations_copy:  # 检查副本是否为空
                    explanation = (
                        explanations_copy.pop(0)
                        .replace("'", "&#39;")
                        .replace('"', "&quot;")
                    )
                else:
                    explanation = "No explanation available"  # 提供一个默认的解释
                result.append(
                    f"<ins style='color:blue;text-decoration: underline' title='{explanation}'>{diff[i][2:].lstrip()}</ins>"
                )
        else:
            result.append(f"<span>{diff[i][2:].lstrip()}</span>")

    return " ".join(result)
