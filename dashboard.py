# -*- coding: utf-8 -*-
"""
주식 상세 대시보드 (카톡 요약과 짝이 되는 상세 화면).
Streamlit Community Cloud 에 올려서 웹 주소로 접속해 사용한다.
로컬 실행:  streamlit run dashboard.py
"""
 
import datetime
import urllib.parse
import feedparser
import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import FinanceDataReader as fdr
 
st.set_page_config(page_title="주식 브리핑 대시보드", page_icon="📈", layout="wide")
 
# ---- 설정 ------------------------------------------------------------------
 
WATCHLIST = [
    ("대한항공", "003490"),
    ("한화오션", "042660"),
    ("태경비케이", "014580"),
    ("컨스텔레이션에너지", "CEG"),
]
 
MAJORS = [
    ("삼성전자", "005930"), ("SK하이닉스", "000660"), ("LG에너지솔루션", "373220"),
    ("삼성바이오로직스", "207940"), ("현대차", "005380"), ("기아", "000270"),
    ("셀트리온", "068270"), ("NAVER", "035420"), ("카카오", "035720"),
    ("POSCO홀딩스", "005490"), ("LG화학", "051910"), ("한화에어로스페이스", "012450"),
    ("HD현대중공업", "329180"), ("두산에너빌리티", "034020"), ("삼성SDI", "006400"),
]
 
INDICES = [
    ("코스피", "KS11"), ("코스닥", "KQ11"),
    ("S&P500", "US500"), ("나스닥", "IXIC"), ("원/달러", "USD/KRW"),
]
 
NEWS_QUERY = "코스피 OR 증시 OR 반도체"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"}
 
 
# ---- 데이터 함수 (캐시로 속도 확보) -----------------------------------------
 
@st.cache_data(ttl=600)
def load_history(symbol, days=120):
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    df = fdr.DataReader(symbol, start).dropna(subset=["Close"])
    return df
 
 
def last_and_change(df):
    if df is None or len(df) < 2:
        return None, None
    last = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2])
    if prev == 0:
        return last, None
    return last, (last - prev) / prev * 100
 
 
@st.cache_data(ttl=600)
def search_news(query, count=15):
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
    res = requests.get(url, headers=UA, timeout=10)
    feed = feedparser.parse(res.content)
    items = []
    for e in feed.entries[:count]:
        title, source = e.title, ""
        if " - " in title:
            title, source = title.rsplit(" - ", 1)
        items.append({"title": title.strip(), "source": source.strip(), "link": e.link})
    return items
 
 
def trend_sentence(df, days=5):
    """최근 며칠 흐름을 한 문장으로 요약 (뉴스가 없을 때 안내용)."""
    if df is None or len(df) < 2:
        return "최근 데이터가 충분하지 않습니다."
    window = df["Close"].tail(min(days, len(df)))
    first, last = float(window.iloc[0]), float(window.iloc[-1])
    if first == 0:
        return "최근 흐름을 계산할 수 없습니다."
    change = (last - first) / first * 100
    n = len(window)
    if change > 1:
        shape = f"최근 {n}거래일간 완만한 상승세"
    elif change < -1:
        shape = f"최근 {n}거래일간 완만한 하락세"
    else:
        shape = f"최근 {n}거래일간 큰 변동 없이 보합권"
    return (f"특별히 눈에 띄는 관련 뉴스는 찾지 못했습니다. "
            f"{shape}({change:+.1f}%)를 보이고 있습니다.")
 
 
# ---- 화면 -------------------------------------------------------------------
 
st.title("📈 주식 브리핑 대시보드")
st.caption(f"업데이트: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  ·  "
           "카톡은 요약, 여기는 상세")
 
# 1) 시황 현황
st.subheader("시황 현황")
cols = st.columns(len(INDICES))
for col, (name, sym) in zip(cols, INDICES):
    try:
        last, pct = last_and_change(load_history(sym, 30))
        if last is None:
            col.metric(name, "-")
        else:
            col.metric(name, f"{last:,.0f}",
                       f"{pct:+.2f}%" if pct is not None else None)
    except Exception:
        col.metric(name, "조회 실패")
 
st.divider()
 
# 2) 관심 종목 + 차트 + 등락 사유(관련 뉴스 / 추세 안내)
st.subheader("관심 종목")
tabs = st.tabs([n for n, _ in WATCHLIST])
for tab, (name, sym) in zip(tabs, WATCHLIST):
    with tab:
        try:
            df = load_history(sym, 120)
            last, pct = last_and_change(df)
            c1, c2 = st.columns([1, 3])
            with c1:
                st.metric(name, f"{last:,.2f}" if last else "-",
                          f"{pct:+.2f}%" if pct is not None else None)
            with c2:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df.index, y=df["Close"],
                                         mode="lines", name=name))
                fig.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(fig, use_container_width=True)
 
            # 등락 배경: 관련 뉴스 있으면 표시, 없으면 추세 안내
            st.markdown("**이 종목 관련 소식**")
            try:
                news = search_news(name, count=4)
            except Exception:
                news = []
            if news:
                st.caption("아래는 이 종목과 관련된 최근 뉴스입니다. "
                           "등락의 직접 원인이라는 보장은 없으니 참고용으로만 보세요.")
                for it in news:
                    src = f"  ·  {it['source']}" if it["source"] else ""
                    st.markdown(f"- [{it['title']}]({it['link']}){src}")
            else:
                st.info(trend_sentence(df))
        except Exception as e:
            st.warning(f"{name} 데이터를 불러오지 못했습니다: {e}")
 
st.divider()
 
# 3) 등락 상위 (대형주 중)
st.subheader("오늘 등락 상위 (주요 대형주)")
rows = []
for name, sym in MAJORS:
    try:
        last, pct = last_and_change(load_history(sym, 30))
        if last is not None and pct is not None:
            rows.append({"종목": name, "현재가": round(last), "등락률(%)": round(pct, 2)})
    except Exception:
        continue
 
if rows:
    df_rank = pd.DataFrame(rows)
    up = df_rank.sort_values("등락률(%)", ascending=False).head(5)
    down = df_rank.sort_values("등락률(%)").head(5)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🔺 상승 TOP 5**")
        st.dataframe(up, hide_index=True, use_container_width=True)
    with c2:
        st.markdown("**🔻 하락 TOP 5**")
        st.dataframe(down, hide_index=True, use_container_width=True)
else:
    st.info("등락 데이터를 불러오지 못했습니다.")
 
st.divider()
 
# 4) 뉴스
st.subheader("증시 뉴스")
try:
    for it in search_news(NEWS_QUERY, count=15):
        src = f"  ·  {it['source']}" if it["source"] else ""
        st.markdown(f"- [{it['title']}]({it['link']}){src}")
except Exception as e:
    st.warning(f"뉴스를 불러오지 못했습니다: {e}")
 
st.caption("※ 사실 정리용 참고 자료이며, 투자 판단과 책임은 본인에게 있습니다.")
