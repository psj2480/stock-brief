# -*- coding: utf-8 -*-
"""
매일 아침 주식 브리핑을 카카오톡 '나에게 보내기'로 발송.
메시지 2개: (1) 시황 요약 텍스트  (2) 링크되는 뉴스 리스트
"""
 
import os
import json
import math
import datetime
import requests
 
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")
 
# 뉴스 카드 헤더/버튼이 가리킬 주소 (도메인 등록 필요: finance.naver.com)
NEWS_PAGE_URL = "https://finance.naver.com/news/mainnews.naver"
SISE_PAGE_URL = "https://finance.naver.com/sise/"
 
NEWS_COUNT = 5  # 뉴스 개수 (리스트 템플릿은 최대 5개)
NEWS_QUERY = "코스피 OR 증시 OR 반도체"
 
# 뉴스 항목에 표시할 아이콘 이미지 (카카오 공식 예제용 이미지)
ITEM_IMAGE = ("https://mud-kage.kakao.com/dn/Q2iNx/btqgeRgV54P/"
              "VLdBs9cvyn8BJXB3o7N8UK/kakaolink40_original.png")
 
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0 Safari/537.36"}
 
MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
 
 
def get_access_token():
    res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "refresh_token",
            "client_id": REST_API_KEY,
            "refresh_token": REFRESH_TOKEN,
        },
        timeout=10,
    )
    res.raise_for_status()
    token = res.json()
    if "refresh_token" in token:
        print("[알림] 새 refresh_token 발급됨. GitHub Secret을 아래 값으로 갱신하세요:")
        print(token["refresh_token"])
    return token["access_token"]
 
 
def fetch_market():
    import FinanceDataReader as fdr
 
    targets = [
        ("코스피", "KS11"),
        ("코스닥", "KQ11"),
        ("S&P", "US500"),
        ("나스닥", "IXIC"),
        ("환율", "USD/KRW"),
    ]
    start = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    lines = []
    for name, symbol in targets:
        try:
            df = fdr.DataReader(symbol, start).dropna(subset=["Close"])
            if len(df) < 2:
                continue
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])
            if prev == 0 or math.isnan(last) or math.isnan(prev):
                continue
            pct = (last - prev) / prev * 100
            sign = "▲" if pct > 0 else ("▼" if pct < 0 else "-")
            unit = "원" if name == "환율" else ""
            lines.append(f"{name} {last:,.0f}{unit} {sign}{abs(pct):.1f}%")
        except Exception as e:
            print(f"[경고] {name}({symbol}) 시황 수집 실패: {e}")
    return lines
 
 
def fetch_news():
    import feedparser
    import urllib.parse
 
    q = urllib.parse.quote(NEWS_QUERY)
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        res = requests.get(url, headers=UA, timeout=10)
        feed = feedparser.parse(res.content)
    except Exception as e:
        print(f"[경고] 뉴스 요청 실패: {e}")
        return []
 
    print(f"[정보] 뉴스 항목 수: {len(feed.entries)}")
    items = []
    for entry in feed.entries[:NEWS_COUNT]:
        title = entry.title
        source = ""
        if " - " in title:
            title, source = title.rsplit(" - ", 1)
        items.append({
            "title": title.strip(),
            "source": source.strip() or "뉴스",
            "link": entry.link,
        })
    return items
 
 
def build_market_text(lines):
    today = datetime.date.today()
    weekday = "월화수목금토일"[today.weekday()]
    text = f"📊 {today.month}/{today.day}({weekday}) 증시 브리핑\n"
    text += "\n".join(lines)
    return text
 
 
def send_text(token, text):
    template = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": SISE_PAGE_URL, "mobile_web_url": SISE_PAGE_URL},
        "button_title": "국내증시 보기",
    }
    _send(token, template)
    print("[성공] 시황 카드 발송 완료")
 
 
def send_news_list(token, items):
    contents = []
    for it in items:
        contents.append({
            "title": it["title"],
            "description": it["source"],
            "image_url": ITEM_IMAGE,
            "link": {"web_url": it["link"], "mobile_web_url": it["link"]},
        })
    template = {
        "object_type": "list",
        "header_title": "📰 오늘의 증시 뉴스",
        "header_link": {"web_url": NEWS_PAGE_URL, "mobile_web_url": NEWS_PAGE_URL},
        "contents": contents,
        "buttons": [{
            "title": "네이버 금융 뉴스",
            "link": {"web_url": NEWS_PAGE_URL, "mobile_web_url": NEWS_PAGE_URL},
        }],
    }
    _send(token, template)
    print("[성공] 뉴스 카드 발송 완료")
 
 
def _send(token, template):
    headers = {"Authorization": f"Bearer {token}"}
    data = {"template_object": json.dumps(template, ensure_ascii=False)}
    res = requests.post(MEMO_URL, headers=headers, data=data, timeout=10)
    if res.status_code != 200:
        print("[오류] 발송 실패:", res.text)
    res.raise_for_status()
 
 
def main():
    if not REST_API_KEY or not REFRESH_TOKEN:
        raise SystemExit("환경변수 KAKAO_REST_API_KEY, KAKAO_REFRESH_TOKEN 가 필요합니다.")
 
    token = get_access_token()
 
    try:
        lines = fetch_market()
    except Exception as e:
        print(f"[경고] 시황 수집 전체 실패: {e}")
        lines = []
    if lines:
        send_text(token, build_market_text(lines))
 
    try:
        items = fetch_news()
    except Exception as e:
        print(f"[경고] 뉴스 수집 실패: {e}")
        items = []
    # 리스트 템플릿은 항목이 2개 이상이어야 함
    if len(items) >= 2:
        send_news_list(token, items)
    elif len(items) == 1:
        send_text(token, "📰 오늘의 뉴스\n· " + items[0]["title"])
    else:
        print("[정보] 뉴스가 없어 뉴스 카드는 생략")
 
 
if __name__ == "__main__":
    main()
