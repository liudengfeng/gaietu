from collections import defaultdict
import difflib
import json
import logging
import string
import time
import azure.cognitiveservices.speech as speechsdk
import wave
from typing import Union, Dict, List, Tuple, Iterator


# 创建或获取logger对象
logger = logging.getLogger("streamlit")


def read_audio_file(file_path):
    from pydub import AudioSegment

    # 读取音频文件
    audio = AudioSegment.from_file(file_path)

    # 转换为 wav 格式并保存到临时文件
    audio.export("temp.wav", format="wav")

    # 读取 wav 文件的信息
    with wave.open("temp.wav", "rb") as audio_file:
        audio_info = {
            "sample_rate": audio_file.getframerate(),
            "sample_width": audio_file.getsampwidth(),
            "channels": audio_file.getnchannels(),
            "bytes": audio_file.readframes(audio_file.getnframes()),
        }

    return audio_info


def get_word_durations(
    recognized_words: List[speechsdk.PronunciationAssessmentWordResult],
) -> List[float]:
    durations = []
    for w in recognized_words:
        w_ns = 0
        for s in w.syllables:
            w_ns += s.duration
        # duration_in_seconds = w_ns / 10000000
        # 以纳秒为单位
        durations.append(w_ns)
        # print(f"word: {w.word}, duration: {duration_in_seconds}")
    return durations


def get_syllable_durations_and_offsets(
    recognized_words: List[speechsdk.PronunciationAssessmentWordResult],
) -> Iterator[Tuple[str, float, float, float]]:
    accumulated_text = ""
    for w in recognized_words:
        word_text = ""
        for s in w.syllables:
            word_text += " " if s.grapheme is None else s.grapheme + " "
            duration_in_seconds = s.duration / 10000000
            offset_in_seconds = s.offset / 10000000
            yield accumulated_text + word_text, duration_in_seconds, offset_in_seconds, s.accuracy_score
        accumulated_text += w.word + " "
        yield accumulated_text, duration_in_seconds, offset_in_seconds, w.accuracy_score


def read_wave_header(file_path):
    with wave.open(file_path, "rb") as audio_file:
        framerate = audio_file.getframerate()
        bits_per_sample = audio_file.getsampwidth() * 8
        num_channels = audio_file.getnchannels()
        return framerate, bits_per_sample, num_channels


class _PronunciationAssessmentWordResultV2(speechsdk.PronunciationAssessmentWordResult):
    """
    Contains word level pronunciation assessment result

    .. note::
      Added in version 1.14.0.
    """

    def __init__(self, _json):
        self._word = _json["Word"]
        # 新增
        self._duration = _json.get("Duration", 0)
        if "PronunciationAssessment" in _json:
            self._accuracy_score = _json["PronunciationAssessment"].get(
                "AccuracyScore", 0
            )
            self._error_type = _json["PronunciationAssessment"]["ErrorType"]
        # 新增
        if "PronunciationAssessment" in _json:
            self._feedback = _json["PronunciationAssessment"].get("Feedback", {})
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
    def duration(self) -> int:
        """
        The total duration of the word, in ticks (100 nanoseconds).
        """
        return self._duration

    @property
    def feedback(self) -> str:
        """
        The word text.
        """
        return self._feedback

    @property
    def is_unexpected_break(self) -> bool:
        """
        Returns a boolean indicating whether the feedback contains an unexpected break error.

        Returns:
            bool: True if the feedback contains an unexpected break error, False otherwise.
        """
        try:
            return "UnexpectedBreak" in self._feedback["Prosody"]["Break"]["ErrorTypes"]
        except:
            return False

    @property
    def is_missing_break(self) -> bool:
        """
        Returns a boolean indicating whether the feedback contains an missing break error.

        Returns:
            bool: True if the feedback contains an missing break error, False otherwise.
        """
        try:
            return "MissingBreak" in self._feedback["Prosody"]["Break"]["ErrorTypes"]
        except:
            return False

    @property
    def is_monotone(self) -> bool:
        """
        Returns a boolean indicating whether the feedback contains an missing break error.

        Returns:
            bool: True if the feedback contains an missing break error, False otherwise.
        """
        try:
            return "Monotone" in self._feedback["Prosody"]["Intonation"]["ErrorTypes"]
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
        if json_result is not None and (
            "PronunciationAssessment" in json_result
            or "ContentAssessment" in json_result
        ):
            jo = json.loads(json_result)
            nb = jo["NBest"][0]
            if "PronunciationAssessment" in nb:
                self._accuracy_score = nb["PronunciationAssessment"]["AccuracyScore"]
                self._pronunciation_score = nb["PronunciationAssessment"]["PronScore"]
                self._completeness_score = nb["PronunciationAssessment"][
                    "CompletenessScore"
                ]
                self._fluency_score = nb["PronunciationAssessment"]["FluencyScore"]
                self._prosody_score = nb["PronunciationAssessment"].get(
                    "ProsodyScore", None
                )
            if "ContentAssessment" in nb:
                self._content_assessment_result = speechsdk.ContentAssessmentResult(
                    nb["ContentAssessment"]
                )
            else:
                self._content_assessment_result = None
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


def adjust_recognized_words_and_scores(
    reference_text,
    recognized_words,
    language,
    durations,
    enable_miscue,
    fluency_scores,
):
    """Adjusts the recognized words and scores based on the reference text"""
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

    final_accuracy_scores = []
    for word in final_words:
        if word.error_type == "Insertion":
            continue
        else:
            final_accuracy_scores.append(word.accuracy_score)
    accuracy_score = sum(final_accuracy_scores) / len(final_accuracy_scores)

    fluency_score = sum([x * y for (x, y) in zip(fluency_scores, durations)]) / sum(
        durations
    )

    completeness_score = (
        len([w for w in recognized_words if w.error_type == "None"])
        / len(reference_words)
        * 100
    )
    completeness_score = completeness_score if completeness_score <= 100 else 100

    return {
        "accuracy_score": accuracy_score,
        "completeness_score": completeness_score,
        "fluency_score": fluency_score,
    }, final_words


def _pronunciation_assessment(
    audio_data: Union[str, Dict],
    secrets: Dict[str, str],
    topic: str = None,
    reference_text: str = None,
    language="en-US",
):
    if (not topic or len(topic.strip()) < 1) and (
        not reference_text or len(reference_text.strip()) < 1
    ):
        raise ValueError("Either topic or reference_text must be provided.")

    with_content_assessment = False
    if topic and len(topic.strip()) > 1:
        with_content_assessment = True

    # print(f"with_content_assessment: {with_content_assessment}")

    scores = {
        "accuracy_score": 0.0,
        "prosody_score": 0.0,
        "fluency_score": 0.0,
        "completeness_score": 0.0,
        "pronunciation_score": 0.0,
    }
    output = {}
    # Creates an instance of a speech config with specified subscription key and service region.
    speech_config = speechsdk.SpeechConfig(
        subscription=secrets["Microsoft"]["SPEECH_KEY"],
        region=secrets["Microsoft"]["SPEECH_REGION"],
    )

    if isinstance(audio_data, dict):
        # Create a custom audio stream format
        format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=audio_data["sample_rate"],
            bits_per_sample=audio_data["sample_width"] * 8,  # Convert bytes to bits
            channels=audio_data.get("channels", 1),  # Assuming mono audio
        )

        # Setup the audio stream
        stream = speechsdk.audio.PushAudioInputStream(stream_format=format)
        audio_config = speechsdk.audio.AudioConfig(stream=stream)
        # Write the audio data to the stream
        stream.write(audio_data["bytes"])
        stream.close()
    else:
        audio_config = speechsdk.audio.AudioConfig(filename=audio_data)

    # Create pronunciation assessment config, set grading system, granularity and if enable miscue based on your requirement.
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=None if with_content_assessment else reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=True,
    )
    pronunciation_config.enable_prosody_assessment()
    if with_content_assessment:
        pronunciation_config.enable_content_assessment_with_topic(topic)
    # must set phoneme_alphabet, otherwise the output of phoneme is **not** in form of  /hɛˈloʊ/
    pronunciation_config.phoneme_alphabet = "IPA"

    # Create a speech recognizer using a file as audio input.
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, language=language, audio_config=audio_config
    )
    # Apply pronunciation assessment config to speech recognizer
    pronunciation_config.apply_to(speech_recognizer)

    # Rest of the code remains the same as pronunciation_assessment_with_content_assessment function...
    done = False
    recognized_text = ""
    pron_results = []
    recognized_words = []
    fluency_scores = []
    durations = []

    def stop_cb(evt):
        """callback that signals to stop continuous recognition upon receiving an event `evt`"""
        # print("CLOSING on {}".format(evt))
        nonlocal done
        done = True

    def recognized(evt: speechsdk.SpeechRecognitionEventArgs):
        nonlocal recognized_words, pron_results, recognized_text, fluency_scores, durations
        if (
            evt.result.reason == speechsdk.ResultReason.RecognizedSpeech
            or evt.result.reason == speechsdk.ResultReason.NoMatch
        ):
            pronunciation_result = _PronunciationAssessmentResultV2(evt.result)
            pron_results.append(pronunciation_result)

            if evt.result.text.strip().rstrip(".") != "":
                # print(f"Recognizing: {evt.result.text}")
                fluency_scores.append(pronunciation_result.fluency_score)
                recognized_text += " " + evt.result.text.strip()
                recognized_words += pronunciation_result.words

                # Update the scores
                scores["prosody_score"] += pronunciation_result.prosody_score
                scores["accuracy_score"] += pronunciation_result.accuracy_score
                scores["fluency_score"] += pronunciation_result.fluency_score
                scores["completeness_score"] += pronunciation_result.completeness_score
                scores[
                    "pronunciation_score"
                ] += pronunciation_result.pronunciation_score
                # Duration
                duration = sum([int(w.duration) for w in pronunciation_result.words])
                durations.append(duration)

    # Connect callbacks to the events fired by the speech recognizer
    speech_recognizer.recognized.connect(recognized)
    # speech_recognizer.session_started.connect(
    #     lambda evt: print("SESSION STARTED: {}".format(evt))
    # )
    # speech_recognizer.session_stopped.connect(
    #     lambda evt: print("SESSION STOPPED {}".format(evt))
    # )
    # speech_recognizer.canceled.connect(lambda evt: print("CANCELED {}".format(evt)))
    # Stop continuous recognition on either session stopped or canceled events
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    # Start continuous pronunciation assessment
    speech_recognizer.start_continuous_recognition()
    while not done:
        time.sleep(0.5)
    speech_recognizer.stop_continuous_recognition()

    output["error"] = ""
    # Content assessment result is in the last pronunciation assessment block
    if with_content_assessment and pron_results[-1].content_assessment_result is None:
        output["error"] = "No content assessment result"
        return output

    if with_content_assessment:
        # content_result = pron_results[-1].content_assessment_result
        content_result = pron_results.pop().content_assessment_result
        output["content_result"] = {
            "grammar_score": content_result.grammar_score,
            "vocabulary_score": content_result.vocabulary_score,
            "topic_score": content_result.topic_score,
        }

    # Calculate the average scores
    n = len(pron_results)
    scores["prosody_score"] /= n
    scores["accuracy_score"] /= n
    scores["fluency_score"] /= n
    scores["completeness_score"] /= n
    scores["pronunciation_score"] /= n

    # print(f"Content Assessment for: {recognized_text.strip()}")
    output["recognized_text"] = recognized_text.strip()
    error_counts = defaultdict(int)
    # 对内容进行评估时，不需要对识别结果进行调整
    if not with_content_assessment:
        updated, final_words = adjust_recognized_words_and_scores(
            reference_text=reference_text,
            recognized_words=recognized_words,
            language=language,
            durations=durations,
            enable_miscue=True,
            fluency_scores=fluency_scores,
        )
        for k, v in updated.items():
            scores[k] = v

        # 定义各项分数的权重
        weights = {
            "accuracy_score": 0.4,
            "prosody_score": 0.2,
            "fluency_score": 0.2,
            "completeness_score": 0.2,
        }
        scores["pronunciation_score"] = sum(
            scores[key] * weight for key, weight in weights.items()
        )
        for word in final_words:
            error_counts[word.error_type] += 1
            # logger.debug(f"{word.word=}\t{word.Feedback=}")
            if word.is_unexpected_break:
                error_counts["UnexpectedBreak"] += 1
            if word.is_missing_break:
                error_counts["MissingBreak"] += 1
            if word.is_monotone:
                error_counts["Monotone"] += 1
    else:
        final_words = recognized_words
        for word in final_words:
            error_counts[word.error_type] += 1

    output["pronunciation_result"] = scores
    output["recognized_words"] = final_words
    output["error_counts"] = dict(error_counts)
    return output


# def pronunciation_assessment_from_stream(
#     audio_info: Dict[str, any],
#     secrets: Dict[str, str],
#     topic: str = None,
#     reference_text: str = None,
#     language="en-US",
# ):
#     """Performs content assessment asynchronously with input from an audio stream"""
#     # 定价层：S0 标准 每分钟 300 个请求
#     # Check that either topic or reference_text is provided
#     if (not topic or len(topic.strip()) < 1) and (
#         not reference_text or len(reference_text.strip()) < 1
#     ):
#         raise ValueError("Either topic or reference_text must be provided.")

#     with_content_assessment = False
#     if topic and len(topic.strip()) > 1:
#         with_content_assessment = True

#     # print(f"with_content_assessment: {with_content_assessment}")

#     scores = {
#         "accuracy_score": 0.0,
#         "prosody_score": 0.0,
#         "fluency_score": 0.0,
#         "completeness_score": 0.0,
#         "pronunciation_score": 0.0,
#     }
#     output = {}
#     # Creates an instance of a speech config with specified subscription key and service region.
#     speech_config = speechsdk.SpeechConfig(
#         subscription=secrets["Microsoft"]["SPEECH_KEY"],
#         region=secrets["Microsoft"]["SPEECH_REGION"],
#     )

#     # Create a custom audio stream format
#     format = speechsdk.audio.AudioStreamFormat(
#         samples_per_second=audio_info["sample_rate"],
#         bits_per_sample=audio_info["sample_width"] * 8,  # Convert bytes to bits
#         channels=audio_info.get("channels", 1),  # Assuming mono audio
#     )

#     # Setup the audio stream
#     stream = speechsdk.audio.PushAudioInputStream(stream_format=format)
#     audio_config = speechsdk.audio.AudioConfig(stream=stream)

#     # Create pronunciation assessment config, set grading system, granularity and if enable miscue based on your requirement.
#     pronunciation_config = speechsdk.PronunciationAssessmentConfig(
#         reference_text=None if with_content_assessment else reference_text,
#         grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
#         granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
#         enable_miscue=True,
#     )
#     pronunciation_config.enable_prosody_assessment()
#     if with_content_assessment:
#         pronunciation_config.enable_content_assessment_with_topic(topic)
#     # must set phoneme_alphabet, otherwise the output of phoneme is **not** in form of  /hɛˈloʊ/
#     pronunciation_config.phoneme_alphabet = "IPA"

#     # Create a speech recognizer using a file as audio input.
#     speech_recognizer = speechsdk.SpeechRecognizer(
#         speech_config=speech_config, language=language, audio_config=audio_config
#     )
#     # Apply pronunciation assessment config to speech recognizer
#     pronunciation_config.apply_to(speech_recognizer)

#     # Write the audio data to the stream
#     stream.write(audio_info["bytes"])
#     stream.close()

#     # Rest of the code remains the same as pronunciation_assessment_with_content_assessment function...
#     done = False
#     recognized_text = ""
#     pron_results = []
#     recognized_words = []
#     fluency_scores = []
#     durations = []

#     def stop_cb(evt):
#         """callback that signals to stop continuous recognition upon receiving an event `evt`"""
#         # print("CLOSING on {}".format(evt))
#         nonlocal done
#         done = True

#     def recognized(evt: speechsdk.SpeechRecognitionEventArgs):
#         nonlocal recognized_words, pron_results, recognized_text, fluency_scores, durations
#         if (
#             evt.result.reason == speechsdk.ResultReason.RecognizedSpeech
#             or evt.result.reason == speechsdk.ResultReason.NoMatch
#         ):
#             pronunciation_result = _PronunciationAssessmentResultV2(evt.result)
#             pron_results.append(pronunciation_result)

#             if evt.result.text.strip().rstrip(".") != "":
#                 # print(f"Recognizing: {evt.result.text}")
#                 fluency_scores.append(pronunciation_result.fluency_score)
#                 recognized_text += " " + evt.result.text.strip()
#                 recognized_words += pronunciation_result.words

#                 # Update the scores
#                 scores["prosody_score"] += pronunciation_result.prosody_score
#                 scores["accuracy_score"] += pronunciation_result.accuracy_score
#                 scores["fluency_score"] += pronunciation_result.fluency_score
#                 scores["completeness_score"] += pronunciation_result.completeness_score
#                 scores[
#                     "pronunciation_score"
#                 ] += pronunciation_result.pronunciation_score
#                 # Duration
#                 duration = sum([int(w.duration) for w in pronunciation_result.words])
#                 durations.append(duration)

#     # Connect callbacks to the events fired by the speech recognizer
#     speech_recognizer.recognized.connect(recognized)
#     # speech_recognizer.session_started.connect(
#     #     lambda evt: print("SESSION STARTED: {}".format(evt))
#     # )
#     # speech_recognizer.session_stopped.connect(
#     #     lambda evt: print("SESSION STOPPED {}".format(evt))
#     # )
#     # speech_recognizer.canceled.connect(lambda evt: print("CANCELED {}".format(evt)))
#     # Stop continuous recognition on either session stopped or canceled events
#     speech_recognizer.session_stopped.connect(stop_cb)
#     speech_recognizer.canceled.connect(stop_cb)

#     # Start continuous pronunciation assessment
#     speech_recognizer.start_continuous_recognition()
#     while not done:
#         time.sleep(0.5)
#     speech_recognizer.stop_continuous_recognition()

#     output["error"] = ""
#     # Content assessment result is in the last pronunciation assessment block
#     if with_content_assessment and pron_results[-1].content_assessment_result is None:
#         output["error"] = "No content assessment result"
#         return output

#     if with_content_assessment:
#         # content_result = pron_results[-1].content_assessment_result
#         content_result = pron_results.pop().content_assessment_result
#         output["content_result"] = {
#             "grammar_score": content_result.grammar_score,
#             "vocabulary_score": content_result.vocabulary_score,
#             "topic_score": content_result.topic_score,
#         }

#     # Calculate the average scores
#     n = len(pron_results)
#     scores["prosody_score"] /= n
#     scores["accuracy_score"] /= n
#     scores["fluency_score"] /= n
#     scores["completeness_score"] /= n
#     scores["pronunciation_score"] /= n

#     # print(f"Content Assessment for: {recognized_text.strip()}")
#     output["recognized_text"] = recognized_text.strip()
#     error_counts = defaultdict(int)
#     # 对内容进行评估时，不需要对识别结果进行调整
#     if not with_content_assessment:
#         updated, final_words = adjust_recognized_words_and_scores(
#             reference_text=reference_text,
#             recognized_words=recognized_words,
#             language=language,
#             durations=durations,
#             enable_miscue=True,
#             fluency_scores=fluency_scores,
#         )
#         for k, v in updated.items():
#             scores[k] = v

#         # 定义各项分数的权重
#         weights = {
#             "accuracy_score": 0.4,
#             "prosody_score": 0.2,
#             "fluency_score": 0.2,
#             "completeness_score": 0.2,
#         }
#         scores["pronunciation_score"] = sum(
#             scores[key] * weight for key, weight in weights.items()
#         )
#         for word in final_words:
#             error_counts[word.error_type] += 1
#             # logger.debug(f"{word.word=}\t{word.Feedback=}")
#             if word.is_unexpected_break:
#                 error_counts["UnexpectedBreak"] += 1
#             if word.is_missing_break:
#                 error_counts["MissingBreak"] += 1
#             if word.is_monotone:
#                 error_counts["Monotone"] += 1
#     else:
#         final_words = recognized_words
#         for word in final_words:
#             error_counts[word.error_type] += 1

#     output["pronunciation_result"] = scores
#     output["recognized_words"] = final_words
#     output["error_counts"] = dict(error_counts)
#     return output


# def pronunciation_assessment_from_wavfile(
#     wavfile: str,
#     secrets: Dict[str, str],
#     topic: str,
#     language="en-US",
# ):
#     output = {}
#     speech_config = speechsdk.SpeechConfig(
#         subscription=secrets["Microsoft"]["SPEECH_KEY"],
#         region=secrets["Microsoft"]["SPEECH_REGION"],
#     )
#     audio_config = speechsdk.audio.AudioConfig(filename=wavfile)
#     pronunciation_config = speechsdk.PronunciationAssessmentConfig(
#         grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
#         granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
#         enable_miscue=False,
#     )
#     pronunciation_config.enable_prosody_assessment()
#     pronunciation_config.enable_content_assessment_with_topic(topic)
#     # must set phoneme_alphabet, otherwise the output of phoneme is **not** in form of  /hɛˈloʊ/
#     pronunciation_config.phoneme_alphabet = "IPA"

#     speech_recognizer = speechsdk.SpeechRecognizer(
#         speech_config=speech_config, language=language, audio_config=audio_config
#     )
#     # Apply pronunciation assessment config to speech recognizer
#     pronunciation_config.apply_to(speech_recognizer)

#     done = False
#     pron_results = []
#     recognized_text = ""

#     def stop_cb(evt):
#         """callback that signals to stop continuous recognition upon receiving an event `evt`"""
#         logger.debug("CLOSING on {}".format(evt))
#         nonlocal done
#         done = True

#     def recognized(evt):
#         nonlocal pron_results, recognized_text
#         if (
#             evt.result.reason == speechsdk.ResultReason.RecognizedSpeech
#             or evt.result.reason == speechsdk.ResultReason.NoMatch
#         ):
#             pron_results.append(speechsdk.PronunciationAssessmentResult(evt.result))
#             if evt.result.text.strip().rstrip(".") != "":
#                 logger.debug(f"Recognizing: {evt.result.text}")
#                 recognized_text += " " + evt.result.text.strip()

#     # Connect callbacks to the events fired by the speech recognizer
#     speech_recognizer.recognized.connect(recognized)
#     speech_recognizer.session_started.connect(
#         lambda evt: logger.debug("SESSION STARTED: {}".format(evt))
#     )
#     speech_recognizer.session_stopped.connect(
#         lambda evt: logger.debug("SESSION STOPPED {}".format(evt))
#     )
#     speech_recognizer.canceled.connect(
#         lambda evt: logger.debug("CANCELED {}".format(evt))
#     )
#     # Stop continuous recognition on either session stopped or canceled events
#     speech_recognizer.session_stopped.connect(stop_cb)
#     speech_recognizer.canceled.connect(stop_cb)

#     # Start continuous pronunciation assessment
#     speech_recognizer.start_continuous_recognition()
#     while not done:
#         time.sleep(0.5)
#     speech_recognizer.stop_continuous_recognition()

#     # Content assessment result is in the last pronunciation assessment block
#     assert pron_results[-1].content_assessment_result is not None
#     content_result = pron_results[-1].content_assessment_result

#     output["content_result"] = {
#         "grammar_score": content_result.grammar_score,
#         "vocabulary_score": content_result.vocabulary_score,
#         "topic_score": content_result.topic_score,
#     }
#     output["recognized_text"] = recognized_text.strip()
#     # 平均分
#     n = len(pron_results) - 1
#     pronunciation_score = []
#     accuracy_score = []
#     fluency_score = []
#     completeness_score = []
#     prosody_score = []
#     words_list = []
#     error_counts = defaultdict(int)
#     for i in range(n):
#         p = pron_results[i]
#         pronunciation_score.append(p.pronunciation_score)
#         accuracy_score.append(p.accuracy_score)
#         fluency_score.append(p.fluency_score)
#         completeness_score.append(p.completeness_score)
#         prosody_score.append(p.prosody_score)
#         words_list.extend(p.words)
#         for w in p.words:
#             if w.error_type:
#                 error_counts[w.error_type] += 1
#     scores = {
#         "pronunciation_score": sum(pronunciation_score) / n,
#         "accuracy_score": sum(accuracy_score) / n,
#         "fluency_score": sum(fluency_score) / n,
#         "completeness_score": sum(completeness_score) / n,
#         "prosody_score": sum(prosody_score) / n,
#     }
#     output["pronunciation_result"] = scores
#     output["recognized_words"] = words_list
#     output["error_counts"] = dict(error_counts)
#     return output


def pronunciation_assessment_from_stream(
    audio_info: Dict[str, any],
    secrets: Dict[str, str],
    topic: str = None,
    reference_text: str = None,
    language="en-US",
):
    return _pronunciation_assessment(
        audio_info,
        secrets,
        topic=topic,
        reference_text=reference_text,
        language=language,
    )


def pronunciation_assessment_from_wavfile(
    wavfile: str,
    secrets: Dict[str, str],
    topic: str = None,
    reference_text: str = None,
    language="en-US",
):
    return _pronunciation_assessment(
        wavfile,
        secrets,
        topic=topic,
        reference_text=reference_text,
        language=language,
    )
