import logging

from mypylib.st_helper import (
    check_access,
    check_and_force_logout,
    configure_google_apis,
    setup_logger,
)
import streamlit as st

# region 配置

# 创建或获取logger对象


logger = logging.getLogger("streamlit")
setup_logger(logger)

st.set_page_config(
    page_title="写作练习",
    page_icon=":muscle:",
    layout="wide",
)

check_access(False)
configure_google_apis()

sidebar_status = st.sidebar.empty()
check_and_force_logout(sidebar_status)

# endregion

# region 边栏

# endregion

# region 主体

st.subheader("写作练习", divider="rainbow", anchor="写作练习")
st.markdown(
    "本写作练习旨在全面提升您的写作技巧和能力。我们提供多种场景的写作练习，以帮助您在各种实际情境中提升写作技巧。AI辅助功能将在您的写作过程中提供语法、词汇、主题和风格的评估或修正，甚至在需要时提供创作灵感。这是一个全面提升您的写作能力的过程，旨在让您在各种写作场景中都能自如应对。"
)
w_cols = st.columns([4, 4, 2])
text = w_cols[0].text_area("输入文本", max_chars=10000, height=500)
suggestions = w_cols[1].container(border=True)
actions = w_cols[2].container(border=True)

w_btn_cols = st.columns(8)


# st.markdown(
#     """
#     <span style='color:red'><s>删除的词语</s></span>
#     <span style='color:blue'><u>需要关注的词语</u></span>
#     <span style='color:green;text-decoration: wavy underline'>可能的语法错误</span>
#     <span style='color:purple'><em>引用的词语</em></span>
#     <span style='color:orange'><strong><em>强烈强调的词语</em></strong></span>
#     """,
#     unsafe_allow_html=True,
# )

if prompt := st.chat_input("从AI写作助教处获取支持"):
    st.write(f"您输入的提示是：{prompt}")

# endregion
