from datetime import datetime
import streamlit as st
import pytz
import pandas as pd
from .st_helper import (
    MAX_WORD_STUDY_TIME,
)
import plotly.express as px


@st.cache_data(ttl=60 * 30)
def get_exercises(phone_number, start_date=None, end_date=None, previous_period=False):
    dbi = st.session_state.dbi
    db = dbi.db

    # 将日期转换为 Firestore 时间戳
    if start_date is not None:
        start_timestamp = datetime.combine(start_date, datetime.min.time())
        start_timestamp = pytz.UTC.localize(start_timestamp)  # 转换为 UTC 时间
    if end_date is not None:
        end_timestamp = datetime.combine(end_date, datetime.max.time())
        end_timestamp = pytz.UTC.localize(end_timestamp)  # 转换为 UTC 时间

    if previous_period and start_date is not None and end_date is not None:
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
            if (
                timestamp
                and (start_date is None or start_timestamp <= timestamp)
                and (end_date is None or timestamp <= end_timestamp)
            ):
                # 给 record 字典添加 phone_number 键值对
                record["phone_number"] = phone_number
                record_list.append(record)

    return record_list


@st.cache_data(ttl=60 * 30)
def get_performances(
    phone_number, start_date=None, end_date=None, previous_period=False
):
    dbi = st.session_state.dbi
    db = dbi.db

    # 将日期转换为 Firestore 时间戳
    if start_date is not None:
        start_timestamp = datetime.combine(start_date, datetime.min.time())
        start_timestamp = pytz.UTC.localize(start_timestamp)  # 转换为 UTC 时间
    if end_date is not None:
        end_timestamp = datetime.combine(end_date, datetime.max.time())
        end_timestamp = pytz.UTC.localize(end_timestamp)  # 转换为 UTC 时间

    if previous_period and start_date is not None and end_date is not None:
        # 计算上一个周期的日期范围
        period_length = end_timestamp - start_timestamp
        start_timestamp -= period_length
        end_timestamp -= period_length

    # 获取指定 ID 的文档
    doc = db.collection("performances").document(phone_number).get()

    # 初始化一个空列表来保存查询结果
    record_list = []

    # 检查文档是否存在
    if doc.exists:
        # 获取文档的数据
        data = doc.to_dict()

        # 遍历 "history" 数组
        for record in data.get("history", []):
            # 获取 "record_time" 字段
            timestamp = record.get("record_time")
            timestamp = timestamp.astimezone(pytz.UTC)
            # 如果 "record_time" 字段存在，并且在指定的范围内，则添加到查询结果中
            if (
                timestamp
                and (start_date is None or start_timestamp <= timestamp)
                and (end_date is None or timestamp <= end_timestamp)
            ):
                # 给 record 字典添加 phone_number 键值对
                record_list.append(
                    {
                        "phone_number": phone_number,
                        "item": record["item"],
                        "record_time": record["record_time"],
                        "score": record["score"],
                    }
                )

    return record_list


def get_valid_exercise_time(data, column_mapping):
    df = data.copy()
    df.rename(columns=column_mapping, inplace=True)
    # 删除无效项目
    to_remove = [
        "Home",
        "订阅续费",
        "用户中心",
        "用户注册",
        "帮助中心",
        "系统管理",
    ]
    df = df[~df["项目"].isin(to_remove)]
    df["时长"] = (df["时长"] / 60).round(2)
    return df


def _process_word_exercise_data(
    data: pd.DataFrame, column_mapping, user_tz: str, period: str = "天"
):
    df = data.copy()
    df.rename(columns=column_mapping, inplace=True)
    df["学习日期"] = pd.to_datetime(df["学习日期"])
    df["学习日期"] = df["学习日期"].dt.tz_convert(user_tz)
    if period == "天":
        df["学习日期"] = df["学习日期"].dt.date
    else:
        df["学习日期"] = df["学习日期"].dt.strftime("%m-%d %H")
    df["单词"] = df["项目"].str.extract("单词练习-.*?-([a-zA-Z\s]+)$")
    df = df[df["单词"].notna()]
    # 修正错误计时，单个时长超过阈值的，以阈值代替
    df.loc[df["时长"] > MAX_WORD_STUDY_TIME, "时长"] = MAX_WORD_STUDY_TIME
    df["时长"] = (df["时长"] / 60).round(2)
    # st.write(df)
    return df


def display_word_study(
    data: pd.DataFrame,
    data_previous_period: pd.DataFrame,
    column_mapping,
    user_tz,
    period: str = "天",
):
    df = _process_word_exercise_data(data, column_mapping, user_tz, period)
    total_study_time = df["时长"].sum()
    total_word_count = df["单词"].count()

    delta_study_time = "NA"
    delta_word_count = "NA"

    df_previous_period = None
    if not data_previous_period.empty:
        df_previous_period = _process_word_exercise_data(
            data_previous_period, column_mapping, user_tz, period
        )

        total_study_time_previous_period = df_previous_period["时长"].sum()
        total_word_count_previous_period = df_previous_period["单词"].count()

        delta_study_time = total_study_time - total_study_time_previous_period
        delta_word_count = total_word_count - total_word_count_previous_period

    cols = st.columns([2, 1])
    metric_cols = cols[0].columns([1, 1])
    metric_cols[0].metric(
        label="学习时间",
        value=f"{total_study_time.sum():.2f} 分钟",
        delta=f"{delta_study_time} 小时" if delta_study_time != "NA" else "NA",
    )
    metric_cols[1].metric(
        label="单词数量",
        value=f"{total_word_count.sum()} 个",
        delta=f"{delta_word_count} 个" if delta_word_count != "NA" else "NA",
    )

    # 按 "学习日期" 分组并计算学习时间和单词数量
    stats = df.groupby("学习日期").agg({"时长": "sum", "单词": "count"})
    stats = stats.rename(columns={"时长": "学习时间", "单词": "单词数量"}).reset_index()
    # stats["学习时间"] = stats["学习时间"].round(2)

    fig1 = px.bar(stats, x="学习日期", y="学习时间", title="学习时间")
    if period == "天":
        fig1.update_xaxes(tickformat="%Y-%m-%d")
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.bar(stats, x="学习日期", y="单词数量", title="学习单词")
    if period == "天":
        fig2.update_xaxes(tickformat="%Y-%m-%d")
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("#### 统计数据")
    column_config = {
        "学习日期": "学习日期",
        "学习时间": st.column_config.LineChartColumn("学习时间", y_min=0, y_max=1440.0),
        "单词数量": st.column_config.LineChartColumn("单词数量", y_min=0, y_max=1000),
    }
    st.dataframe(
        stats,
        # column_config=column_config,
        hide_index=True,
    )


def get_first_part(project):
    return project.split("-")[0]


def _process_study_time_data(
    data: pd.DataFrame, column_mapping, user_tz: str, period: str = "天"
):
    df = data.copy()
    df.rename(columns=column_mapping, inplace=True)
    # 删除无效项目 Home
    to_remove = [
        "Home",
        "订阅续费",
        "用户中心",
        "用户注册",
        "帮助中心",
        "系统管理",
    ]
    df = df[~df["项目"].isin(to_remove)]
    df["时长"] = (df["时长"] / 60).round(2)
    df["学习日期"] = df["学习日期"].dt.tz_convert(user_tz)
    if period == "天":
        df["学习日期"] = df["学习日期"].dt.date
    else:
        df["学习日期"] = df["学习日期"].dt.strftime("%m-%d %H")
    df["项目"] = df["项目"].apply(get_first_part)
    return df


def display_study_time(
    data: pd.DataFrame,
    data_previous_period: pd.DataFrame,
    column_mapping,
    user_tz,
    period: str = "天",
):
    df = _process_study_time_data(data, column_mapping, user_tz, period)
    total_study_time = df["时长"].sum()
    delta_study_time = "NA"
    df_previous_period = None
    if not data_previous_period.empty:
        df_previous_period = _process_study_time_data(
            data_previous_period, column_mapping, user_tz, period
        )
        total_study_time_previous_period = df_previous_period["时长"].sum()
        delta_study_time = total_study_time - total_study_time_previous_period

    cols = st.columns([2, 1])
    metric_cols = cols[0].columns([1, 1])
    metric_cols[0].metric(
        label="学习时间",
        value=f"{total_study_time.sum():.2f} 分钟",
        delta=f"{delta_study_time} 小时" if delta_study_time != "NA" else "NA",
    )

    project_time = df.groupby("项目")["时长"].sum().reset_index()

    fig1 = px.pie(
        project_time,
        values="时长",
        names="项目",
        title="你的学习时间是如何分配的？",
    )
    # fig.update_layout(title_x=0.27)
    st.plotly_chart(fig1, use_container_width=True)

    # 添加一个以学习日期x轴，按项目汇总时间的堆柱状图
    stats = df.groupby(["学习日期", "项目"]).agg({"时长": "sum"}).reset_index()
    fig2 = px.bar(
        stats,
        x="学习日期",
        y="时长",
        color="项目",
        title="分项目的学习时间",
        barmode="stack",
    )
    st.plotly_chart(fig2, use_container_width=True)


def display_average_scores(
    data: pd.DataFrame, data_previous_period: pd.DataFrame, user_tz
):
    # 将时间列转换为日期
    data["date"] = pd.to_datetime(data["record_time"]).dt.tz_convert(user_tz)
    # 按天和项目分组，计算平均得分
    data_grouped = data.groupby(["date", "item"])["score"].mean().reset_index()

    st.dataframe(data_grouped)

    # 获取项目集合
    items = set(data_grouped["item"])

    # 如果上一周期的数据不为空，计算得分变化
    if not data_previous_period.empty:
        data_previous_period["date"] = pd.to_datetime(
            data_previous_period["record_time"]
        ).dt.tz_convert(user_tz)
        data_previous_period_grouped = (
            data_previous_period.groupby(["date", "item"])["score"].mean().reset_index()
        )

        # 更新项目集合
        items = items.union(data_previous_period_grouped["item"])

    cols = st.columns(len(items))

    # 计算每个项目的得分变化
    for i, item in enumerate(items):
        current_score = round(
            data_grouped[data_grouped["item"] == item]["score"].mean(), 2
        )
        if not data_previous_period.empty:
            previous_score = round(
                data_previous_period_grouped[
                    data_previous_period_grouped["item"] == item
                ]["score"].mean(),
                2,
            )
            delta = (
                round(current_score - previous_score, 2)
                if pd.notna(previous_score)
                else "NA"
            )
        else:
            delta = "NA"

        # 在 Streamlit 应用中显示得分变化
        cols[i].metric(label=f"{item}", value=current_score, delta=delta)

    # 使用 plotly 绘制折线图
    fig = px.line(
        data_grouped, x="date", y="score", color="item", title="当前期间平均得分"
    )

    # 在 streamlit 中显示图表
    st.plotly_chart(fig)
