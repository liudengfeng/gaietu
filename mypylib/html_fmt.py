import difflib
import streamlit as st
import re


def view_error_counts_legend(session_state_key: str, idx=None):
    if idx is not None:
        d = st.session_state[session_state_key].get(idx, {}).get("error_counts", {})
    else:
        d = st.session_state[session_state_key].get("error_counts", {})
    st.markdown("##### 图例")

    n1 = str(d.get("Mispronunciation", 0)).rjust(3).replace(" ", "&nbsp;")
    n2 = str(d.get("Omission", 0)).rjust(3).replace(" ", "&nbsp;")
    n3 = str(d.get("Insertion", 0)).rjust(3).replace(" ", "&nbsp;")
    n4 = str(d.get("UnexpectedBreak", 0)).rjust(3).replace(" ", "&nbsp;")
    n5 = str(d.get("MissingBreak", 0)).rjust(3).replace(" ", "&nbsp;")
    n6 = str(d.get("Monotone", 0)).rjust(3).replace(" ", "&nbsp;")

    st.markdown(
        f"<div><span style='text-align: right; color: black; background-color: #FFD700; margin-right: 5px;'>{n1}</span> <span>发音错误</span></div>",
        help="✨ 说得不正确的字词。",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div><span style='text-align: right; color: white; background-color: #696969; margin-right: 5px;'>{n2}</span> <span>遗漏</span></div>",
        help="✨ 脚本中已提供，但未说出的字词。",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div><span style='text-align: right; color: white; background-color: #FF4500; margin-right: 5px;'>{n3}</span> <span>插入内容</span></div>",
        help="✨ 不在脚本中但在录制中检测到的字词。",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div><span style='text-align: right; color: black; background-color: #FFC0CB; margin-right: 5px;'>{n4}</span> <span>意外中断</span></div>",
        help="✨ 同一句子中的单词之间未正确暂停。",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div><span style='text-align: right; color: black; background-color: #D3D3D3; margin-right: 5px;'>{n5}</span> <span>缺少停顿</span></div>",
        help="✨ 当两个单词之间存在标点符号时，词之间缺少暂停。",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"<div><span style='text-align: right; color: white; background-color: #800080; margin-right: 5px;'>{n6}</span> <span>发音单调</span></div>",
        help="✨ 这些单词正以平淡且不兴奋的语调阅读，没有任何节奏或表达。",
        unsafe_allow_html=True,
    )


def pronunciation_assessment_word_format(word_obj):
    if isinstance(word_obj, str):
        return f'<span style="margin-right: 5px;">{word_obj}</span>'
    error_type = word_obj.error_type
    accuracy_score = round(word_obj.accuracy_score)
    underline_style = (
        "text-decoration: underline wavy; text-decoration-color: purple;"
        if word_obj.is_monotone
        else ""
    )
    result = ""

    if error_type == "Mispronunciation":
        result = f'<span style="color: black; background-color: #FFD700; margin-right: 5px; text-decoration: underline; {underline_style}" title="{accuracy_score}">{word_obj.word}</span>'
    elif error_type == "Omission":
        result = f'<span style="color: white; background-color: #696969; margin-right: 5px; {underline_style}">[{word_obj.word}]</span>'
    elif error_type == "Insertion":
        result = f'<span style="color: white; background-color: #FF4500; margin-right: 5px; text-decoration: line-through; {underline_style}" title="{accuracy_score}">{word_obj.word}</span>'

    if word_obj.is_unexpected_break:
        result = f'<span style="color: black; background-color: #FFC0CB; text-decoration: line-through; margin-right: 5px; {underline_style}" title="{accuracy_score}">[]</span>'
        result += f'<span style="color: white; background-color: #FF4500; margin-right: 5px; {underline_style}" title="{accuracy_score}">{word_obj.word}</span>'
    elif word_obj.is_missing_break:
        result = f'<span style="color: black; background-color: #D3D3D3; margin-right: 5px; {underline_style}" title="{accuracy_score}">[]</span>'
        result += f'<span style="margin-right: 5px; {underline_style}" title="{accuracy_score}">{word_obj.word}</span>'
    elif not result:
        result = f'<span style="margin-right: 5px; {underline_style};" title="{accuracy_score}">{word_obj.word}</span>'

    return result


def display_grammar_errors(corrected, explanations):
    if corrected == "请使用英语写作！":
        return '<p style="color: red; font-weight: bold;">' + corrected + "</p>"
    if len(explanations) == 0:
        return '<p style="color: green; font-weight: bold;">在您的写作练习中没有检测到语法错误。</p>'

    pattern_del = r"~~(.*?)~~"
    pattern_add = r"<ins>(.*?)</ins>"
    pattern_both = r"~~(.*?)~~\s*<ins>(.*?)</ins>"

    counter = [0]  # 使用列表来作为可变的计数器

    def replace_both(match):
        old, new = match.groups()
        explanation = explanations[counter[0]]
        counter[0] += 1
        return f'<span style="text-decoration: line-through; color: red;" title="{explanation}">{old}</span> <span style="text-decoration: underline; color: green;" title="{explanation}">[{new}]</span>'

    def replace_del(match):
        old = match.group(1)
        explanation = explanations[counter[0]]
        counter[0] += 1
        return f'<span style="text-decoration: line-through; color: red;" title="{explanation}">{old}</span>'

    def replace_add(match):
        new = match.group(1)
        explanation = explanations[counter[0]]
        counter[0] += 1
        return f'<span style="text-decoration: underline; color: #008000;" title="{explanation}">[{new}]</span>'

    corrected = re.sub(pattern_both, replace_both, corrected)
    corrected = re.sub(pattern_del, replace_del, corrected)
    corrected = re.sub(pattern_add, replace_add, corrected)

    corrected = corrected.replace("\n", "<br/>")

    return corrected
