"""
추추무매
Streamlit 앱 — app.py

실행: streamlit run app.py
배포: 이 파일 + requirements.txt 를 GitHub 저장소에 올리고
      streamlit.io/cloud 에서 저장소를 연결하면 바로 웹페이지가 됩니다.

거래 데이터는 data.json 파일에 저장되고, 시세는 Yahoo Finance에서 자동 조회됩니다.
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

def load_data():
    loaded = github_load_file("data.json", [])
    if isinstance(loaded, list):
        return sorted(loaded, key=lambda x: str(x.get("Date", "")), reverse=True)
    return []

def save_data(data):
    sorted_data = sorted(data, key=lambda x: str(x.get("Date", "")), reverse=True)
    return github_save_file("data.json", sorted_data)


# 데이터 구조 확장: 다중 포트폴리오(portfolios) 지원
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

def load_data():
    d = github_load_file(DATA_FILE, None)
    if d is None:
        return json.loads(json.dumps(DEFAULT_DATA))
    # 이전 단일 포트폴리오 데이터 마이그레이션 처리
    if "portfolios" not in d:
        old_cfg = d.get("config")
        old_hist = d.get("price_history", [])
        old_rounds = d.get("rounds", [])
        d = {
            "portfolios": [
                {
                    "id": 1,
                    "name": "기본 포트폴리오",
                    "config": old_cfg,
                    "price_history": old_hist,
                    "rounds": old_rounds
                }
            ],
            "active_portfolio_id": 1
        }
    return d

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
    return 15 if symbol == "TQQQ" else 20

def ma20(history):
    if len(history) < 20:
        return None
    last20 = history[-20:]
    return sum(p["close"] for p in last20) / 20

def determine_multiplier(close, ma20val):
    if ma20val is None or close is None:
        return 1.0, "MA20 데이터 부족 (기본 1.0T)"
    if close >= ma20val:
        return 1.0, "MA20 상단"
    drawdown = (ma20val - close) / ma20val * 100
    tiers = [(47, 2.5), (41, 2.1), (35, 1.95)]
    for th, mult in tiers:
        if drawdown >= th:
            return mult, f"MA20 대비 -{th}% 이상 구간"
    return 0.75, "MA20 하단 (35% 미만 이격)"

def crash_tier_table(ma20val, base1x):
    """MA20 대비 추가 하락률(35/41/47/50/55%)별 폭락장 매수 단가·수량표"""
    tiers = [(35, 1.95), (41, 2.1), (47, 2.5)]
    rows = []
    if ma20val is None or base1x is None:
        return rows
    for th, mult in tiers:
        price = ma20val * (1 - th / 100)
        amount = base1x * mult
        qty = (amount / price) if price and price > 0 else None
        rows.append({"tier": th, "mult": mult, "price": price, "amount": amount, "qty": qty})
    return rows

def phase_of(T, splits):
    if T >= splits - 1:
        return "소진모드"
    if T < splits / 2:
        return "전반전"
    return "후반전"

def active_round(p):
    rounds = p["rounds"]
    if not rounds:
        return None
    return rounds[-1] if rounds[-1]["status"] == "active" else None


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
    """
    ticker = yf.Ticker(symbol)

    daily = ticker.history(
        period="3mo",
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

    # 오늘이 정규장 진행 중인지 판단
    weekday = now_et.weekday() < 5
    regular_session_open = time(9, 30)
    regular_session_close = time(16, 0)
    market_open = (
        weekday
        and regular_session_open <= now_et.time().replace(second=0, microsecond=0) < regular_session_close
    )

    # 일봉 MA20:
    # 장중에는 오늘 미완성 일봉 제외,
    # 장 마감 후에는 오늘 종가 포함.
    daily_dates = pd.to_datetime(daily.index)
    if getattr(daily_dates, "tz", None) is not None:
        daily_dates_et = daily_dates.tz_convert(NY_TZ)
    else:
        daily_dates_et = daily_dates.tz_localize(NY_TZ)

    daily = daily.copy()
    daily["_date_et"] = daily_dates_et.date

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
    
    # 표시용 최근 60개 일봉
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
    amount = price * qty
    pnl = (price - r["avgCost"]) * qty
    t_before = r["T"]
    r["cash"] += amount
    r["qty"] -= qty
    r["T"] = r["T"] * 0.75
    r["trades"].append({
        "id": len(r["trades"]) + 1,
        "date": dt, "type": "quarter_sell", "price": price, "qty": qty, "amount": amount,
        "tDelta": r["T"] - t_before, "tAfter": r["T"], "avgAfter": r["avgCost"],
        "cashAfter": r["cash"], "pnl": pnl,
    })

def apply_final_sell(p, r, dt, price, qty):
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
    realized = sum(t["pnl"] for t in r["trades"] if t["pnl"] is not None)
    r["status"] = "closed"
    r["closedDate"] = dt
    r["realizedPnl"] = realized
    next_capital = r["cash"] if p["config"]["compounding"] else p["config"]["capital"]
    start_new_round(p, next_capital, dt)

def recalculate_round(r, initial_capital):
    """거래 삭제 시 라운드 상태 전체 재계산"""
    r["cash"] = initial_capital
    r["qty"] = 0.0
    r["avgCost"] = 0.0
    r["T"] = 0.0
    trades = r["trades"].copy()
    r["trades"] = []
    
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
            r["realizedPnl"] = sum(tr["pnl"] for tr in r["trades"] if tr["pnl"] is not None)

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
    ma = market.get("ma20")
    gap_pct = market.get("gap_pct")
    mult, tier = determine_multiplier(close, ma)

    # =========================================================
    # 1회 매수액
    # =========================================================
    base1x = (
        cfg["capital"] / splits
        if splits > 0 else None
    )

    # =========================================================
    # 현재 누적 매수금액
    # = 현재 평단가 × 현재 보유수량
    # =========================================================
    cumulative_buy_amount = (
        r["avgCost"] * r["qty"]
        if r["qty"] > 0 else 0.0
    )

    # =========================================================
    # 현재 T
    # = (평단가 × 보유수량) ÷ 1회 매수액
    # =========================================================
    current_T = (
        cumulative_buy_amount / base1x
        if base1x is not None and base1x > 0
        else 0.0
    )

    # =========================================================
    # T는 이제 current_T 하나만 사용
    # =========================================================
    T = current_T

    phase = phase_of(T, splits)

    star_pct = star_percent(symbol, splits, T)

    star_point = (
        r["avgCost"] * (1 + star_pct / 100)
        if r["avgCost"] > 0 else None
    )

    buy_trigger = (
        star_point - 0.01
        if star_point is not None else None
    )

    divisor_remaining = splits - T

    # 오늘 적용 배수를 적용한 매수 목표금액
    target_amount = (
        base1x * mult
        if base1x is not None else None
    )

    # 오늘 매수 수량
    buy_qty = (
        target_amount / close
        if target_amount is not None
        and close is not None
        and close > 0
        else None
    )

    s_pct = sell_profit_pct(symbol)

    sell_target = (
        r["avgCost"] * (1 + s_pct / 100)
        if r["avgCost"] > 0 else None
    )

    quarter_qty = r["qty"] / 4
    remainder_qty = r["qty"] - quarter_qty

    is_first_buy = (r["qty"] == 0 and current_T == 0)

    return dict(
        round=r,
        close=close,
        ma=ma,
        gap_pct=gap_pct,
        mult=mult,
        tier=tier,

        # 현재 T는 current_T 하나만 사용
        phase=phase,
        current_T=current_T,

        star_pct=star_pct,
        star_point=star_point,
        buy_trigger=buy_trigger,

        base1x=base1x,
        target_amount=target_amount,
        cumulative_buy_amount=cumulative_buy_amount,

        buy_qty=buy_qty,
        one_time_buy_amount=base1x,

        sell_target=sell_target,
        s_pct=s_pct,
        quarter_qty=quarter_qty,
        remainder_qty=remainder_qty,
        is_first_buy=is_first_buy,
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
    """매매 가이드/보유수량처럼 사람이 읽는 주식 수량은 소수점 없이 정수(반올림)로 표시"""
    return "—" if n is None else f"{round(n):,}주"

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

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0F1219;
    --surface: #171B24;
    --surface2: #1D2330;
    --border: #2A3140;
    --text: #E8EAEE;
    --text-dim: #8B93A6;
    --text-faint: #545C6E;
    --buy: #4FD1C5;
    --profit: #E8B44C;
    --loss: #E5636B;
    --accent: #7C9CFF;
    --card-shadow: none;
  }
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

data = st.session_state.data

def persist():
    ok = save_data(data)
    return ok

# ---- 사이드바: 백업 / 복원 ----
with st.sidebar:
    st.markdown("### ⚙️ 데이터 관리")
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
elif isinstance(data, list):
    portfolios = data
else:
    portfolios = []

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
    st.title("📊 추추매매 포트폴리오")
    st.caption("현재 진행 중인 추추매매 포트폴리오를 관리하고 추적하세요.")

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
                        unrealized = (g["close"] - r["avgCost"]) * r["qty"] if (g and g["close"] and r["qty"] > 0) else None
                        c_a, c_b, c_c = st.columns(3)
                        with c_a:
                            kv("평단가", money(r["avgCost"]) if r["avgCost"] > 0 else "—")
                            kv("보유수량", shares_fmt(r["qty"]))
                        with c_b:
                            kv("잔금", money(r["cash"]))
                            kv("미실현손익", money(unrealized), color=("var(--profit)" if (unrealized or 0) >= 0 else "var(--loss)") if unrealized is not None else None)
                        
                        if g and g["buy_trigger"]:
                            st.markdown(
                                f'<div class="note"><b>🟢 LOC 매수:</b> {money(g["buy_trigger"])}이하 × {shares_fmt(g["buy_qty"])} <br>'
                                f'<b>🟡 쿼터매도:</b>{money(g["star_point"])} × {shares_fmt(g["quarter_qty"])}<br>'
                                f'<b>🔴 매도 목표:</b> {money(g["sell_target"])} × {shares_fmt(g["remainder_qty"])}</div>',
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

guide = compute_guide(current_p, market) if market_error is None else None

# 포트폴리오 상단 콕핏
st.title(f"📈 {current_p['name']}")
if market_error:
    st.error(
        f"Yahoo Finance 시세를 불러오지 못했습니다: {market_error}"
    )
total_realized = sum(x.get("realizedPnl", 0) for x in current_p["rounds"] if x["status"] == "closed")
unrealized = None
if guide and guide["close"] is not None and r["qty"] > 0:
    unrealized = (guide["close"] - r["avgCost"]) * r["qty"]

st.markdown(
    f'<div class="round-badge">{cfg["symbol"]} · {cfg["splits"]}분할 · Round #{r["id"]} · {phase_of(guide["current_T"], cfg["splits"])}</div>',
    unsafe_allow_html=True,
)

# ------------------ Modified Cockpit Columns ------------------
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kv("평단가", money(r["avgCost"]) if r["avgCost"] > 0 else "—")
with c2:
    kv("보유수량", shares_fmt(r["qty"]))
with c3:
    # Calculate dynamic remaining cash: Total Seed - (Avg Cost * Qty)
    rem_cash = cfg["capital"] - (r["avgCost"] * r["qty"])
    kv("잔금", money(rem_cash))
with c4:
    kv("미실현손익", money(unrealized), color=("var(--profit)" if (unrealized or 0) >= 0 else "var(--loss)") if unrealized is not None else None)
with c5:
    kv("누적 실현손익", money(total_realized), color="var(--profit)" if total_realized >= 0 else "var(--loss)")
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
    st.markdown(
        f'<div class="card-title">시세 상태 <span class="tag {"loss" if g["mult"]>=2 else "buy" if g["mult"]<1 else "dim"}">{g["tier"]}</span></div>',
        unsafe_allow_html=True,
    )
    cc1, cc2, cc3, cc4 = st.columns(4)
    with cc1:
        kv("현재 Yahoo 가격", money(g["close"]) if g["close"] is not None else "가격 확인 실패")
    with cc2:
        kv("MA20", money(g["ma"]) if g["ma"] is not None else f"데이터 {len(current_p['price_history'])}/20")
    with cc3:
        kv("MA20 대비 괴리율", pct(g["gap_pct"]))
    with cc4:
        kv("오늘 적용 배수", f'{g["mult"]:.2f}T', color="var(--accent)")
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
        kv(
            "★ Star 값",
            pct(g["star_pct"]),
            color="var(--buy)" if g["star_pct"] is not None and g["star_pct"] < 0 else "var(--loss)",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if g["divisor_remaining"] <= 0:
        st.markdown(
            f"""<div class="card"><div class="card-title">매수 가이드 <span class="tag loss">소진모드</span></div>
            <div class="note warn">T값이 {cfg['splits']-1} 이상(소진모드 구간)입니다. 이 앱은 <b>일반모드</b> 로직만 지원하므로,
            소진모드 매수/매도는 별도 기준으로 직접 판단해 주세요.</div></div>""",
            unsafe_allow_html=True,
        )
    elif g["is_first_buy"]:
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
    else:
        half = g["target_amount"] / 2 if g["target_amount"] is not None else None
        crash_rows = crash_tier_table(g["ma"], g["base1x"])
        buy_qty_at_trigger = (
            g["target_amount"] / g["buy_trigger"]
            if g["target_amount"] is not None and g["buy_trigger"] not in (None, 0)
            else None
        )

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="card-title">매수 가이드 LOC <span class="tag buy">★ {pct(g["star_pct"])}</span> '
            f'<span class="tag dim">{g["phase"]} </span></div>',
            unsafe_allow_html=True,
        )

        half_qty = (buy_qty_at_trigger / 2) if buy_qty_at_trigger else 0
        st.markdown(
            f'<div class="kv-value" style="font-size:18px; margin-top:8px; line-height:1.6;">'
            f'<span style="color:var(--buy); font-weight:bold;">{money(g["buy_trigger"])} × {shares_fmt(buy_qty_at_trigger)}</span></div> '
            f'<span style="color:var(--text-faint); font-weight:bold;">(</span>'
            f'<span style="font-size:9pt; color:#000000; font-weight:bold;">평단매수</span> '
            f'<span style="color:#4DABF7;">{money(r["avgCost"])} × {shares_fmt(half_qty)}</span>'
            f'<span style="margin-left:20px; font-size:9pt; color:#000000; font-weight:bold;">★매수</span> '
            f'<span style="color:#B197FC;">{money(g["buy_trigger"])} × {shares_fmt(half_qty)}</span>'
            f'<span style="color:var(--text-faint); font-weight:bold;">)</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
       

        if crash_rows:
            st.markdown(
                '<div class="kv-label" style="margin-top:6px;">+@ 폭락장 추가 매수</div>',
                unsafe_allow_html=True,
            )
            crash_lines = "".join(
                f'<div style="display:flex; justify-content:space-between; '
                f'font-family: ui-monospace, monospace; font-size:13px; padding:3px 0; color:var(--loss);">'
                f'<span>- {row["tier"]}%</span><span>{money(row["price"])} × {shares_fmt(row["qty"])}</span></div>'
                for row in crash_rows
            )
            st.markdown(f'<div class="note">{crash_lines}</div>', unsafe_allow_html=True)

        if g["phase"] == "전반전":
            st.markdown(
                f'<div class="note"><b>전반전 매수:</b> 목표금액의 절반({money(half)})은 매수기준가 {money(g["buy_trigger"])}에, '
                f'나머지 절반({money(half)})은 평단가 {money(r["avgCost"])}에 LOC 매수. '
                f'급락 대비 그 아래로도 분할 LOC 매수 추가 권장.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="note"><b>후반전 매수:</b> 목표금액 전액({money(g["target_amount"])})을 '
                f'매수기준가 {money(g["buy_trigger"])}에 LOC 매수. 급락 대비 그 아래로도 분할 LOC 매수 추가 권장.</div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    if r["qty"] > 0:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(
            f'<div class="card-title">매도 가이드 LOC <span class="tag profit">★ {pct(g["star_pct"])}</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="kv-label" style="margin-top:4px;">쿼터매도</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="kv-value" style="font-size:20px; color:var(--profit);">'
            f'{money(g["star_point"])} × {shares_fmt(g["quarter_qty"])}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="kv-label" style="margin-top:6px;">지정가 매도 +{g["s_pct"]}%</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="kv-value" style="font-size:18px; color:var(--profit);">'
            f'{money(g["sell_target"])} × {shares_fmt(g["remainder_qty"])}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="note">쿼터매도는 별지점에 LOC로, 나머지는 평단 대비 +{g["s_pct"]}% 지정가로 매일 동시에 걸어둡니다.</div>',
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

    cc1, cc2, cc3, cc4, cc5 = st.columns(5)
    with cc1:
        kv("현재 가격", money(m["price"]))
    with cc2:
        kv("MA20", money(m["ma20"]) if m["ma20"] is not None else "데이터 부족")
    with cc3:
        kv("MA20 괴리율", pct(m["gap_pct"]))
    with cc4:
        kv("적용 배수", f'{guide["mult"]:.2f}T')
    with cc5:
        kv("시장 상태", "장중" if m["market_open"] else "장외")

    st.markdown(
        f'<div class="note">데이터: <b>{m["source_label"]}</b> · '
        f'마지막 업데이트: {m["fetched_at"][:19].replace("T", " ")} '
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
        default_qty = round(r["qty"] / 4, 4)
        if guide and guide["star_point"] is not None:
            default_price = round(guide["star_point"], 2)
    else:
        default_qty = round(r["qty"], 4)
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
            st.markdown('<div class="note">쿼터매도 규칙: T값은 직전 T × 0.75 로 자동 갱신됩니다. 평단은 변하지 않습니다.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="note">지정가매도(전량)는 라운드를 종료합니다. 실현손익이 집계되고 새 라운드가 자동으로 시작됩니다.</div>', unsafe_allow_html=True)

        submitted = st.form_submit_button("기록 추가", use_container_width=True)

    if submitted:
        if t_price <= 0 or t_qty <= 0:
            st.error("가격과 수량을 올바르게 입력하세요.")
        elif ttype in ("quarter_sell", "final_sell") and t_qty > r["qty"] + 1e-9:
            st.error("보유수량보다 많습니다.")
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

# ---------------- 히스토리 (거래 삭제 기능 추가) ----------------
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

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">전체 요약</div>', unsafe_allow_html=True)
        h1, h2 = st.columns(2)
        with h1:
            kv("완료된 라운드", str(sum(1 for x in current_p["rounds"] if x["status"] == "closed")))
        with h2:
            kv("누적 실현손익", money(total_realized), color="var(--profit)" if total_realized >= 0 else "var(--loss)")
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
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    # 거래 기록 삭제 UI (진행 중인 라운드 또는 최근 라운드 개별 수정 가능)
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