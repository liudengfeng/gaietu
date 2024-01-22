import time
import azure.cognitiveservices.speech as speechsdk
import threading
import wave
from typing import Dict


def read_wave_header(file_path):
    with wave.open(file_path, "rb") as audio_file:
        framerate = audio_file.getframerate()
        bits_per_sample = audio_file.getsampwidth() * 8
        num_channels = audio_file.getnchannels()
        return framerate, bits_per_sample, num_channels


def push_stream_writer(stream):
    # The number of bytes to push per buffer
    n_bytes = 3200
    wav_fh = wave.open(weatherfilename)
    # Start pushing data until all data has been read from the file
    try:
        while True:
            frames = wav_fh.readframes(n_bytes // 2)
            print("read {} bytes".format(len(frames)))
            if not frames:
                break
            stream.write(frames)
            time.sleep(0.1)
    finally:
        wav_fh.close()
        stream.close()  # must be done to signal the end of stream


def push_stream_writer(stream):
    # The number of bytes to push per buffer
    n_bytes = 3200
    wav_fh = wave.open(weatherfilename)
    # Start pushing data until all data has been read from the file
    try:
        while True:
            frames = wav_fh.readframes(n_bytes // 2)
            print("read {} bytes".format(len(frames)))
            if not frames:
                break
            stream.write(frames)
            time.sleep(0.1)
    finally:
        wav_fh.close()
        stream.close()  # must be done to signal the end of stream


# def pronunciation_assessment_from_stream(
#     speech_key: str, service_region: str, language="en-US"
# ):
#     """Performs pronunciation assessment asynchronously with input from an audio stream.
#     See more information at https://aka.ms/csspeech/pa"""

#     # Creates an instance of a speech config with specified subscription key and service region.
#     # Replace with your own subscription key and service region (e.g., "westus").
#     # Note: The sample is for en-US language.
#     speech_config = speechsdk.SpeechConfig(
#         subscription=speech_key, region=service_region
#     )

#     # Setup the audio stream
#     framerate, bits_per_sample, num_channels = read_wave_header(weatherfilename)
#     format = speechsdk.audio.AudioStreamFormat(
#         samples_per_second=framerate,
#         bits_per_sample=bits_per_sample,
#         channels=num_channels,
#     )
#     stream = speechsdk.audio.PushAudioInputStream(format)
#     audio_config = speechsdk.audio.AudioConfig(stream=stream)

#     reference_text = "What's the weather like?"
#     # Create pronunciation assessment config, set grading system, granularity and if enable miscue based on your requirement.
#     pronunciation_config = speechsdk.PronunciationAssessmentConfig(
#         reference_text=reference_text,
#         grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
#         granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
#         enable_miscue=True,
#     )
#     pronunciation_config.enable_prosody_assessment()

#     # Create a speech recognizer using a file as audio input.
#     language = "en-US"
#     speech_recognizer = speechsdk.SpeechRecognizer(
#         speech_config=speech_config, language=language, audio_config=audio_config
#     )
#     # Apply pronunciation assessment config to speech recognizer
#     pronunciation_config.apply_to(speech_recognizer)

#     # Start push stream writer thread
#     push_stream_writer_thread = threading.Thread(
#         target=push_stream_writer, args=[stream]
#     )
#     push_stream_writer_thread.start()
#     result = speech_recognizer.recognize_once_async().get()
#     push_stream_writer_thread.join()

#     # Check the result
#     if result.reason == speechsdk.ResultReason.RecognizedSpeech:
#         print("pronunciation assessment for: {}".format(result.text))
#         pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
#         print(
#             "    Accuracy score: {}, prosody score: {}, pronunciation score: {}, completeness score : {}, fluency score: {}".format(
#                 pronunciation_result.accuracy_score,
#                 pronunciation_result.prosody_score,
#                 pronunciation_result.pronunciation_score,
#                 pronunciation_result.completeness_score,
#                 pronunciation_result.fluency_score,
#             )
#         )
#         print("  Word-level details:")
#         for idx, word in enumerate(pronunciation_result.words):
#             print(
#                 "    {}: word: {}\taccuracy score: {}\terror type: {};".format(
#                     idx + 1, word.word, word.accuracy_score, word.error_type
#                 )
#             )
#     elif result.reason == speechsdk.ResultReason.NoMatch:
#         print("No speech could be recognized")
#     elif result.reason == speechsdk.ResultReason.Canceled:
#         cancellation_details = result.cancellation_details
#         print("Speech Recognition canceled: {}".format(cancellation_details.reason))
#         if cancellation_details.reason == speechsdk.CancellationReason.Error:
#             print("Error details: {}".format(cancellation_details.error_details))


def pronunciation_assessment_from_stream(
    reference_text,
    audio_info: Dict[str, any],
    secrets: Dict[str, str],
    language="en-US",
):
    """Performs pronunciation assessment asynchronously with input from an audio stream.
    See more information at https://aka.ms/csspeech/pa"""

    # Creates an instance of a speech config with specified subscription key and service region.
    speech_config = speechsdk.SpeechConfig(
        subscription=secrets["Microsoft"]["SPEECH_KEY"],
        region=secrets["Microsoft"]["SPEECH_REGION"],
    )

    # Create a custom audio stream format
    format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=audio_info["sample_rate"],
        bits_per_sample=audio_info["sample_width"] * 8,  # Convert bytes to bits
        channels=1,  # Assuming mono audio
    )

    # Setup the audio stream
    stream = speechsdk.audio.PushAudioInputStream(format=format)
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    # Create pronunciation assessment config, set grading system, granularity and if enable miscue based on your requirement.
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=True,
    )
    pronunciation_config.enable_prosody_assessment()

    # Create a speech recognizer using a file as audio input.
    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config, language=language, audio_config=audio_config
    )
    # Apply pronunciation assessment config to speech recognizer
    pronunciation_config.apply_to(speech_recognizer)

    # Write the audio data to the stream
    stream.write(audio_info["bytes"])
    stream.close()

    result = speech_recognizer.recognize_once_async().get()

    # Check the result
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        print("pronunciation assessment for: {}".format(result.text))
        pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
        print(
            "    Accuracy score: {}, prosody score: {}, pronunciation score: {}, completeness score : {}, fluency score: {}".format(
                pronunciation_result.accuracy_score,
                pronunciation_result.prosody_score,
                pronunciation_result.pronunciation_score,
                pronunciation_result.completeness_score,
                pronunciation_result.fluency_score,
            )
        )
        print("  Word-level details:")
        for idx, word in enumerate(pronunciation_result.words):
            print(
                "    {}: word: {}\taccuracy score: {}\terror type: {};".format(
                    idx + 1, word.word, word.accuracy_score, word.error_type
                )
            )
    elif result.reason == speechsdk.ResultReason.NoMatch:
        print("No speech could be recognized")
    elif result.reason == speechsdk.ResultReason.Canceled:
        cancellation_details = result.cancellation_details
        print("Speech Recognition canceled: {}".format(cancellation_details.reason))
        if cancellation_details.reason == speechsdk.CancellationReason.Error:
            print("Error details: {}".format(cancellation_details.error_details))
