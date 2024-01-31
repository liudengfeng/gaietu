import logging

from mypylib.st_helper import check_access, configure_google_apis, setup_logger
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

# endregion

# region 边栏

# endregion

# region 主体

st.subheader("写作练习", divider="rainbow", anchor="写作练习")
w_cols = st.columns([4, 4, 2])
text = w_cols[0].text_area("输入文本", max_chars=10000, height=400)
suggestions = w_cols[1].container(border=True)
actions = w_cols[2].container(border=True)
# endregion
