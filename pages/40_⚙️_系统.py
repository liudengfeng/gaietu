import datetime
import json
import logging

# import mimetypes
import os
import random
import re
import time
from pathlib import Path
from typing import List

import pandas as pd
import pytz
import streamlit as st
from google.cloud import firestore
from vertexai.preview.generative_models import GenerationConfig, Image, Part

from mypylib.constants import CEFR_LEVEL_MAPS
from mypylib.db_interface import PRICES
from mypylib.db_model import Payment, PaymentStatus, PurchaseType, str_to_enum
from mypylib.google_ai import load_vertex_model, select_best_images_for_word
from mypylib.google_cloud_configuration import PROJECT_ID
from mypylib.st_helper import (
    check_access,
    check_and_force_logout,
    configure_google_apis,
    get_and_save_word_image_urls,
    get_blob_container_client,
    get_blob_service_client,
    google_translate,
    select_word_image_indices,
    select_word_image_urls,
    setup_logger,
    update_and_display_progress,
)
from mypylib.word_utils import (
    get_lowest_cefr_level,
    get_unique_words,
    get_word_image_urls,
    load_image_bytes_from_url,
)

# region 配置

# 创建或获取logger对象
logger = logging.getLogger("streamlit")
setup_logger(logger)

CURRENT_CWD: Path = Path(__file__).parent.parent

st.set_page_config(
    page_title="系统管理",
    page_icon=":gear:",
    layout="wide",
)

check_access(True)
configure_google_apis()

tz = pytz.timezone(
    st.session_state.dbi.cache.get("user_info", {}).get("timezone", "Asia/Shanghai")
)
# endregion

# region 常量配置

PM_OPTS = list(PaymentStatus)

PAYMENT_COLUMN_CONFIG = {
    "phone_number": "手机号码",
    "payment_id": "付款编号",
    "order_id": "订单编号",
    "payment_time": st.column_config.DatetimeColumn(
        "支付时间",
        min_value=datetime.datetime(2024, 1, 1),
        max_value=datetime.datetime(2134, 1, 1),
        step=60,
    ),
    "registration_time": st.column_config.DatetimeColumn(
        "登记时间",
        min_value=datetime.datetime(2024, 1, 1),
        max_value=datetime.datetime(2134, 1, 1),
        step=60,
    ),
    "sales_representative": "销售代表",
    "purchase_type": st.column_config.SelectboxColumn(
        "套餐类型",
        help="✨ 购买的套餐类型",
        width="small",
        options=list(PurchaseType),
        default=list(PurchaseType)[-1],
        required=True,
    ),
    "receivable": st.column_config.NumberColumn(
        "应收 (元)",
        help="✨ 购买套餐应支付的金额",
        min_value=0.00,
        max_value=10000.00,
        step=0.01,
        format="￥%.2f",
    ),
    "discount_rate": st.column_config.NumberColumn(
        "折扣率",
        help="✨ 享受的折扣率",
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        format="%.2f",
    ),
    "payment_method": "付款方式",
    # "real_name": "姓名",
    # "display_name": "显示名称",
    "payment_amount": st.column_config.NumberColumn(
        "实收 (元)",
        help="✨ 购买套餐实际支付的金额",
        min_value=0.01,
        max_value=10000.00,
        step=0.01,
        format="￥%.2f",
    ),
    "is_approved": st.column_config.CheckboxColumn(
        "是否批准",
        help="✨ 选中表示允许用户使用系统",
        default=False,
    ),
    "expiry_time": st.column_config.DatetimeColumn(
        "服务截至时间",
        min_value=datetime.datetime(2024, 1, 1),
        max_value=datetime.datetime(2134, 1, 1),
        step=60,
    ),
    "status": st.column_config.SelectboxColumn(
        "服务状态",
        help="✨ 服务状态",
        width="small",
        options=PM_OPTS,
        default=PM_OPTS[-1],
        required=True,
    ),
    "remark": "服务备注",
}

PAYMENT_COLUMN_ORDER = [
    "phone_number",
    "payment_id",
    "order_id",
    "payment_time",
    "registration_time",
    "sales_representative",
    "purchase_type",
    "receivable",
    "discount_rate",
    "payment_method",
    "payment_amount",
    "is_approved",
    "expiry_time",
    "status",
    "remark",
]

PAYMENT_TIME_COLS = ["payment_time", "expiry_time", "registration_time"]

PAYMENT_EDITABLE_COLS: list[str] = [
    "is_approved",
    "payment_time",
    "expiry_time",
    "phone_number",
    "payment_id",
    "registration_time",
    "sales_representative",
    "purchase_type",
    "receivable",
    "discount_rate",
    "payment_method",
    "payment_amount",
    "status",
    "remark",
]


# endregion

# region 函数

# region 支付管理辅助函数


def get_new_order_id():
    db = st.session_state.dbi.db

    # 获取用于生成订单编号的文档
    doc_ref = db.collection("system").document("order_id_generator")

    # 定义一个事务函数
    @firestore.transactional
    def update_order_id(transaction):
        # 在事务中获取文档的内容
        doc = doc_ref.get(transaction=transaction)

        # 如果文档不存在，创建一个新的文档，设置 "last_order_id" 为 0
        if not doc.exists:
            transaction.set(doc_ref, {"last_order_id": "0"})
            last_order_id = "0"
        else:
            # 获取 "last_order_id" 的值
            last_order_id = doc.get("last_order_id")

        # 将 "last_order_id" 转换为整数，然后加 1
        new_order_id = str(int(last_order_id) + 1).zfill(10)

        # 在事务中更新文档，设置 "last_order_id" 为新的订单编号
        transaction.update(doc_ref, {"last_order_id": new_order_id})

        return new_order_id

    # 开始事务
    transaction = db.transaction()
    new_order_id = update_order_id(transaction)

    return new_order_id


def generate_timestamp(key: str, type: str, idx: int):
    # 获取日期和时间
    if type:
        date = st.session_state.get(f"{key}_{type}_date-{idx}")
        time = st.session_state.get(f"{key}_{type}_time-{idx}")
    else:
        date = st.session_state.get(f"{key}_date-{idx}")
        time = st.session_state.get(f"{key}_time-{idx}")

    # 将日期和时间组合成一个 datetime 对象
    datetime_obj = datetime.datetime.combine(date, time)

    # 设置时区
    datetime_obj = tz.localize(datetime_obj)

    # 转换为 UTC 时区
    datetime_utc = datetime_obj.astimezone(pytz.UTC)

    # 返回字典
    if type:
        return {f"{type}_" + key: datetime_utc}
    else:
        return {key: datetime_utc}


# endregion

# region 处理反馈辅助函数


@st.cache_data(ttl=60 * 60 * 1)  # 缓存有效期为1小时
def get_feedbacks():
    container_name = "feedback"
    # connect_str = st.secrets["Microsoft"]["AZURE_STORAGE_CONNECTION_STRING"]
    # blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    # container_client = blob_service_client.get_container_client(container_name)
    container_client = get_blob_container_client(container_name)

    # 获取blob列表
    blobs_list = container_client.list_blobs()

    # 获取一周前的日期
    one_week_ago = datetime.datetime.now(tz=pytz.UTC) - datetime.timedelta(weeks=1)

    feedbacks = {}
    for blob in blobs_list:
        # 检查 blob 是否在最近一周内创建
        if blob.last_modified >= one_week_ago:
            name, ext = os.path.splitext(blob.name)
            if name not in feedbacks:
                feedbacks[name] = {
                    "txt": None,
                    "webm": None,
                    "delete": False,
                    "view": False,
                }
            if ext == ".txt":
                feedbacks[name]["txt"] = blob.name
            elif ext == ".webm":
                feedbacks[name]["webm"] = blob.name

    return feedbacks


# endregion

# region 词典管理辅助函数


@st.cache_data(ttl=60 * 60 * 2)  # 缓存有效期为2小时
def translate_text(text: str, target_language_code):
    return google_translate(text, target_language_code)


def translate_dict(d, target_language_code):
    res = {}
    if d.get("definition", None):
        res["definition"] = translate_text(d["definition"], target_language_code)
    examples = []
    for e in d["examples"]:
        examples.append(translate_text(e, target_language_code))
    res["examples"] = examples
    return res


def translate_pos(pos: str, target_language_code):
    res = []
    for d in pos:
        res.append(translate_dict(d, target_language_code))
    return res


def translate_doc(doc, target_language_code):
    doc[target_language_code] = {}
    doc[target_language_code]["translation"] = translate_text(
        doc["word"], target_language_code
    )
    for k, v in doc["en-US"].items():
        doc[target_language_code][k] = translate_pos(v, target_language_code)


def init_mini_dict():
    st.text("初始化简版词典")
    target_language_code = "zh-CN"
    db = st.session_state.dbi.db
    words_ref = db.collection("words")
    mini_dict_ref = db.collection("mini_dict")
    wp = CURRENT_CWD / "resource" / "dictionary" / "word_lists_by_edition_grade.json"
    words = get_unique_words(wp, True)
    st.text(f"单词总数：{len(words)}")
    mini_progress = st.progress(0)

    # 获取 mini_dict 集合中所有的文档名称
    mini_dict_docs = [doc.id for doc in mini_dict_ref.stream()]

    for i, w in enumerate(words):
        update_and_display_progress(i + 1, len(words), mini_progress)
        # logger.info(f"单词：{w}")
        # 将单词作为文档名称，将其内容存档
        doc_name = w.replace("/", " or ")

        if doc_name in mini_dict_docs:
            # logger.info(f"单词：{w} 已存在，跳过")
            continue

        word_doc_ref = words_ref.document(doc_name)
        word_doc = word_doc_ref.get()
        translation = ""

        if word_doc.exists:
            p = word_doc.to_dict()
            if "zh-CN" in p and "translation" in p["zh-CN"]:
                translation = p["zh-CN"]["translation"]

        if translation == "":
            translation = translate_text(w, target_language_code)

        p = {
            "translation": translation,
            "level": get_lowest_cefr_level(w),
        }
        mini_dict_ref.document(doc_name).set(p)
        logger.info(f"🎇 单词：{w} 完成")
        # 每次写入操作后休眠 0.5 秒
        time.sleep(0.5)


def update_mini_dict():
    st.text("更新简版词典")
    target_language_code = "zh-CN"
    db = st.session_state.dbi.db
    mini_dict_ref = db.collection("mini_dict")
    mini_progress = st.progress(0)

    # 获取 mini_dict 集合中所有的文档
    mini_dict_docs = [doc for doc in mini_dict_ref.stream()]
    n = len(mini_dict_docs)

    for i, doc in enumerate(mini_dict_docs):
        update_and_display_progress(i + 1, n, mini_progress)
        doc_name = doc.id
        data = doc.to_dict()

        # 检查是否存在 'level' 和 'translation' 字段
        if "level" not in data and "translation" not in data:
            # 更新文档
            p = {
                "translation": translate_text(doc_name, target_language_code),
                "level": get_lowest_cefr_level(doc_name),
            }
            mini_dict_ref.document(doc_name).set(p, merge=True)
            logger.info(f"🎇 单词：{doc_name} 更新完成")
            # 每次写入操作后休眠 0.5 秒
            time.sleep(0.5)


def add_new_words_from_mini_dict_to_words():
    st.text("添加简版词典到默认词典")
    target_language_code = "zh-CN"
    db = st.session_state.dbi.db
    words_ref = db.collection("words")
    mini_dict_ref = db.collection("mini_dict")
    # wp = CURRENT_CWD / "resource" / "dictionary" / "word_lists_by_edition_grade.json"
    # words = get_unique_words(wp, True)
    mini_progress = st.progress(0)

    # 获取 mini_dict 中的所有单词
    mini_dict_words = set([doc.id for doc in mini_dict_ref.stream()])

    # 获取 words 中的所有单词
    words_words = set([doc.id for doc in words_ref.stream()])

    # 找出只在 mini_dict 中存在的单词
    new_words = mini_dict_words - words_words
    st.write(f"单词总数：{len(new_words)}")

    for i, w in enumerate(new_words):
        update_and_display_progress(i + 1, len(new_words), mini_progress)
        logger.info(f"单词：{w}")

        _add_to_words(mini_dict_ref, words_ref, w, target_language_code)


def _add_to_words(mini_dict_ref, words_ref, doc_name, target_language_code):
    mini_dict_doc_ref = mini_dict_ref.document(doc_name)
    mini_dict_doc = mini_dict_doc_ref.get()

    if mini_dict_doc.exists:
        p = mini_dict_doc.to_dict()
        d = {
            "level": p["level"],
            target_language_code: {"translation": p["translation"]},
        }
        words_ref.document(doc_name).set(d)
        logger.info(f"🎇 单词：{doc_name} 完成")
        # 每次写入操作后休眠 0.5 秒
        # time.sleep(0.5)


# endregion

# region 简版词典辅助函数


@st.cache_data(show_spinner="提取简版词典...", ttl=60 * 60 * 2)  # 缓存有效期为2小时
def get_mini_dict_dataframe():
    db = st.session_state.dbi.db
    collection = db.collection("mini_dict")

    # 从 Firestore 获取数据
    docs = collection.get()

    # 将数据转换为 DataFrame
    data = [{"word": doc.id, **doc.to_dict()} for doc in docs]

    return pd.DataFrame(data)


def display_mini_dict_changes(current_df, elem):
    # 获取已编辑的行
    edited_rows = st.session_state["mini_dict_df"]["edited_rows"]

    # 遍历已编辑的行
    for idx, new_values in edited_rows.items():
        # 获取原始的行
        original_row = current_df.iloc[idx]

        # 获取单词
        word = original_row["word"]

        # 显示变动
        elem.write(f"单词：{word} 的变动：")
        for key, new_value in new_values.items():
            # 获取原始的值
            original_value = original_row[key]

            # 显示变动
            elem.write(f"{key}: {original_value} -> {new_value}")


def save_dataframe_changes_to_database(current_df):
    db = st.session_state.dbi.db
    collection = db.collection("mini_dict")
    # 获取已编辑的行
    edited_rows = st.session_state["mini_dict_df"]["edited_rows"]

    # 遍历已编辑的行
    for idx, new_values in edited_rows.items():
        # 获取原始的行
        original_row = current_df.iloc[idx]

        # 获取单词，作为文档名称
        doc_name = original_row["word"]

        # 更新文档
        doc_ref = collection.document(doc_name)
        doc_ref.update(new_values)
        st.toast(f"更新简版词典，单词：{doc_name}", icon="🎉")


# endregion

# region 单词图片辅助函数


@st.spinner("使用 Gemini 准备单词关联照片...")
def fetch_and_update_word_image_indices(word):
    container_name = "word-images"

    blob_service_client = get_blob_service_client()
    container_client = get_blob_container_client(container_name)

    # 获取名称以 "abbreviated_" 开始的所有 blob
    blobs_list = container_client.list_blobs(name_starts_with=f"{word}_")

    images = []
    for blob_name in blobs_list:
        try:
            blob_client = blob_service_client.get_blob_client(container_name, blob_name)
            image_bytes = blob_client.download_blob().readall()
            images.append(Image.from_bytes(image_bytes))
        except Exception as e:
            logger.error(f"加载图片 {blob_name} 时出现错误: {e}")

    if len(images) == 0:
        logger.error(f"没有找到单词 {word} 的图片")
        return

    model_name = "gemini-pro-vision"
    model = load_vertex_model(model_name)
    indices = select_best_images_for_word(model_name, model, word, images)

    if indices:
        # 检查 indices 是否为列表
        if not isinstance(indices, list):
            st.error(f"{word} indices 必须是一个列表")
            return
        # 检查列表中的每个元素是否都是整数
        if not all(isinstance(i, int) for i in indices):
            st.error(f"{word} indices 列表中的每个元素都必须是整数")
            return
        st.session_state.dbi.update_image_indices(word, indices)
        logger.info(f"🧨 单词:{word} 图片索引:{indices} 已经更新")


# endregion

# region 下载单词图片


def process_images():
    mini_dict_dataframe = get_mini_dict_dataframe()
    words = mini_dict_dataframe["word"].tolist()
    # 对列表进行随机洗牌
    random.shuffle(words)

    container_name = "word-images"
    # connect_str = st.secrets["Microsoft"]["AZURE_STORAGE_CONNECTION_STRING"]
    # blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    # container_client = blob_service_client.get_container_client(container_name)
    container_client = get_blob_container_client(container_name)

    progress_bar = st.progress(0)
    n = len(words)
    existing_blob_count = 0  # 初始化已存在的 blob 计数
    for index, word in enumerate(words):
        update_and_display_progress(index + 1, n, progress_bar, word)
        # 获取以单词开头的所有 blob
        word_blobs = container_client.list_blobs(name_starts_with=f"{word}_")
        # 如果存在任何以单词开头的 blob，就跳出循环
        if any(word_blobs):
            logger.info(f"找到 '{word}' 开头的 blob，跳过下载和上传步骤")
            existing_blob_count += 1  # 更新已存在的 blob 计数
            continue

        urls = get_word_image_urls(word, st.secrets["SERPER_KEY"])
        for i, url in enumerate(urls):
            # 创建 blob 名称
            blob_name = f"{word}_{i}.png"
            blob_client = blob_service_client.get_blob_client(container_name, blob_name)

            try:
                img_byte_arr = load_image_bytes_from_url(url)
            except Exception as e:
                logger.error(f"加载单词{word}第{i+1}张图片时出错:{str(e)}")
                continue

            blob_client.upload_blob(img_byte_arr, blob_type="BlockBlob", overwrite=True)
        # 计算已存在的 blob 的百分比，并将结果记录在日志中
        existing_blob_percentage = (existing_blob_count / (index + 1)) * 100
        logger.info(f"🎇 单词：{word} 图片上传成功 完成率：{existing_blob_percentage:.2f}%")


# endregion

# endregion

# region 侧边栏

menu = st.sidebar.selectbox("菜单", options=["支付管理", "处理反馈", "词典管理", "统计分析"])
sidebar_status = st.sidebar.empty()
check_and_force_logout(sidebar_status)

# endregion

# region 主页

# region 支付管理


if menu == "支付管理":
    items = ["订阅登记", "支付管理"]
    tabs = st.tabs(items)
    with tabs[items.index("订阅登记")]:
        st.subheader("订阅登记")
        with st.form(key="payment_form", clear_on_submit=True):
            cols = st.columns(2)
            phone_number = cols[0].text_input(
                "手机号码",
                key="phone_number",
                help="✨ 请输入订阅者可接收短信的手机号码",
                placeholder="请输入订阅者可接收短信的手机号码[必须]",
            )
            sales_representative = cols[1].text_input(
                "销售代表",
                key="sales_representative",
                help="✨ 请提供销售代表的名称（选填）",
                placeholder="请提供销售代表的名称（选填）",
            )
            purchase_type = cols[0].selectbox(
                "套餐类型",
                key="purchase_type",
                help="✨ 请选择套餐类型",
                options=list(PurchaseType),
                index=1,
                format_func=lambda x: x.value,
                # on_change=compute_discount,
            )
            payment_amount = cols[1].number_input(
                "实收金额",
                key="payment_amount",
                help="✨ 请输入实际收款金额",
                value=0.0,
                # on_change=compute_discount,
            )
            payment_method = cols[0].text_input(
                "付款方式", key="payment_method", help="✨ 请输入付款方式", placeholder="必填。付款方式"
            )
            payment_id = cols[1].text_input(
                "付款编号",
                key="payment_id",
                help="✨ 请输入付款编号",
                placeholder="必填。请在付款凭证上查找付款编号",
            )
            cols[0].date_input(
                "支付日期",
                key="payment_time_date-0",
                value=datetime.datetime.now(tz).date(),
                help="✨ 请选择支付日期。登记日期默认为今天。",
            )
            cols[1].time_input(
                "时间",
                key="payment_time_time-0",
                value=datetime.time(0, 0, 0),
                help="✨ 请选择支付时间。登记时间默认为系统处理时间。",
            )
            remark = st.text_input(
                "备注",
                key="remark",
                help="✨ 请输入备注信息",
            )
            is_approved = st.toggle("是否批准")
            if st.form_submit_button(label="登记"):
                if not phone_number:
                    st.error("手机号码不能为空")
                    st.stop()
                if not payment_id:
                    st.error("付款编号不能为空")
                    st.stop()

                order_id = get_new_order_id()

                receivable = PRICES[purchase_type]  # type: ignore
                discount_rate = payment_amount / receivable
                key = "payment_time"
                payment_time = generate_timestamp(key, "", 0)[key]
                payment = Payment(
                    phone_number=phone_number,
                    payment_id=payment_id,
                    registration_time=datetime.datetime.now(datetime.timezone.utc),
                    payment_time=payment_time,
                    expiry_time=datetime.datetime.now(datetime.timezone.utc),
                    receivable=receivable,
                    payment_amount=payment_amount,  # type: ignore
                    purchase_type=str_to_enum(purchase_type, PurchaseType),  # type: ignore
                    order_id=order_id,
                    payment_method=payment_method,
                    discount_rate=discount_rate,
                    sales_representative=sales_representative,
                    is_approved=is_approved,
                    remark=remark,
                )
                st.session_state.dbi.add_payment(payment)
                st.toast(f"成功登记，订单号:{order_id}", icon="🎉")

    with tabs[items.index("支付管理")]:
        st.subheader("查询参数")
        with st.form(key="query_form", clear_on_submit=True):
            # 精确匹配
            t_0_cols = st.columns(4)
            t_0_cols[0].markdown(":rainbow[精确匹配查询]")
            t0 = t_0_cols[1].toggle(
                label="包含",
                key="is_include-0",
                help="✨ 选中表示包含该查询条件，否则表示不包含",
            )
            payment_0_cols = st.columns(4)
            payment_0_cols[0].text_input(label="手机号码", key="phone_number-1")
            payment_0_cols[1].text_input(label="付款编号", key="payment_id-1")
            payment_0_cols[2].text_input(label="订单编号", key="order_id-1")
            payment_0_cols[3].text_input(label="销售代表", key="sales_representative-1")
            # 选项查询
            t_1_cols = st.columns(4)
            t_1_cols[0].markdown(":rainbow[状态查询]")
            t1 = t_1_cols[1].toggle(
                label="包含",
                key="is_include-1",
                help="✨ 选中表示包含该查询条件，否则表示不包含",
            )
            payment_1_cols = st.columns(4)
            payment_1_cols[0].selectbox(
                label="套餐类型",
                key="purchase_type-1",
                options=["All"] + [x.value for x in PurchaseType],
            )
            payment_1_cols[1].selectbox(
                label="支付状态",
                key="status-1",
                options=["All"] + [x.value for x in PaymentStatus],
            )
            payment_1_cols[2].selectbox(
                label="是否批准",
                key="is_approved-1",
                options=["All", False, True],
            )

            # 支付时间
            t_2_cols = st.columns(4)
            t_2_cols[0].markdown(":rainbow[支付期间查询]")
            t2 = t_2_cols[1].toggle(
                label="包含",
                key="is_include-2",
                help="✨ 选中表示包含该查询条件，否则表示不包含",
            )
            payment_2_cols = st.columns(4)
            payment_2_cols[0].date_input(
                "支付【开始日期】",
                key="payment_time_start_date-1",
                value=datetime.datetime.now(tz).date(),
            )
            payment_2_cols[1].time_input(
                "支付【开始时间】",
                key="payment_time_start_time-1",
                value=datetime.time(0, 0, 0),
            )
            payment_2_cols[2].date_input(
                "支付【结束日期】",
                key="payment_time_end_date-1",
                value=datetime.datetime.now(tz).date(),
            )
            payment_2_cols[3].time_input(
                "支付【结束时间】",
                key="payment_time_end_time-1",
                value=datetime.time(23, 59, 59),
            )

            # 服务时间查询
            t_3_cols = st.columns(4)
            t_3_cols[0].markdown(":rainbow[服务期间查询]")
            t3 = t_3_cols[1].toggle(
                label="包含",
                key="is_include-3",
                help="✨ 选中表示包含该查询条件，否则表示不包含",
            )
            payment_3_cols = st.columns(4)
            payment_3_cols[0].date_input(
                "服务【开始日期】",
                key="expiry_time_start_date-1",
                value=datetime.datetime.now(tz).date(),
            )
            payment_3_cols[1].time_input(
                "服务【开始时间】", key="expiry_time_start_time-1", value=datetime.time(0, 0, 0)
            )
            payment_3_cols[2].date_input(
                "服务【结束日期】",
                key="expiry_time_end_date-1",
                value=datetime.datetime.now(tz).date(),
            )
            payment_3_cols[3].time_input(
                "服务【结束时间】",
                key="expiry_time_end_time-1",
                value=datetime.time(23, 59, 59),
            )

            # 模糊查询
            t_4_cols = st.columns(4)
            t_4_cols[0].markdown(":rainbow[模糊查询]")
            t4 = t_4_cols[1].toggle(
                label="包含",
                key="is_include-4",
                help="✨ 选中表示包含该查询条件，否则表示不包含",
            )
            payment_4_cols = st.columns(2)
            payment_4_cols[0].text_input(
                "支付方式",
                key="payment_method-1",
                help="✨ 要查询的支付方式信息",
            )
            payment_4_cols[1].text_input(
                "备注",
                key="remark-1",
                help="✨ 要查询的备注信息",
            )
            query_button = st.form_submit_button(label="查询")

            if query_button:
                kwargs = {}
                if t0:
                    kwargs.update(
                        {
                            "phone_number": st.session_state.get(
                                "phone_number-1", None
                            ),
                            "payment_id": st.session_state.get("payment_id-1", None),
                            "order_id": st.session_state.get("order_id-1", None),
                            "sales_representative": st.session_state.get(
                                "sales_representative-1", None
                            ),
                        }
                    )
                if t1:
                    kwargs.update(
                        {
                            "purchase_type": None
                            if st.session_state.get("purchase_type-1", None) == "ALL"
                            else str_to_enum(
                                st.session_state.get("purchase_type-1", None),
                                PurchaseType,
                            ),
                            "status": None
                            if st.session_state.get("status-1", None) == "ALL"
                            else str_to_enum(
                                st.session_state.get("status-1", None), PaymentStatus
                            ),
                            "is_approved": None
                            if st.session_state.get("is_approved-1", None) == "ALL"
                            else st.session_state.get("is_approved-1", None),
                        }
                    )

                if t2:
                    kwargs.update(generate_timestamp("payment_time", "start", 1))
                    kwargs.update(generate_timestamp("payment_time", "end", 1))

                if t3:
                    kwargs.update(generate_timestamp("expiry_time", "start", 1))
                    kwargs.update(generate_timestamp("expiry_time", "end", 1))

                if t4:
                    kwargs.update(
                        {
                            "payment_method": st.session_state.get(
                                "payment_method-1", None
                            ),
                            "remark": st.session_state.get("remark-1", None),
                        }
                    )

                # 删除字典中的空值部分【None ""】
                kwargs = {k: v for k, v in kwargs.items() if v}
                st.write(f"{kwargs=}")

                # 检查数据生成的参数及其类型
                # st.write(kwargs)
                # for k, v in kwargs.items():
                #     st.write(f"{k=}, {type(v)=}")
                results = st.session_state.dbi.query_payments(kwargs)
                # 将每个文档转换为字典
                dicts = [{"order_id": doc.id, **doc.to_dict()} for doc in results]
                st.write(f"{dicts=}")
                st.session_state["queried_payments"] = dicts

        st.subheader("支付清单")
        df = pd.DataFrame(st.session_state.get("queried_payments", {}))

        placeholder = st.empty()
        status = st.empty()
        pay_cols = st.columns([1, 1, 8])
        upd_btn = pay_cols[0].button("更新", key="upd_btn", help="✨ 更新数据库中选中的支付记录")
        del_btn = pay_cols[1].button("删除", key="del_btn", help="✨ 在数据库中删除选中的支付记录")
        # # st.divider()
        if df.empty:
            placeholder.info("没有记录")
        else:
            # 将时间列转换为本地时区
            for col in PAYMENT_TIME_COLS:
                if col in df.columns:
                    df[col] = df[col].dt.tz_convert(tz)
            edited_df = placeholder.data_editor(
                df,
                column_config=PAYMENT_COLUMN_CONFIG,
                column_order=PAYMENT_COLUMN_ORDER,
                hide_index=True,
                num_rows="dynamic",
                key="users_payments",
                disabled=[
                    col for col in df.columns if col not in PAYMENT_EDITABLE_COLS
                ],
            )

        # # Access edited data
        if upd_btn and st.session_state.get("users_payments", None):
            users_payments = st.session_state["users_payments"]
            # st.write(f"{users_payments=}")
            for idx, d in users_payments["edited_rows"].items():
                order_id = df.iloc[idx]["order_id"]  # type: ignore
                for key in d.keys():
                    if key in PAYMENT_TIME_COLS:
                        # 检查返回的对象的类型及其值
                        # st.write(f"{type(d[key])=}, {d[key]=}")
                        value = d[key]
                        # 将 'Z' 替换为 '+00:00'
                        value = value.replace("Z", "+00:00")
                        # 将字符串转换为 datetime 对象
                        timestamp = datetime.datetime.fromisoformat(value).astimezone(
                            datetime.timezone.utc
                        )
                        d[key] = timestamp
                st.session_state.dbi.update_payment(order_id, d)
                st.toast(f"更新支付记录，订单号：{order_id}", icon="🎉")
            users_payments["edited_rows"] = {}

        if del_btn and st.session_state.get("users_payments", None):
            users_payments = st.session_state["users_payments"]
            # st.write(f'{users_payments["deleted_rows"]=}')
            for idx in users_payments["deleted_rows"]:
                order_id = df.iloc[idx]["order_id"]  # type: ignore
                st.session_state.dbi.delete_payment(order_id)
                st.toast(f"删除支付记录，订单号：{order_id}", icon="⚠️")
            # 清除删除的行
            users_payments["deleted_rows"] = []


# endregion

# region 处理反馈

elif menu == "处理反馈":
    st.subheader("处理反馈", divider="rainbow", anchor=False)
    container_name = "feedback"
    # connect_str = st.secrets["Microsoft"]["AZURE_STORAGE_CONNECTION_STRING"]
    blob_service_client = get_blob_service_client()
    # container_client = blob_service_client.get_container_client(container_name)
    container_client = get_blob_container_client(container_name)
    # 设置缓存为 1 小时，不能实时查看反馈
    feedbacks = get_feedbacks()
    # st.write(f"{feedbacks=}")
    if len(feedbacks):
        # 将反馈字典转换为一个DataFrame
        feedbacks_df = pd.DataFrame(feedbacks.values())
        feedbacks_df.columns = ["文件文件", "视频文件", "删除", "显示"]

        feedbacks_edited_df = st.data_editor(
            feedbacks_df, hide_index=True, key="feedbacks"
        )

        cols = st.columns(2)
        # 添加一个按钮来删除反馈
        if cols[0].button("删除", help="✨ 删除选中的反馈"):
            # 获取要删除的反馈
            edited_rows = st.session_state["feedbacks"]["edited_rows"]
            for idx, vs in edited_rows.items():
                if vs.get("删除", False):
                    try:
                        txt = feedbacks_df.iloc[idx]["文件文件"]
                        webm = feedbacks_df.iloc[idx]["视频文件"]
                        if txt is not None:
                            container_client.delete_blob(txt)
                            feedbacks_df.iloc[idx]["删除"] = True
                            st.toast(f"从blob中删除：{txt}", icon="🎉")
                        if webm is not None:
                            container_client.delete_blob(webm)
                            st.toast(f"从blob中删除：{webm}", icon="🎉")
                    except Exception as e:
                        pass

        if cols[1].button("显示", help="✨ 显示选中的反馈"):
            # 显示反馈
            edited_rows = st.session_state["feedbacks"]["edited_rows"]
            for idx, vs in edited_rows.items():
                if vs.get("显示", False):
                    deleted = feedbacks_df.iloc[idx]["删除"]
                    if not deleted:
                        try:
                            st.divider()
                            txt = feedbacks_df.iloc[idx]["文件文件"]
                            if txt is not None:
                                text_blob_client = blob_service_client.get_blob_client(
                                    container_name, txt
                                )
                                text_data = (
                                    text_blob_client.download_blob()
                                    .readall()
                                    .decode("utf-8")
                                )
                                st.text(f"{text_data}")
                            webm = feedbacks_df.iloc[idx]["视频文件"]
                            if webm is not None:
                                video_blob_client = blob_service_client.get_blob_client(
                                    container_name, webm
                                )
                                video_data = video_blob_client.download_blob().readall()
                                st.video(video_data)
                        except Exception as e:
                            pass

# endregion

# region 词典管理


elif menu == "词典管理":
    dict_items = ["词典管理", "图片网址", "查漏补缺", "挑选照片"]
    dict_tabs = st.tabs(dict_items)

    MINI_DICT_COLUMN_CONFIG = {
        "word": "单词",
        "level": st.column_config.SelectboxColumn(
            "CEFR分级",
            help="✨ CEFR分级",
            width="small",
            options=list(CEFR_LEVEL_MAPS.keys()),
            required=True,
        ),
        "translation": "译文",
    }

    # region 词典管理
    include = st.sidebar.checkbox("是否包含短语", key="include-2", value=True)
    cate = st.sidebar.selectbox(
        "选择分类",
        options=[
            "all",
            "A1",
            "A2",
            "B1",
            "B2",
            "C1",
            "C2",
            "人教版_小学",
            "人教版_初中",
            "人教版_高中",
        ],
        key="cate-2",
    )
    with dict_tabs[dict_items.index("词典管理")]:
        st.subheader("词典管理", divider="rainbow", anchor=False)
        btn_cols = st.columns(10)

        if btn_cols[0].button("整理", key="init_btn-3", help="✨ 整理简版词典"):
            init_mini_dict()

        if btn_cols[1].button("添加", key="add-btn-3", help="✨ 将简版词典单词添加到默认词典"):
            add_new_words_from_mini_dict_to_words()

        if btn_cols[2].button("更新", key="update-btn-3", help="✨ 更新简版词典"):
            update_mini_dict()

    # endregion

    # # region 编辑微型词典

    # with dict_tabs[dict_items.index("编辑微型词典")]:
    #     st.subheader("编辑微型词典", divider="rainbow", anchor=False)

    #     btn_cols = st.columns(10)
    #     view_cols = st.columns(2)
    #     edited_elem = view_cols[0].empty()
    #     view_elem = view_cols[1].container()

    #     mini_dict_dataframe = get_mini_dict_dataframe()

    #     # 显示可编辑的 DataFrame
    #     edited_elem.data_editor(
    #         mini_dict_dataframe,
    #         key="mini_dict_df",
    #         column_config=MINI_DICT_COLUMN_CONFIG,
    #         hide_index=True,
    #         disabled=["word"],
    #     )

    #     if btn_cols[0].button("显示变动", key="view-btn-4", help="✨ 显示编辑后的简版词典变动部分"):
    #         display_mini_dict_changes(mini_dict_dataframe, view_elem)

    #     if btn_cols[1].button("提交保存", key="save-btn-4", help="✨ 将编辑后的简版词典变动部分保存到数据库"):
    #         save_dataframe_changes_to_database(mini_dict_dataframe)
    #         st.session_state["mini_dict_df"]["edited_rows"] = {}

    # # endregion

    # region 下载图片

    with dict_tabs[dict_items.index("图片网址")]:
        st.subheader("关联图片网址", divider="rainbow", anchor=False)
        st.markdown("使用 serper Google api 添加单词关联图片网址")
        progress_pic_bar = st.progress(0)
        fp = (
            CURRENT_CWD / "resource" / "dictionary" / "word_lists_by_edition_grade.json"
        )
        # 创建一个按钮，当用户点击这个按钮时，执行 process_images 函数
        if st.button("开始", key="urls-images-btn-2", help="✨ 下载单词图片"):
            db = st.session_state.dbi.db
            words = get_unique_words(fp, include, cate)
            n = len(words)
            # 对列表进行随机洗牌
            random.shuffle(words)
            for i, word in enumerate(words):
                q = word.replace("/", " or ")
                update_and_display_progress(i + 1, n, progress_pic_bar, word)
                get_and_save_word_image_urls(q)

    # endregion

    # region 查漏补缺

    with dict_tabs[dict_items.index("查漏补缺")]:
        st.subheader("查漏补缺", divider="rainbow", anchor=False)
        st.markdown("使用 serper Google api 为没有图片网址的单词添加图片网址")
        progress_pic_bar = st.progress(0)
        # 创建一个按钮，当用户点击这个按钮时，执行 process_images 函数
        if st.button("开始", key="images-urls-btn-2", help="✨ 图片网址补缺"):
            words = st.session_state.dbi.find_docs_with_empty_image_urls()
            n = len(words)
            for i, word in enumerate(words):
                update_and_display_progress(i + 1, n, progress_pic_bar, word)
                get_and_save_word_image_urls(word)

    # endregion

    # region 单词图片

    with dict_tabs[dict_items.index("挑选照片")]:
        st.subheader("挑选单词关联照片", divider="rainbow", anchor=False)
        st.text("使用 gemini 多模态挑选能形象解释单词含义的图片")
        progress_pic_bar = st.progress(0)
        fp = (
            CURRENT_CWD / "resource" / "dictionary" / "word_lists_by_edition_grade.json"
        )
        if st.button(
            "执行", key="pick-image-btn", help="✨ 使用 gemini 多模态检验图片是否能形象解释单词的含义"
        ):
            words = get_unique_words(fp, include, cate)
            n = len(words)
            # 对列表进行随机洗牌
            random.shuffle(words)
            # to_do = st.session_state.dbi.find_docs_without_image_indices(words)
            # st.write(f"待处理的文档数量：{len(to_do)}")
            for i, word in enumerate(words):
                q = word.replace("/", " or ")
                update_and_display_progress(i + 1, n, progress_pic_bar, word)
                if st.session_state.dbi.word_has_image_indices(q):
                    logger.info(f"✅ 单词：{word} 已经有图片序号，跳过")
                    continue
                select_word_image_indices(q)
                logger.info(f"🎆 单词：{word}")

    # endregion

# endregion

# # region 转移数据库


# # def transfer_data_from_mongodb_to_firestore():
# #     from bson import ObjectId
# #     from pymongo import MongoClient

# #     mongodb_uri = st.secrets["Microsoft"]["COSMOS_CONNECTION_STRING"]
# #     client = MongoClient(mongodb_uri)
# #     db = client["pg"]
# #     words = db["words"]
# #     firestore_db = st.session_state.dbi.db

# #     # 查询 Firestore 中的所有文档 ID
# #     firestore_doc_ids = set(doc.id for doc in firestore_db.collection("words").stream())

# #     # 查询 MongoDB 中的所有文档 ID
# #     mongodb_doc_ids = set(str(doc["_id"]) for doc in words.find())

# #     # 找出需要转移的文档 ID
# #     doc_ids_to_transfer = mongodb_doc_ids - firestore_doc_ids

# #     # 显示需要转移的文档数量
# #     st.write(f"需要转移的文档数量：{len(doc_ids_to_transfer)}")

# #     # 创建一个进度条
# #     progress = st.progress(0)

# #     # 遍历需要转移的文档 ID
# #     for i, doc_id in enumerate(doc_ids_to_transfer):
# #         # 从 MongoDB 中获取文档
# #         doc = words.find_one({"_id": ObjectId(doc_id)})
# #         # 将它添加到 Firestore 中
# #         del doc["_id"]
# #         firestore_db.collection("words").document(doc_id).set(doc)

# #         # 更新进度条
# #         progress.progress((i + 1) / len(doc_ids_to_transfer))

# #     # 完成后，关闭 MongoDB 客户端
# #     client.close()


# # def rename_firestore_documents(num_docs_to_process):
# #     firestore_db = st.session_state.dbi.db
# #     words_collection = firestore_db.collection("words")

# #     # 创建一个正则表达式，用于匹配 MongoDB ObjectId
# #     mongodb_objectid_regex = re.compile("^[0-9a-fA-F]{24}$")

# #     # 遍历 Firestore 中的所有文档，检查每个文档的 ID 是否符合特定的格式
# #     num_docs_to_rename = sum(
# #         1 for doc in words_collection.stream() if mongodb_objectid_regex.match(doc.id)
# #     )
# #     # 显示待处理的文档数量
# #     st.write(f"待处理的文档数量：{num_docs_to_rename}")

# #     # 取待处理的文档数量与用户指定的数量的最小值作为要处理的文档数量
# #     num_docs_to_process = min(num_docs_to_process, num_docs_to_rename)

# #     # 创建一个进度条
# #     progress_bar = st.progress(0)

# #     # 遍历 Firestore 中的所有文档
# #     for i, doc in enumerate(words_collection.stream()):
# #         # 如果已处理的文档数量达到了用户指定的数量，就停止处理
# #         if i >= num_docs_to_process:
# #             break

# #         # 如果文档的 ID 不符合特定的格式，就跳过这个文档
# #         if not mongodb_objectid_regex.match(doc.id):
# #             continue

# #         # 获取文档的数据
# #         data = doc.to_dict()
# #         # 获取文档的单词字段
# #         word = data.get("word")
# #         if word:
# #             # 如果单词字段存在，将其删除
# #             del data["word"]
# #             # 将单词中的 "/" 字符替换为 " or "
# #             new_doc_id = word.replace("/", " or ")
# #             # 创建一个新的文档，其 ID 为新的单词，其数据为原文档的数据
# #             words_collection.document(new_doc_id).set(data)
# #             # 删除原文档
# #             doc.reference.delete()

# #         # 更新进度条的值
# #         update_and_display_progress(i + 1, num_docs_to_process, progress_bar)

# #     # 完成后，显示一条消息
# #     st.success("完成！")


# # with tabs[items.index("转移词典")]:
# #     st.subheader("转移词典", divider="rainbow")
# #     st.text("将 MongoDB 中的数据转移到 Firestore 中")
# #     if st.button("开始", key="start_btn-4"):
# #         transfer_data_from_mongodb_to_firestore()
# #     st.text("注意：全部转移完成后，才可重命名")
# #     num_docs_to_process = st.number_input(
# #         "输入要处理的文档数量", min_value=10, max_value=21000, value=10
# #     )
# #     if st.button("重命名 Firestore 文档", key="rename_btn"):
# #         rename_firestore_documents(num_docs_to_process)

# # endregion


# # region 创建统计分析页面

# # endregion

# endregion
