import streamlit as st

from mypylib.st_helper import (
    check_access,
    check_and_force_logout,
    configure_google_apis,
    save_and_clear_all_learning_records,
)

# region 配置

st.set_page_config(
    page_title="能力评估",
    page_icon=":bookmark:",
    layout="wide",
)

check_access(False)
st.session_state["current-page"] = "评估"
save_and_clear_all_learning_records()
configure_google_apis()
# endregion

menu_items = ["发音评估", "口语评估", "写作评估"]
menu = st.sidebar.selectbox("菜单", menu_items, help="选择你要练习的项目")
st.sidebar.divider()
sidebar_status = st.sidebar.empty()
check_and_force_logout(sidebar_status)
