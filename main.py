# -*- coding: utf-8 -*-
"""
매일 아침 주식 모닝 브리핑을 카카오톡 '나에게 보내기'로 발송하는 스크립트.
"""
 
import os
import json
import math
import datetime
import requests
 
REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")
 
NEWS_PAGE_URL = "https://finance.naver.com/news/mainnews.naver"
MAX_LEN = 195
NEWS_COUNT = 3
# 관심 키워드 (원하는 대로 바꾸세요: "반도체 OR HBM", "조선 OR 방산" 등)
NEWS_QUERY = "코스피 OR 증시 OR 반도체"
 
# 서버에서 차단당하지 않도록 브라우저인 척하는 헤더
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0 Safari/537.36"}
 
 
def get_access_token():
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": REFRESH_TOKEN,
    }
    res = requests.post(url, data=data, timeout=10)
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
            df = fdr.DataReader(symbol, start)
            # 빈 값(NaN) 행 제거 → -nan% 방지
            df = df.dropna(subset=["Close"])
            if len(df) < 2:
                continue
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])
            if prev == 0 or math.isnan(last) or math.isnan(prev):
                continue
            pct = (last - prev) / prev * 100
            sign = "▲" if pct > 0 else ("▼" if pct < 0 else "-")
            if name == "환율":
                lines.append(f"{name} {last:,.0f}원 {sign}{abs(pct):.1f}%")
            else:
                lines.append(f"{name} {last:,.0f} {sign}{abs(pct):.1f}%")
        except Exception as e:
            print(f"[경고] {name}({symbol}) 시황 수집 실패: {e}")
            continue
    return lines
 
 
def fetch_news():
    import feedparser
    import urllib.parse
 
    q = urllib.parse.quote(NEWS_QUERY)
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        # feedparser 에 바로 맡기지 않고, User-Agent 를 붙여 직접 받아온 뒤 넘긴다
        res = requests.get(url, headers=UA, timeout=10)
        feed = feedparser.parse(res.content)
    except Exception as e:
        print(f"[경고] 뉴스 요청 실패: {e}")
        return []
 
    print(f"[정보] 뉴스 항목 수: {len(feed.entries)}")
    titles = []
    for entry in feed.entries[:NEWS_COUNT]:
        title = entry.title
        if " - " in title:
            title = title.rsplit(" - ", 1)[0]
        titles.append(title.strip())
    return titles
 
 
def build_message(market_lines, news_titles):
    today = datetime.date.today()
    weekday = "월화수목금토일"[today.weekday()]
    body = f"📊 {today.month}/{today.day}({weekday}) 증시 브리핑"
 
    for i in range(0, len(market_lines), 2):
        chunk = " / ".join(market_lines[i:i + 2])
        candidate = body + "\n" + chunk
        if len(candidate) <= MAX_LEN:
            body = candidate
 
    if news_titles:
        candidate = body + "\n📰 오늘의 뉴스"
        if len(candidate) <= MAX_LEN:
            body = candidate
        for t in news_titles:
            short = t if len(t) <= 22 else t[:21] + "…"
            candidate = body + "\n· " + short
            if len(candidate) <= MAX_LEN:
                body = candidate
            else:
                break
    return body
 
 
def send_kakao(access_token, text):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {"Authorization": f"Bearer {access_token}"}
    template = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": NEWS_PAGE_URL, "mobile_web_url": NEWS_PAGE_URL},
        "button_title": "전체 뉴스 보기",
    }
    data = {"template_object": json.dumps(template, ensure_ascii=False)}
    res = requests.post(url, headers=headers, data=data, timeout=10)
    res.raise_for_status()
    print("[성공] 카카오톡 발송 완료")
 
 
def main():
    if not REST_API_KEY or not REFRESH_TOKEN:
        raise SystemExit("환경변수 KAKAO_REST_API_KEY, KAKAO_REFRESH_TOKEN 가 필요합니다.")
 
    access_token = get_access_token()
 
    try:
        market_lines = fetch_market()
    except Exception as e:
        print(f"[경고] 시황 수집 전체 실패: {e}")
        market_lines = []
 
    try:
        news_titles = fetch_news()
    except Exception as e:
        print(f"[경고] 뉴스 수집 실패: {e}")
        news_titles = []
 
    message = build_message(market_lines, news_titles)
    print("---- 보낼 메시지 (%d자) ----" % len(message))
    print(message)
    print("---------------------------")
 
    send_kakao(access_token, message)
 
 
if __name__ == "__main__":
    main()
