from pathlib import Path
import io
import wave
import toml


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
