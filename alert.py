# -*- coding: utf-8 -*-
"""
관심 종목 급등·급락 알림 (하루 1회 중복 방지).
매시간 실행되며, 당일 등락률이 기준(±5%)을 넘은 종목만 카카오톡으로 발송.
단, 같은 날 이미 알린 종목은 다시 보내지 않는다.
'오늘 알린 종목' 기록은 alert_state.json 파일에 저장한다.
"""

import os
import json
import math
import datetime

import requests

REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
REFRESH_TOKEN = os.environ.get("KAKAO_REFRESH_TOKEN", "")

THRESHOLD = 5.0  # 알림 기준 등락률(%)

WATCHLIST = [
    ("대한항공", "003490"),
    ("한화오션", "042660"),
    ("태경비케이", "014580"),
    ("컨스텔레이션에너지", "CEG"),
]

MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
LINK_URL = "https://finance.naver.com/sise/"
STATE_FILE = "alert_state.json"  # 오늘 이미 알린 종목 기록


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


def load_state():
    """오늘 날짜에 이미 알린 종목 집합을 반환."""
    today = datetime.date.today().isoformat()
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == today:
            return set(data.get("alerted", []))
    except Exception:
        pass
    return set()  # 파일이 없거나 날짜가 바뀌면 새로 시작


def save_state(alerted):
    today = datetime.date.today().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"date": today, "alerted": sorted(alerted)},
                  f, ensure_ascii=False, indent=2)


def check_watchlist(already):
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
            if abs(pct) >= THRESHOLD and name not in already:
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

    already = load_state()
    hits = check_watchlist(already)

    if not hits:
        print("[정보] 새로 알릴 종목 없음 → 발송 생략")
        # 날짜만 갱신되도록 상태 저장(파일이 없으면 생성)
        save_state(already)
        return

    token = get_access_token()
    send_kakao(token, build_message(hits))

    # 방금 알린 종목을 기록에 추가
    already.update(name for name, _, _ in hits)
    save_state(already)
    print(f"[정보] 오늘 알린 종목: {sorted(already)}")


if __name__ == "__main__":
    main()
