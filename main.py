# -*- coding: utf-8 -*-
"""
매일 아침 주식 모닝 브리핑을 카카오톡 '나에게 보내기'로 발송하는 스크립트.

동작 순서
  1) refresh_token 으로 access_token 새로 발급 (access_token 은 몇 시간이면 만료됨)
  2) 국내/미국 지수 + 환율 시황 수집 (FinanceDataReader)
  3) 주식 관련 뉴스 헤드라인 수집 (Google News RSS)
  4) 200자 이내 텍스트 메시지로 조립
  5) 카카오톡 '나에게 보내기' API로 발송

필요한 환경변수 (GitHub Secrets 로 주입)
  - KAKAO_REST_API_KEY   : 카카오 개발자 앱의 REST API 키
  - KAKAO_REFRESH_TOKEN  : get_token.py 로 1회 발급받은 refresh token
"""

import os
import json
import datetime
import requests

# --- 설정값 -----------------------------------------------------------------

REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")

# 버튼을 눌렀을 때 이동할 곳 (네이버 금융 뉴스 전체 목록)
NEWS_PAGE_URL = "https://finance.naver.com/news/mainnews.naver"

# 카톡 텍스트 템플릿은 최대 200자. 안전하게 195자로 자름.
MAX_LEN = 195

# 뉴스 헤드라인 개수
NEWS_COUNT = 3

# 관심 키워드로 뉴스 검색 (원하는 대로 바꾸세요: "반도체", "조선", "방산" 등)
NEWS_QUERY = "코스피 OR 증시 OR 반도체"


# --- 1) 토큰 갱신 ------------------------------------------------------------

def get_access_token():
    """refresh_token 으로 새 access_token 을 발급받는다."""
    url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": REST_API_KEY,
        "refresh_token": REFRESH_TOKEN,
    }
    res = requests.post(url, data=data, timeout=10)
    res.raise_for_status()
    token = res.json()
    # 응답에 refresh_token 이 새로 포함되면(만료 임박 시) 로그로 남겨둔다.
    if "refresh_token" in token:
        print("[알림] 새 refresh_token 이 발급되었습니다. "
              "GitHub Secret 을 아래 값으로 갱신하면 만료 없이 계속 쓸 수 있습니다:")
        print(token["refresh_token"])
    return token["access_token"]


# --- 2) 시황 수집 ------------------------------------------------------------

def fetch_market():
    """지수/환율의 최근 종가와 등락률을 문자열 리스트로 반환. 실패 항목은 건너뛴다."""
    import FinanceDataReader as fdr

    # (표시이름, FDR 심볼)
    targets = [
        ("코스피", "KS11"),
        ("코스닥", "KQ11"),
        ("S&P", "US500"),
        ("나스닥", "IXIC"),
        ("환율", "USD/KRW"),
    ]
    start = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    lines = []
    for name, symbol in targets:
        try:
            df = fdr.DataReader(symbol, start)
            if len(df) < 2:
                continue
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])
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


# --- 3) 뉴스 수집 ------------------------------------------------------------

def fetch_news():
    """Google News RSS 에서 헤드라인 제목을 가져온다."""
    import feedparser
    import urllib.parse

    q = urllib.parse.quote(NEWS_QUERY)
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    titles = []
    for entry in feed.entries[:NEWS_COUNT]:
        title = entry.title
        # 구글 뉴스는 제목 끝에 " - 언론사명"을 붙이므로 제거
        if " - " in title:
            title = title.rsplit(" - ", 1)[0]
        titles.append(title.strip())
    return titles


# --- 4) 메시지 조립 ----------------------------------------------------------

def build_message(market_lines, news_titles):
    today = datetime.date.today()
    weekday = "월화수목금토일"[today.weekday()]
    header = f"📊 {today.month}/{today.day}({weekday}) 증시 브리핑"

    body = header
    # 시황: 두 개씩 한 줄에 붙여서 공간 절약
    for i in range(0, len(market_lines), 2):
        chunk = " / ".join(market_lines[i:i + 2])
        candidate = body + "\n" + chunk
        if len(candidate) <= MAX_LEN:
            body = candidate

    # 뉴스 헤드라인: 남는 공간만큼만 추가 (한 줄당 길면 잘라냄)
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


# --- 5) 카톡 발송 ------------------------------------------------------------

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


# --- 실행 --------------------------------------------------------------------

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
