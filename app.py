import streamlit as st
import pandas as pd
import json
import base64
import requests
import yfinance as yf
from datetime import date

def get_5ma_gap(ticker_symbol):
    # 5일 이동평균 계산을 위해 최근 10일치 데이터 호출
    ticker = yf.Ticker(ticker_symbol)
    hist = ticker.history(period="10d")
    
    if len(hist) < 5:
        return None, None, None
    
    current_price = float(hist['Close'].iloc[-1])
    ma5 = float(hist['Close'].rolling(window=5).mean().iloc[-1])
    
    # 이격률(%) 계산
    gap_pct = ((current_price - ma5) / ma5) * 100
    return current_price, ma5, gap_pct

st.set_page_config(page_title="Aiden Infinite Loop Strategy Live Manager", layout="wide")

# --- GitHub API Sync Helpers ---
try:
    GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
    REPO_NAME = st.secrets.get("REPO_NAME", "codeyegrian/infiniteloop-manager")
except Exception:
    GITHUB_TOKEN = ""
    REPO_NAME = "codeyegrian/infiniteloop-manager"

BRANCH = "main"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def github_load_file(filename, default_value):
    if not GITHUB_TOKEN:
        import os
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
        import os
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True, "Saved locally"
        
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{filename}"
    try:
        get_resp = requests.get(f"{url}?ref={BRANCH}", headers=HEADERS, timeout=5)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
        
        json_str = json.dumps(data, indent=4, ensure_ascii=False)
        content_encoded = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
        
        payload = {
            "message": f"Update {filename} via Live Manager",
            "content": content_encoded,
            "branch": BRANCH
        }
        if sha:
            payload["sha"] = sha
            
        put_resp = requests.put(url, headers=HEADERS, json=payload, timeout=5)
        if put_resp.status_code in [200, 201]:
            return True, "Successfully updated GitHub!"
        else:
            return False, f"GitHub Error {put_resp.status_code}: {put_resp.text}"
    except Exception as e:
        return False, f"Exception: {str(e)}"

# --- Load & Save Helpers ---
def load_settings():
    default_s = {
        "total_capital": 65000.0, 
        "use_custom_active": False,
        "custom_active_capital": 52000.0,
        "active_ratio": 80.0,
        "manual_tier_1": 302.0, 
        "col_widths": {
            "Tier": 60, "매수": 100, "수량": 80, "매도": 100, 
            "매수기준": 90, "매도기준": 90, "시드비율": 90, 
            "배정시드": 100, "1Tier대비": 100, "매수 (입력)": 100, 
            "실수량": 80, "예상": 80, "실매수": 80
        }
    }
    loaded = github_load_file("settings.json", default_s)
    return loaded if isinstance(loaded, dict) else default_s

def save_settings(settings_dict):
    github_save_file("settings.json", settings_dict)

def load_trades():
    loaded = github_load_file("trades.json", [])
    if isinstance(loaded, list):
        return sorted(loaded, key=lambda x: str(x.get("Date", "")), reverse=True)
    return []

def save_trades(trades):
    sorted_trades = sorted(trades, key=lambda x: str(x.get("Date", "")), reverse=True)
    return github_save_file("trades.json", sorted_trades)

if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

if "trades" not in st.session_state:
    st.session_state.trades = load_trades()

st.title("⚡ Aiden Infinite Loop Strategy - SOXL Live Manager")

# --- Fetch Live SOXL Price, 52-Week High & Extended Hours ---
@st.cache_data(ttl=60)
def get_soxl_market_data():
    try:
        ticker = yf.Ticker("SOXL")
        hist = ticker.history(period="1y")
        if not hist.empty:
            current_p = float(hist["Close"].iloc[-1])
            high_52w = float(hist["High"].max())
            
            info = ticker.info
            regular_p = info.get("regularMarketPrice", current_p)
            pre_p = info.get("preMarketPrice", None)
            post_p = info.get("postMarketPrice", None)
            
            return regular_p, high_52w, pre_p, post_p
    except Exception:
        pass
    return 115.88, 302.00, None, None

current_soxl_price, high_52_week, pre_market_price, post_market_price = get_soxl_market_data()

# --- Sidebar Inputs (Strategy Settings) ---
st.sidebar.header("⚙️ Strategy Settings")
settings = st.session_state.settings

total_capital = st.sidebar.number_input(
    "전체자금 (Total Capital $)", 
    value=float(settings.get("total_capital", 65000.0)), 
    step=1000.0
)

st.sidebar.divider()
st.sidebar.subheader("💰 Capital Allocation (운용자금 설정)")
use_custom_active = st.sidebar.checkbox("운용자금 직접 입력 (Custom Active Capital)", value=settings.get("use_custom_active", False))

if use_custom_active:
    active_capital = st.sidebar.number_input(
        "운용자금 (Active Capital $)",
        value=float(settings.get("custom_active_capital", total_capital * 0.8)),
        step=500.0
    )
    if active_capital > total_capital:
        st.sidebar.error("⚠️ 운용자금은 전체자금을 초과할 수 없습니다.")
        active_capital = total_capital
    reserve_capital = total_capital - active_capital
    active_ratio_val = (active_capital / total_capital) * 100 if total_capital > 0 else 80.0
else:
    active_ratio_input = st.sidebar.slider(
        "운용자금 비율 (%)", 
        min_value=10.0, max_value=100.0, 
        value=float(settings.get("active_ratio", 80.0)), 
        step=5.0
    )
    active_capital = total_capital * (active_ratio_input / 100.0)
    reserve_capital = total_capital - active_capital
    active_ratio_val = active_ratio_input

divisions = 40
unit_capital = active_capital / divisions

st.sidebar.info(f"**전체자금 (Total):** ${total_capital:,.2f}\n\n"
                f"**운용자금 (Active):** ${active_capital:,.2f} ({active_ratio_val:.1f}%)\n\n"
                f"**여유자금 / 진돗개 (Reserve):** ${reserve_capital:,.2f}\n\n"
                f"**1 Tier Unit Capital:** ${unit_capital:,.2f}")

st.sidebar.divider()
st.sidebar.subheader("🎯 Tier 1 Settings (Manual)")

manual_tier_1_val = st.sidebar.number_input(
    "Manual Tier 1 Price ($)", 
    value=float(settings.get("manual_tier_1", 302.0)), 
    step=0.5
)
tier_1_price = manual_tier_1_val if manual_tier_1_val > 0 else 302.0

reference_peak = tier_1_price
tier_0_price = tier_1_price * 1.05

st.sidebar.info(f"**0 Tier (Tier 1 + 5%):** ${tier_0_price:,.2f}")

# Column Width Customizer Panel
st.sidebar.divider()
st.sidebar.subheader("📐 Table Column Widths (px)")
default_widths = settings.get("col_widths", {
    "Tier": 40, "매수": 80, "수량": 40, "매도": 80, 
    "매수기준": 60, "매도기준": 60, "시드비율": 60, 
    "배정시드": 80, "1Tier대비": 80, "매수 (입력)": 40, 
    "실수량": 0, "예상": 40, "실매수": 40
})

col_widths = {}
with st.sidebar.expander("Customize Column Widths", expanded=False):
    for col_name, default_w in default_widths.items():
        col_widths[col_name] = st.number_input(f"{col_name} Width", min_value=40, max_value=300, value=int(default_w), step=10)

updated_settings = {
    "total_capital": total_capital,
    "use_custom_active": use_custom_active,
    "custom_active_capital": active_capital if use_custom_active else float(settings.get("custom_active_capital", 52000.0)),
    "active_ratio": active_ratio_val if not use_custom_active else float(settings.get("active_ratio", 80.0)),
    "manual_tier_1": manual_tier_1_val,
    "col_widths": col_widths
}
if updated_settings != settings:
    st.session_state.settings = updated_settings
    save_settings(updated_settings)

# --- Data Calculations ---
df_trades = pd.DataFrame(st.session_state.trades)
if not df_trades.empty:
    if "Type" not in df_trades.columns:
        df_trades["Type"] = "BUY"

    buy_mask = df_trades["Type"].str.upper() == "BUY"
    sell_mask = df_trades["Type"].str.upper() == "SELL"

    total_spent = float(df_trades.loc[buy_mask, "Amount"].abs().sum() - df_trades.loc[sell_mask, "Amount"].abs().sum())
    total_shares = float(df_trades.loc[buy_mask, "Qty"].abs().sum() - df_trades.loc[sell_mask, "Qty"].abs().sum())

    total_spent = max(0.0, total_spent)
    total_shares = max(0.0, total_shares)

    avg_price = total_spent / total_shares if total_shares > 0 else 0.0
    tp_10_price = avg_price * 1.10 if total_shares > 0 else 0.0

    one_t_capital = active_capital / 40.0 if active_capital > 0 else 0.0
    current_tier = round(total_spent / one_t_capital, 2) if one_t_capital > 0 else 0.0
else:
    total_spent = 0.0
    total_shares = 0.0
    avg_price = 0.0
    tp_10_price = 0.0
    current_tier = 0.0

# --- Pre-calculate Tiers ---
temp_tiers = [(0, tier_0_price)]
prev_buy = tier_1_price
for t in range(1, 41):
    buy_p = tier_1_price if t == 1 else prev_buy * 0.95
    prev_buy = buy_p
    temp_tiers.append((t, buy_p))

tiers_1_40 = temp_tiers[1:]

drop_from_peak_pct = ((current_soxl_price - tier_1_price) / tier_1_price) * 100
invested_pct_of_active = (total_spent / active_capital) * 100 if active_capital > 0 else 0.0

# --- Top Summary Dashboard ---
col1, col2, col3, col4, col5 = st.columns(5)

ext_text = f"{drop_from_peak_pct:.1f}% from T1"
if pre_market_price:
    ext_text += f" | Pre:${pre_market_price:,.2f}"
elif post_market_price:
    ext_text += f" | Post:${post_market_price:,.2f}"

col1.metric("SOXL Live Price", f"${current_soxl_price:,.2f}", ext_text)
col2.metric("Tier 1 Base Price", f"${tier_1_price:,.2f}", "Manual Tier 1")
col3.metric("Invested Capital", f"${total_spent:,.2f}", f"{invested_pct_of_active:.1f}% Active")
col4.metric("Average Purchase Price", f"${avg_price:,.2f}")
col5.metric("Position & Tier", f"{total_shares:,.0f} shares", f"Tier {current_tier:.1f} / 40")

st.divider()

# --- Target Tier Calculations ---
target_tier_idx = 1
for t, buy_p in tiers_1_40:
    if current_soxl_price <= buy_p:
        target_tier_idx = t
    else:
        break

tier_filled_shares = {t: 0 for t in range(1, 41)}
tier_trade_dates = {t: [] for t in range(1, 41)}

if not df_trades.empty:
    for _, trade in df_trades.iterrows():
        t_price = trade["Price"]
        t_qty = trade["Qty"]
        t_date = str(trade.get("Date", ""))
        matched_tier = 1
        for t, buy_p in tiers_1_40:
            if buy_p >= t_price:
                matched_tier = t
            else:
                break
        tier_filled_shares[matched_tier] += int(t_qty)
        if t_date and t_date not in tier_trade_dates[matched_tier]:
            tier_trade_dates[matched_tier].append(t_date)

target_tier_price = dict(tiers_1_40)[target_tier_idx]
standard_tier_qty = int(unit_capital // target_tier_price) if target_tier_price > 0 else 0
half_tier_buy_qty = max(1, int(standard_tier_qty / 2))
current_filled_qty = int(tier_filled_shares.get(target_tier_idx, 0))
remaining_qty = standard_tier_qty - current_filled_qty

if current_filled_qty >= standard_tier_qty:
    recommended_buy_qty = 0
elif current_filled_qty > 0:
    recommended_buy_qty = min(remaining_qty, half_tier_buy_qty)
else:
    recommended_buy_qty = half_tier_buy_qty

today_str = str(date.today())
today_trades_df = pd.DataFrame()
today_shares_sum = 0
if not df_trades.empty and "Date" in df_trades.columns:
    today_trades_df = df_trades[df_trades["Date"].astype(str).str.startswith(today_str)]
    if not today_trades_df.empty:
        today_shares_sum = int(today_trades_df["Qty"].sum())

already_bought_today = not today_trades_df.empty

# --- Dynamic Daily Order Text Generator ---
half_tier_qty = int((unit_capital * 0.5) // current_soxl_price) if current_soxl_price > 0 else 0
avg_buy_active = (avg_price > 0) and (current_soxl_price < avg_price)
tier_buy_active = (recommended_buy_qty > 0) and not already_bought_today

action_summary_parts = []
if already_bought_today:
    action_summary_parts.append(f"✅ 오늘 매수 완료 ({today_str}: {today_shares_sum}주)")
else:
    if tier_buy_active:
        action_summary_parts.append(f"📍 Tier {target_tier_idx} 매수 추천 (0.5티어 / {recommended_buy_qty}주 @ ${target_tier_price:,.2f})")
    else:
        action_summary_parts.append(f"📍 Tier {target_tier_idx} 이미 충족됨 (추가 매수 불필요)")
    
    if avg_buy_active:
        action_summary_parts.append(f"📊 평단매수 추천 (0.5티어 / {half_tier_qty}주 @ ${current_soxl_price:,.2f})")

action_summary_str = " | ".join(action_summary_parts)

# --- Top Section: Buy & Sell Guides ---
st.subheader("🛒 Today's Buy & Sell Guides")
st.info(f"**🎯 오늘의 핵심 요약 (Action Summary):** {action_summary_str}")

ticker_to_check = 'SOXL'
price, ma5, gap = get_5ma_gap(ticker_to_check)

if gap is not None:
    st.info(f"📈 {ticker_to_check} 5일선 이격률: {gap:.2f}% (현재가: ${price:.2f} / 5일선: ${ma5:.2f})")

c_avg_buy, c_tier_buy, c_crash_buy, c_sell = st.columns(4)

with c_avg_buy:
    st.markdown("### 📊 평단매수 가이드")
    if avg_price > 0:
        if current_soxl_price < avg_price:
            est_cost_avg = half_tier_qty * current_soxl_price
            st.success(
                f"평단매수 추천\n\n"
                f"현재가 ${current_soxl_price:,.2f} < 평단 ${avg_price:,.2f}\n\n"
                f"* 추천 수량: 0.5 티어 ({half_tier_qty}주)\n"
                f"* 예상 필요자금: ${est_cost_avg:,.2f}"
            )
        else:
            st.info(f"평단매수 비추천\n\n현재가 ${current_soxl_price:,.2f} >= 평단 ${avg_price:,.2f}")
    else:
        st.info("보유 포지션 없음")
    
    if already_bought_today:
        st.warning(f"오늘 매수 완료\n\n{today_str} : {today_shares_sum}주 매수완료")

with c_tier_buy:
    st.markdown(f"### 📍 티어매수 가이드 (Tier {target_tier_idx})")

    target_dates = tier_trade_dates.get(target_tier_idx, [])
    dates_str = ", ".join(target_dates) if target_dates else "-"

    tier_mult = 0.5
    condition_text = ""
    if gap is not None:
        if gap >= 0:
            tier_mult, condition_text = 0.5, "5일선 위"
        elif -3.0 <= gap < 0:
            tier_mult, condition_text = 0.75, "0% ~ -3%"
        elif -6.0 <= gap < -3.0:
            tier_mult, condition_text = 1.0, "-3% ~ -6%"
        elif -10.0 <= gap < -6.0:
            tier_mult, condition_text = 1.5, "-6% ~ -10%"
        else:
            tier_mult, condition_text = 2.0, "-10% 이하"

    target_tier_qty = int(standard_tier_qty * tier_mult)
    recommended_buy_qty = max(0, target_tier_qty - current_filled_qty)
    est_cost_tier = recommended_buy_qty * target_tier_price

    if current_filled_qty >= target_tier_qty:
        st.warning(f"티어매수 완료 ({current_filled_qty}/{target_tier_qty}주 보유)")
    elif current_filled_qty > 0:
        st.success(
            f"티어매수 추가 추천 ({tier_mult}티어)\n"
            f"tier {target_tier_idx} ({dates_str}) {current_filled_qty} / {target_tier_qty} 보유\n"
            f"* 잔여 수량 중 {recommended_buy_qty}주 매수 필요"
        )
    else:
        st.success(
            f"티어매수 추천 ({tier_mult}티어)\n"
            f"tier {target_tier_idx} 0 / {target_tier_qty} 보유\n"
            f"* 추천 수량: {recommended_buy_qty}주"
        )

    st.info(
        f"* 5일선 이격률: {gap:.2f}% ({condition_text})\n" if gap is not None else ""
        f"* 목표 가격: ${target_tier_price:,.2f}\n"
        f"* 추천 수량: {recommended_buy_qty}주 ({tier_mult}티어)\n"
        f"* 예상 필요자금: ${est_cost_tier:,.2f}"
    )

with c_crash_buy:
    st.markdown("### 🚨 5일선 매매 가이드")

    if gap is not None:
        st.info(
            f"📊 **MA5 주가 가이드**\n\n"
            f"* **현재 5일선 이격률:** `{gap:.2f}%` ➔ **적용: {condition_text}**\n"
            f"* **오늘 추천 배율:** `{tier_mult}T`"
        )

    curr_p = current_soxl_price
    daily_capital = unit_capital

    if curr_p > 0 and daily_capital > 0:
        base_qty = int(daily_capital // curr_p)

        q_05 = int(base_qty * 0.5)
        q_075 = int(base_qty * 0.75)
        q_10 = int(base_qty * 1.0)
        q_15 = int(base_qty * 1.5)
        q_20 = int(base_qty * 2.0)

        container_html = (
            f"<div style='background-color: #f8d7da; padding: 15px; border-radius: 8px; "
            f"font-size: 13px; color: #333; font-family: sans-serif;'>"
            f"<b>📍 (${daily_capital:,.2f}) / 현재가 (${curr_p:,.2f}) </b><br><br>"
            f"• <b>5일선 위 (0.5T):</b> {q_05}주<br>"
            f"• <b>0% ~ -3% (0.75T):</b> {q_075}주<br>"
            f"• <b>-3% ~ -6% (1.0T):</b> {q_10}주<br>"
            f"• <b>-6% ~ -10% (1.5T):</b> {q_15}주<br>"
            f"• <b>-10% 이하 (2.0T):</b> {q_20}주"
            f"</div>"
        )
        st.markdown(container_html, unsafe_allow_html=True)

star_percent = 20.0 - (1.0 * current_tier)
star_price = avg_price * (1.0 + (star_percent / 100.0))

with c_sell:
    st.markdown("### 🎯 매도 가이드")
    if avg_price > 0 and total_shares > 0:
        quarter_qty = max(1, int(total_shares / 4.0))
        p_20 = avg_price * 1.20
        qty_all = int(total_shares)
        
        st.success(f"""
         ⭐ **별값**

         **T값:** {current_tier:.2f} | **별가:** {star_percent:.2f}%

         * **매도 ★:** ${star_price:,.2f}
         * **10% :** ${tp_10_price:,.2f}
         * **1/4 쿼터:** {quarter_qty}주
         * **체결 시:** T값 → T * 0.75
         """)
        
        st.info(
            f"🎯 **20% 익절**\n\n"
            f"* 지정가: **${p_20:,.2f}**\n"
            f"* 전량 **{qty_all}주** (사이클 종료)"
        )
    else:
        st.info("보유 포지션 없음")

st.divider()

# --- Lower Section: Master Grid Table ---
st.subheader("📊 Master Grid & Target Price Table (Live Price Highlighted)")

tier_data = []
cum_shares = 0
cum_actual_shares = 0

t0_num, t0_price = temp_tiers[0]
tier_data.append({
    "Tier": "0 (T1+5%)",
    "매수": round(t0_price, 2),
    "수량": "-",
    "매도": round(t0_price * 1.10, 2),
    "매수기준": "T1기준+5%",
    "매도기준": "10.00%",
    "시드비율": "-",
    "배정시드": "-",
    "1Tier대비": "+5.00%",
    "매수 (입력)": "-",
    "실매수": "-",
    "예상": "-",
    "티어값": 0.0
})

# --- tier_filled_shares를 계산하는 기존 구간을 이 코드로 교체하세요 ---
tier_filled_shares = {t: 0 for t in range(1, 41)}
tier_trade_dates = {t: [] for t in range(1, 41)}

if not df_trades.empty:
    for _, trade in df_trades.iterrows():
        t_price = float(trade["Price"])
        t_qty = float(trade["Qty"])
        t_type = str(trade.get("Type", "BUY")).upper()
        t_date = str(trade.get("Date", ""))
        
        # Find the best matching tier where t_price is closest to or falls within the tier buy price
        matched_tier = 1
        min_diff = float('inf')
        
        for t, buy_p in tiers_1_40:
            diff = abs(buy_p - t_price)
            if diff < min_diff:
                min_diff = diff
                matched_tier = t

        # Add for BUY, subtract for SELL
        if t_type == "SELL":
            tier_filled_shares[matched_tier] -= int(t_qty)
        else:
            tier_filled_shares[matched_tier] += int(t_qty)
            
        if t_date and t_date not in tier_trade_dates[matched_tier]:
            tier_trade_dates[matched_tier].append(t_date)

    # Prevent negative values per tier
    for t in tier_filled_shares:
        tier_filled_shares[t] = max(0, tier_filled_shares[t])

for t, buy_p in tiers_1_40:
    drop_pct = ((buy_p - tier_1_price) / tier_1_price) * 100
    take_profit_p = buy_p * 1.10
    suggested_shares = int(unit_capital // buy_p) if buy_p > 0 else 0
    cum_shares += suggested_shares
    
    input_bought_qty = tier_filled_shares.get(t, 0)
    cum_actual_shares += input_bought_qty

    input_tier_val = round(input_bought_qty / suggested_shares, 2) if suggested_shares > 0 else 0.0

    tier_data.append({
        "Tier": str(t),
        "매수": round(buy_p, 2),
        "수량": suggested_shares,
        "매도": round(take_profit_p, 2),
        "매수기준": "-5.00%" if t > 1 else "기준(T1)",
        "매도기준": "10.00%",
        "시드비율": f"{(1/40)*100:.2f}%",
        "배정시드": round(unit_capital, 2),
        "1Tier대비": f"{drop_pct:.2f}%",
        "매수 (입력)": input_bought_qty,
        "실매수": cum_actual_shares,
        "예상": cum_shares,
        "티어값": input_tier_val
    })

df_tiers = pd.DataFrame(tier_data)
current_tier = sum(float(row.get("티어값", 0)) for row in tier_data)

def highlight_current_price_tier(row):
    t_val = row["Tier"]
    if t_val == "0 (T1+5%)":
        return ['background-color: #fff3cd; color: #856404; font-weight: bold'] * len(row)
    
    try:
        buy_price = float(row["매수"])
    except Exception:
        return [''] * len(row)
        
    # 현재가와 티어 매수가를 직접 비교하여 현재 구간에 맞는 곳을 하이라이트
    # (테이블 정렬 방향에 맞춰 부등호를 조절할 수 있습니다)
    if current_soxl_price >= buy_price:
        return ['background-color: #cce5ff; color: #004085; font-weight: bold'] * len(row)
    else:
        return ['background-color: #f8d7da; color: #721c24'] * len(row)
    
styled_df = df_tiers.style.apply(highlight_current_price_tier, axis=1).format({
    "매수": lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) else x,
    "매도": lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) else x,
    "배정시드": lambda x: f"{x:,.2f}" if isinstance(x, (int, float)) else x,
    "티어값": lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else x
})

column_configs = {
    "매수 (입력)": st.column_config.NumberColumn("매수 (입력)", format="%d", min_value=0, step=1, width=col_widths.get("매수 (입력)", 100))
}
for col in ["Tier", "매수", "수량", "매도", "매수기준", "매도기준", "시드비율", "배정시드", "1Tier대비", "실수량", "예상", "실매수"]:
    if col != "매수 (입력)":
        column_configs[col] = st.column_config.Column(width=col_widths.get(col, 90))

st.dataframe(
    styled_df,
    use_container_width=True,
    hide_index=True,
    column_config=column_configs
)

st.divider()

# --- Trade Input Section ---
st.subheader("📝 Record Executed Trade")

with st.form("trade_form", clear_on_submit=True):
    f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns(5)
    
    date_input_val = f_col1.date_input("Trade Date")
    trade_type_val = f_col2.selectbox("Trade Type", ["BUY", "SELL"])
    price = f_col3.number_input("Execution Price ($)", min_value=0.01, value=float(round(target_tier_price, 2)))
    qty = f_col4.number_input("Execution Quantity (Shares)", min_value=1.0, value=float(max(1.0, recommended_buy_qty)))

    suggested_tier_weight = round(qty / standard_tier_qty, 2) if standard_tier_qty > 0 else 0.5
    suggested_tier_weight = max(0.01, suggested_tier_weight)

    tier_add = f_col5.number_input(
        "Auto-Calculated T Weight",
        min_value=0.01,
        max_value=5.0,
        value=float(suggested_tier_weight),
        step=0.01,
        help="Automatically calculated based on execution quantity vs standard tier quantity."
    )

    submitted = st.form_submit_button("Save Trade")
    if submitted:
        new_trade = {
            "Date": str(date_input_val),
            "Type": trade_type_val,
            "Price": float(round(price, 2)),
            "Qty": float(qty),
            "Amount": float(round(price * qty, 2)),
            "Tier": float(tier_add if trade_type_val == "BUY" else -tier_add)
        }

        st.session_state.trades.append(new_trade)
        st.session_state.trades = sorted(st.session_state.trades, key=lambda x: str(x.get("Date", "")), reverse=True)
        save_trades(st.session_state.trades)
        st.rerun()

# --- Editable & Sortable Trade History Section ---
st.subheader("📋 Trade History (Newest First)")

if st.session_state.trades:
    sorted_trades = sorted(st.session_state.trades, key=lambda x: str(x.get("Date", "")), reverse=True)
    df_trades = pd.DataFrame(sorted_trades)
    df_trades["Date"] = df_trades["Date"].astype(str)
    
    edited_df = st.data_editor(
        df_trades[["Date", "Type", "Price", "Qty", "Amount", "Tier"]],
        num_rows="dynamic",
        use_container_width=True,
        key="trade_history_editor"
    )

    if edited_df is not None:
        updated_records = edited_df.to_dict(orient="records")
        cleaned_records = []
        for r in updated_records:
            if r.get("Date") and str(r.get("Date")) != "nan":
                p_val = float(r.get("Price", 0.0))
                q_val = float(r.get("Qty", 0.0))
                cleaned_records.append({
                    "Date": str(r.get("Date")),
                    "Type": str(r.get("Type", "BUY")),
                    "Price": p_val,
                    "Qty": q_val,
                    "Amount": float(round(p_val * q_val, 2)),
                    "Tier": float(r.get("Tier", 1.0))
                })
        
        cleaned_records = sorted(cleaned_records, key=lambda x: str(x.get("Date", "")), reverse=True)
        
        if cleaned_records != sorted_trades:
            st.session_state.trades = cleaned_records
            save_trades(cleaned_records)
            st.rerun()

    if st.button("Clear All History (Cycle Reset)"):
        st.session_state.trades = []
        save_trades([])
        if "trade_history_editor" in st.session_state:
            del st.session_state["trade_history_editor"]
        st.rerun()
else:
    st.info("No trade history recorded yet.")