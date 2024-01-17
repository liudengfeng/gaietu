from pathlib import Path

import streamlit as st
from PIL import Image

from mypylib.st_helper import on_page_changed

CURRENT_CWD: Path = Path(__file__).parent.parent
WXSKM_DIR = CURRENT_CWD / "resource" / "wxskm"

st.session_state["current-page"] = "订阅套餐"

on_page_changed()

# region 订阅付费

st.subheader(":package: 订阅套餐", anchor="订阅套餐", divider="rainbow")

# Define pricing tiers
pricing_tiers = [
    {
        "title": "黄金版",
        "price": "6570",
        "unit": "每年",
        "description": [
            "按天计费节约40%",
            "学习分析报告",
            "用英语与AI🤖对话",
            "成才奖励最多30%",
        ],
        "img_name": "zx.jpeg",
    },
    {
        "title": "白金版",
        "price": "1890",
        "unit": "每季度",
        "description": [
            "按天计费节约30%",
            "学习分析报告",
            "用英语与AI🤖对话",
            "成才奖励最多20%",
        ],
        "img_name": "pf.jpeg",
    },
    {
        "title": "星钻版",
        "price": "720",
        "unit": "每月",
        "description": [
            "按天计费节约20%",
            "学习分析报告",
            "",
            "成才奖励最多10%",
        ],
        "img_name": "gf.jpeg",
    },
    {
        "title": "尝鲜版",
        "price": "210",
        "unit": "每周",
        "description": [
            "按每天30元计费",
            "每天不限时学习",
            "",
            "随机小额红包🧧",
        ],
        "img_name": "pa.jpeg",
    },
]

cols = st.columns(len(pricing_tiers))

# Create a column for each pricing tier
for col, tier in zip(cols, pricing_tiers):
    # with col.container():
    # col.header(tier["title"])
    col.subheader(f"￥{tier['price']} / {tier['unit']}")
    for feature in tier["description"]:
        col.markdown(f":high_brightness: {feature}")
    # col.button(tier["img_name"])
    image = Image.open(WXSKM_DIR / tier["img_name"])
    col.image(image, width=100)

# endregion
