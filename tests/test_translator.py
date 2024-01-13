import pytest

from mypylib import utils
from mypylib.azure_translator import (
    _ensure_body,
    translate,
    language_detect,
    dictionary_lookup,
    dictionary_example,
)


def test_ensure_body():
    with pytest.raises(ValueError) as e:
        _ensure_body([{"info": "other"}])
        _ensure_body([("info", "other")])


@pytest.mark.parametrize(
    "test_input,src,tgts,expected",
    [
        ("可接受的格式", "zh-Hans", ["en"], "Acceptable format"),
        ("Formato aceptable", "es", ["zh-Hans"], "可接受的格式"),
        ("受け入れ可能な形式", "ja", ["en"], "Acceptable formats"),
    ],
)
def test_translate(test_input, src, tgts, expected):
    secret = utils.get_secrets()["Microsoft"]
    response = translate(
        test_input,
        src,
        tgts,
        secret["TRANSLATOR_TEXT_SUBSCRIPTION_KEY"],
        secret["TRANSLATOR_TEXT_REGION"],
    )
    x = ""
    x.capitalize()
    actual = [x.capitalize() for x in response[0]["translations"][0]["text"].split(" ")]
    expected = [x.capitalize() for x in expected.split(" ")]
    assert actual == expected


@pytest.mark.parametrize(
    "test_input,expected",
    [("可接受的格式", "zh-Hans"), ("Formato aceptable", "es"), ("受け入れ可能な形式", "ja")],
)
def test_language_detect(test_input, expected):
    secret = utils.get_secrets()["Microsoft"]
    response = language_detect(
        test_input,
        secret["TRANSLATOR_TEXT_SUBSCRIPTION_KEY"],
        secret["TRANSLATOR_TEXT_REGION"],
    )
    assert response[0]["language"] == expected


@pytest.mark.parametrize(
    "test_input,src,tgt,expected,normalizedSource",
    [
        ("work", "en", "zh-Hans", ["NOUN", "VERB"], "work"),
        ("make-up", "en", "zh-Hans", ["NOUN"], "makeup"),
    ],
)
def test_dictionary_lookup(test_input, src, tgt, expected, normalizedSource):
    secret = utils.get_secrets()["Microsoft"]
    response = dictionary_lookup(
        test_input,
        src,
        tgt,
        secret["TRANSLATOR_TEXT_SUBSCRIPTION_KEY"],
        secret["TRANSLATOR_TEXT_REGION"],
    )

    assert response[0]["normalizedSource"] == normalizedSource

    actual = []
    for t in response[0]["translations"]:
        if t["confidence"] >= 0.1:
            actual.append(t["posTag"])
    assert len(set(expected).difference(actual)) == 0


@pytest.mark.parametrize(
    "normalizedText,normalizedTarget,src,tgt,min_num",
    [
        ("work", "工作", "en", "zh-Hans", 10),
    ],
)
def test_dictionary_example(normalizedText, normalizedTarget, src, tgt, min_num):
    secret = utils.get_secrets()["Microsoft"]
    body = [{"text": normalizedText, "translation": normalizedTarget}]
    response = dictionary_example(
        body,
        src,
        tgt,
        secret["TRANSLATOR_TEXT_SUBSCRIPTION_KEY"],
        secret["TRANSLATOR_TEXT_REGION"],
    )
    assert len(response[0]["examples"]) >= min_num
