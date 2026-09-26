"""
추추무매v3.3
Streamlit 앱 — app.py
 
실행: streamlit run app.py
배포: 이 파일 + requirements.txt 를 GitHub 저장소에 올리고
      streamlit.io/cloud 에서 저장소를 연결하면 바로 웹페이지가 됩니다.
 
거래 데이터는 data.json 파일에 저장되고, 시세는 Yahoo Finance에서 자동 조회됩니다.
 
------------------------------------------------------------------------------
[수정 내역] (원본 코드 대비 문서(추추무매 이론)와 어긋나던 부분을 수정)
1. 1회 매수액(base1x) = 잔금 ÷ (분할수 − T) 로 매일 재계산 (기존: capital/splits 고정값 오류)
2. T값은 실제 체결로 누적된 r["T"] 값을 그대로 사용 (기존: 평단×수량÷base1x 로 역산하던 오류 제거)
3. 쿼터매도: 익절이면 원가만 잔금에 편입 + 초과분은 실현손익으로 별도 기록,
   손절이면 매도대금 전액 잔금 편입 (기존: 항상 전액 편입하던 오류 수정)
4. 매수 목표금액은 항상 절반씩 나눠 "평단가"와 "★지점(별지점)"에 각각 매수
   (기존: 두 수량 모두 별지점 가격으로 계산하던 오류 수정, 전반전/후반전 구분 로직 제거 - 문서에 없는 내용)
5. 42일선 위에 있어도 오늘 종가가 20일전 종가보다 낮으면 하단(0.76T) 규칙 적용 (문서 2-1 규칙, 기존 미구현)
6. 실제 체결 가능한 주식 수량은 정수 내림으로 표시 (기존: 반올림 오류)
7. ★값 색상(수익=초록/손절=빨강) 로직 반대 오류 수정
8. 백업 복원 시 호출되던 normalize_data() 함수가 정의되어 있지 않던 오류 수정 (NameError 발생하던 버그)
9. 진행 중인 라운드의 쿼터매도 실현손익도 누적 실현손익에 즉시 반영되도록 수정
10. 중복 정의되어 있던 죽은 load_data/save_data 코드 정리
 
------------------------------------------------------------------------------
[2차 수정 내역]
11. [치명] 복리 모드에서 쿼터매도 익절 초과분이 다음 라운드 자본에 반영되지 않던 오류 수정.
    라운드 종료 시 next_capital = 잔금 + 미편입 실현수익(쿼터매도 익절 초과분) 으로 계산한다.
12. 쿼터매도 T 갱신은 실제 매도비율 기준(T×(1-매도비율))을 그대로 사용 (문서가 실제비율 기준으로 갱신됨)
13. 20일 전 종가 인덱스 오류 수정: history[-20] 은 19거래일 전이므로 history[-21] 로 수정
14. 폭락장 대응이 평단매수/별지점매수로 절반씩 쪼개지던 오류 수정.
    문서대로 '해당 단계 1개만 단독 실행'하도록 별도 분기 처리하고, 일반 종가 매수 표시를 하지 않는다.
15. 20% 지정가 익절 수량을 전량으로 수정 (기존: 보유수량의 3/4만 표시 → 사이클이 종료되지 않던 오류)
16. recalculate_round 에서 final_sell 재생 시 status/closedDate 가 복원되지 않아
    종료된 라운드가 '진행중'으로 되살아나던 오류 수정
17. is_first_buy 의 부동소수점 직접 비교(T == 0) 를 허용오차 비교로 수정
18. phase_of 소진모드 판정을 문서 기준(T > 분할수-1) 으로 수정
19. 미국 증시 휴장일에 '장중'으로 잘못 표시되고 MA42 계산에서 오늘을 제외하던 오류 수정
    (최신 일봉 날짜가 오늘인지로 실제 거래일 여부를 판정)
20. 콕핏에 '총자산'(잔금 + 평가금액 + 미편입 실현수익) 표시 추가 — 증권사 잔고 대조용
21. GitHub 토큰 미설정 시 로컬 파일 저장은 휘발성이므로 사이드바에 경고 표시
------------------------------------------------------------------------------
[3차 수정 내역] (v3.3 최종 이론·백테스터 정합)
22. [치명] 사이클 첫 매수일에 폭락장이 와도 1T 고정 (기존: 폭락 배율 1.95T+를 그대로 유지하던 오류).
    백테스트와 동일하게 "첫날은 지표·폭락 여부와 무관하게 1T 한 번만 매수"한다.
23. 전량익절 후 재시작일 가이드 추가 (이론 0-1): 새 라운드 첫 매수 + 직전 라운드가 전량익절로
    종료됐으면 "1T 매수 + 같은 날 일일매수 절반"을 종가 기준으로 안내한다.
    (폭락장이면 폭락 배율의 절반, 아니면 당일 국면 배율의 절반)
24. MA42/MA43/20일전 종가를 "오늘 이전 완료봉" 기준으로 통일.
    장중·장전·장마감후·휴장일 모두 백테스트 전일 기준(shift(1)/shift(20))과 동일하게 동작한다.
25. 매도 가이드 라벨 수정: "Limit Sell all Trailing Stop" → "지정가 전량익절 +20% (트레일링 없음)".
26. 매수 가이드 표시 순서 수정: 첫 매수일(일반/재시작) 판정을 폭락장보다 먼저 처리한다.
    (기존: 첫날 폭락 시 폭락장 카드가 먼저 떠서 1.95T 매수를 안내하던 오류)
27. determine_multiplier 비교를 백테스트와 동일한 엄격 부등식(>)으로 통일.
    20일전 종가 데이터 부족 시 백테스트처럼 MA42 위치만으로 1.4976T/0.6831T를 선택한다.
28. ★매수 판정 기준을 백테스트와 동일하게 별지점-0.01로 수정
    (determine_buy_action에 buy_trigger 전달).
29. 전량익절률을 백테스트 채택값 20%로 수정 (기존 19.8%).
30. Yahoo 시세 조회 실패 시 오늘의 가이드가 표시되지 않던 문제 수정
    (guide를 항상 계산하도록 변경).
31. 수동 입력/Excel에서 전량매도 수량이 보유수량과 다르면 라운드를 닫지 않고 오류 처리.
32. Excel 가져오기에 전량매도 유형 추가 ("전량매도"/"지정가매도"/"final_sell").
    전량매도 이후 거래는 자동으로 시작된 새 라운드에 기록된다.
------------------------------------------------------------------------------
3.0
일반매수 기 이평선 병경, 폭락장매수 기준이평선 변경, 일반매수 비중변경
MA_PERIOD = 42
DEEP_MA_PERIOD = 43
# 1. 종가 > MA42 AND 종가 > 20거래일 전 종가   1
# 2. 종가 > MA42 AND 종가 < 20거래일 전 종가  0.7675
# 3. 종가 < MA42 AND 종가 > 20거래일 전 종가  0.7475
# 4. 종가 < MA42 AND 종가 < 20거래일 전 종가  0.7875
-----------------------------------------------------------------------------
3.1 (2026-09-019)
수익률변경 및 일반매수 비중변경

# 1. 종가 > MA42 AND 종가 > 20거래일 전 종가   1
# 2. 종가 > MA42 AND 종가 < 20거래일 전 종가  0.77
# 3. 종가 < MA42 AND 종가 > 20거래일 전 종가  0.7525
# 4. 종가 < MA42 AND 종가 < 20거래일 전 종가  0.765

수익률 13.4% 에서 지정가 -0.2% 트레일링 매도 
-----------------------------------------------------------------------------
3.2
backtest에서 수익금이 두번 편입되는 오류 수정
20분할로 변경, 일일매도 비율 변경, 수익률 13.4% 에서 20%로 변경

# 1. 종가 > MA42 AND 종가 > 20거래일 전 종가   1
# 2. 종가 > MA42 AND 종가 < 20거래일 전 종가  0.7675
# 3. 종가 < MA42 AND 종가 > 20거래일 전 종가  0.7475
# 4. 종가 < MA42 AND 종가 < 20거래일 전 종가  0.7875

수익률 20% 에서 지정가 -0.25% 트레일링 매도 
------------------------------------------------------------------------------------
에이든-추추무매 v3.2
MA_PERIOD = 42
DEEP_MA_PERIOD = 43

BUY_MULT_1 = 1.4976
BUY_MULT_2 = 0.7356
BUY_MULT_3 = 0.6831
BUY_MULT_4 = 1.0003

# 1. 종가 > MA42 AND 종가 > 20거래일 전 종가 
# 2. 종가 > MA42 AND 종가 < 20거래일 전 종가 
# 3. 종가 < MA42 AND 종가 > 20거래일 전 종가 
# 4. 종가 < MA42 AND 종가 < 20거래일 전 종가 

DEEP_35_PCT = -35.0
DEEP_35_T = 1.95

DEEP_41_PCT = -37.0
DEEP_41_T = 2.10

DEEP_45_5_PCT = -41
DEEP_45_5_T = 2.50

PROFIT_TARGET = 1.20

"""
 
import json
import os
import base64
import requests
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
 
import pandas as pd
import streamlit as st
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
 
# 페이지 설정은 Streamlit UI 호출보다 먼저 실행합니다.
st.set_page_config(page_title="추추무매 · 포트폴리오 대시보드", layout="centered")
 
# 60초마다 Yahoo 시세를 자동 갱신합니다.
st_autorefresh(interval=60_000, key="yahoo_market_refresh")
 
# =============================================================================
# 저장소 (GitHub 저장소의 data.json — 토큰이 없으면 로컬 파일로 자동 폴백)
# =============================================================================
 
try:
    GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
    REPO_NAME = st.secrets.get("REPO_NAME", "codeyegrian/infiniteloop-manager")
except Exception:
    GITHUB_TOKEN = ""
    REPO_NAME = "codeyegrian/infiniteloop-manager"
 
BRANCH = "main"
DATA_FILE = "data.json"                       # 저장소 루트 기준 파일명 (로컬 폴백 시에도 동일 파일명 사용)
 
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}
 
def github_load_file(filename, default_value):
    if not GITHUB_TOKEN:
        if os.path.exists(filename):
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return default_value
 
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{filename}"
    try:
           response = requests.get(url, headers=HEADERS, timeout=5)
           if response.status_code == 200:
               file_data = response.json()
               content_encoded = file_data.get("content", "")
               decoded_bytes = base64.b64decode(content_encoded)
               return json.loads(decoded_bytes.decode("utf-8"))
    except Exception:
           pass
    return default_value
 
def github_save_file(filename, data):
    if not GITHUB_TOKEN:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True, "Saved locally"
 
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{filename}"
    try:
        get_resp = requests.get(f"{url}?ref={BRANCH}", headers=HEADERS, timeout=5)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
 
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        content_encoded = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
 
        payload = {
            "message": f"Update {filename} via 추추무매 앱",
            "content": content_encoded,
            "branch": BRANCH,
        }
        if sha:
            payload["sha"] = sha
 
        put_resp = requests.put(url, headers=HEADERS, json=payload, timeout=5)
        if put_resp.status_code in (200, 201):
            return True, "Successfully updated GitHub!"
        else:
            return False, f"GitHub Error {put_resp.status_code}: {put_resp.text}"
    except Exception as e:
        return False, f"Exception: {str(e)}"
 
 
# 데이터 구조: 다중 포트폴리오(portfolios) 지원
DEFAULT_DATA = {
    "portfolios": [
        {
            "id": 1,
            "name": "기본 포트폴리오",
            "config": {
                "symbol": "SOXL",
                "splits": 40,
                "capital": 20000.0,
                "compounding": True
            },
            "price_history": [],
            "rounds": []
        }
    ],
    "active_portfolio_id": 1
}
 
 
def normalize_data(d):
    """백업 파일(구버전 단일 포트폴리오 구조 포함)을 현재 표준(다중 포트폴리오) 구조로 변환한다."""
    if not isinstance(d, dict):
        return json.loads(json.dumps(DEFAULT_DATA))
    if "portfolios" not in d:
        old_cfg = d.get("config")
        old_hist = d.get("price_history", [])
        old_rounds = d.get("rounds", [])
        d = {
            "portfolios": [
                {
                    "id": 1,
                    "name": d.get("name", "기본 포트폴리오"),
                    "config": old_cfg,
                    "price_history": old_hist,
                    "rounds": old_rounds
                }
            ],
            "active_portfolio_id": 1
        }
    if "active_portfolio_id" not in d:
        portfolios = d.get("portfolios", [])
        d["active_portfolio_id"] = portfolios[0]["id"] if portfolios else None
    return d
 
 
def load_data():
    d = github_load_file(DATA_FILE, None)
    if d is None:
        return json.loads(json.dumps(DEFAULT_DATA))
    return normalize_data(d)
 
 
def save_data(data):
    ok, msg = github_save_file(DATA_FILE, data)
    if not ok:
        st.sidebar.warning(f"⚠️ 저장 실패: {msg}")
    return ok
 
# =============================================================================
# 핵심 계산 로직 (추추무매 오버레이)
# =============================================================================
def star_percent(symbol, splits, T):
    if symbol == "TQQQ":
        return (15 - 1.5 * T) if splits == 20 else (15 - 0.75 * T)
    return (20 - 2 * T) if splits == 20 else (20 - T)
 
def sell_profit_pct(symbol):
    # 전량익절은 평단 × 1.20 고정 지정가 (트레일링 없음)
    return 15 if symbol == "TQQQ" else 20
 
def ma42(history):
    if len(history) < 42:
        return None
    last42 = history[-42:]
    return sum(p["close"] for p in last42) / 42
 
# 폭락장 단계 정의 (MA43 대비 하락률, 배수) — 깊은 단계가 앞에 오도록 정렬
CRASH_TIERS = [(41, 2.5), (37, 2.1), (35, 1.95)]
 
def determine_multiplier(close, ma42val, ma43val, close_20d_ago=None):
    """
    추추무매 매수 로직
 
    0) 최초 매수: 1.0T (지표·폭락 여부와 무관하게 1T 한 번만 매수)
    0-1) 전량익절 후 재시작일: 1T + 같은 날 일일매수 절반
    1-1) MA42 위 + 20일전 종가보다 위: 1.4976T
    1-2) MA42 위 + 20일전 종가보다 아래: 0.7356T
    2-1) MA42 아래 + 20일전 종가보다 위: 0.6831T
    2-2) MA42 아래 + 20일전 종가보다 낮음: 1.0003T
 
    폭락장 조건은 위 일반 매수 로직보다 항상 최우선:
    MA43 대비 -35% 이상  -> 1.95T
    MA43 대비 -37% 이상  -> 2.10T
    MA43 대비 -41% 이상  -> 2.50T
 
    ※ 1.4976T / 0.7356T / 0.6831T / 1.0003T 는 각각
       별지점 매수와 평단매수에 절반씩 배분한다.
    ※ 폭락장 배수(1.95T~2.5T)는 절반으로 쪼개지 않고
       해당 단계 가격 1곳에 단독으로 집행한다. (문서 규칙)
 
    반환: (배수, 설명, 폭락장단계 or None)
    """
    if ma42val is None or ma43val is None or close is None:
        return 1.0, "이동평균 데이터 부족 (기본 1.0T)", None
 
    # ---------------------------------------------------------
    # 폭락장 조건 최우선
    # ---------------------------------------------------------
    drawdown = (ma43val - close) / ma43val * 100
    for th, mult in CRASH_TIERS:
        if drawdown >= th:
            return mult, f"MA43 대비 -{th}% 이상 구간 (폭락장 대응)", th
 
    # ---------------------------------------------------------
    # 일반 매수 로직
    # ---------------------------------------------------------
    above_ma = close > ma42val

    # 20거래일 전 종가 데이터가 아직 없으면 백테스트와 동일하게
    # MA42 위치만으로 판단한다 (위: 1.4976T / 아래: 0.6831T).
    if close_20d_ago is None:
        if above_ma:
            return 1.4976, "MA42 위 (20일전 종가 데이터 부족)", None
        return 0.6831, "MA42 아래 (20일전 종가 데이터 부족)", None

    above_20d_close = close > close_20d_ago

    if above_ma and above_20d_close:
        # 1-1 상승추세: 0.7488T 별지점 + 0.7488T 평단
        return 1.4976, "MA42 위 + 20일전 종가 위 (상승추세)", None

    if above_ma and not above_20d_close:
        # 1-2 횡보: 0.3678T 별지점 + 0.3678T 평단
        return 0.7356, "MA42 위 + 20일전 종가 아래 (횡보)", None

    if not above_ma and above_20d_close:
        # 2-1 횡보: 0.34155T 별지점 + 0.34155T 평단
        return 0.6831, "MA42 아래 + 20일전 종가 위 (횡보)", None

    # 2-2 하락추세: 0.50015T 별지점 + 0.50015T 평단
    return 1.0003, "MA42 아래 + 20일전 종가 아래 (하락추세)", None
 
def crash_tier_table(ma43val, base1x):
    """MA43 대비 추가 하락률(35/37/41%)별 폭락장 매수 단가·수량표 (참고용, 실제 발동은 determine_multiplier가 판단)"""
    rows = []
    if ma43val is None or base1x is None:
        return rows
    for th, mult in sorted(CRASH_TIERS):
        price = ma43val * (1 - th / 100)
        amount = base1x * mult
        qty = (amount / price) if price and price > 0 else None
        rows.append({"tier": th, "mult": mult, "price": price, "amount": amount, "qty": qty})
    return rows
 
def phase_of(T, splits):
    # 문서: T > 분할수-1 에 도달하면 소진(리버스)모드
    if T > splits - 1:
        return "소진모드"
    if T < splits / 2:
        return "전반전"
    return "후반전"
 
def active_round(p):
    rounds = p["rounds"]
    if not rounds:
        return None
    return rounds[-1] if rounds[-1]["status"] == "active" else None
 
 
def unbanked_profit(r):
    """
    쿼터매도 익절 시 '초과분(수익)'은 문서 규칙상 잔금에 편입하지 않고
    실현손익으로만 기록한다. 따라서 이 금액은 r["cash"] 에 들어있지 않다.
    라운드 종료(복리 재투입) 및 총자산 계산 시 반드시 더해주어야 한다.
    """
    if not r:
        return 0.0
    return sum(
        t["pnl"]
        for t in r.get("trades", [])
        if t.get("type") == "quarter_sell"
        and t.get("pnl") is not None
        and t["pnl"] > 0
    )
 
 
# =============================================================================
# Yahoo Finance 자동 시세
# =============================================================================
 
NY_TZ = ZoneInfo("America/New_York")
 
 
@st.cache_data(ttl=30, show_spinner=False)
def fetch_yahoo_market(symbol):
    """
    Yahoo Finance에서 자동으로:
      - 장중: 1분봉 최신 정규장 가격
      - 장외: 최근 정규장 종가
      - MA20: 최근 20개 완료된 일봉 종가 평균
    을 가져옵니다.
 
    MA20은 장중에는 오늘의 미완성 일봉을 제외하고 계산합니다.
    휴장일에는 '장중'으로 판정하지 않습니다.
    """
    ticker = yf.Ticker(symbol)
 
    daily = ticker.history(
        period="6mo",
        interval="1d",
        auto_adjust=False,
        actions=False,
        prepost=False,
    )
 
    if daily is None or daily.empty:
        raise RuntimeError(f"{symbol} Yahoo 일봉 데이터를 가져오지 못했습니다.")
 
    daily = daily.dropna(subset=["Close"]).copy()
 
    now_et = datetime.now(NY_TZ)
    current_date = now_et.date()
 
    daily_dates = pd.to_datetime(daily.index)
    if getattr(daily_dates, "tz", None) is not None:
        daily_dates_et = daily_dates.tz_convert(NY_TZ)
    else:
        daily_dates_et = daily_dates.tz_localize(NY_TZ)
 
    daily = daily.copy()
    daily["_date_et"] = daily_dates_et.date
 
    # -------------------------------------------------------------
    # 오늘이 실제 '거래일'인지 판정
    # 요일/시간만으로는 미국 증시 휴장일(추수감사절, 독립기념일 등)을
    # 걸러낼 수 없으므로, Yahoo 일봉에 오늘 날짜 봉이 존재하는지로 확인한다.
    # (장 시작 직후에는 오늘 봉이 이미 생성되어 있다)
    # -------------------------------------------------------------
    has_today_bar = bool((daily["_date_et"] == current_date).any())
 
    weekday = now_et.weekday() < 5
    regular_session_open = time(9, 30)
    regular_session_close = time(16, 0)
    within_session_hours = (
        regular_session_open
        <= now_et.time().replace(second=0, microsecond=0)
        < regular_session_close
    )
 
    market_open = weekday and within_session_hours and has_today_bar
 
    # 일봉 MA20:
    # 장중에는 오늘 미완성 일봉 제외,
    # 장 마감 후(및 휴장일)에는 마지막 완료 종가까지 포함.
    if market_open:
        completed = daily[daily["_date_et"] < current_date].copy()
    else:
        completed = daily[daily["_date_et"] <= current_date].copy()
 
    if len(completed) < 20:
        ma20_val = None
    else:
        ma20_val = float(completed["Close"].tail(20).mean())
 
    # 실시간/최근 종가
    live_price = None
    live_timestamp = None
    source_label = "Yahoo 최근 종가"
 
    if market_open:
        try:
            intraday = ticker.history(
                period="1d",
                interval="1m",
                auto_adjust=False,
                actions=False,
                prepost=False,
            )
 
            if intraday is not None and not intraday.empty:
                intraday = intraday.dropna(subset=["Close"])
                if not intraday.empty:
                    last = intraday.iloc[-1]
                    live_price = float(last["Close"])
                    live_timestamp = intraday.index[-1]
                    source_label = "Yahoo 장중 1분 시세"
        except Exception:
            live_price = None
 
    if live_price is None:
        if len(completed) == 0:
            raise RuntimeError(f"{symbol} 최근 종가를 확인하지 못했습니다.")
        live_price = float(completed.iloc[-1]["Close"])
        live_timestamp = completed.index[-1]
 
    gap_pct = (
    ((live_price - ma20_val) / ma20_val * 100)
    if ma20_val is not None and live_price is not None and ma20_val > 0
    else None
)
 
    # 표시용 최근 60개 일봉 (오래된 -> 최신 순)
    hist = completed.tail(60).copy()
    history_rows = []
    for idx, row in hist.iterrows():
        dt = row["_date_et"]
        history_rows.append(
            {
                "date": str(dt),
                "close": float(row["Close"]),
            }
        )
 
    previous_close = (
        float(completed.iloc[-2]["Close"])
        if len(completed) >= 2
        else None
    )
 
    return {
        "symbol": symbol,
        "price": live_price,
        "ma20": ma20_val,
        "gap_pct": gap_pct,
        "previous_close": previous_close,
        "timestamp": str(live_timestamp),
        "fetched_at": now_et.isoformat(),
        "source_label": source_label,
        "market_open": market_open,
        "history": history_rows,
    }
 
 
 
def start_new_round(p, start_capital, start_date):
    r = {
        "id": len(p["rounds"]) + 1,
        "startDate": start_date,
        "startCapital": start_capital,
        "cash": start_capital,
        "qty": 0.0,
        "avgCost": 0.0,
        "T": 0.0,
        "trades": [],
        "status": "active",
    }
    p["rounds"].append(r)
    return r
 
def apply_buy(r, dt, price, qty, t_delta):
    amount = price * qty
    new_qty = r["qty"] + qty
    new_cost = r["avgCost"] * r["qty"] + amount
    r["cash"] -= amount
    r["avgCost"] = (new_cost / new_qty) if new_qty > 0 else 0.0
    r["qty"] = new_qty
    r["T"] += t_delta
    r["trades"].append({
        "id": len(r["trades"]) + 1,
        "date": dt, "type": "buy", "price": price, "qty": qty, "amount": amount,
        "tDelta": t_delta, "tAfter": r["T"], "avgAfter": r["avgCost"],
        "cashAfter": r["cash"], "pnl": None,
    })
 
def apply_quarter_sell(r, dt, price, qty):
    """
    문서 규칙:
    - 쿼터매도  *직전T × (1 - 매도수량/보유수량) * 실제 주식매도 비율로 T값을 낮춤
    - 익절매도(매도가 >= 평단가): 매도대금 중 '원가' 부분만 잔금에 편입,
      초과분(수익)은 잔금에 넣지 않고 실현손익으로만 기록한다.
    - 손절매도(매도가 < 평단가): 실제 매도대금 전액을 잔금에 편입한다.
      T_after = 직전T × (1 - 매도주식수 / 매도 전 보유주식수)
      정확히 25% 매도한 경우 직전T × 0.75 와 동일한 값이 되고,
      정수 내림 등으로 25%에서 조금 벗어나도 실제 체결 비율을 그대로 반영한다.
    """
    cost_basis = r["avgCost"] * qty
    proceeds = price * qty
    pnl = proceeds - cost_basis
    t_before = r["T"]
 
    if price >= r["avgCost"]:
        # 익절: 원가만 잔금으로 복귀, 초과 수익분은 잔금에 편입하지 않음
        r["cash"] += cost_basis
    else:
        # 손절: 매도대금 전액 잔금 편입
        r["cash"] += proceeds
 
    # 실제 매도 비율에 따라 T 감소 (매도 전 보유수량 기준)
    qty_before_sell = r["qty"]
    sell_ratio = qty / qty_before_sell if qty_before_sell > 0 else 0.0
 
    r["qty"] -= qty
    r["T"] = r["T"] * (1 - sell_ratio)
 
    r["trades"].append({
        "id": len(r["trades"]) + 1,
        "date": dt, "type": "quarter_sell", "price": price, "qty": qty, "amount": proceeds,
        "tDelta": r["T"] - t_before, "tAfter": r["T"], "avgAfter": r["avgCost"],
        "cashAfter": r["cash"], "pnl": pnl,
    })
 
def apply_final_sell(p, r, dt, price, qty):
    amount = price * qty
    pnl = (price - r["avgCost"]) * qty
 
    # 라운드 종료 전, 잔금에 편입되지 않은 쿼터매도 익절 초과분을 확인한다.
    pending_profit = unbanked_profit(r)
 
    r["cash"] += amount
    r["qty"] -= qty
    r["trades"].append({
        "id": len(r["trades"]) + 1,
        "date": dt, "type": "final_sell", "price": price, "qty": qty, "amount": amount,
        "tDelta": 0, "tAfter": r["T"], "avgAfter": r["avgCost"],
        "cashAfter": r["cash"], "pnl": pnl,
    })
    realized = sum(t["pnl"] for t in r["trades"] if t["pnl"] is not None)
    r["status"] = "closed"
    r["closedDate"] = dt
    r["realizedPnl"] = realized
 
    # 라운드 최종 회수금 = 잔금 + 미편입 실현수익(쿼터매도 익절 초과분)
    # 이 값을 더하지 않으면 복리 모드에서 쿼터매도 수익이 사라진다.
    r["finalCapital"] = r["cash"] + pending_profit
 
    next_capital = r["finalCapital"] if p["config"]["compounding"] else p["config"]["capital"]
    start_new_round(p, next_capital, dt)
 
def recalculate_round(r, initial_capital):
    """거래 삭제 시 라운드 상태 전체 재계산"""
    r["cash"] = initial_capital
    r["qty"] = 0.0
    r["avgCost"] = 0.0
    r["T"] = 0.0
    trades = r["trades"].copy()
    r["trades"] = []
 
    # 재계산 전 종료 관련 필드 초기화 (final_sell 이 남아있으면 아래에서 다시 설정)
    r["status"] = "active"
    r.pop("closedDate", None)
    r.pop("realizedPnl", None)
    r.pop("finalCapital", None)
 
    for t in trades:
        ttype = t["type"]
        dt = t["date"]
        price = t["price"]
        qty = t["qty"]
        t_delta = t.get("tDelta", 0.0)
 
        if ttype == "buy":
            apply_buy(r, dt, price, qty, t_delta)
        elif ttype == "quarter_sell":
            apply_quarter_sell(r, dt, price, qty)
        elif ttype == "final_sell":
            pending_profit = unbanked_profit(r)
            amount = price * qty
            pnl = (price - r["avgCost"]) * qty
            r["cash"] += amount
            r["qty"] -= qty
            r["trades"].append({
                "id": len(r["trades"]) + 1,
                "date": dt, "type": "final_sell", "price": price, "qty": qty, "amount": amount,
                "tDelta": 0, "tAfter": r["T"], "avgAfter": r["avgCost"],
                "cashAfter": r["cash"], "pnl": pnl,
            })
            # 종료 상태를 원래대로 복원한다 (기존: status/closedDate 미복원으로
            # 종료된 라운드가 '진행중'으로 되살아나던 오류)
            r["status"] = "closed"
            r["closedDate"] = dt
            r["realizedPnl"] = sum(tr["pnl"] for tr in r["trades"] if tr["pnl"] is not None)
            r["finalCapital"] = r["cash"] + pending_profit
 
# =============================================================================
# Excel 거래내역 가져오기
# =============================================================================
 
def import_trades_from_excel(p, r, uploaded_file):
    """
    Excel 거래내역을 현재 활성 라운드에 다시 재생한다.
 
    Excel 필수 열:
      날짜 / 구분 / 수량 / 가격 
 
    거래금액 열은 있어도 되고 없어도 된다.
    거래금액은 가격 × 수량으로 다시 계산한다.
 
    구분:
      매수
      쿼터매도
      전량매도 (보유수량 전부 매도 → 라운드 종료 후 새 라운드 시작)
 
    T는 Excel에서 가져오지 않고 현재 추추무매 규칙으로 다시 계산한다.
    """
 
    try:
        df = pd.read_excel(uploaded_file)
 
        # -----------------------------
        # 열 이름 정리
        # -----------------------------
        df.columns = [str(c).strip() for c in df.columns]
 
        # 영문/한글 열 이름 모두 어느 정도 허용
        column_alias = {
            "날짜": "date",
            "date": "date",
            "거래일": "date",
            "Date": "date",
 
            "구분": "type",
            "유형": "type",
            "type": "type",
            "Activity Description": "type",
 
            "가격": "price",
            "체결가": "price",
            "체결가격": "price",
            "price": "price",
            "Price": "price",
 
            "수량": "qty",
            "체결수량": "qty",
            "qty": "qty",
            "Quantity": "qty",
 
            "거래금액": "amount",
            "금액": "amount",
            "amount": "amount",
            "Amount": "amount",
        }
 
        renamed = {}
        for col in df.columns:
            if col in column_alias:
                renamed[col] = column_alias[col]
 
        df = df.rename(columns=renamed)
 
        # -----------------------------
        # 필수 열 확인
        # -----------------------------
        required = ["date", "type", "qty", "price"]
        missing = [c for c in required if c not in df.columns]
 
        if missing:
            raise ValueError(
                "필수 열이 없습니다: "
                + ", ".join(missing)
                + "\n필수 형식: 날짜 / 구분 / 수량 / 가격"
            )
 
        # 빈 행 제거
        df = df.dropna(subset=["date", "type", "qty", "price"]).copy()
 
        if df.empty:
            raise ValueError("Excel에 거래내역이 없습니다.")
 
        # -----------------------------
        # 날짜 / 숫자 변환
        # -----------------------------
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
 
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["qty"] = pd.to_numeric(df["qty"], errors="coerce")
 
        df = df.dropna(subset=["date", "qty", "price"]).copy()
 
        # -----------------------------
        # 거래 유형 정리
        # -----------------------------
        type_map = {
            "매수": "buy",
            "buy": "buy",
            "매입": "buy",
            "YOU BOUGHT": "buy",
 
            "쿼터매도": "quarter_sell",
            "쿼터 매도": "quarter_sell",
            "quarter_sell": "quarter_sell",
            "quarter sell": "quarter_sell",
            "YOU SOLD": "quarter_sell",

            "전량매도": "final_sell",
            "전량 매도": "final_sell",
            "지정가매도": "final_sell",
            "final_sell": "final_sell",
            "final sell": "final_sell",
        }
 
        df["type_normalized"] = (
            df["type"]
            .astype(str)
            .str.strip()
            .map(type_map)
        )
 
        invalid_types = df[df["type_normalized"].isna()]
 
        if not invalid_types.empty:
            bad_types = (
                invalid_types["type"]
                .astype(str)
                .drop_duplicates()
                .tolist()
            )
            raise ValueError(
                "인식할 수 없는 거래 유형: "
                + ", ".join(bad_types)
                + "\n사용 가능한 유형: 매수 / 쿼터매도 / 전량매도"
            )
 
        # -----------------------------
        # 거래 날짜순 정렬
        #
        # 같은 날짜의 거래는 Excel에 입력된 순서를 유지한다.
        # 따라서 같은 날 여러 거래가 있다면 실제 체결 순서대로
        # Excel에 배치하는 것이 좋다.
        # -----------------------------
        df["_original_order"] = range(len(df))
 
        df = df.sort_values(
            ["date", "_original_order"],
            ascending=[True, True],
            kind="stable",
        ).reset_index(drop=True)
 
        # -----------------------------
        # 기존 거래를 초기화
        # -----------------------------
        initial_capital = float(r["startCapital"])
 
        r["cash"] = initial_capital
        r["qty"] = 0.0
        r["avgCost"] = 0.0
        r["T"] = 0.0
        r["trades"] = []
        r["status"] = "active"
 
        r.pop("closedDate", None)
        r.pop("realizedPnl", None)
        r.pop("finalCapital", None)
 
        # -----------------------------
        # 거래 하나씩 재생
        # -----------------------------
        imported_count = 0
 
        for _, row in df.iterrows():
            dt = row["date"].date().isoformat()
            price = float(row["price"])
            qty = float(row["qty"])
            trade_type = row["type_normalized"]

            # YOU SOLD / 쿼터매도 수량은 음수로 들어와도 양수로 처리
            if trade_type == "quarter_sell":
                qty = abs(qty)

            if price <= 0:
                raise ValueError(
                    f"{dt}: 가격이 0 이하입니다."
                )
 
            if qty <= 0:
                raise ValueError(
                    f"{dt}: 수량이 0 이하입니다."
                )
 
            if trade_type == "buy":
 
                splits = int(p["config"]["splits"])
 
                remaining = splits - r["T"]
 
                if remaining <= 0:
                    raise ValueError(
                        f"{dt}: T={r['T']:.4f}에서 추가 매수를 계산할 수 없습니다."
                    )
 
                base1x = r["cash"] / remaining
 
                if base1x <= 0:
                    raise ValueError(
                        f"{dt}: 매수 전 잔금이 부족합니다."
                    )
 
                amount = price * qty
 
                # 기존 수동 입력 화면과 같은 방식으로
                # 실제 체결금액 ÷ 당시 1T = 이번 매수의 T 증가량
                t_delta = amount / base1x
 
                apply_buy(
                    r,
                    dt,
                    price,
                    qty,
                    t_delta
                )
 
            elif trade_type == "quarter_sell":

                if qty > r["qty"] + 1e-9:
                    raise ValueError(
                        f"{dt}: 쿼터매도 수량 {qty:g}주가 "
                        f"당시 보유수량 {r['qty']:g}주보다 많습니다."
                    )

                apply_quarter_sell(
                    r,
                    dt,
                    price,
                    qty
                )

            elif trade_type == "final_sell":

                qty = abs(qty)

                if qty > r["qty"] + 1e-9:
                    raise ValueError(
                        f"{dt}: 전량매도 수량 {qty:g}주가 "
                        f"당시 보유수량 {r['qty']:g}주보다 많습니다."
                    )

                if qty < r["qty"] - 1e-9:
                    raise ValueError(
                        f"{dt}: 전량매도 수량 {qty:g}주가 보유수량 {r['qty']:g}주와 다릅니다. "
                        f"전량매도는 보유수량 전부를 입력해야 합니다."
                    )

                apply_final_sell(p, r, dt, price, r["qty"])

                # 전량매도는 새 라운드를 시작하므로 이후 거래는 새 라운드에 기록한다.
                r = active_round(p)

            imported_count += 1
 
        return True, imported_count
 
    except Exception as e:
        return False, str(e)
 

def determine_buy_action(current_price, avg_cost, star_point):
    """
    현재가 / 평단가 / ★매수기준가(별지점 - 0.01)의 위치를 비교하여
    매수 방법을 자동 결정한다. (세 번째 인자는 buy_trigger를 전달)

    1) 현재가 > 평단 < ★
       → 평단 + ★ 매수

    2) 현재가 < 평단 < ★
       → ★ 매수만

    3) 현재가 > 평단 > ★
       → 평단 매수만

    4) 현재가 < 평단 > ★
       → 매수하지 않음
    """

    if (
        current_price is None
        or avg_cost is None
        or star_point is None
        or current_price <= 0
        or avg_cost <= 0
        or star_point <= 0
    ):
        return "계산 불가"

    # 1. 현재가 > 평단 < ★
    if current_price < avg_cost and current_price < star_point:
        return "평단, ★지점 매수를 하세요"

    if current_price < avg_cost and current_price >= star_point:
        return "평단 매수만 하세요"

    if current_price >= avg_cost and current_price < star_point:
        return "★지점 매수만 하세요"

    if current_price >= avg_cost and current_price >= star_point:
        return "매수하지 마세요"

    return "계산 불가"

def compute_guide(p, market=None):
    r = active_round(p)
    if r is None or p["config"] is None:
        return None

    cfg = p["config"]
    splits, symbol = cfg["splits"], cfg["symbol"]

    # Yahoo Finance 자동 시세
    if market is None:
        market = fetch_yahoo_market(symbol)

    close = market.get("price")

    # ---------------------------------------------------------
    # MA42 / MA43 / 20거래일 전 종가
    # - 화면 표시용
    # - gap_pct 계산용
    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # 최근 완료 일봉
    # fetch_yahoo_market()에서
    # 장중에는 오늘 봉을 제외하고,
    # 장 마감 후에는 오늘 봉까지 포함한다.
    # ---------------------------------------------------------
    hist_rows = market.get("history", [])

    # 백테스트 전일 기준(shift(1)/shift(20))과 통일: 오늘 날짜 봉(미완성 또는
    # 당일 완료봉)은 신호일이 아니므로 제외하고, 오늘 이전 완료봉만으로
    # MA42/MA43/20일전 종가를 계산한다. 장중·장전·장마감후·휴장일 모두 동일.
    today_str = str(datetime.now(NY_TZ).date())
    ref_rows = [x for x in hist_rows if x["date"] < today_str]

    # ---------------------------------------------------------
    # MA42 / MA43 계산
    # 추추무매 실제 매수 판단용
    # ---------------------------------------------------------
    ma42val = (
        sum(x["close"] for x in ref_rows[-42:]) / 42
        if len(ref_rows) >= 42
        else None
    )

    ma43val = (
        sum(x["close"] for x in ref_rows[-43:]) / 43
        if len(ref_rows) >= 43
        else None
    )

    ma43_gap_pct = (
    (close - ma43val) / ma43val * 100
    if close is not None and ma43val is not None and ma43val > 0
    else None
    )

    # 오늘 기준 20거래일 전 종가 = 오늘 이전 완료봉 기준 [-20]
    # (백테스트 shift(20)과 동일)
    close_20d_ago = (
        ref_rows[-20]["close"]
        if len(ref_rows) >= 20
        else None
    )

    # ---------------------------------------------------------
    # 추추무매 매수 배수 계산
    #
    # 중요:
    # close
    # MA42
    # MA43
    # 20거래일 전 종가
    # 순서대로 정확히 전달
    # ---------------------------------------------------------
    mult, reason, crash_tier = determine_multiplier(
        close,
        ma42val,
        ma43val,
        close_20d_ago
    )

    # =========================================================
    # T값
    # =========================================================
    T = r["T"]
    current_T = T

    phase = phase_of(T, splits)

    is_first_buy = (
        r["qty"] <= 1e-9
        and abs(T) < 1e-9
    )

    # 전량익절 후 재시작일 판정 (이론 0-1):
    # 새 라운드에 아직 거래가 없고, 직전 라운드가 전량익절로 종료됐으며,
    # 종료일이 오늘보다 이전이면 오늘이 재시작일이다.
    today_iso = date.today().isoformat()
    rounds_all = p.get("rounds", [])
    prev_round = rounds_all[-2] if len(rounds_all) >= 2 else None
    prev_closed = (
        prev_round is not None
        and prev_round.get("status") == "closed"
    )
    is_restart_day = (
        is_first_buy
        and prev_closed
        and (prev_round.get("closedDate") or "") < today_iso
    )
    # 전량익절 당일은 재매수하지 않는다 (이론: 당일 재매수 금지)
    is_exit_day = (
        is_first_buy
        and prev_closed
        and prev_round.get("closedDate") == today_iso
    )

    # ---------------------------------------------------------
    # 사이클 첫날은 지표·폭락 여부와 무관하게 1T 한 번만 매수
    # (백테스트와 동일). 단, 전량익절 후 재시작일은 이론 0-1에 따라
    # "1T + 같은 날 일일매수 절반"을 안내하므로 배율을 유지한다.
    # ---------------------------------------------------------
    if is_first_buy and not is_restart_day:
        mult = 1.0
        reason = "최초 매수 (1T 고정)"
        crash_tier = None

    # ---------------------------------------------------------
    # 별지점
    # ---------------------------------------------------------
    star_pct = star_percent(symbol, splits, T)

    star_point = (
        r["avgCost"] * (1 + star_pct / 100)
        if r["avgCost"] > 0
        else None
    )

    buy_trigger = (
        star_point - 0.01
        if star_point is not None
        else None
    )
    # =========================================================
    # 현재가 / 평단 / ★지점 자동 매수 판단
    # =========================================================
    # 백테스트 STAR_BUY_OFFSET: 별 조건은 종가 <= 별지점 - 0.01
    buy_action = determine_buy_action(
        close,
        r["avgCost"],
        buy_trigger,
    )

    divisor_remaining = splits - T

    # ---------------------------------------------------------
    # 1회 매수액
    # 잔금 ÷ (분할수 - T)
    # ---------------------------------------------------------
    base1x = (
        r["cash"] / divisor_remaining
        if divisor_remaining > 0
        else None
    )

    cumulative_buy_amount = (
        r["avgCost"] * r["qty"]
        if r["qty"] > 0
        else 0.0
    )

    target_amount = (
        base1x * mult
        if base1x is not None
        else None
    )

    buy_qty = (
        target_amount / close
        if target_amount is not None
        and close is not None
        and close > 0
        else None
    )

    # ---------------------------------------------------------
    # 폭락장 가격
    # 반드시 MA43 기준
    # ---------------------------------------------------------
    crash_price = None
    crash_qty = None

    if crash_tier is not None and ma43val is not None:
        crash_price = ma43val * (1 - crash_tier / 100)

        if target_amount is not None and crash_price > 0:
            crash_qty = target_amount / crash_price

    s_pct = sell_profit_pct(symbol)

    sell_target = (
        r["avgCost"] * (1 + s_pct / 100)
        if r["avgCost"] > 0
        else None
    )

    quarter_qty = r["qty"] / 4

    final_sell_qty = r["qty"]

    return dict(
    round=r,

    close=close,

    # MA42 / MA43 / 20거래일 전 종가
    ma42=ma42val,
    ma43=ma43val,
    close_20d_ago=close_20d_ago,

    # MA43 대비 괴리율
    gap_pct=ma43_gap_pct,

    mult=mult,
    tier=reason,
    crash_tier=crash_tier,
    crash_price=crash_price,
    crash_qty=crash_qty,

    phase=phase,
    current_T=current_T,

    star_pct=star_pct,
    star_point=star_point,
    buy_trigger=buy_trigger,
    buy_action=buy_action,

    base1x=base1x,
    target_amount=target_amount,
    cumulative_buy_amount=cumulative_buy_amount,

    buy_qty=buy_qty,
    one_time_buy_amount=base1x,

    sell_target=sell_target,
    s_pct=s_pct,
    quarter_qty=quarter_qty,
    final_sell_qty=final_sell_qty,
    remainder_qty=final_sell_qty,

    is_first_buy=is_first_buy,
    is_restart_day=is_restart_day,
    is_exit_day=is_exit_day,
    restart_half_amount=(
        base1x * mult * 0.5
        if (is_restart_day and base1x is not None)
        else None
    ),
    divisor_remaining=divisor_remaining,

    market=market,
)
# =============================================================================
# 포맷 헬퍼
# =============================================================================
def money(n):
    return "—" if n is None else f"${n:,.2f}"
 
def pct(n):
    if n is None:
        return "—"
    sign = "+" if n >= 0 else ""
    return f"{sign}{n:.2f}%"
 
def qty_fmt(n):
    return "—" if n is None else f"{n:,.4f}"
 
def shares_fmt(n):
    """매매 가이드/보유수량처럼 실제 체결 가능한 주식 수량은 문서 규칙(소수점 주식주는
    정수 주수로 '내림')에 따라 정수 내림(버림)으로 표시한다. (기존 round() 반올림 오류 수정)"""
    if n is None:
        return "—"
    if n < 0:
        return f"-{int(-n):,}주"
    return f"{int(n):,}주"
 
# =============================================================================
# 스타일 (라이트/다크 테마 반응형 CSS 변수 사용)
# =============================================================================
CSS = """
<style>
:root {
  --bg: #F8F9FA;
  --surface: #FFFFFF;
  --surface2: #F1F3F5;
  --border: #E9ECEF;
  --text: #212529;
  --text-dim: #6C757D;
  --text-faint: #ADB5BD;
  --buy: #0CA678;
  --profit: #F59F00;
  --loss: #F03E3E;
  --accent: #4C6EF5;
  --card-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}
 
 
.stApp { background: var(--bg); }
.block-container { max-width: 920px; padding-top: 1.2rem; }
h1,h2,h3,h4,p,span,div,label { font-family: -apple-system, "Malgun Gothic", sans-serif; }
 
.round-badge {
  display: inline-block; font-family: ui-monospace, monospace; font-size: 13px; color: var(--accent);
  background: rgba(124,156,255,0.13); border: 1px solid rgba(124,156,255,0.3);
  padding: 4px 12px; border-radius: 20px; margin-bottom: 12px; font-weight: 600;
}
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 18px 20px; margin-bottom: 16px; box-shadow: var(--card-shadow);
}
.card-title { font-size: 15px; font-weight: 700; color: var(--text); margin-bottom: 12px; }
.tag { font-family: ui-monospace, monospace; font-size: 11px; padding: 3px 8px; border-radius: 20px; margin-left: 6px; }
.tag.buy { background: rgba(12,166,120,0.15); color: var(--buy); }
.tag.profit { background: rgba(245,159,0,0.15); color: var(--profit); }
.tag.loss { background: rgba(240,62,62,0.15); color: var(--loss); }
.tag.dim { background: var(--surface2); color: var(--text-dim); }

.tag.market-up {
  background: rgba(154,205,50,0.15);
  color: #00A651;
  border: 1px solid #9ACD32;
}

.tag.market-down {
  background: rgba(255,152,0,0.15);
  color: #F03E3E;
  border: 1px solid #FF9800;
}

.tag.market-blue {
  background: rgba(135,206,235,0.15);
  color: #2196F3;
  border: 1px solid #87CEEB;
}
 
.kv-label { font-size: 12px; color: var(--text-dim); font-weight: 500; }
.kv-value { font-family: ui-monospace, monospace; font-size: 16px; color: var(--text); margin-top: 2px; margin-bottom: 10px; font-weight: 600; }
.note { font-size: 12.5px; color: var(--text-dim); line-height: 1.6; background: var(--surface2); border-radius: 8px; padding: 10px 12px; margin-top: 8px; }
.note.warn { background: rgba(240,62,62,0.12); color: var(--loss); }
 
.tgauge-track { position: relative; height: 10px; border-radius: 5px; overflow: hidden; background: var(--surface2); display: flex; margin-top: 6px;}
.tgauge-zone { height: 100%; }
.tgauge-marker { position: absolute; top: -3px; width: 3px; height: 16px; background: var(--text); border-radius: 2px; }
 
/* Dashboard Card UI */
.portfolio-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--card-shadow);
  transition: transform 0.1s ease;
}
.portfolio-card:hover { border-color: var(--accent); }
.portfolio-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.portfolio-card-title { font-size: 18px; font-weight: 700; color: var(--text); }
</style>
"""
 
def kv(label, value, color=None):
    style = f"color:{color};" if color else ""
    st.markdown(
        f'<div class="kv-label">{label}</div><div class="kv-value" style="{style}">{value}</div>',
        unsafe_allow_html=True,
    )
 
# =============================================================================
# 앱 시작
# =============================================================================
st.markdown(CSS, unsafe_allow_html=True)
 
if "data" not in st.session_state:
    st.session_state.data = load_data()
 
    # 앱을 새로 시작할 때만 전체 포트폴리오 화면에서 시작
    if isinstance(st.session_state.data, dict):
        st.session_state.data["active_portfolio_id"] = None
 
data = st.session_state.data
 
def persist():
    ok = save_data(data)
    return ok
 
# ---- 사이드바: 백업 / 복원 ----
with st.sidebar:
    st.markdown("### ⚙️ 데이터 관리")
 
    if not GITHUB_TOKEN:
        st.warning(
            "⚠️ GITHUB_TOKEN이 설정되지 않아 데이터가 **서버 로컬 파일**에 저장됩니다. "
            "Streamlit Cloud에서는 앱이 재시작되면 기록이 사라질 수 있으니, "
            "Secrets에 토큰을 등록하거나 아래에서 자주 백업해 주세요."
        )
 
    st.download_button(
        "📥 내 데이터 내보내기 (JSON)",
        data=json.dumps(data, ensure_ascii=False, indent=2),
        file_name=f"infbuy_backup_{date.today().isoformat()}.json",
        mime="application/json",
        use_container_width=True,
    )
    uploaded = st.file_uploader("📂 백업 파일 불러오기", type=["json"])
    if uploaded is not None:
        if st.button("🔄 이 파일로 복원", use_container_width=True):
            try:
                uploaded_data = json.load(uploaded)
 
                # 백업 파일을 현재 표준 구조로 변환
                restored_data = normalize_data(uploaded_data)
 
                # 메모리에 적용
                st.session_state.data = restored_data
 
                # GitHub / 로컬 data.json에 저장
                ok = save_data(restored_data)
 
                if ok:
                    st.success("✅ 데이터 복원이 완료되었습니다.")
                    st.rerun()
                else:
                    st.error("❌ 데이터 저장에 실패했습니다. GitHub 설정을 확인해주세요.")
 
            except Exception as e:
                st.error(f"❌ 백업 파일 복원 중 오류: {e}")
 
 
    st.markdown("---")
    st.caption("💡 데이터는 서버의 data.json 파일에 저장됩니다. 주기적으로 백업을 권장합니다.")
 
# 활성 포트폴리오 가져오기
if isinstance(data, dict):
    portfolios = data.get("portfolios", [])
    active_id = data.get("active_portfolio_id", None)
elif isinstance(data, list):
    portfolios = data
    active_id = portfolios[0].get("id") if portfolios else None
else:
    portfolios = []
    active_id = None
 
# 상단 내비게이션 (포트폴리오 선택 및 대시보드 이동)
if active_id is not None:
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.caption("현재 관리에 집중 중인 포트폴리오:")
    with top_col2:
        if st.button("🏠 전체 포트폴리오 보기", use_container_width=True):
            data["active_portfolio_id"] = None
            persist()
            st.rerun()
 
# =============================================================================
# 1. 포트폴리오 대시보드 메인 화면 (active_portfolio_id 가 None 일 때)
# =============================================================================
if active_id is None:
    st.title("📊 추추무매 포트폴리오")
    st.caption("현재 진행 중인 추추무매 포트폴리오를 관리하고 추적하세요.")
 
    # 1. 포트폴리오 목록 카드 뷰
    if portfolios:
        st.markdown("### 📋 오늘의 매수/매도 가이드 요약")
 
        # 2열 카드로 표시
        for idx in range(0, len(portfolios), 2):
            cols = st.columns(2)
            for c_idx, p in enumerate(portfolios[idx:idx+2]):
                with cols[c_idx]:
                    cfg = p.get("config")
                    r = active_round(p)
                    g = None
                    if cfg:
                        try:
                            mkt = fetch_yahoo_market(cfg["symbol"])
                            g = compute_guide(p, mkt)
                        except Exception:
                            g = None
 
                    st.markdown('<div class="portfolio-card">', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="portfolio-card-header">'
                        f'<div class="portfolio-card-title">{p["name"]}</div>'
                        f'<span class="tag buy">{cfg["symbol"] if cfg else "미설정"}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
 
                    if cfg and r:
                        unrealized = (
                            (g["close"] - r["avgCost"]) * r["qty"]
                            if (g and g["close"] and r["qty"] > 0)
                            else None
                        )
 
                        # =========================================================
                        # 사용한 시드 = 현재 평단가 × 현재 보유수량
                        # =========================================================
                        used_seed = (
                            r["avgCost"] * r["qty"]
                            if r["qty"] > 0
                            else 0.0
                        )
 
                        # 전체 시드
                        total_seed = cfg["capital"]
 
                        # 시드 사용률
                        seed_pct = (
                            used_seed / total_seed * 100
                            if total_seed > 0
                            else None
                        )
 
                        c_a, c_b, c_c = st.columns(3)
 
                        with c_a:
                            kv(
                                "평단가",
                                money(r["avgCost"]) if r["avgCost"] > 0 else "—"
                            )
                            kv(
                                "보유수량",
                                shares_fmt(r["qty"])
                            )
 
                        with c_b:
                            st.markdown(
                                f'<div class="kv-value" style="margin-top:2px; margin-bottom:10px;">'
                                f'{money(used_seed)} / {money(total_seed)}'
                                + (
                                    f' ({seed_pct:.1f}%)'
                                    if seed_pct is not None
                                    else ""
                                )
                                + '</div>',
                                unsafe_allow_html=True,
                            )
 
                            kv(
                                "평가손익",
                                money(unrealized),
                                color=(
                                    "var(--profit)"
                                    if (unrealized or 0) >= 0
                                    else "var(--loss)"
                                )
                                if unrealized is not None
                                else None
                            )
 
                        # 폭락장 발동 시에는 단독 매수 주문만 안내한다.
                        if g and g.get("crash_tier") is not None:
                            st.markdown(
                                f'<div class="note warn"><b>🚨 폭락장 대응 (-{g["crash_tier"]}% · {g["mult"]:.2f}T)</b><br>'
                                f'<span style="margin-left:20px;">{money(g["crash_price"])} × {shares_fmt(g["crash_qty"])} 단독 매수</span><br>'
                                f'<b>🔴 매도 20%:</b> {money(g["sell_target"])} × {shares_fmt(g["final_sell_qty"])}</div>',
                                unsafe_allow_html=True,
                            )
                        elif g and g["buy_trigger"]:
                            st.markdown(
                                f'<div class="note"><b>🟢 매수LOC <span class="tag buy">★ {pct(g["star_pct"])}</span></b> <br>'
                                f'<span style="margin-left:40px;"> {money(g["buy_trigger"])}이하 × {shares_fmt(g["buy_qty"])} <br>'
                                f'<b>🟡 매도LOC <span class="tag buy">★ {pct(g["star_pct"])}</span></b><br>'
                                f'<span style="margin-left:40px;">{money(g["star_point"])} × {shares_fmt(g["quarter_qty"])}<br>'
                                f'<b>🔴 매도 20%:</b> {money(g["sell_target"])} × {shares_fmt(g["final_sell_qty"])}</div>',
                                unsafe_allow_html=True,
                            )
                    else:
                        st.info("기본 설정이 필요한 포트폴리오입니다.")
 
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(f"👉 {p['name']} 관리하기", key=f"select_p_{p['id']}", use_container_width=True):
                        data["active_portfolio_id"] = p["id"]
                        persist()
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
 
    # 2. 새로운 포트폴리오 추가 버튼 (+)
    st.markdown("---")
    with st.expander("➕ 새 포트폴리오 추가하기", expanded=not bool(portfolios)):
        with st.form("add_portfolio_form"):
            new_p_name = st.text_input("포트폴리오 이름", placeholder="예: SOXL 서브 계좌, TQQQ 연금계좌")
            p_symbol = st.selectbox("종목", ["TQQQ", "SOXL"])
            p_splits = st.selectbox("분할 수", [20, 40], index=1)
            p_capital = st.number_input("운용 원금 ($)", min_value=0.0, value=20000.0, step=100.0)
            p_compounding = st.radio("라운드 종료 후 재투입 방식", ["복리 (수익 재투입)", "단리 (원금 고정)"]) == "복리 (수익 재투입)"
            add_p_submitted = st.form_submit_button("포트폴리오 생성하기", use_container_width=True)
 
        if add_p_submitted:
            if not new_p_name:
                st.error("포트폴리오 이름을 입력해주세요.")
            else:
                new_id = max([p["id"] for p in portfolios], default=0) + 1
                new_p = {
                    "id": new_id,
                    "name": new_p_name,
                    "config": {
                        "symbol": p_symbol,
                        "splits": p_splits,
                        "capital": p_capital,
                        "compounding": p_compounding
                    },
                    "price_history": [],
                    "rounds": []
                }
                start_new_round(new_p, p_capital, date.today().isoformat())
                data["portfolios"].append(new_p)
                data["active_portfolio_id"] = new_id
                persist()
                st.success(f"'{new_p_name}' 포트폴리오가 성공적으로 생성되었습니다!")
                st.rerun()
 
    st.stop()
 
# =============================================================================
# 2. 특정 포트폴리오 상세 관리 화면
# =============================================================================
current_p = next((p for p in data["portfolios"] if p["id"] == active_id), None)
 
if current_p is None:
    data["active_portfolio_id"] = None
    persist()
    st.rerun()
 
# 설정 없으면 초기화
if current_p["config"] is None:
    st.title(f"⚙️ {current_p['name']} 초기 설정")
    with st.form("setup_form"):
        symbol = st.selectbox("종목", ["TQQQ", "SOXL"])
        splits = st.selectbox("분할 수", [20, 40], index=1)
        capital = st.number_input("운용 원금 ($)", min_value=0.0, value=20000.0, step=100.0)
        compounding = st.radio("라운드 종료 후 재투입 방식", ["복리 (수익 재투입)", "단리 (원금 고정)"]) == "복리 (수익 재투입)"
        submitted = st.form_submit_button("시작하기", use_container_width=True)
    if submitted:
        current_p["config"] = {"symbol": symbol, "splits": splits, "capital": capital, "compounding": compounding}
        start_new_round(current_p, capital, date.today().isoformat())
        persist()
        st.rerun()
    st.stop()
 
cfg = current_p["config"]
r = active_round(current_p)
 
if r is None:
    start_new_round(current_p, cfg["capital"], date.today().isoformat())
    persist()
    st.rerun()
 
try:
    market = fetch_yahoo_market(cfg["symbol"])
    market_error = None
except Exception as exc:
    market = {
        "symbol": cfg["symbol"],
        "price": None,
        "ma20": None,
        "gap_pct": None,
        "previous_close": None,
        "timestamp": None,
        "fetched_at": None,
        "source_label": "Yahoo 연결 실패",
        "market_open": False,
        "history": [],
    }
    market_error = str(exc)
 
guide = compute_guide(current_p, market)
 
# 포트폴리오 상단 콕핏
st.title(f"📈 {current_p['name']}")
if market_error:
    st.error(
        f"Yahoo Finance 시세를 불러오지 못했습니다: {market_error}"
    )
 
# 누적 실현손익: 종료된 라운드 + 진행 중인 라운드에서 이미 발생한 쿼터매도 실현손익까지 포함
closed_realized = sum(x.get("realizedPnl", 0) for x in current_p["rounds"] if x["status"] == "closed")
active_realized = sum(t["pnl"] for t in r["trades"] if t.get("pnl") is not None) if r else 0.0
total_realized = closed_realized + active_realized
 
unrealized = None
if guide and guide["close"] is not None and r["qty"] > 0:
    unrealized = (guide["close"] - r["avgCost"]) * r["qty"]
 
# -----------------------------------------------------------------
# 총자산 = 잔금 + 보유 평가금액 + 미편입 실현수익(쿼터매도 익절 초과분)
# 쿼터매도 익절 초과분은 문서 규칙상 잔금에 편입되지 않으므로
# 이 항목을 더해야 증권사 실제 잔고와 대조된다.
# -----------------------------------------------------------------
pending_profit = unbanked_profit(r)
position_value = (
    guide["close"] * r["qty"]
    if guide and guide["close"] is not None and r["qty"] > 0
    else 0.0
)
total_asset = r["cash"] + position_value + pending_profit
 
st.markdown(
    f'<div class="round-badge">{cfg["symbol"]} · {cfg["splits"]}분할 · Round #{r["id"]} · {phase_of(guide["current_T"], cfg["splits"]) if guide else "—"}</div>',
    unsafe_allow_html=True,
)
 
# ------------------ Modified Cockpit Columns ------------------
c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1:
    kv("평단가", money(r["avgCost"]) if r["avgCost"] > 0 else "—")
with c2:
    kv("보유수량", shares_fmt(r["qty"]))
with c3:
    # 잔금은 실제 추적되는 현금(raw cash)을 그대로 사용한다.
    kv("잔금", money(r["cash"]))
with c4:
    kv("미실현손익", money(unrealized), color=("var(--profit)" if (unrealized or 0) >= 0 else "var(--loss)") if unrealized is not None else None)
with c5:
    kv("누적 실현손익", money(total_realized), color="var(--profit)" if total_realized >= 0 else "var(--loss)")
with c6:
    kv("총자산", money(total_asset), color="var(--accent)")
 
if pending_profit > 0:
    st.caption(
        f"ℹ️ 잔금에는 쿼터매도 익절 초과분 {money(pending_profit)} 이 포함되어 있지 않습니다 "
        f"(문서 규칙). 총자산에는 포함되며, 라운드 종료 시 복리로 재투입됩니다."
    )
# --------------------------------------------------------------
 
splits = cfg["splits"]
T = guide["current_T"] if guide else 0.0
pos = max(0, min(100, T / splits * 100))
z1 = (splits / 2) / splits * 100
z2 = ((splits - 1) - splits / 2) / splits * 100
z3 = 100 - z1 - z2
st.markdown(
    f"""
    <div class="tgauge-track">
      <div class="tgauge-zone" style="width:{z1}%; background:rgba(12,166,120,0.28);"></div>
      <div class="tgauge-zone" style="width:{z2}%; background:rgba(245,159,0,0.28);"></div>
      <div class="tgauge-zone" style="width:{z3}%; background:rgba(240,62,62,0.30);"></div>
      <div class="tgauge-marker" style="left:{pos}%;"></div>
    </div>
    <div style="font-family: ui-monospace, monospace; font-size:11px; color:var(--text-faint); margin-top:4px;">
      T = {T:.2f} / {splits} · 전반전 / 후반전 / 소진모드
    </div>
    """,
    unsafe_allow_html=True,
)
 
st.markdown("<br>", unsafe_allow_html=True)
 
# 탭 메뉴
tab_guide, tab_market, tab_trade, tab_history, tab_settings = st.tabs(
    ["오늘의 가이드", "자동 시세", "매매기록", "히스토리", "설정"]
)
 
# ---------------- 오늘의 가이드 ----------------
with tab_guide:
    g = guide
    st.markdown('<div class="card">', unsafe_allow_html=True)
    # 시세 상태별 색상
    tier = g["tier"]

    if "MA42 위 + 20일전 종가 위" in tier:
        market_tag_class = "market-up"
    elif "MA42 위 + 20일전 종가 아래" in tier:
        market_tag_class = "market-down"
    elif "MA42 아래 + 20일전 종가 위" in tier:
        market_tag_class = "market-down"
    elif "MA42 아래 + 20일전 종가 아래" in tier:
        market_tag_class = "market-blue"
    else:
        # 폭락장 등 기존 색상 유지
        market_tag_class = (
            "loss" if g["mult"] >= 2
            else "buy" if g["mult"] < 1
            else "dim"
        )

    st.markdown(
        f'<div class="card-title">시세 상태 '
        f'<span class="tag {market_tag_class}">{g["tier"]}</span></div>',
        unsafe_allow_html=True,
    )
    cc1, cc2, cc3, cc4, cc5 = st.columns(5)

    with cc1:
        kv(
            "현재 Yahoo 가격",
            money(g["close"]) if g["close"] is not None else "가격 확인 실패"
        )

    with cc2:
        kv(
            "MA42",
            money(g["ma42"])
            if g["ma42"] is not None
            else f"데이터 {len(current_p['price_history'])}/42"
        )

    with cc3:
        kv(
            "MA43",
            money(g["ma43"])
            if g["ma43"] is not None
            else f"데이터 {len(current_p['price_history'])}/43"
        )

    with cc4:
        kv(
            "MA43 대비 괴리율",
            pct(g["gap_pct"])
        )

    with cc5:
        kv(
            "오늘 적용 배수",
            f'{g["mult"]:.2f}T',
            color="var(--accent)"
        )

    st.markdown("</div>", unsafe_allow_html=True)
 
    st.markdown('<div class="card">', unsafe_allow_html=True)
    used_seed = g["cumulative_buy_amount"]
    total_seed = cfg["capital"]
    seed_pct = (used_seed / total_seed * 100) if total_seed else None
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        kv(
            "사용한 시드",
            f'{money(used_seed)} / {money(total_seed)}' + (f' ({seed_pct:.1f}%)' if seed_pct is not None else ""),
        )
    with sc2:
        kv("T 값", f'{g["current_T"]:.3f}회', color="var(--accent)")
    with sc3:
        # 별값 > 0 = 수익 쪽 기준선(초록) / 별값 < 0 = 손절·리스크 관리 기준선(빨강)
        kv(
            "★ Star 값",
            pct(g["star_pct"]),
            color="var(--buy)" if g["star_pct"] is not None and g["star_pct"] >= 0 else "var(--loss)",
        )
    st.markdown("</div>", unsafe_allow_html=True)
 
    if g["divisor_remaining"] <= 0 or g["phase"] == "소진모드":
        st.markdown(
            f"""<div class="card"><div class="card-title">매수 가이드 <span class="tag loss">소진모드</span></div>
            <div class="note warn">T값이 {cfg['splits']-1} 초과(소진모드 구간)입니다. 이 앱은 <b>일반모드</b> 로직만 지원하므로,
            소진모드(리버스모드) 매수/매도는 별도 기준으로 직접 판단해 주세요.</div></div>""",
            unsafe_allow_html=True,
        )

    elif g["is_first_buy"]:
        # 사이클 첫날은 하루에 한 종류만 매수한다 (이론 0-2):
        # 폭락장 카드보다 먼저 판정한다.
        if g["is_restart_day"]:
            half_amt = g["restart_half_amount"]
            half_qty = (half_amt / g["close"]) if (half_amt and g["close"]) else None
            first_qty = (g["base1x"] / g["close"]) if (g["base1x"] and g["close"]) else None
            if g["crash_tier"] is not None:
                half_label = f'② 폭락장 대응 절반 (-{g["crash_tier"]}%)'
            else:
                half_label = f'② 일일매수 절반 ({g["mult"]:.2f}T × 0.5)'
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">매수 가이드 <span class="tag buy">전량익절 후 재시작</span></div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="note">사이클 종료 후 첫날입니다. <b>1T 매수 + 같은 날 일일매수 절반</b>을 종가로 매수하세요 (이론 0-1). '
                '오늘 이 두 건이 하나의 "첫날매수"이므로 다른 매수는 하지 않습니다 (이론 0-2).</div>',
                unsafe_allow_html=True,
            )
            b1, b2 = st.columns(2)
            with b1:
                kv("① 첫 매수 1T (종가)", f'{money(g["base1x"])} × {shares_fmt(first_qty)}')
            with b2:
                kv(f'{half_label} (종가)', f'{money(half_amt)} × {shares_fmt(half_qty)}')
            st.markdown("</div>", unsafe_allow_html=True)
        elif g["is_exit_day"]:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">매수 가이드 <span class="tag dim">전량익절일</span></div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="note">오늘 전량익절로 사이클이 종료됐습니다. <b>당일은 재매수하지 않습니다.</b> '
                '다음 거래일부터 새 사이클(1T + 일일매수 절반)로 시작하세요.</div>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            low = g["close"] * 1.10 if g["close"] is not None else None
            high = g["close"] * 1.15 if g["close"] is not None else None
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">매수 가이드 <span class="tag buy">최초 매수</span></div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="note">보유수량이 없는 최초 매수입니다. 전일 종가 대비 <b>10~15% 위</b> 가격부터 아래로 '
                f'LOC 매수를 걸어 목표금액({money(g["target_amount"])})을 소진하세요.</div>',
                unsafe_allow_html=True,
            )
            b1, b2 = st.columns(2)
            with b1:
                kv("권장 시작가 (10~15% 위)", f'{money(low)} ~ {money(high)}' if low else "종가 입력 필요")
            with b2:
                kv(f'오늘 매수 목표금액 ({g["mult"]:.2f}T)', money(g["target_amount"]))
            st.markdown("</div>", unsafe_allow_html=True)
    elif g["crash_tier"] is not None:
        # -----------------------------------------------------------------
        # 폭락장 대응: 문서 규칙상 가장 깊은 단계 1개만 단독 실행하고,
        # 일반 종가 매수/매도(평단매수·별지점매수)는 무시한다.
        # 따라서 목표금액을 절반으로 쪼개지 않는다.
        # -----------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="card-title">매수 가이드 <span class="tag loss">🚨 폭락장 대응 · {g["mult"]:.2f}T</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="kv-value" style="font-size:17px; margin-top:8px; line-height:1.9;">'
            f'<span style="font-size:9pt; color:#000000; font-weight:bold;">MA43 대비 -{g["crash_tier"]}% 단독 매수</span> '
            f'<span style="font-size:15pt;color:#F03E3E;">{money(g["crash_price"])} × {shares_fmt(g["crash_qty"])}</span>'
            f'<br><span style="font-size:9pt; color:var(--text-faint); font-weight:bold;">'
            f'목표금액 {money(g["target_amount"])} (1T {money(g["base1x"])} × {g["mult"]:.2f})</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="note warn">폭락장 대응은 앞선 모든 로직에 <b>최우선</b>하며, 가장 깊은 단계 1개만 실행합니다. '
            '오늘은 평단매수 / ★지점매수를 하지 않습니다. '
            '이 매수로 일일매수금과 T값을 예외적으로 초과할 수 있으며, T가 빠르게 올라 소진(리버스)모드가 앞당겨질 수 있습니다.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        # 문서 규칙: 목표금액을 항상 절반씩 나눠 "평단가"와 "★지점(별지점)"에 각각 매수한다.
        # (1.4976T / 0.7356T / 0.6831T / 1.0003T 로 목표금액 자체가 달라질 뿐, 절반씩 나누는 방식은 동일)
        half_amount = g["target_amount"] / 2 if g["target_amount"] is not None else None
        crash_rows = crash_tier_table(g["ma43"], g["base1x"])

        qty_avgcost = (
            half_amount / r["avgCost"]
            if half_amount is not None and r["avgCost"] > 0
            else None
        )
        qty_starpoint = (
            half_amount / g["buy_trigger"]
            if half_amount is not None and g["buy_trigger"]
            else None
        )
        current_price_qty = g["buy_qty"]
 
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="card-title">매수 가이드 LOC <span class="tag buy">★ {pct(g["star_pct"])}</span> '
            f'<span class="tag dim">{g["phase"]} · {g["mult"]:.3f}T</span></div>',
            unsafe_allow_html=True,
        )
        
        st.markdown(
            f"""
            <div style="
                padding: 12px 12px;
                margin: 10px 0 12px 0;
                border-radius: 10px;
                border: 1px solid rgba(128,128,128,0.25);
                font-size: 18px;
                font-weight: 700;
            ">
                📌 <span style="font-size: 13px;">
                    {g["buy_action"]}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        

 
        st.markdown(
            f'<div class="kv-value" style="font-size:17px; margin-top:8px; line-height:1.9;">'
            f'<span style="font-size:9pt; color:#000000; font-weight:bold;">평단매수</span> '
            f'<span style="font-size:14pt;color:#4DABF7;">{money(r["avgCost"])} × {shares_fmt(qty_avgcost)}</span>'
            f'<span style="margin-left:24px; font-size:9pt; color:#000000; font-weight:bold;">★매수(별지점)</span> '
            f'<span style="font-size:14pt;color:#B197FC;">{money(g["buy_trigger"])} × {shares_fmt(qty_starpoint)}</span>'
            f'<br><span style="font-size:9pt; color:var(--text-faint); font-weight:bold;">'
            f'참고: 현재가 기준 목표금액 전액매수 시 → {money(g["close"])} × {shares_fmt(current_price_qty)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
 
        if crash_rows:
            st.markdown(
                '<div class="kv-label" style="margin-top:6px;">+@ 폭락장 매수 (발동 시 해당 단계 1개만 단독 실행)</div>',
                unsafe_allow_html=True,
            )
            crash_lines = "".join(
                f'<div style="display:flex; justify-content:space-between; '
                f'font-family: ui-monospace, monospace; font-size:13px; padding:3px 0; color:var(--loss);">'
                f'<span>- {row["tier"]}% ({row["mult"]:.2f}T)</span><span>{money(row["price"])} × {shares_fmt(row["qty"])}</span></div>'
                for row in crash_rows
            )
            st.markdown(f'<div class="note">{crash_lines}</div>', unsafe_allow_html=True)
 
        st.markdown(
            f'<div class="note">오늘 목표매수금액 {money(g["target_amount"])} 을 절반씩 나누어 '
            f'평단가 {money(r["avgCost"])} 와 매수기준가(★지점) {money(g["buy_trigger"])} 에  LOC 매수합니다. </div>',
          
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
 
    if r["qty"] > 0:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="card-title">매도 가이드 LOC <span class="tag profit">★ {pct(g["star_pct"])}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="kv-label" style="margin-top:4px;font-weight:bold;">쿼터매도 (종가 LOC · 보유수량의 25%)</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="kv-value" style="font-size:19px; color:var(--profit);">'
            f'{money(g["star_point"])} × {shares_fmt(g["quarter_qty"])}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="kv-label" style="margin-top:6px;font-weight:bold;">지정가 전량익절 +{g["s_pct"]}% (트레일링 없음)</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="kv-value" style="font-size:19px; color:var(--profit);">'
            f'{money(g["sell_target"])} × {shares_fmt(g["final_sell_qty"])}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="note">지정가 +{g["s_pct"]}% 익절은 <b>전량</b>이며 장중 매도 최우선입니다. 체결되면 사이클이 종료됩니다.<br>'
            f'쿼터매도는 별지점에 종가(LOC)로 걸어둡니다.<br>'
            f'※ 두 주문은 시점(장중 지정가 / 종가 LOC)이 다르므로, 증권사에서 주문 가능 수량이 겹치면 지정가 전량익절을 우선하세요.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
 
# ---------------- 자동 시세 ----------------
with tab_market:
    m = market
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="card-title">Yahoo Finance 자동 시세 '
        f'<span class="tag buy">자동 갱신</span></div>',
        unsafe_allow_html=True,
    )
 
    cc1, cc2, cc3, cc4, cc5, cc6 = st.columns(6)
    with cc1:
        kv("현재 가격", money(m["price"]))
    with cc2:
        kv(
            "MA43",
            money(guide["ma43"])
            if guide and guide["ma43"] is not None
            else "데이터 부족"
        )
    with cc3:
        kv(
            "MA43 괴리율",
            pct(guide["gap_pct"]) if guide else "데이터 부족"
        )
    with cc4:
        kv("적용 배수", f'{guide["mult"]:.2f}T' if guide else "—")
    with cc5:
        kv("시장 상태", "장중" if m["market_open"] else "장외/휴장")
 
    st.markdown(
        f'<div class="note">데이터: <b>{m["source_label"]}</b> · '
        f'마지막 업데이트: {m["fetched_at"][:19].replace("T", " ") if m["fetched_at"] else "—"} '
        f'(미국 동부시간 기준)</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
 
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">최근 20일 종가 / MA20 계산에 사용</div>', unsafe_allow_html=True)
 
    hist_rows = m.get("history", [])
    if hist_rows:
        hist_df = pd.DataFrame(hist_rows)
        hist_df = hist_df.rename(
            columns={"date": "날짜", "close": "종가"}
        )
        hist_df["종가"] = hist_df["종가"].map(lambda x: round(float(x), 2))
        st.dataframe(
            hist_df.tail(20).iloc[::-1],
            use_container_width=True,
            hide_index=True,
        )
 
    st.markdown("</div>", unsafe_allow_html=True)
 
    if st.button("🔄 지금 Yahoo 시세 새로고침", use_container_width=True):
        fetch_yahoo_market.clear()
        st.rerun()
 
# ---------------- 매매기록 ----------------
with tab_trade:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<div class="card-title">매매 기록 입력 · Round #{r["id"]}</div>', unsafe_allow_html=True)
 
        # =========================================================
    # Excel 거래내역 가져오기
    # =========================================================
    st.markdown("---")
    st.markdown("### 📊 Excel 거래내역 가져오기")
 
    st.caption(
        "Excel의 거래내역을 현재 라운드에 처음부터 다시 적용합니다. "
        "기존 거래기록이 있는 경우 기존 기록은 Excel 내용으로 교체됩니다."
    )
 
    excel_file = st.file_uploader(
        "Excel 파일 선택",
        type=["xlsx", "xls"],
        key=f"excel_trade_upload_{r['id']}",
    )
 
    confirm_excel_import = st.checkbox(
        "현재 라운드의 기존 거래기록을 Excel 내용으로 교체하겠습니다.",
        key=f"confirm_excel_import_{r['id']}",
    )
 
    if excel_file is not None:
        try:
            preview_df = pd.read_excel(excel_file)
 
            st.caption(
                f"총 {len(preview_df)}개 거래를 읽었습니다."
            )
 
            st.dataframe(
                preview_df,
                use_container_width=True,
                hide_index=True,
            )
 
        except Exception as e:
            st.error(f"Excel 파일을 읽을 수 없습니다: {e}")
 
    if st.button(
        "📥 Excel 거래내역 가져오기",
        key=f"import_excel_btn_{r['id']}",
        use_container_width=True,
        type="primary",
    ):
        if excel_file is None:
            st.error("먼저 Excel 파일을 선택해주세요.")
 
        elif not confirm_excel_import:
            st.error(
                "기존 거래기록을 Excel 내용으로 교체한다는 것을 확인해주세요."
            )
 
        else:
            ok, result = import_trades_from_excel(
                current_p,
                r,
                excel_file,
            )
 
            if ok:
                persist()
 
                st.success(
                    f"✅ Excel 거래내역 {result}건을 가져왔습니다. "
                    f"T / 평단 / 잔금 / 보유수량을 다시 계산했습니다."
                )
 
                st.rerun()
 
            else:
                st.error(
                    f"❌ Excel 거래내역 가져오기 실패: {result}"
                )
 
    st.markdown("---")
    
 
    trade_type_label = st.radio(
        "거래 유형", ["매수", "쿼터매도", "지정가매도 (전량, 라운드 종료)"], horizontal=True
    )
    type_map = {"매수": "buy", "쿼터매도": "quarter_sell", "지정가매도 (전량, 라운드 종료)": "final_sell"}
    ttype = type_map[trade_type_label]
 
    default_price = 0.0
    default_qty = 0.0
    if ttype == "buy":
        if guide and guide["buy_trigger"] is not None:
            default_price = round(guide["buy_trigger"], 2)
        elif guide and guide["close"] is not None:
            default_price = round(guide["close"] * 1.1, 2)
    elif ttype == "quarter_sell":
        default_qty = float(int(r["qty"] / 4))  # 정수 내림 (문서 규칙)
        if guide and guide["star_point"] is not None:
            default_price = round(guide["star_point"], 2)
    else:
        default_qty = float(int(r["qty"]))  # 정수 내림 (문서 규칙)
        if guide and guide["sell_target"] is not None:
            default_price = round(guide["sell_target"], 2)
 
    with st.form("trade_form"):
        t_date = st.date_input("날짜", value=date.today(), key="t_date")
        tc1, tc2 = st.columns(2)
        with tc1:
            t_price = st.number_input("체결가 ($)", min_value=0.0, value=default_price, step=0.01, format="%.2f")
        with tc2:
            t_qty = st.number_input("체결수량", min_value=0.0, value=default_qty, step=0.0001, format="%.4f")
 
        t_delta = None
        if ttype == "buy":
            amount_preview = t_price * t_qty
            suggested_t = None
            if guide and guide["target_amount"] and guide["target_amount"] > 0:
                suggested_t = guide["mult"] * (amount_preview / guide["target_amount"])
            t_delta = st.number_input(
                "T 증가값 (자동 제안값, 필요시 직접 수정)",
                value=round(suggested_t, 4) if suggested_t is not None else 0.0,
                step=0.0001, format="%.4f",
            )
            st.markdown(
                f'<div class="note">제안값 = 오늘 배수({guide["mult"] if guide else 1.0:.2f}T) × (체결금액 ÷ 오늘 목표매수금액).</div>',
                unsafe_allow_html=True,
            )
        elif ttype == "quarter_sell":
            preview_ratio = (t_qty / r["qty"]) if r["qty"] > 0 and t_qty > 0 else None
            preview_t_after = (r["T"] * (1 - preview_ratio)) if preview_ratio is not None else None
            st.markdown(
                '<div class="note">쿼터매도 규칙: T값은 실제 매도비율 기준으로 갱신됩니다 '
                '(T_after = 직전T × (1 − 매도수량÷매도전보유수량)). 정확히 25%를 매도하면 직전T × 0.75와 같아집니다. '
                '평단은 변하지 않습니다. '
                '체결가가 평단가 이상이면(익절) 원가만 잔금에 편입되고 초과분은 실현손익으로 별도 기록되며, '
                '체결가가 평단가 미만이면(손절) 매도대금 전액이 잔금에 편입됩니다.'
                + (
                    f'<br>이번 매도비율: {preview_ratio*100:.1f}% · 매도 후 예상 T = {preview_t_after:.3f}'
                    if preview_ratio is not None else ""
                )
                + '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="note">지정가매도(전량)는 라운드를 종료합니다. 실현손익이 집계되고, '
                        '잔금과 그동안 편입되지 않았던 쿼터매도 익절 초과분을 합산해 새 라운드가 자동으로 시작됩니다.</div>', unsafe_allow_html=True)
 
        submitted = st.form_submit_button("기록 추가", use_container_width=True)
 
    if submitted:
        if t_price <= 0 or t_qty <= 0:
            st.error("가격과 수량을 올바르게 입력하세요.")
        elif ttype in ("quarter_sell", "final_sell") and t_qty > r["qty"] + 1e-9:
            st.error("보유수량보다 많습니다.")
        elif ttype == "final_sell" and t_qty < r["qty"] - 1e-9:
            st.error(f"지정가매도(전량)는 보유수량 전부를 매도해야 합니다. 현재 보유수량: {r['qty']:g}주")
        else:
            d_str = t_date.isoformat()
            if ttype == "buy":
                apply_buy(r, d_str, t_price, t_qty, t_delta or 0.0)
            elif ttype == "quarter_sell":
                apply_quarter_sell(r, d_str, t_price, t_qty)
            else:
                apply_final_sell(current_p, r, d_str, t_price, t_qty)
            persist()
            st.success("기록이 추가되었습니다.")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
 
# ---------------- 히스토리 (거래 삭제 기능 포함) ----------------
with tab_history:
    if not current_p["rounds"]:
        st.caption("기록이 없습니다.")
    else:
        # ---- 그래프 1: 평단가 vs 현재가 ----
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📈 평단가 vs 현재가 (현재 라운드)</div>', unsafe_allow_html=True)
        hist_rows_all = market.get("history", []) if market else []
        if hist_rows_all and r["trades"]:
            price_df = pd.DataFrame(hist_rows_all)
            price_df["date"] = pd.to_datetime(price_df["date"])
            price_df = price_df.sort_values("date").rename(columns={"close": "현재가"})
 
            trade_df = pd.DataFrame([{"date": t["date"], "평단가": t["avgAfter"]} for t in r["trades"]])
            trade_df["date"] = pd.to_datetime(trade_df["date"])
            trade_df = trade_df.sort_values("date")
 
            merged = pd.merge_asof(price_df, trade_df, on="date", direction="backward")
            chart_df = merged[["date", "현재가", "평단가"]].dropna(subset=["현재가"]).set_index("date")
            st.line_chart(chart_df, use_container_width=True)
        else:
            st.caption("표시할 데이터가 부족합니다 (현재 라운드 거래 기록 또는 시세 데이터 필요).")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("#### 라운드별 상세 기록")
        st.caption("완료된 라운드를 포함해 모든 라운드 기록을 아래에서 펼쳐볼 수 있습니다.")
         
        for rr in reversed(current_p["rounds"]):
                    if rr["status"] == "active":
                        status_html = '<span class="tag dim">진행중</span>'
                    else:
                        pnl = rr.get("realizedPnl", 0)
                        status_html = f'<span class="tag {"profit" if pnl>=0 else "loss"}">{"수익" if pnl>=0 else "손절"} {money(pnl)}</span>'
                    period = rr["startDate"] + (f' ~ {rr["closedDate"]}' if rr.get("closedDate") else "")
                    expander_label = f'Round #{rr["id"]}  ·  {period}  ·  {"진행중" if rr["status"]=="active" else ("수익 " + money(rr.get("realizedPnl", 0)) if rr.get("realizedPnl", 0) >= 0 else "손절 " + money(rr.get("realizedPnl", 0)))}'
         
                    with st.expander(expander_label, expanded=(rr["status"] == "active")):
                        st.markdown('<div class="round-block">', unsafe_allow_html=True)
                        st.markdown(
                            f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">'
                            f'<div><b>Round #{rr["id"]}</b> <span style="color:var(--text-faint); font-size:12px;">{period}</span></div>'
                            f'<div>{status_html}</div></div>',
                            unsafe_allow_html=True,
                        )
                        if rr.get("finalCapital") is not None:
                            st.caption(
                                f"라운드 종료 시 다음 라운드로 이월된 금액(잔금+미편입 쿼터매도 익절 초과분): {money(rr['finalCapital'])}"
                            )
                        if rr["trades"]:
                            rows = []
                            type_label = {"buy": "매수", "quarter_sell": "쿼터매도", "final_sell": "지정가매도"}
                            for idx, t in enumerate(rr["trades"]):
                                rows.append({
                                    "ID": t.get("id", idx + 1),
                                    "날짜": t["date"],
                                    "유형": type_label[t["type"]],
                                    "가격": round(t["price"], 2),
                                    "수량": round(t["qty"], 4),
                                    "금액": round(t["amount"], 2),
                                    "T": round(t["tAfter"], 3),
                                    "평단": round(t["avgAfter"], 2),
                                    "손익": (round(t["pnl"], 2) if t["pnl"] is not None else "—"),
                                })
                            display_df = pd.DataFrame(rows)
        
                            # 화면 표시 순서만 최신 날짜 → 과거 날짜
                            display_df["_date_sort"] = pd.to_datetime(
                                display_df["날짜"],
                                errors="coerce"
                            )
        
                            display_df = (
                                display_df
                                .sort_values(
                                    "_date_sort",
                                    ascending=False,
                                    kind="stable"
                                )
                                .drop(columns="_date_sort")
                                .reset_index(drop=True)
                            )
        
                            st.dataframe(
                                display_df,
                                use_container_width=True,
                                hide_index=True
                            )
         
                            # 거래 기록 삭제 UI (진행 중인 라운드는 개별 수정 가능)
                            if rr["status"] == "active":
                                st.markdown("---")
                                del_col1, del_col2 = st.columns([3, 1])
                                with del_col1:
                                    del_trade_id = st.selectbox(
                                        "삭제할 매매 기록 선택",
                                        options=[t.get("id", i+1) for i, t in enumerate(rr["trades"])],
                                        format_func=lambda tid: next(f"ID {tid}: {t['date']} {type_label[t['type']]} ({money(t['price'])}, {t['qty']}주)" for i, t in enumerate(rr["trades"]) if t.get("id", i+1) == tid),
                                        key=f"del_trade_sel_{rr['id']}"
                                    )
                                with del_col2:
                                    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                                    if st.button("🗑️ 기록 삭제", key=f"btn_del_trade_{rr['id']}", use_container_width=True):
                                        rr["trades"] = [t for i, t in enumerate(rr["trades"]) if t.get("id", i+1) != del_trade_id]
                                        recalculate_round(rr, rr["startCapital"])
                                        persist()
                                        st.success("선택한 거래가 삭제되고 라운드 상태가 재계산되었습니다.")
                                        st.rerun()
                        else:
                            st.caption("거래 기록 없음")
                        st.markdown("</div>", unsafe_allow_html=True)
                        
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">전체 요약</div>', unsafe_allow_html=True)
        h1, h2 = st.columns(2)
        with h1:
            kv("완료된 라운드", str(sum(1 for x in current_p["rounds"] if x["status"] == "closed")))
        with h2:
            kv("누적 실현손익", money(total_realized), color="var(--profit)" if total_realized >= 0 else "var(--loss)")
        st.markdown("</div>", unsafe_allow_html=True)


        # ---- 그래프 2: 라운드별 수익금 / 수익률 ----
        closed_rounds_for_chart = [x for x in current_p["rounds"] if x["status"] == "closed"]
        if closed_rounds_for_chart:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">💰 라운드별 수익금 / 수익률</div>', unsafe_allow_html=True)
            perf_rows = []
            cum = 0.0
            for rr2 in closed_rounds_for_chart:
                pnl = rr2.get("realizedPnl", 0.0)
                cum += pnl
                ret_pct = (pnl / rr2["startCapital"] * 100) if rr2.get("startCapital") else None
                perf_rows.append({
                    "라운드": f'#{rr2["id"]}',
                    "수익금": round(pnl, 2),
                    "누적수익금": round(cum, 2),
                    "수익률(%)": round(ret_pct, 2) if ret_pct is not None else None,
                })
            perf_df = pd.DataFrame(perf_rows).set_index("라운드")
 
            pc1, pc2 = st.columns(2)
            with pc1:
                st.caption("라운드별 수익금 ($)")
                st.bar_chart(perf_df[["수익금"]], use_container_width=True)
            with pc2:
                st.caption("라운드별 수익률 (%)")
                st.bar_chart(perf_df[["수익률(%)"]], use_container_width=True)
            st.caption("누적 실현손익 추이")
            st.line_chart(perf_df[["누적수익금"]], use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
 

 
        
 
# ---------------- 설정 ----------------
with tab_settings:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">포트폴리오 설정</div>', unsafe_allow_html=True)
    with st.form("settings_form"):
        p_name = st.text_input("포트폴리오 이름", value=current_p["name"])
        sc1, sc2 = st.columns(2)
        with sc1:
            n_symbol = st.selectbox("종목", ["TQQQ", "SOXL"], index=["TQQQ", "SOXL"].index(cfg["symbol"]))
        with sc2:
            n_splits = st.selectbox("분할 수", [20, 40], index=[20, 40].index(cfg["splits"]))
        n_capital = st.number_input("기준 원금 ($, 단리 모드에서 다음 라운드 시작자본)", min_value=0.0, value=float(cfg["capital"]), step=100.0)
        n_compounding = st.radio(
            "라운드 종료 후 재투입 방식", ["복리", "단리"], index=0 if cfg["compounding"] else 1
        ) == "복리"
        save_submit = st.form_submit_button("저장", use_container_width=True)
    if save_submit:
        current_p["name"] = p_name
        cfg["symbol"] = n_symbol
        cfg["splits"] = n_splits
        cfg["capital"] = n_capital
        cfg["compounding"] = n_compounding
 
        ok = persist()
 
        if ok:
            st.success("✅ 저장되었습니다.")
            st.rerun()
        else:
            st.error("❌ 저장에 실패했습니다. GitHub 설정을 확인해주세요.")
 
 
st.markdown("</div>", unsafe_allow_html=True)
 
 
# ---------------------------------------------------------
# 포트폴리오 삭제
# ---------------------------------------------------------
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">🗑️ 이 포트폴리오 삭제</div>', unsafe_allow_html=True)
 
st.markdown(
    '<div class="note warn">이 포트폴리오의 모든 데이터가 삭제됩니다. 되돌릴 수 없습니다.</div>',
    unsafe_allow_html=True
)
 
confirm_del_p = st.checkbox(
    "정말로 이 포트폴리오를 삭제하겠습니다",
    key="chk_del_p"
)
 
if st.button(
    "포트폴리오 삭제",
    disabled=not confirm_del_p,
    type="primary"
):
    data["portfolios"] = [
        p for p in data["portfolios"]
        if p["id"] != active_id
    ]
 
    data["active_portfolio_id"] = None
 
    persist()
    st.rerun()
 
st.markdown("</div>", unsafe_allow_html=True)
 
