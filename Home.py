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
    add_exercises_to_db,
    get_firestore_client,
    on_project_changed,
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

menu()
on_project_changed("Home")
add_exercises_to_db()


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
is_logged_in = st.session_state.dbi.is_logged_in()


login_btn = s_cols[0].button(
    label="离线[💔]" if not is_logged_in else "在线[🌐]",
    disabled=True,
)

logout_btn = s_cols[1].button(
    "退出[🏃‍♂️]",
    help="✨ 在公共场所使用本产品时，请在离开前退出登录，以保护您的隐私和安全。",
    disabled=not is_logged_in,
)

if not is_logged_in:
    st.sidebar.info(
        "请注意，如果您使用同一账号在多个地方同时登录，系统将只保留最新的登录会话，其他早先的登录会话将被自动注销。",
        icon="🚨",
    )

sidebar_status = st.sidebar.empty()


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
                    st.session_state.role = st.session_state.dbi.cache["user_info"][
                        "user_role"
                    ]
                    time.sleep(2)
                    st.rerun()
                elif info["status"] == "pending":
                    sidebar_status.warning(info["message"])
                    time.sleep(2)
                    st.switch_page("pages/01_💰_订阅.py")
                elif info["status"] == "warning":
                    sidebar_status.warning(info["message"])
                    st.stop()
                else:
                    sidebar_status.error(info["message"])
                    time.sleep(2)
                    st.switch_page("pages/00_📇_注册.py")
else:
    sidebar_status.success(
        f"您已登录，{st.session_state.dbi.cache['user_info']['display_name']} 您好！"
    )

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        ## `Gaietu`[英语学习]

        **Gaietu**，你的全方位英语学习平台！我们提供记忆单词、口语练习、听力练习、阅读理解、写作练习和能力评估等一站式服务，让你的英语学习之旅更加丰富多彩。

        **👩‍🏫 卓越的AI教师**：我们的AI教师，智力超群，知识广博，利用先进的语音合成技术，为你提供纯正的发音，带你体验前所未有的英语学习之旅。

        **⏰ 24小时在线**：无论何时何地，只要你想学，我们的虚拟教练都会在线等待你，让你随时随地享受英语学习的乐趣，无需受时间和地点的限制。

        **💰 性价比高**：我们提供高质量、价格合理的教学服务。我们的课程设计精心，教师资质优秀，使我们的服务具有高性价比。选择我们，你将获得超值的学习体验，让你的投资物超所值。

        """
    )

logo_image = Image.open(LOGO_DIR / "logo.jpg")
with col2:
    st.image(logo_image, width=360)
st.divider()


step_cols = st.columns(3)
with step_cols[0]:
    img1 = Image.open(LOGO_DIR / "step-1.jpg")
    st.image(img1, use_column_width=True)

with step_cols[1]:
    img2 = Image.open(LOGO_DIR / "step-2.jpg")
    st.image(img2, use_column_width=True)

with step_cols[2]:
    img3 = Image.open(LOGO_DIR / "step-3.jpg")
    st.image(img3, use_column_width=True)

if step_cols[0].button(":bust_in_silhouette: 注册用户", key="注册用户"):
    st.switch_page("pages/00_📇_注册.py")

if step_cols[1].button(":package: 订阅续费", key="订阅续费"):
    st.switch_page("pages/01_💰_订阅.py")

if step_cols[2].button(":key: 登录使用", key="登录使用"):
    st.switch_page("Home.py")


if is_logged_in:
    if logout_btn:
        add_exercises_to_db(True)
        st.session_state.dbi.logout()
        sidebar_status.success("已退出登录")
        st.session_state.role = None
        time.sleep(2)
        st.switch_page("Home.py")
