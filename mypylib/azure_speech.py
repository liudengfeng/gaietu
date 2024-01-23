"""
Speech recognition samples for the Microsoft Cognitive Services Speech SDK
# install
# https://learn.microsoft.com/zh-cn/azure/ai-services/speech-service/quickstarts/setup-platform?pivots=programming-language-javascript&tabs=linux%2Cubuntu%2Cdotnetcli%2Cdotnet%2Cjre%2Cmaven%2Cnodejs%2Cmac%2Cpypi
使用发音评估: https://learn.microsoft.com/zh-cn/azure/ai-services/speech-service/how-to-pronunciation-assessment?pivots=programming-language-python
"""
import difflib
import json
import os
import io
import string
import threading
import time

# import wave
from collections import defaultdict
from typing import Callable, Dict, List, Optional
import logging

try:
    import azure.cognitiveservices.speech as speechsdk
except ImportError:
    print(
        """
    Importing the Speech SDK for Python failed.
    Refer to
    https://docs.microsoft.com/azure/cognitive-services/speech-service/quickstart-python for
    installation instructions.
    """
    )
    import sys

    sys.exit(1)

# 创建或获取logger对象
logger = logging.getLogger("streamlit")


def synthesize_speech_to_file(
    text,
    fp,
    speech_key,
    service_region,
    voice_name="en-US-JennyMultilingualNeural",
):
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=service_region,
    )
    # speech_config.speech_synthesis_language = language
    speech_config.speech_synthesis_voice_name = voice_name
    audio_config = speechsdk.audio.AudioOutputConfig(filename=fp)  # type: ignore
    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=audio_config
    )
    speech_synthesizer.speak_text_async(text).get()
    # result = speech_synthesizer.speak_text(text)
    # stream = speechsdk.AudioDataStream(result)
    # stream.save_to_wav_file(fp)


def synthesize_speech(
    text, speech_key, service_region, voice_name="en-US-JennyMultilingualNeural"
):
    """
    Synthesizes speech from the given text using Azure Speech service.

    Args:
        text (str): The text to be synthesized into speech.
        speech_key (str): The subscription key for the Speech service.
        service_region (str): The region where the Speech service is hosted.
        voice_name (str, optional): The name of the voice to be used for synthesis.
            Defaults to "en-US-JennyMultilingualNeural".

    Returns:
        SpeechSynthesisResult: The result of the speech synthesis operation.
    """
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key, region=service_region
    )
    speech_config.speech_synthesis_voice_name = voice_name
    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=None
    )
    result = speech_synthesizer.speak_text_async(text).get()
    return result


def speech_recognize_once_from_mic(
    language, speech_key, service_region, end_silence_timeout_ms=3000
):
    """performs one-shot speech recognition from the default microphone"""
    # 只进行识别，不评估
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=service_region,
    )
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, language=language
    )
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
        f"{end_silence_timeout_ms}",
    )
    result = speech_recognizer.recognize_once()
    return result


def pronunciation_assessment_from_microphone(
    reference_text, language, speech_key, service_region, end_silence_timeout_ms=3000
):
    """Performs one-shot pronunciation assessment asynchronously with input from microphone.
    See more information at https://aka.ms/csspeech/pa"""
    # 完整的听录显示在“显示”窗口中。 与参考文本相比，如果省略或插入了某个单词，或者该单词发音有误，则将根据错误类型突出显示该单词。 发音评估中的错误类型使用不同的颜色表示。 黄色表示发音错误，灰色表示遗漏，红色表示插入。 借助这种视觉区别，可以更容易地发现和分析特定错误。 通过它可以清楚地了解语音中错误类型和频率的总体情况，帮助你专注于需要改进的领域。 将鼠标悬停在每个单词上时，可查看整个单词或特定音素的准确度得分。

    # Creates an instance of a speech config with specified subscription key and service region.
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=service_region,
    )
    # The pronunciation assessment service has a longer default end silence timeout (5 seconds) than normal STT
    # as the pronunciation assessment is widely used in education scenario where kids have longer break in reading.
    # You can adjust the end silence timeout based on your real scenario.
    speech_config.set_property(
        speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs,
        f"{end_silence_timeout_ms}",
    )

    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=True,
    )
    # must set phoneme_alphabet, otherwise the output of phoneme is **not** in form of  /hɛˈloʊ/
    pronunciation_config.phoneme_alphabet = "IPA"
    # Creates a speech recognizer, also specify the speech language
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, language=language
    )

    pronunciation_config.apply_to(recognizer)

    # Starts recognizing.
    # logger.debug('Read out "{}" for pronunciation assessment ...'.format(reference_text))

    # Note: Since recognize_once() returns only a single utterance, it is suitable only for single
    # shot evaluation.
    # result = recognizer.recognize_once_async().get()
    result = recognizer.recognize_once()
    # logger.debug(f"{result.text=}")
    return result


def speech_synthesis_get_available_voices(
    language: str,
    speech_key: str,
    service_region: str,
):
    """gets the available voices list."""
    res = []
    # "Enter a locale in BCP-47 format (e.g. en-US) that you want to get the voices of, "
    # "or enter empty to get voices in all locales."
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key, region=service_region
    )

    # Creates a speech synthesizer.
    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=None
    )

    result = speech_synthesizer.get_voices_async(language).get()
    # Check result
    if (
        result is not None
        and result.reason == speechsdk.ResultReason.VoicesListRetrieved
    ):
        res = []
        for voice in result.voices:
            res.append(
                (
                    voice.short_name,
                    voice.gender.name,
                    voice.local_name,
                )
            )
        return res
    elif result is not None and result.reason == speechsdk.ResultReason.Canceled:
        raise ValueError(
            "Speech synthesis canceled; error details: {}".format(result.error_details)
        )
