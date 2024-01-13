"""
下载解析 EnglishProfile the CEFR for English 单词细节部分
参考网址： http://www.englishprofile.org/american-english/words/usdetail/6604
"""
import json
import os
import re

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

COLUMNS = ["Base Word", "Guideword", "Level", "Part of Speech", "Topic", "Details"]
BASE_URL = "http://www.englishprofile.org"
COL_NUM = 6


def _parse_pos_header(div):
    headword = div.find("span", class_="headword")
    pos = div.find("span", class_="pos")
    written = div.find("span", class_="written")
    return {
        "headword": headword.get_text(strip=True) if headword else "",
        "pos": pos.get_text(strip=True) if pos else "",
        "written": written.get_text(strip=True) if written else "",
    }


def _parse_examples(example):
    if example:
        return [p.text for p in example.find_all("p", class_="blockquote")]
    return ""


def _parse_info_body(body):
    label = body.find("span", class_=re.compile("label label-"))
    grammar = body.find("span", class_="grammar")
    definition = body.find("span", class_="definition")
    example = body.find("div", class_=re.compile("example not_in_summary"))
    learner = body.find("div", class_=re.compile("learner not_in_summary"))
    return {
        "label": label.get_text(strip=True) if label else "",
        "grammar": grammar.get_text(strip=True) if grammar else "",
        "definition": definition.get_text(strip=True) if definition else "",
        "Dictionary example": _parse_examples(example),
        "Learner example": _parse_examples(learner),
    }


def _parse_info_sense(sense):
    title = sense.find("div", class_=re.compile("sense_title"))
    body = sense.find("div", class_="info body")
    return {"title": title.get_text(strip=True), "body": _parse_info_body(body)}


def _parse_section(section):
    res = []
    header = section.find("div", class_="pos_header")
    senses = section.find_all("div", class_="info sense")
    res.append(_parse_pos_header(header))
    for sense in senses:
        res.append(_parse_info_sense(sense))
    return res


def get_detail(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "lxml")
    sections = soup.find_all("div", class_="pos_section")
    res = []
    for section in sections:
        res.append(_parse_section(section))
    return res


def parse_wordlists_page(url):
    table = []
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "lxml")
    tds = soup.find_all("td", attrs={"style": "white-space:normal"})
    row = []
    for idx in range(len(tds)):
        if (idx + 1) % COL_NUM == 0:
            row.append(BASE_URL + tds[idx].find("a")["href"])
            table.append(row)
            row = []
        else:
            row.append(tds[idx].get_text(strip=True))
    return pd.DataFrame.from_records(table, columns=COLUMNS)


def get_american_english_wordlists():
    start = 0
    end = 15380
    sub_dir = "us"
    for start in tqdm(range(0, end + 1, 20)):
        fn = "html_data/{}/df_{}.json".format(sub_dir, str(start).zfill(5))
        if os.path.exists(fn):
            continue
        if start == 0:
            url = BASE_URL + "/american-english"
        else:
            url = BASE_URL + f"/american-english?start={start}"
        df = parse_wordlists_page(url)
        df.to_json(fn)


def get_british_english_wordlists():
    start = 0
    end = 15680
    sub_dir = "uk"
    for start in tqdm(range(0, end + 1, 20)):
        fn = "html_data/{}/df_{}.json".format(sub_dir, str(start).zfill(5))
        if os.path.exists(fn):
            continue
        if start == 0:
            url = BASE_URL + "/wordlists/evp?limitstart=0"
        else:
            url = BASE_URL + f"/wordlists/evp?start={start}"
        df = parse_wordlists_page(url)
        df.to_json(fn)


def get_full_wordlists(name):
    """合并临时下载数据"""
    base_dir = "/home/ldf/github/EngAimm/temps/html_data/"
    data_dir = base_dir + name
    fps = [os.path.join(data_dir, fn) for fn in os.listdir(data_dir)]
    dfs = [pd.read_json(fp) for fp in fps]
    df = pd.concat(dfs, ignore_index=True)
    fn = f"{name}_wordlists.json"
    fp = base_dir + fn
    df.to_json(fp)

    data = {}
    urls = df.Details.unique()
    n = len(urls)
    detail_path = base_dir + f"{name}_wordlists_detail.json"
    for i in tqdm(range(n)):
        url = urls[i]
        data[url] = get_detail(url)
        if i % 50 == 0:
            with open(detail_path, "w", encoding="utf-8") as f:
                json.dump(
                    data,
                    f,
                    ensure_ascii=False,
                )


if __name__ == "__main__":
    # cd /home/ldf/github/EngAimm/temps/
    # python englishprofile.py
    # get_american_english_wordlists()
    # get_british_english_wordlists()
    get_full_wordlists("us")
    get_full_wordlists("uk")
