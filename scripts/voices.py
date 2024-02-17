# 语音示例
import sys

sys.path.append("..")

from mypylib.azure_speech import (
    speech_synthesis_get_available_voices,
    synthesize_speech_to_file,
)
from mypylib.utils import get_secrets


secrets = get_secrets()

voices = speech_synthesis_get_available_voices(
    "en-US",
    secrets["Microsoft"]["SPEECH_KEY"],
    secrets["Microsoft"]["SPEECH_REGION"],
)

text = """My name is Li Ming. I am from China. I am a student at Peking University. I am majoring in computer science. I am interested in artificial intelligence and machine learning. I am excited to be here today and I look forward to meeting all of you."""
for short_name, name, local_name in voices:
    # print(f"{short_name}: {name} {local_name}")
    fp = f"../resource/us_voices/{short_name}-{name}.wav"
    synthesize_speech_to_file(
        text,
        fp,
        secrets["Microsoft"]["F0_SPEECH_KEY"],
        secrets["Microsoft"]["F0_SPEECH_REGION"],
        short_name,
    )
