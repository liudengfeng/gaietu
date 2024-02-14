from datetime import datetime
import streamlit as st
import pytz
import pandas as pd
from mypylib.st_helper import (
    MAX_WORD_STUDY_TIME,
)
import plotly.express as px


@st.cache_data(ttl=60 * 30)
def get_exercises(phone_number, start_date, end_date, previous_period=False):
    dbi = st.session_state.dbi
    db = dbi.db
    # phone_number = dbi.cache["user_info"]["phone_number"]

    # 将日期转换为 Firestore 时间戳
    start_timestamp = datetime.combine(start_date, datetime.min.time())
    end_timestamp = datetime.combine(end_date, datetime.max.time())

    # 转换为 UTC 时间
    start_timestamp = pytz.UTC.localize(start_timestamp)
    end_timestamp = pytz.UTC.localize(end_timestamp)

    if previous_period:
        # 计算上一个周期的日期范围
        period_length = end_timestamp - start_timestamp
        start_timestamp -= period_length
        end_timestamp -= period_length

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


def display_word_study(
    data: pd.DataFrame,
    data_previous_period: pd.DataFrame,
    column_mapping,
    user_tz,
    period: str = "天",
):
    df = data.copy()
    df.rename(columns=column_mapping, inplace=True)
    df["学习日期"] = pd.to_datetime(df["学习日期"])
    df["学习日期"] = df["学习日期"].dt.tz_convert(user_tz)
    if period == "天":
        df["学习日期"] = df["学习日期"].dt.date
    else:
        df["学习日期"] = df["学习日期"].dt.strftime("%m-%d %H")

    df_previous_period = None
    if not data_previous_period.empty:
        df_previous_period = data_previous_period.copy()
        df_previous_period.rename(columns=column_mapping, inplace=True)
        df_previous_period["学习日期"] = pd.to_datetime(df_previous_period["学习日期"])
        df_previous_period["学习日期"] = df_previous_period["学习日期"].dt.tz_convert(
            user_tz
        )
        if period == "天":
            df_previous_period["学习日期"] = df_previous_period["学习日期"].dt.date
        else:
            df_previous_period["学习日期"] = df_previous_period["学习日期"].dt.strftime(
                "%m-%d %H"
            )

    df["单词"] = df["项目"].str.extract("单词练习-.*?-([a-zA-Z\s]+)$")
    df.loc[df["时长"] > MAX_WORD_STUDY_TIME, "时长"] = MAX_WORD_STUDY_TIME
    grouped = df.groupby(["学习日期", "单词"])
    # 修正错误计时，单个时长超过阈值的，以阈值代替
    total_study_time = grouped["时长"].sum()
    total_word_count = grouped.size()

    stats = pd.DataFrame({"学习时间": total_study_time, "单词数量": total_word_count})
    stats = stats.reset_index()

    delta_study_time = "NA"
    delta_word_count = "NA"
    if df_previous_period is not None:
        df_previous_period["单词"] = df_previous_period["项目"].str.extract(
            "单词练习-.*?-([a-zA-Z\s]+)$"
        )
        df_previous_period.loc[
            df_previous_period["时长"] > MAX_WORD_STUDY_TIME, "时长"
        ] = MAX_WORD_STUDY_TIME
        grouped_previous_period = df_previous_period.groupby(["学习日期", "单词"])
        total_study_time_previous_period = grouped_previous_period["时长"].sum()
        total_word_count_previous_period = grouped_previous_period.size()

        delta_study_time = (
            total_study_time.sum() - total_study_time_previous_period.sum()
        )
        delta_word_count = (
            total_word_count.sum() - total_word_count_previous_period.sum()
        )

    cols = st.columns(2)
    cols[0].metric(
        label="学习时间",
        value=f"{total_study_time.sum():.2f} 分钟",
        delta=f"{delta_study_time} 小时" if delta_study_time != "NA" else "NA",
    )
    cols[1].metric(
        label="单词数量",
        value=f"{total_word_count.sum()} 个",
        delta=f"{delta_word_count} 个" if delta_word_count != "NA" else "NA",
    )

    if period == "天":
        stats["学习日期"] = stats["学习日期"].apply(lambda x: x.strftime("%Y-%m-%d"))

    fig1 = px.bar(stats, x="学习日期", y="学习时间", title="学习时间")
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.bar(stats, x="学习日期", y="单词数量", title="学习单词")
    st.plotly_chart(fig2, use_container_width=True)

    st.dataframe(stats)
