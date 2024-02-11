from datetime import datetime
import streamlit as st
import pytz


@st.cache_data(ttl=60 * 20)
def get_exercises(phone_number, start_date, end_date):
    dbi = st.session_state.dbi
    db = dbi.db
    # phone_number = dbi.cache["user_info"]["phone_number"]

    # 将日期转换为 Firestore 时间戳
    start_timestamp = datetime.combine(start_date, datetime.min.time())
    end_timestamp = datetime.combine(end_date, datetime.max.time())

    # 转换为 UTC 时间
    start_timestamp = pytz.UTC.localize(start_timestamp)
    end_timestamp = pytz.UTC.localize(end_timestamp)

    # 获取指定 ID 的文档
    doc = db.collection("exercises").document(phone_number).get()

    # 初始化一个空列表来保存查询结果
    record_list = []

    # 检查文档是否存在
    if doc.exists:
        # 获取文档的数据
        data = doc.to_dict()

        # 遍历 "history" 数组
        for record in data.get("history", []):

            # 获取 "record_time" 字段
            timestamp = record.get("timestamp")
            timestamp = timestamp.astimezone(pytz.UTC)
            # 如果 "record_time" 字段存在，并且在指定的范围内，则添加到查询结果中
            if timestamp and start_timestamp <= timestamp <= end_timestamp:
                # 给 record 字典添加 phone_number 键值对
                record["phone_number"] = phone_number
                record_list.append(record)

    return record_list
