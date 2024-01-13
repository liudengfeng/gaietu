from typing import List, Any, Dict
import requests, uuid, json

endpoint = "https://api.cognitive.microsofttranslator.com"
version = "3.0"


def _ensure_body(input_):
    if isinstance(input_, str):
        return [{"text": input_}]
    elif isinstance(input_, list):
        is_all_str = all([isinstance(item, str) for item in input_])
        if is_all_str:
            return [{"text": item} for item in input_]
        is_all_dict = all(
            [isinstance(item, dict) and "text" in item for item in input_]
        )
        if is_all_dict:
            return [{"text": item["text"]} for item in input_]
    raise ValueError("Data in wrong format !")


def translate(
    body: Any, src: str, tgts: List[str], api_key: str, location: str
) -> List[Dict]:
    """
    The translate function is used to translate text from one language to multiple target languages using the Azure Translator API.

    body: Any: The body is a JSON array. Each array element is a JSON object with a string property named "Text", which represents the string to be translated.
    src: str: The source language of the text. -: List[str]`: A list of target languages to translate the text into.
    api_key: str: The API key for accessing the Azure Translator API.
    location: str: The location of the Azure Translator resource.

    Returns

    List[Dict]: A list of dictionaries representing the translated text. Each dictionary contains the translated text for a specific target language.

    >>> translation = translate("Hello, how are you?", "en", ["fr", "es"], "API_KEY", "LOCATION")

    >>> print(translation)

    Note:

    that you need to replace "API_KEY" and "LOCATION" with your actual API key and location.

    """
    # body 请求的正文是一个 JSON 数组。 每个数组元素都是一个 JSON 对象，具有一个名为 Text 的字符串属性，该属性表示要翻译的字符串。
    path = "/translate"
    constructed_url = endpoint + path
    params = {"api-version": version, "from": src, "to": tgts}
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        # location required if you're using a multi-service or regional (not global) resource.
        "Ocp-Apim-Subscription-Region": location,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    request = requests.post(
        constructed_url, params=params, headers=headers, json=_ensure_body(body)
    )
    response = request.json()
    # print(
    #     json.dumps(
    #         response,
    #         sort_keys=True,
    #         ensure_ascii=False,
    #         indent=4,
    #         separators=(",", ": "),
    #     )
    # )
    return response


def language_detect(body: Any, api_key: str, location: str) -> List[Dict]:
    # 检测源文本的语言，而不进行翻译
    path = "/detect"
    constructed_url = endpoint + path
    params = {"api-version": version}
    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        # location required if you're using a multi-service or regional (not global) resource.
        "Ocp-Apim-Subscription-Region": location,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }
    request = requests.post(
        constructed_url, params=params, headers=headers, json=_ensure_body(body)
    )
    response = request.json()
    return response


def dictionary_lookup(body: Any, src: str, tgt: str, api_key: str, location: str):
    """
    Looks up words or phrases in a dictionary for translations.

    Args:
        body (Any): The word or phrase to translate.
        src (str): The language code of the source text.
        tgt (str): The language code of the target text.
        api_key (str): The subscription key for the Azure service.
        location (str): The region of the Azure service.

    Returns:
        List[Dict]: A list of dictionaries containing the translations.
    """
    # https://learn.microsoft.com/zh-cn/azure/ai-services/translator/reference/v3-0-dictionary-lookup
    path = "/dictionary/lookup"
    constructed_url = endpoint + path
    params = {"api-version": version, "from": src, "to": tgt}

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        # location required if you're using a multi-service or regional (not global) resource.
        "Ocp-Apim-Subscription-Region": location,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }

    # You can pass more than one object in body.
    request = requests.post(
        constructed_url, params=params, headers=headers, json=_ensure_body(body)
    )
    response = request.json()
    return response


def dictionary_example(
    body: List[Dict], src: str, tgt: str, api_key: str, location: str
) -> List[Dict]:
    # Each object takes two key/value pairs: 'text' and 'translation'.
    path = "/dictionary/examples"
    constructed_url = endpoint + path

    params = {"api-version": version, "from": src, "to": tgt}

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        # location required if you're using a multi-service or regional (not global) resource.
        "Ocp-Apim-Subscription-Region": location,
        "Content-type": "application/json",
        "X-ClientTraceId": str(uuid.uuid4()),
    }

    # 字典查找响应中的 normalizedText 和 normalizedTarget 分别用作 text 和 translation。
    # You can pass more than one object in body.
    # body = [{"text": "sunlight", "translation": "luz solar"}]
    valid = all(["text" in item and "translation" in item for item in body])
    if not valid:
        raise ValueError(
            "`normalizedText` and `normalizedTarget` in dictionary lookup responses are used as 'text' and 'translation' respectively."
        )
    request = requests.post(constructed_url, params=params, headers=headers, json=body)
    response = request.json()
    return response
