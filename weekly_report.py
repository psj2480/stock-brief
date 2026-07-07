# -*- coding: utf-8 -*-
"""
주간 리포트 (금요일 저녁 발송).
관심 종목의 이번 주 등락(월요일 대비 금요일)과 지수 흐름을 카카오톡으로 정리.
"""

import os
import json
import math
import datetime

import requests

REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")

WATCHLIST = [
    ("대한항공", "003490"),
    ("한화오션", "042660"),
    ("태경비케이", "014580"),
    ("컨스텔레이션에너지", "CEG"),
]
INDICES = [("코스피", "KS11"), ("코스닥", "KQ11")]

MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
LINK_URL = "https://finance.naver.com/sise/"


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


def weekly_change(symbol):
    """이번 주 첫 거래일 대비 마지막 거래일 등락률(%)과 현재가."""
    import FinanceDataReader as fdr
    today = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())  # 이번 주 월요일
    df = fdr.DataReader(symbol, monday.isoformat()).dropna(subset=["Close"])
    if len(df) < 2:
        return None, None
    first = float(df["Close"].iloc[0])
    last = float(df["Close"].iloc[-1])
    if first == 0 or math.isnan(first) or math.isnan(last):
        return last, None
    return last, (last - first) / first * 100


def fmt_line(name, last, pct):
    if last is None:
        return f"{name} -"
    sign = "▲" if (pct or 0) > 0 else ("▼" if (pct or 0) < 0 else "-")
    pct_str = f"{sign}{abs(pct):.1f}%" if pct is not None else ""
    return f"{name} {last:,.0f} {pct_str}"


def build_message():
    today = datetime.date.today()
    lines = [f"📅 주간 리포트 ({today.month}/{today.day} 마감 기준)", "", "[지수]"]
    for name, sym in INDICES:
        try:
            last, pct = weekly_change(sym)
            lines.append("· " + fmt_line(name, last, pct))
        except Exception as e:
            print(f"[경고] {name} 실패: {e}")
    lines.append("")
    lines.append("[관심 종목 · 이번 주]")
    for name, sym in WATCHLIST:
        try:
            last, pct = weekly_change(sym)
            lines.append("· " + fmt_line(name, last, pct))
        except Exception as e:
            print(f"[경고] {name} 실패: {e}")
    lines.append("")
    lines.append("※ 사실 정리용 참고 자료이며 투자 판단·책임은 본인에게 있습니다.")
    return "\n".join(lines)


def send_kakao(token, text):
    template = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": LINK_URL, "mobile_web_url": LINK_URL},
        "button_title": "시세 확인",
    }
    headers = {"Authorization": f"Bearer {token}"}
    data = {"template_object": json.dumps(template, ensure_ascii=False)}
    res = requests.post(MEMO_URL, headers=headers, data=data, timeout=10)
    if res.status_code != 200:
        print("[오류] 발송 실패:", res.text)
    res.raise_for_status()
    print("[성공] 주간 리포트 발송 완료")


def main():
    if not REST_API_KEY or not REFRESH_TOKEN:
        raise SystemExit("환경변수 KAKAO_REST_API_KEY, KAKAO_REFRESH_TOKEN 가 필요합니다.")
    text = build_message()
    print(text)
    token = get_access_token()
    send_kakao(token, text)


if __name__ == "__main__":
    main()
