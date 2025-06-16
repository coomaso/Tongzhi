
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

def generate_textrank_summary(text, sentence_count=3):
    sentences = re.split(r"[。！？!?]", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    processed_text = "。".join(sentences)
    parser = PlaintextParser.from_string(processed_text, Tokenizer("chinese"))
    summarizer = TextRankSummarizer()
    summary = summarizer(parser.document, sentence_count)
    return "\n".join(str(sentence) for sentence in summary)

def safe_filename(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name)

def fetch_news_list():
    url = "https://www.hbjzxh.org.cn/ajax/ajaxLoadModuleDom_h.jsp"
    data = {
        "cmd": "getWafNotCk_getAjaxPageModuleInfo",
        "_colId": "125",
        "_extId": "0",
        "moduleId": "1172",
        "href": "/col.jsp?m1172pageno=1&id=125",
        "newNextPage": "false",
        "needIncToVue": "false"
    }
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.post(url, data=data, headers=headers)
    response.raise_for_status()

    match = re.search(r'"domStr"\s*:\s*"(.*?)"\s*,\s*"scripts"', response.text)
    if not match:
        raise ValueError("未找到 domStr 字段")
    json_str = '{' + match.group(0) + '}'
    parsed_json = json.loads(json_str)
    html_encoded = parsed_json["domStr"]

    soup = BeautifulSoup(html_encoded, "html.parser")
    base_url = "https://www.hbjzxh.org.cn"
    results = []

    for item in soup.select("div.m_news_info"):
        a_tag = item.select_one("a.article_title")
        date_span = item.select_one("span.normal_time")
        if a_tag and date_span:
            title = a_tag.get("title", "").strip()
            href = base_url + a_tag.get("href", "").strip()
            date = date_span.get_text(strip=True)
            results.append((title, href, date))
    return results

def process_article(title, url, date):
    print(f"[处理中] 正在处理：《{title}》")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://www.hbjzxh.org.cn/",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }

    resp = requests.get(url, headers=headers)
    if resp.status_code == 403:
        print(f"[错误] 403 Forbidden：{url}")
        return
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    content_div = soup.select_one("div.richContent.richContent0")
    if not content_div:
        print("[警告] 未找到正文内容")
        return
    full_text = content_div.get_text(separator="\n", strip=True)
    if not full_text:
        print("[警告] 正文为空")
        return

    summary = generate_textrank_summary(full_text, sentence_count=3)

    attachments = []
    attach_div = soup.select_one("div.attachBox")
    if attach_div:
        for a in attach_div.select("a.attachName"):
            name = a.get_text(strip=True)
            href = a["href"]
            if href.startswith("//"):
                href = "https:" + href
            filename = safe_filename(name)
            file_path = os.path.join("attachments", filename)
            try:
                with requests.get(href, stream=True) as r:
                    with open(file_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                attachments.append((name, file_path))
            except Exception as e:
                print(f"[错误] 附件下载失败：{name} - {e}")

    msg = f"## {title}\n\n"           f"[发布时间] {date}\n\n"           f"---\n\n"           f"[摘要]\n{summary}\n\n"

    if attachments:
        msg += "\n[附件列表]\n"
        for name, path in attachments:
            msg += f"- [{name}]({path})\n"

    safe_title = safe_filename(title)
    md_path = os.path.join("通知输出", f"{safe_title}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(msg)

    print(f"[完成] 《{title}》 处理完毕")

if __name__ == "__main__":
    os.makedirs("attachments", exist_ok=True)
    os.makedirs("通知输出", exist_ok=True)
    news_list = fetch_news_list()
    for title, url, date in news_list:
        try:
            process_article(title, url, date)
        except Exception as e:
            print(f"[错误] 《{title}》 - {e}")
