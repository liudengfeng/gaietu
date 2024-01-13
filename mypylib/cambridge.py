import requests
from bs4 import BeautifulSoup


headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "DNT": "1",
    "Host": "dictionary.cambridge.org",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "sec-ch-ua": '"Not A(Brand";v="99", "Microsoft Edge";v="121", "Chromium";v="121"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}


def parse_block(block):
    pos = block.find("span", class_="pos dpos")
    result = []
    senses = block.find_all("div", class_="def-block")
    for sense in senses:
        definition = sense.find("div", class_="def").text.strip()
        examples = []
        for exam in sense.find_all("span", class_="eg deg"):
            examples.append(exam.text.strip())
        result.append({"definition": definition, "examples": examples})
    return {pos.text: result}


def _get_word_info(word):
    url = f"https://dictionary.cambridge.org/dictionary/english/{word}"
    res = requests.get(url, headers=headers)
    # res = requests.get(url, timeout=10)
    soup = BeautifulSoup(res.text, "lxml")
    # 二个字典，第一个是通用字典，第二个是美式字典
    dictionary = soup.find("div", class_="pr dictionary")
    # 找到音标
    pronunciations = dictionary.find_all("span", class_="ipa")  # type: ignore
    uk_pron = pronunciations[0].text if pronunciations else None
    us_pron = pronunciations[1].text if len(pronunciations) > 1 else None
    result = {"uk_written": uk_pron, "us_written": us_pron}
    # 找到词性、释义和例句
    blocks = dictionary.find_all("div", class_="pr entry-body__el")  # type: ignore
    for block in blocks:
        result.update(parse_block(block))
    return result


def get_word_info(word):
    """
    Get information about a word from the Cambridge Dictionary.

    Args:
        word (str): The word to look up.

    Returns:
        dict: A dictionary containing the word's information, including pronunciation, parts of speech, definitions, and example sentences.
    """
    try:
        return _get_word_info(word)
    except AttributeError as e:
        # 单词没有列入剑桥字典
        return {}
    except Exception as e:
        print(e)
        return {}
