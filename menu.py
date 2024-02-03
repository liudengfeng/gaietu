import streamlit as st


def authenticated_menu():
    # Show a navigation menu for authenticated users
    st.sidebar.page_link("Home.py", label="Switch accounts")
    st.sidebar.page_link("pages/02_👥_用户.py", label="Your profile")
    st.sidebar.page_link("pages/12_📚_单词.py", label="单词练习")
    if st.session_state.role in ["管理员"]:
        st.sidebar.page_link("pages/40_⚙️_系统.py", label="Manage users")
        # st.sidebar.page_link(
        #     "pages/super-admin.py",
        #     label="Manage admin access",
        #     disabled=st.session_state.role != "super-admin",
        # )


def unauthenticated_menu():
    # Show a navigation menu for unauthenticated users
    st.sidebar.page_link("Home.py", label="主页", icon="🏠")
    st.sidebar.page_link(
        "pages/00_👤_注册.py",
        label="用户注册",
        help="✨ 请注意，您需要先完成注册才能继续。",
        icon="👤",
    )
    st.sidebar.page_link(
        "pages/01_💰_订阅.py",
        label="订阅套餐",
        help="请选择适合您的套餐选项。",
        icon="💰",
    )
    st.sidebar.page_link(
        "pages/30_🛠️_帮助.py",
        label="帮助文档",
        help="请选择适合您的套餐选项。",
        icon="🛠️",
    )


def menu():
    # Determine if a user is logged in or not, then show the correct
    # navigation menu
    if "role" not in st.session_state or st.session_state.role is None:
        unauthenticated_menu()
        return
    authenticated_menu()


def menu_with_redirect():
    # Redirect users to the main page if not logged in, otherwise continue to
    # render the navigation menu
    if "role" not in st.session_state or st.session_state.role is None:
        st.switch_page("Home.py")
    menu()
