import json
import logging
import os
import random
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import streamlit as st
from PIL import Image

from menu import menu
from mypylib.auth_utils import is_valid_phone_number
from mypylib.azure_speech import speech_synthesis_get_available_voices
from mypylib.constants import LANGUAGES, VOICES_FP
from mypylib.db_interface import DbInterface
from mypylib.db_model import PaymentStatus, UserRole, str_to_enum
from mypylib.st_helper import (  # save_and_clear_all_learning_records,
    check_and_force_logout,
    get_firestore_client,
    on_page_to,
    setup_logger,
)

# 创建或获取logger对象
logger = logging.getLogger("streamlit")
setup_logger(logger)

CURRENT_CWD: Path = Path(__file__).parent
LOGO_DIR: Path = CURRENT_CWD / "resource/logo"

# Initialize st.session_state.role to None
if "role" not in st.session_state:
    st.session_state.role = None

st.set_page_config(
    page_title="主页",
    page_icon="🏠",
    layout="wide",
)


on_page_to("Home")
# save_and_clear_all_learning_records()


if "dbi" not in st.session_state:
    st.session_state["dbi"] = DbInterface(get_firestore_client())


# region 更新语音列表
need_update = False
# 如果文件不存在，或者文件的最后修改时间距离当前时间超过120天
if not os.path.exists(VOICES_FP):
    need_update = True
else:
    # 获取当前时间
    now = time.time()
    # 获取文件的最后修改时间
    mtime = os.path.getmtime(VOICES_FP)
    if now - mtime >= 120 * 24 * 60 * 60:
        need_update = True

if need_update:
    res = {}
    with st.spinner("正在更新语音列表，请稍候..."):
        for lan in LANGUAGES:
            res[lan] = speech_synthesis_get_available_voices(
                lan,
                st.secrets["Microsoft"]["SPEECH_KEY"],
                st.secrets["Microsoft"]["SPEECH_REGION"],
            )
        # 将数据存储为 JSON 格式
        with open(VOICES_FP, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False)
# endregion

s_cols = st.sidebar.columns(3)
is_logged_in = st.session_state.dbi.cache.get("user_info", {}).get(
    "is_logged_in", False
)

login_btn = s_cols[0].button(
    label="离线[💔]" if not is_logged_in else "在线[📶]",
    type="primary" if not is_logged_in else "secondary",
    disabled=True,
)

logout_btn = s_cols[1].button(
    "退出",
    help="✨ 在公共场所使用本产品时，请在离开前退出登录，以保护您的隐私和安全。",
    disabled=not is_logged_in,
)


sidebar_status = st.sidebar.empty()

# 在页面加载时检查是否有需要强制退出的登录会话
check_and_force_logout(sidebar_status)


def extend_service_period():
    # if is_logged_in:
    db = st.session_state.dbi.db
    extend_time_btn_disabled = False
    # 获取用户的数据
    user_dic = st.session_state.dbi.get_user(False)
    # 获取用户角色
    user_role = str_to_enum(user_dic.get("user_role"), UserRole)
    # 定义角色范围
    role_range = [UserRole.SVIP, UserRole.ADMIN]
    # logger.info(f"用户角色：{user_role} {type(user_role)}")
    if user_role in role_range:
        return

    user_tz = user_dic["timezone"]
    timezone = pytz.timezone(user_tz)
    # 获取当前的日期和时间
    current_datetime = datetime.now(timezone)
    # 查询在服务期内，处于服务状态的支付记录
    payment_record = st.session_state.dbi.get_last_active_payment()

    if not payment_record:
        return

    # 限制在正常时段才能领取
    if 6 <= current_datetime.hour <= 20:
        extend_time_btn_disabled = False
    else:
        extend_time_btn_disabled = True

    # 获取用户的最后领取日期
    last_received_date = user_dic.get("last_received_date")
    # 检查 last_received_date 是否存在并且是 datetime 对象
    if last_received_date and isinstance(last_received_date, datetime):
        if current_datetime.date() == last_received_date.date():
            extend_time_btn_disabled = True

    extend_time_btn = s_cols[2].button(
        "免费🎁",
        disabled=extend_time_btn_disabled,
        help="✨ 付费用户每天上午6点至下午8点打卡。奖励1小时。",
    )

    if extend_time_btn and payment_record:
        # 获取用户的到期时间
        expiry_time = payment_record.get("expiry_time", datetime.now(timezone))

        # 增加1小时
        new_expiry_time = expiry_time + timedelta(hours=1)

        # 更新用户的到期时间

        # 获取订单号
        order_id = payment_record.get("order_id")

        # logger.info(f"订单号：{order_id}")

        # 获取 payments 集合中的文档引用
        doc_ref = db.collection("payments").document(order_id)

        # 更新 expiry_time 字段
        doc_ref.update({"expiry_time": new_expiry_time})

        # 获取手机号码
        phone_number = user_dic["phone_number"]

        # 获取 users 集合中的文档引用
        doc_ref = db.collection("users").document(phone_number)

        # 更新 last_received_date 字段
        doc_ref.update({"last_received_date": current_datetime})

        # 重新刷新
        st.rerun()

    if payment_record:
        # 计算剩余的时间
        expiry_time = payment_record.get("expiry_time", datetime.now(timezone))
        remaining_time = (expiry_time - datetime.now(timezone)).total_seconds()
        remaining_days = remaining_time // (24 * 60 * 60)
        remaining_hours = (remaining_time - remaining_days * 24 * 60 * 60) // 3600
        remaining_minutes = (
            remaining_time - remaining_days * 24 * 60 * 60 - remaining_hours * 3600
        ) // 60
        sidebar_status.info(
            f"剩余{remaining_days:.0f}天{remaining_hours:.0f}小时{remaining_minutes:.0f}分钟到期"
        )


# 登录用户才能使用免费功能
if is_logged_in:
    extend_service_period()

# 没有登录的用户，显示登录表单
if not is_logged_in:
    with st.sidebar.form(key="login_form", clear_on_submit=True):
        phone_number = st.text_input(
            "手机号码",
            type="password",
            key="phone_number",
            help="✨ 请输入手机号码",
            placeholder="输入手机号码",
        )
        password = st.text_input(
            "密码",
            type="password",
            key="password",
            help="✨ 输入个人登录密码",
            placeholder="输入个人登录密码",
        )
        sub_btn = st.form_submit_button(label="登录")
        if sub_btn:
            if not is_valid_phone_number(phone_number):
                sidebar_status.error(
                    f"请输入有效的手机号码。您输入的号码是：{phone_number}"
                )
                st.stop()
            else:
                info = st.session_state.dbi.login(
                    phone_number=phone_number, password=password
                )
                if info["status"] == "success":
                    sidebar_status.success(info["message"])
                    time.sleep(2)
                    st.rerun()
                elif info["status"] == "warning":
                    sidebar_status.warning(info["message"])
                    st.stop()
                else:
                    sidebar_status.error(info["message"])
                    st.stop()
else:
    sidebar_status.success(
        f"您已登录，{st.session_state.dbi.cache['user_info']['display_name']} 您好！"
    )

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
## `Gaietu`[英语速学]

**Gaietu**的功能包括：

**:books: 记忆单词**：通过AI智能推荐和游戏化学习，让你轻松记住单词。

**🎤 口语练习**：与AI对话，提高口语能力。

**🎧 听力练习**：提高听力能力。

**:book: 阅读理解**：阅读原汁原味的英语文章，提升阅读水平。

**✍️ 写作练习**：根据提示写出流利的英语句子。

**🗣️ 能力评估**：使用最新微软语言对话能力评估技术，帮助你纠正错误发音，提升对话能力。

**只需要一副麦克风、耳机，就可以随时随地学习英语。**                
        """
    )


logo_image = Image.open(LOGO_DIR / "logo.png")
with col2:
    st.image(logo_image, width=320)
st.divider()


step_cols = st.columns(5)
if step_cols[1].button(":bust_in_silhouette: 注册用户", key="注册用户"):
    st.switch_page("pages/00_👤_注册.py")

if step_cols[2].button(":package: 订阅套餐", key="订阅套餐"):
    st.switch_page("pages/01_💰_订阅.py")

if step_cols[3].button(":key: 登录使用", key="登录使用"):
    st.switch_page("Home.py")

log_cols = st.columns(3)
welcome_image = Image.open(LOGO_DIR / "welcome-1.jpg")
with log_cols[1]:
    st.image(welcome_image, use_column_width=True)


st.markdown(
    """\
欢迎来到`Gaietu` [英语速学] ，你的英语学习伙伴！

**Gaietu**是一款功能强大的英语学习app，它使用最新AI技术和微软发音评估技术，可以帮助你快速提升英语水平。

**Gaietu**，让你学好英语，so easy！
""",
    unsafe_allow_html=True,
)

if is_logged_in:
    if logout_btn:
        st.session_state.dbi.logout()
        sidebar_status.success("已退出登录")
        time.sleep(1)
        st.rerun()
