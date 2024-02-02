import difflib
import streamlit as st


def view_error_counts_legend(session_state_key: str, idx=None):
    if idx is not None:
        d = st.session_state[session_state_key].get(idx, {}).get("error_counts", {})
    else:
        d = st.session_state[session_state_key].get("error_counts", {})
    st.markdown("##### 图例")

    n1 = str(d.get("Mispronunciation", 0)).zfill(3)
    st.markdown(
        f"<div><span style='text-align: right; color: black; background-color: #F5F5DC; margin-right: 5px;'>{n1}</span> <span>发音错误</span></div>",
        help="✨ 说得不正确的字词。",
        unsafe_allow_html=True,
    )

    n2 = str(d.get("Omission", 0)).zfill(3)
    st.markdown(
        f"<div><span style='text-align: right; color: white; background-color: #808080; margin-right: 5px;'>{n2}</span> <span>遗漏</span></div>",
        help="✨ 脚本中已提供，但未说出的字词。",
        unsafe_allow_html=True,
    )

    n3 = str(d.get("Insertion", 0)).zfill(3)
    st.markdown(
        f"<div><span style='text-align: right; color: white; background-color: #B7410E; margin-right: 5px;'>{n3}</span> <span>插入内容</span></div>",
        help="✨ 不在脚本中但在录制中检测到的字词。",
        unsafe_allow_html=True,
    )

    n4 = str(d.get("UnexpectedBreak", 0)).zfill(3)
    st.markdown(
        f"<div><span style='text-align: right; color: black; background-color: #FFC0CB; margin-right: 5px;'>{n4}</span> <span>意外中断</span></div>",
        help="✨ 同一句子中的单词之间未正确暂停。",
        unsafe_allow_html=True,
    )

    n5 = str(d.get("MissingBreak", 0)).zfill(3)
    st.markdown(
        f"<div><span style='text-align: right; color: black; background-color: #D3D3D3; margin-right: 5px;'>{n5}</span> <span>缺少停顿</span></div>",
        help="✨ 当两个单词之间存在标点符号时，词之间缺少暂停。",
        unsafe_allow_html=True,
    )

    n6 = str(d.get("Monotone", 0)).zfill(3)
    st.markdown(
        f"<div><span style='text-align: right; color: white; background-color: #800080; margin-right: 5px;'>{n6}</span> <span>发音单调</span></div>",
        help="✨ 这些单词正以平淡且不兴奋的语调阅读，没有任何节奏或表达。",
        unsafe_allow_html=True,
    )


def pronunciation_assessment_word_format(word):
    if isinstance(word, str):
        return f"<span style='margin-right: 5px;'>{word}</span>"
    error_type = word.error_type
    accuracy_score = round(word.accuracy_score)
    result = ""
    if error_type == "Mispronunciation":
        result = f"<span style='color: black; background-color: #F5F5DC; margin-right: 5px; text-decoration: underline;' title='{accuracy_score}'>{word}</span>"
    elif error_type == "Omission":
        result = f"<span style='color: white; background-color: #808080; margin-right: 5px;'>[{word}]</span>"
    elif error_type == "Insertion":
        result = f"<span style='color: white; background-color: #B7410E; margin-right: 5px; text-decoration: line-through;' title='{accuracy_score}'>{word}</span>"

    if word.is_unexpected_break:
        result += f"<span style='color: black; background-color: #FFC0CB; text-decoration: line-through; margin-right: 5px;' title='{accuracy_score}'>[]</span>"
        result += f"<span style='color: white; background-color: #B7410E; margin-right: 5px;' title='{accuracy_score}'>{word}</span>"
    elif word.is_missing_break:
        result += f"<span style='color: black; background-color: #D3D3D3; margin-right: 5px;' title='{accuracy_score}'>[]</span>"
        result += (
            f"<span style='margin-right: 5px;' title='{accuracy_score}'>{word}</span>"
        )
    else:
        result = f"<span style='margin-right: 5px;'>{word}</span>"

    if word.is_monotone:
        result = f"<u style='text-decoration: underline; text-decoration-color: purple;'>{result}</u>"
    return result


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
