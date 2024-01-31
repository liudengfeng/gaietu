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
