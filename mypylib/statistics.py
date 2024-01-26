import datetime
import streamlit as st


@st.cache_data(ttl=60 * 60 * 1, suppress_st_warning=True)
def get_records(phone_number, start_date, end_date):
    dbi = st.session_state.dbi
    db = dbi.db
    # phone_number = dbi.cache["user_info"]["phone_number"]

    # 将日期转换为 Firestore 时间戳
    start_timestamp = datetime.combine(start_date, datetime.min.time())
    end_timestamp = datetime.combine(end_date, datetime.max.time())

    # 查询该日期范围内的所有学习记录
    records = (
        db.collection("learning_time")
        .where("phone_number", "==", phone_number)
        .where("record_time", ">=", start_timestamp)
        .where("record_time", "<=", end_timestamp)
        .stream()
    )

    # 将查询结果转换为字典列表
    records_list = [doc.to_dict() for doc in records]

    return records_list
