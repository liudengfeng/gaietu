import datetime
import io
import wave
from pathlib import Path

import pytz
import toml

# region 日期时间相关


def get_current_monday(user_timezone):
    """
    使用会话缓存的用户时区信息，返回当前日期的周一日期。

    Returns:
        datetime.date: 当前日期的周一日期。
    """

    # 获取当前日期和时间
    now = datetime.now(pytz.timezone(user_timezone))

    # 获取今天是周几（0 是周一，6 是周日）
    weekday = now.weekday()

    # 获取当前周的周一
    monday = now.date() - datetime.timedelta(days=weekday)

    return monday


def convert_to_utc(dt, timezone_str):
    """
    将给定的日期时间从指定的时区转换为UTC。

    Args:
        dt (datetime.datetime): 要转换的日期时间。
        timezone_str (str): dt的当前时区。

    Returns:
        datetime.datetime: 转换为UTC的日期时间。
    """
    # 创建时区对象
    timezone = pytz.timezone(timezone_str)

    # 将日期时间本地化到指定的时区
    dt = timezone.localize(dt)

    # 将日期时间转换为UTC
    dt_utc = dt.astimezone(pytz.UTC)

    return dt_utc


def combine_date_and_time_to_utc(date, timezone_str, is_start):
    """
    将给定的日期和一天中的最早或最晚时间组合成一个 datetime.datetime 对象，并将其转换为 UTC。

    Args:
        date (datetime.date): 要组合的日期。
        timezone_str (str): 日期的时区。
        is_start (bool): 如果为 True，那么使用一天中的最早时间。否则，使用一天中的最晚时间。

    Returns:
        datetime.datetime: 转换为 UTC 的 datetime.datetime 对象。
    """
    # 创建时区对象
    timezone = pytz.timezone(timezone_str)

    # 根据 is_start 的值选择一天中的最早或最晚时间
    time = datetime.datetime.min.time() if is_start else datetime.datetime.max.time()

    # 将日期和时间组合成一个 datetime.datetime 对象
    dt = datetime.datetime.combine(date, time)

    # 将 datetime.datetime 对象本地化到指定的时区
    dt = timezone.localize(dt)

    # 将 datetime.datetime 对象转换为 UTC
    dt_utc = dt.astimezone(pytz.UTC)

    return dt_utc


# endregion


def get_secrets():
    """获取密码"""
    secrets = {}
    current_dir: Path = Path(__file__).parent.parent
    fp = current_dir / ".streamlit/secrets.toml"
    with open(fp, encoding="utf-8") as f:
        secrets_file_str = f.read()
        secrets.update(toml.loads(secrets_file_str))
    return secrets


def combine_audio_data(audio_data_list):
    """
    Combine a list of audio data into a single audio file.

    Args:
        audio_data_list (list): A list of audio data, where each element is a byte string representing audio data.

    Returns:
        bytes: The combined audio data as a byte string.
    """
    output = io.BytesIO()

    # 创建一个新的 wave 对象用于输出
    with wave.open(output, "wb") as output_wave:
        # 打开第一个音频数据并获取其参数
        with wave.open(io.BytesIO(audio_data_list[0]), "rb") as first_audio:
            params = first_audio.getparams()
            output_wave.setparams(params)

        # 遍历每个音频数据
        for data in audio_data_list:
            # 打开音频数据
            with wave.open(io.BytesIO(data), "rb") as audio:
                # 将音频的帧写入输出文件
                output_wave.writeframes(audio.readframes(audio.getnframes()))

    # 获取合并后的音频数据
    combined_data = output.getvalue()

    return combined_data


def calculate_audio_duration(
    audio_bytes: bytes, sample_rate: int, sample_width: int
) -> float:
    """
    Calculate the duration of an audio file based on the given audio bytes, sample rate, and sample width.

    Args:
        audio_bytes (bytes): The audio data in bytes.
        sample_rate (int): The sample rate of the audio file.
        sample_width (int): The sample width of the audio file.

    Returns:
        float: The duration of the audio file in seconds.
    """
    total_samples = len(audio_bytes) / sample_width
    duration = total_samples / sample_rate
    return duration
