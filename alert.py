# -*- coding: utf-8 -*-
"""
관심 종목 급등·급락 알림.
매시간 실행되며, 당일 등락률이 기준(±5%)을 넘은 종목만 카카오톡으로 발송.
조건을 넘는 종목이 없으면 아무 메시지도 보내지 않고 종료한다.
"""

import os
import json
import math
import datetime
import requests

REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")

# 알림 기준 등락률 (%). 이 값을 넘으면(±) 알림.
THRESHOLD = 5.0

# 감시할 종목 (표시이름, FDR 심볼)
#   - 국내: 6자리 종목코드
#   - 미국: 티커(CEG 등)
WATCHLIST = [
    ("대한항공", "003490"),
    ("한화오션", "042660"),
    ("태경비케이", "014580"),
    ("컨스텔레이션에너지", "CEG"),
]

MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
# 카드 버튼이 가리킬 주소 (도메인 등록됨: finance.naver.com)
LINK_URL = "https://finance.naver.com/sise/"


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


def check_watchlist():
    """기준을 넘은 종목만 (이름, 현재가, 등락률) 리스트로 반환."""
    import FinanceDataReader as fdr

    start = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    hits = []
    for name, symbol in WATCHLIST:
        try:
            df = fdr.DataReader(symbol, start).dropna(subset=["Close"])
            if len(df) < 2:
                continue
            last = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])
            if prev == 0 or math.isnan(last) or math.isnan(prev):
                continue
            pct = (last - prev) / prev * 100
            print(f"[정보] {name}: {last:,.2f} ({pct:+.2f}%)")
            if abs(pct) >= THRESHOLD:
                hits.append((name, last, pct))
        except Exception as e:
            print(f"[경고] {name}({symbol}) 조회 실패: {e}")
    return hits


def build_message(hits):
    now = datetime.datetime.now().strftime("%m/%d %H시")
    lines = [f"🚨 급등·급락 알림 ({now})"]
    for name, price, pct in hits:
        arrow = "🔺" if pct > 0 else "🔻"
        lines.append(f"{arrow} {name} {price:,.0f} ({pct:+.1f}%)")
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
    print("[성공] 알림 발송 완료")


def main():
    if not REST_API_KEY or not REFRESH_TOKEN:
        raise SystemExit("환경변수 KAKAO_REST_API_KEY, KAKAO_REFRESH_TOKEN 가 필요합니다.")

    hits = check_watchlist()
    if not hits:
        print("[정보] 기준을 넘은 종목 없음 → 알림 생략")
        return

    token = get_access_token()
    send_kakao(token, build_message(hits))


if __name__ == "__main__":
    main()
