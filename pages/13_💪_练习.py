import streamlit as st

from mypylib.st_helper import (
    check_access,
    check_and_force_logout,
    configure_google_apis,
)

# region 配置

st.set_page_config(
    page_title="练习",
    page_icon=":muscle:",
    layout="wide",
)

check_access(False)
configure_google_apis()

# endregion

menu_items = [":ear: 听说练习", ":open_book: 阅读练习", ":pencil2: 写作练习"]
menu = st.sidebar.selectbox("菜单", menu_items, help="请选择您要进行的练习项目")
st.sidebar.divider()
sidebar_status = st.sidebar.empty()
check_and_force_logout(sidebar_status)
