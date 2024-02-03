from pathlib import Path

import streamlit as st
from menu import return_home

from mypylib.st_helper import on_page_to

st.set_page_config(
    page_title="帮助中心",
    page_icon="🛠️",
    layout="centered",
)
return_home()
on_page_to("帮助中心")

CURRENT_CWD: Path = Path(__file__).parent.parent
VIDEO_DIR = CURRENT_CWD / "resource/video_tip"

# region 常见问题

st.subheader(":information_source: 产品介绍", divider="rainbow", anchor="产品介绍")

st.subheader(":woman-tipping-hand: 常见问题", divider="rainbow", anchor="常见问题")

with st.expander(":bulb: 如何注册？", expanded=False):
    # vfp = VIDEO_DIR / "单词" / "基础词库整体加入个人词库.mp4"
    # st.video(str(vfp))
    pass

with st.expander(":bulb: 如何订阅？", expanded=False):
    # vfp = VIDEO_DIR / "单词" / "基础词库整体加入个人词库.mp4"
    # st.video(str(vfp))
    pass

with st.expander(":bulb: 如何登录？", expanded=False):
    fp = VIDEO_DIR / "如何登录.mp4"
    st.video(str(fp))

with st.expander(":bulb: 忘记密码怎么办？", expanded=False):
    # vfp = VIDEO_DIR / "单词" / "基础词库整体加入个人词库.mp4"
    # st.video(str(vfp))
    pass

with st.expander(":bulb: 如何调整布局让屏幕显示更美观？", expanded=False):
    fp = VIDEO_DIR / "调整布局.mp4"
    st.video(str(fp))

# endregion

# region 使用指南
st.subheader("使用指南")

with st.expander(":bulb: 如何把一个基础词库整体添加到个人词库？", expanded=False):
    pass

with st.expander(":bulb: 如何进行阅读练习", expanded=False):
    fp = str(VIDEO_DIR / "reading_excise.mp4")
    video_file = open(fp, "rb")
    video_bytes = video_file.read()
    st.video(video_bytes)

# endregion

# region 联系我们
st.subheader("联系我们")
# endregion
