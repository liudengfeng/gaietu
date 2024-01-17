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


def synthesize_speech_to_audio_data(
    text, speech_key, service_region, voice_name="en-US-JennyMultilingualNeural"
):
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key, region=service_region
    )
    speech_config.speech_synthesis_voice_name = voice_name
    speech_synthesizer = speechsdk.SpeechSynthesizer(
        speech_config=speech_config, audio_config=None
    )
    # SpeechSynthesisResult
    result = speech_synthesizer.speak_text_async(text).get()
    return result.audio_data


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


def get_word_phonemes(word: speechsdk.PronunciationAssessmentWordResult):
    # logger.debug(f"{type(word)}")
    phonemes = []
    scores = []
    if word.error_type != "Omission":
        for p in word.phonemes:
            # logger.debug(f"{p.phoneme=}\t{p.accuracy_score=}")
            phonemes.append(p.phoneme)
            scores.append(p.accuracy_score)
    return (phonemes, scores)


class _PronunciationAssessmentWordResultV2(speechsdk.PronunciationAssessmentWordResult):
    """
    Contains word level pronunciation assessment result

    .. note::
      Added in version 1.14.0.
    """

    def __init__(self, _json):
        self._word = _json["Word"]
        if "PronunciationAssessment" in _json:
            self._accuracy_score = _json["PronunciationAssessment"].get(
                "AccuracyScore", 0
            )
            self._error_type = _json["PronunciationAssessment"]["ErrorType"]
        # 新增
        if "PronunciationAssessment" in _json:
            self._Feedback = _json["PronunciationAssessment"].get("Feedback", {})
        if "Phonemes" in _json:
            self._phonemes = [
                speechsdk.PronunciationAssessmentPhonemeResult(p)
                for p in _json["Phonemes"]
            ]
        if "Syllables" in _json:
            self._syllables = [
                speechsdk.SyllableLevelTimingResult(s) for s in _json["Syllables"]
            ]

    @property
    def Feedback(self) -> str:
        """
        The word text.
        """
        return self._Feedback

    @property
    def IsUnexpectedBreak(self) -> bool:
        """
        Returns a boolean indicating whether the feedback contains an unexpected break error.

        Returns:
            bool: True if the feedback contains an unexpected break error, False otherwise.
        """
        try:
            return (
                self._Feedback["Prosody"]["Break"]["ErrorTypes"][0] == "UnexpectedBreak"
            )
        except:
            return False

    @property
    def IsMissingBreak(self) -> bool:
        """
        Returns a boolean indicating whether the feedback contains an missing break error.

        Returns:
            bool: True if the feedback contains an missing break error, False otherwise.
        """
        try:
            return self._Feedback["Prosody"]["Break"]["ErrorTypes"][0] == "MissingBreak"
        except:
            return False

    @property
    def IsMonotone(self) -> bool:
        """
        Returns a boolean indicating whether the feedback contains an missing break error.

        Returns:
            bool: True if the feedback contains an missing break error, False otherwise.
        """
        try:
            return (
                self._Feedback["Prosody"]["Intonation"]["ErrorTypes"][0] == "Monotone"
            )
        except:
            return False


class _PronunciationAssessmentResultV2(speechsdk.PronunciationAssessmentResult):
    """
    Represents pronunciation assessment result.

    .. note::
      Added in version 1.14.0.

    The result can be initialized from a speech recognition result.

    :param result: The speech recognition result
    """

    def __init__(self, result: speechsdk.SpeechRecognitionResult):
        json_result = result.properties.get(
            speechsdk.PropertyId.SpeechServiceResponse_JsonResult
        )
        if json_result is not None and "PronunciationAssessment" in json_result:
            jo = json.loads(json_result)
            nb = jo["NBest"][0]
            self._accuracy_score = nb["PronunciationAssessment"]["AccuracyScore"]
            self._pronunciation_score = nb["PronunciationAssessment"]["PronScore"]
            self._completeness_score = nb["PronunciationAssessment"][
                "CompletenessScore"
            ]
            self._fluency_score = nb["PronunciationAssessment"]["FluencyScore"]
            if "Words" in nb:
                self._words = [
                    _PronunciationAssessmentWordResultV2(w) for w in nb["Words"]
                ]

    @property
    def words(self) -> List[_PronunciationAssessmentWordResultV2]:
        """
        Word level pronunciation assessment result.
        """
        return self._words


def pronunciation_assessment_from_wavfile(
    wavfile: str,
    reference_text: str,
    language: str,
    speech_key: str,
    service_region: str,
    enable_miscue: bool = True,
):
    """Performs continuous pronunciation assessment asynchronously with input from an audio file.
    See more information at https://aka.ms/csspeech/pa"""
    words_list = []
    accuracy_score = 0.0
    completeness_score = 0.0
    fluency_score = 0.0
    # Creates an instance of a speech config with specified subscription key and service region.
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key, region=service_region
    )

    audio_config = speechsdk.audio.AudioConfig(filename=wavfile)

    # 新增 EnableProsodyAssessment
    pa_config = {
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "EnableMiscue": True,
        "EnableProsodyAssessment": True,
    }
    # logger.debug(f"{json.dumps(pa_config)}")
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        json_string=json.dumps(pa_config)
    )
    pronunciation_config.reference_text = reference_text
    # must set phoneme_alphabet, otherwise the output of phoneme is **not** in form of  /hɛˈloʊ/
    pronunciation_config.phoneme_alphabet = "IPA"
    # Creates a speech recognizer using a file as audio input.
    # language = "en-US"
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, language=language, audio_config=audio_config
    )
    # apply pronunciation assessment config to speech recognizer
    pronunciation_config.apply_to(speech_recognizer)

    done = False
    recognized_words = []
    fluency_scores = []
    # 韵律指示给定语音的性质，包括重音、语调、语速和节奏。
    prosody_scores = []
    durations = []

    def stop_cb(evt: speechsdk.SessionEventArgs):
        """callback that signals to stop continuous recognition upon receiving an event `evt`"""
        # logger.debug("CLOSING on {}".format(evt))
        nonlocal done
        done = True

    def recognized(evt: speechsdk.SpeechRecognitionEventArgs):
        # logger.debug("pronunciation assessment for: {}".format(evt.result.text))
        # pronunciation_result = speechsdk.PronunciationAssessmentResult(evt.result)
        pronunciation_result = _PronunciationAssessmentResultV2(evt.result)
        nonlocal recognized_words, fluency_scores, durations, prosody_scores
        recognized_words += pronunciation_result.words
        fluency_scores.append(pronunciation_result.fluency_score)
        json_result = evt.result.properties.get(
            speechsdk.PropertyId.SpeechServiceResponse_JsonResult
        )
        jo = json.loads(json_result)  # type: ignore
        # logger.debug(json.dumps(jo, indent=4))
        nb = jo["NBest"][0]
        durations.append(sum([int(w["Duration"]) for w in nb["Words"]]))
        prosody_scores.append(nb["PronunciationAssessment"]["ProsodyScore"])

    # Connect callbacks to the events fired by the speech recognizer
    speech_recognizer.recognized.connect(recognized)

    # speech_recognizer.session_started.connect(
    #     lambda evt: logger.debug("SESSION STARTED: {}".format(evt))
    # )
    # speech_recognizer.session_stopped.connect(
    #     lambda evt: logger.debug("SESSION STOPPED {}".format(evt))
    # )
    def view_canceled(evt):
        cancellation_details = evt.result.cancellation_details
        logger.debug(
            "Speech Recognition canceled: {}".format(cancellation_details.reason)
        )
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            logger.debug(
                ":x: Error details: {}".format(cancellation_details.error_details)
            )

    # speech_recognizer.canceled.connect(lambda evt: logger.debug("CANCELED {}".format(evt)))
    speech_recognizer.canceled.connect(view_canceled)
    # stop continuous recognition on either session stopped or canceled events
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    # Start continuous pronunciation assessment
    speech_recognizer.start_continuous_recognition()

    while not done:
        time.sleep(0.5)

    speech_recognizer.stop_continuous_recognition()

    # we need to convert the reference text to lower case, and split to words, then remove the punctuations.
    if language == "zh-CN":
        # Use jieba package to split words for Chinese
        import jieba
        import zhon.hanzi

        jieba.suggest_freq([x.word for x in recognized_words], True)
        reference_words = [
            w for w in jieba.cut(reference_text) if w not in zhon.hanzi.punctuation
        ]
    else:
        reference_words = [
            w.strip(string.punctuation) for w in reference_text.lower().split()
        ]

    # For continuous pronunciation assessment mode, the service won't return the words with `Insertion` or `Omission`
    # even if miscue is enabled.
    # We need to compare with the reference text after received all recognized words to get these error words.
    if enable_miscue:
        diff = difflib.SequenceMatcher(
            None, reference_words, [x.word.lower() for x in recognized_words]
        )
        final_words = []
        for tag, i1, i2, j1, j2 in diff.get_opcodes():
            if tag in ["insert", "replace"]:
                for word in recognized_words[j1:j2]:
                    if word.error_type == "None":
                        word._error_type = "Insertion"
                    final_words.append(word)
            if tag in ["delete", "replace"]:
                for word_text in reference_words[i1:i2]:
                    # word = speechsdk.PronunciationAssessmentWordResult(
                    word = _PronunciationAssessmentWordResultV2(
                        {
                            "Word": word_text,
                            "PronunciationAssessment": {
                                "ErrorType": "Omission",
                            },
                        }
                    )
                    final_words.append(word)
            if tag == "equal":
                final_words += recognized_words[j1:j2]
    else:
        final_words = recognized_words

    # We can calculate whole accuracy by averaging
    final_accuracy_scores = []
    for word in final_words:
        if word.error_type == "Insertion":
            continue
        else:
            final_accuracy_scores.append(word.accuracy_score)
    accuracy_score = sum(final_accuracy_scores) / len(final_accuracy_scores)
    # Re-calculate fluency score
    fluency_score = sum([x * y for (x, y) in zip(fluency_scores, durations)]) / sum(
        durations
    )
    # Calculate whole completeness score
    completeness_score = (
        len([w for w in recognized_words if w.error_type == "None"])
        / len(reference_words)
        * 100
    )
    completeness_score = completeness_score if completeness_score <= 100 else 100
    # Re-calculate prosody score
    prosody_score = sum(prosody_scores) / len(prosody_scores)
    pron_score = (
        accuracy_score * 0.4
        + prosody_score * 0.2
        + fluency_score * 0.2
        + completeness_score * 0.2
    )
    # 创建一个defaultdict，当访问不存在的键时，自动创建一个默认值为0的int
    error_counts = defaultdict(int)
    # logger.debug("Error counts:")
    for word in final_words:
        error_counts[word.error_type] += 1
        # logger.debug(f"{word.word=}\t{word.Feedback=}")
        if word.IsUnexpectedBreak:
            error_counts["UnexpectedBreak"] += 1
        if word.IsMissingBreak:
            error_counts["MissingBreak"] += 1
        if word.IsMonotone:
            error_counts["Monotone"] += 1
        phonemes, scores = get_word_phonemes(word)
        word_info = {
            "word": word.word,
            "accuracy_score": word.accuracy_score,
            "error_type": word.error_type,
            "phonemes": phonemes,
            "scores": scores,
            "feedback": word.Feedback,
        }
        words_list.append(word_info)
    # TODO:根据新版调整
    return {
        "pronunciation_score": pron_score,
        "accuracy_score": accuracy_score,
        "fluency_score": fluency_score,
        "completeness_score": completeness_score,
        "prosody_score": prosody_score,
        "words_list": words_list,
        "error_counts": error_counts,
    }


def pronunciation_assessment_with_content_assessment(
    wavfile: str,
    topic: str,
    language: str,
    speech_key: str,
    service_region: str,
):
    """Performs content assessment asynchronously with input from an audio file.
    See more information at https://aka.ms/csspeech/pa"""
    # See more information at https://aka.ms/csspeech/pa"""
    # 定价层：S0 标准 每分钟 300 个请求
    # Generally, the waveform should longer than 20s and the content should be more than 3 sentences.
    # Create an instance of a speech config with specified subscription key and service region.
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=service_region,
    )
    audio_config = speechsdk.audio.AudioConfig(filename=wavfile)
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=False,
    )
    pronunciation_config.enable_prosody_assessment()
    pronunciation_config.enable_content_assessment_with_topic(topic)
    # must set phoneme_alphabet, otherwise the output of phoneme is **not** in form of  /hɛˈloʊ/
    pronunciation_config.phoneme_alphabet = "IPA"

    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, language=language, audio_config=audio_config
    )
    # Apply pronunciation assessment config to speech recognizer
    pronunciation_config.apply_to(speech_recognizer)

    done = False
    pron_results = []
    recognized_text = ""

    def stop_cb(evt):
        """callback that signals to stop continuous recognition upon receiving an event `evt`"""
        logger.debug("CLOSING on {}".format(evt))
        nonlocal done
        done = True

    def recognized(evt):
        nonlocal pron_results, recognized_text
        if (
            evt.result.reason == speechsdk.ResultReason.RecognizedSpeech
            or evt.result.reason == speechsdk.ResultReason.NoMatch
        ):
            pron_results.append(speechsdk.PronunciationAssessmentResult(evt.result))
            if evt.result.text.strip().rstrip(".") != "":
                logger.debug(f"Recognizing: {evt.result.text}")
                recognized_text += " " + evt.result.text.strip()

    # Connect callbacks to the events fired by the speech recognizer
    speech_recognizer.recognized.connect(recognized)
    speech_recognizer.session_started.connect(
        lambda evt: logger.debug("SESSION STARTED: {}".format(evt))
    )
    speech_recognizer.session_stopped.connect(
        lambda evt: logger.debug("SESSION STOPPED {}".format(evt))
    )
    speech_recognizer.canceled.connect(
        lambda evt: logger.debug("CANCELED {}".format(evt))
    )
    # Stop continuous recognition on either session stopped or canceled events
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    # Start continuous pronunciation assessment
    speech_recognizer.start_continuous_recognition()
    while not done:
        time.sleep(0.5)
    speech_recognizer.stop_continuous_recognition()

    # Content assessment result is in the last pronunciation assessment block
    assert pron_results[-1].content_assessment_result is not None
    content_result = pron_results[-1].content_assessment_result
    # logger.debug(f"Content Assessment for: {recognized_text.strip()}")
    # logger.debug(
    #     "Content Assessment results:\n"
    #     f"\tGrammar score: {content_result.grammar_score:.1f}\n"
    #     f"\tVocabulary score: {content_result.vocabulary_score:.1f}\n"
    #     f"\tTopic score: {content_result.topic_score:.1f}"
    # )
    n = len(pron_results) - 1
    pronunciation_score = []
    accuracy_score = []
    fluency_score = []
    completeness_score = []
    prosody_score = []
    words_list = []
    error_counts = defaultdict(int)
    for i in range(n):
        p = pron_results[i]
        pronunciation_score.append(p.pronunciation_score)
        accuracy_score.append(p.accuracy_score)
        fluency_score.append(p.fluency_score)
        completeness_score.append(p.completeness_score)
        prosody_score.append(p.prosody_score)
        words_list.extend(p.words)
        for w in p.words:
            if w.error_type:
                error_counts[w.error_type] += 1
    return {
        "pronunciation_score": sum(pronunciation_score) / n,
        "accuracy_score": sum(accuracy_score) / n,
        "fluency_score": sum(fluency_score) / n,
        "completeness_score": sum(completeness_score) / n,
        "prosody_score": sum(prosody_score) / n,
        "words_list": words_list,
        "error_counts": error_counts,
        "recognized_text": recognized_text.strip(),
        "content_result": content_result,
    }


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
