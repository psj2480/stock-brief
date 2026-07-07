# -*- coding: utf-8 -*-
"""
장 전환 브리핑 (사실 정리, AI 없음)
  - morning : 국내장 개장 전 → 간밤 미국장 마감 + 환율 + 미국 뉴스
  - evening : 국내장 마감 후 → 오늘 국내장 마감 + 오늘 밤 미국장 참고 뉴스
실행 시 인자로 morning / evening 을 받는다.  예) python session_brief.py morning
"""

import os
import sys
import json
import math
import datetime
import requests

REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")

MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
SISE_URL = "https://finance.naver.com/sise/"
NEWS_PAGE_URL = "https://finance.naver.com/news/mainnews.naver"
NEWS_COUNT = 5

ITEM_IMAGE = ("https://mud-kage.kakao.com/dn/Q2iNx/btqgeRgV54P/"
              "VLdBs9cvyn8BJXB3o7N8UK/kakaolink40_original.png")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"}

# 세션별 설정: (시황 대상, 뉴스 검색어, 헤더 문구)
SESSIONS = {
    "morning": {
        "targets": [("S&P", "US500"), ("나스닥", "IXIC"), ("다우", "DJI"),
                    ("환율", "USD/KRW")],
        "query": "미국증시 OR 나스닥 OR 반도체",
        "title": "🌅 개장 전 브리핑 · 간밤 미국장",
        "news_title": "📰 오늘 국내장 참고 뉴스",
    },
    "evening": {
        "targets": [("코스피", "KS11"), ("코스닥", "KQ11"), ("환율", "USD/KRW")],
        "query": "코스피 마감 OR 미국증시 전망 OR 반도체",
        "title": "🌆 마감 후 브리핑 · 오늘 국내장",
        "news_title": "📰 오늘 밤 미국장 참고 뉴스",
    },
}


def get_access_token():
    res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={"grant_type": "refresh_token", "client_id": REST_API_KEY,
              "refresh_token": REFRESH_TOKEN},
        timeout=10,
    )
    res.raise_for_status()
    token = res.json()
    if "refresh_token" in token:
        print("[알림] 새 refresh_token 발급됨. GitHub Secret을 갱신하세요:")
        print(token["refresh_token"])
    return token["access_token"]


def fetch_market(targets):
    import FinanceDataReader as fdr
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
            print(f"[경고] {name}({symbol}) 실패: {e}")
    return lines


def fetch_news(query):
    import feedparser
    import urllib.parse
    q = urllib.parse.quote(query)
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
        items.append({"title": title.strip(),
                      "source": source.strip() or "뉴스", "link": entry.link})
    return items


def send_text(token, text):
    _send(token, {"object_type": "text", "text": text,
                  "link": {"web_url": SISE_URL, "mobile_web_url": SISE_URL},
                  "button_title": "국내증시 보기"})
    print("[성공] 시황 카드 발송")


def send_news_list(token, items):
    contents = [{
        "title": it["title"], "description": it["source"],
        "image_url": ITEM_IMAGE,
        "link": {"web_url": it["link"], "mobile_web_url": it["link"]},
    } for it in items]
    _send(token, {
        "object_type": "list",
        "header_title": "오늘의 참고 뉴스",
        "header_link": {"web_url": NEWS_PAGE_URL, "mobile_web_url": NEWS_PAGE_URL},
        "contents": contents,
        "buttons": [{"title": "네이버 금융 뉴스",
                     "link": {"web_url": NEWS_PAGE_URL, "mobile_web_url": NEWS_PAGE_URL}}],
    })
    print("[성공] 뉴스 카드 발송")


def _send(token, template):
    headers = {"Authorization": f"Bearer {token}"}
    data = {"template_object": json.dumps(template, ensure_ascii=False)}
    res = requests.post(MEMO_URL, headers=headers, data=data, timeout=10)
    if res.status_code != 200:
        print("[오류] 발송 실패:", res.text)
    res.raise_for_status()


def build_text(cfg, lines):
    today = datetime.date.today()
    weekday = "월화수목금토일"[today.weekday()]
    text = f"{cfg['title']} ({today.month}/{today.day} {weekday})\n"
    text += "\n".join(lines) if lines else "(시황 데이터 없음)"
    text += "\n\n※ 사실 정리용 참고 자료이며 투자 판단·책임은 본인에게 있습니다."
    return text


def main():
    session = sys.argv[1] if len(sys.argv) > 1 else "morning"
    cfg = SESSIONS.get(session)
    if cfg is None:
        raise SystemExit("인자는 morning 또는 evening 이어야 합니다.")
    if not REST_API_KEY or not REFRESH_TOKEN:
        raise SystemExit("환경변수 KAKAO_REST_API_KEY, KAKAO_REFRESH_TOKEN 가 필요합니다.")

    token = get_access_token()

    lines = fetch_market(cfg["targets"])
    send_text(token, build_text(cfg, lines))

    items = fetch_news(cfg["query"])
    if len(items) >= 2:
        send_news_list(token, items)
    else:
        print("[정보] 뉴스 부족 → 뉴스 카드 생략")


if __name__ == "__main__":
    main()
