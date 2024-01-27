import streamlit as st

from mypylib.st_helper import (
    TOEKN_HELP_INFO,
    check_access,
    check_and_force_logout,
    configure_google_apis,
    format_token_count,
    on_page_to,
)

# region 配置

st.set_page_config(
    page_title="能力评估",
    page_icon=":bookmark:",
    layout="wide",
)

check_access(False)
on_page_to("能力评估")
configure_google_apis()

menu_items = ["发音评估", "口语评估", "写作评估"]
menu_emojis = ["🔊", "🗣️", "✍️"]
menu_opts = [f"{e} {i}" for i, e in zip(menu_items, menu_emojis)]
menu = st.sidebar.selectbox("菜单", menu_opts, help="选择你要练习的项目")

st.sidebar.divider()
sidebar_status = st.sidebar.empty()
check_and_force_logout(sidebar_status)

sidebar_status.markdown(
    f"""令牌：{st.session_state.current_token_count} 累计：{format_token_count(st.session_state.total_token_count)}""",
    help=TOEKN_HELP_INFO,
)

# endregion
