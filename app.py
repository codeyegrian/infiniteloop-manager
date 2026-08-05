# app.py
import streamlit as st
import pandas as pd
import json
import os
import yfinance as yf
from datetime import date

st.set_page_config(page_title="Aiden Infinite Loop Strategy Live Manager", layout="wide")

DB_FILE = "trades.json"
SETTINGS_FILE = "settings.json"

# --- Load & Save Helpers ---
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "total_capital": 65000.0, 
        "use_custom_active": False,
        "custom_active_capital": 52000.0,
        "active_ratio": 80.0,
        "custom_peak": 302.0, 
        "use_52w_high": True,
        "col_widths": {
            "Tier": 60, "매수": 100, "수량": 80, "매도": 100, 
            "매수기준": 90, "매도기준": 90, "시드비율": 90, 
            "배정시드": 100, "1Tier대비": 100, "매수 (입력)": 100, 
            "실수량": 80, "예상": 80, "실매수": 80
        }
    }

def save_settings(settings_dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings_dict, f, indent=4)

def load_trades():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                data = json.load(f)
                return sorted(data, key=lambda x: x.get("Date", ""), reverse=True)
        except Exception:
            return []
    return []

def save_trades(trades):
    sorted_trades = sorted(trades, key=lambda x: x.get("Date", ""), reverse=True)
    with open(DB_FILE, "w") as f:
        json.dump(sorted_trades, f, indent=4)

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
st.sidebar.subheader("🎯 Peak Price Settings")
use_52w = st.sidebar.checkbox("Use 52-Week High as Peak", value=settings.get("use_52w_high", True))

if use_52w:
    reference_peak = high_52_week
    st.sidebar.info(f"**52-Week High Peak:** ${high_52_week:,.2f}")
    custom_peak_val = settings.get("custom_peak", 302.0)
else:
    custom_peak_val = st.sidebar.number_input(
        "Custom Peak Price ($)", 
        value=float(settings.get("custom_peak", high_52_week)), 
        step=0.5
    )
    reference_peak = custom_peak_val

# Column Width Customizer Panel
st.sidebar.divider()
st.sidebar.subheader("📐 Table Column Widths (px)")
default_widths = settings.get("col_widths", {
    "Tier": 60, "매수": 100, "수량": 80, "매도": 100, 
    "매수기준": 90, "매도기준": 90, "시드비율": 90, 
    "배정시드": 100, "1Tier대비": 100, "매수 (입력)": 100, 
    "실수량": 80, "예상": 80, "실매수": 80
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
    "custom_peak": custom_peak_val,
    "use_52w_high": use_52w,
    "col_widths": col_widths
}
if updated_settings != settings:
    st.session_state.settings = updated_settings
    save_settings(updated_settings)

# --- Data Calculations ---
df_trades = pd.DataFrame(st.session_state.trades)

if not df_trades.empty:
    df_trades["Amount"] = df_trades["Price"] * df_trades["Qty"]
    total_spent = df_trades["Amount"].sum()
    total_shares = df_trades["Qty"].sum()
    avg_price = total_spent / total_shares if total_shares > 0 else 0.0
    current_tier = df_trades["Tier"].sum()
else:
    total_spent = 0.0
    total_shares = 0.0
    avg_price = 0.0
    current_tier = 0.0

drop_from_peak_pct = ((current_soxl_price - reference_peak) / reference_peak) * 100
invested_pct_of_active = (total_spent / active_capital) * 100 if active_capital > 0 else 0.0

# --- Top Summary Dashboard (5 Columns) ---
col1, col2, col3, col4, col5 = st.columns(5)

ext_text = f"{drop_from_peak_pct:.1f}% peak"
if pre_market_price:
    ext_text += f" | Pre:${pre_market_price:,.2f}"
elif post_market_price:
    ext_text += f" | Post:${post_market_price:,.2f}"

col1.metric("SOXL Live Price", f"${current_soxl_price:,.2f}", ext_text)
col2.metric("Reference Peak Price", f"${reference_peak:,.2f}", "52W High" if use_52w else "Manual Peak")
col3.metric("Invested Capital", f"${total_spent:,.2f}", f"{invested_pct_of_active:.1f}% Active")
col4.metric("Average Purchase Price", f"${avg_price:,.2f}")
col5.metric("Position & Tier", f"{total_shares:,.0f} shares", f"Tier {current_tier:.1f} / 40")

st.divider()

# --- Pre-calculate Tiers & Target Tier Logic (Close-Price Strategy Matching Upper Tier) ---
temp_tiers = []
prev_buy = reference_peak
for t in range(1, 41):
    if t == 1:
        buy_p = reference_peak
    else:
        buy_p = prev_buy * (1.0 - 0.05)
    prev_buy = buy_p
    temp_tiers.append((t, buy_p))

target_tier_idx = 1
for t, buy_p in temp_tiers:
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
        for t, buy_p in temp_tiers:
            if buy_p >= t_price:
                matched_tier = t
            else:
                break
        tier_filled_shares[matched_tier] += int(t_qty)
        if t_date and t_date not in tier_trade_dates[matched_tier]:
            tier_trade_dates[matched_tier].append(t_date)

target_tier_price = temp_tiers[target_tier_idx - 1][1]
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

# Check today's trades from trade history dynamically
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
            st.info(
                f"평단매수 비추천\n\n"
                f"현재가 ${current_soxl_price:,.2f} >= 평단 ${avg_price:,.2f}"
            )
    else:
        st.info("보유 포지션 없음")
    
    if already_bought_today:
        st.warning(f"오늘 매수 완료\n\n{today_str} : {today_shares_sum}주 매수완료")

with c_tier_buy:
    st.markdown(f"### 📍 티어매수 가이드 (Tier {target_tier_idx})")
    
    target_dates = tier_trade_dates.get(target_tier_idx, [])
    dates_str = ", ".join(target_dates) if target_dates else "-"
    
    est_cost_tier = recommended_buy_qty * target_tier_price
    
    if current_filled_qty >= standard_tier_qty:
        st.warning(
            f"티어매수 비추천\n\n"
            f"tier {target_tier_idx}  {dates_str}  {current_filled_qty} / {standard_tier_qty} 매수완료"
        )
    elif current_filled_qty > 0:
        st.success(
            f"티어매수 추가 추천 (0.5티어)\n\n"
            f"tier {target_tier_idx}  {dates_str}  {current_filled_qty} / {standard_tier_qty} 보유\n\n"
            f"* 잔여 수량 중 0.5티어 ({recommended_buy_qty}주) 매수 필요"
        )
    else:
        st.success(
            f"티어매수 추천 (0.5티어)\n\n"
            f"tier {target_tier_idx}  0 / {standard_tier_qty} 보유\n\n"
            f"* 추천 수량: 0.5티어 ({recommended_buy_qty}주)"
        )
    
    st.info(
        f"* 목표 가격: ${target_tier_price:,.2f}\n"
        f"* 추천 수량: {recommended_buy_qty}주 (0.5티어)\n"
        f"* 예상 필요자금: ${est_cost_tier:,.2f}"
    )

with c_crash_buy:
    st.markdown("### 🚨 폭락장 대비 추가매수")
    
    next_tiers_to_show = [t for t in range(target_tier_idx + 1, min(41, target_tier_idx + 6))]
    if next_tiers_to_show:
        html_content = "<div style='background-color: #f8d7da; padding: 15px; border-radius: 5px; font-size: 14px; line-height: 1.6; color: #721c24;'>하위 5개 티어 현황:<br><br>"
        for nt in next_tiers_to_show:
            nt_price = temp_tiers[nt - 1][1]
            nt_qty = int(unit_capital // nt_price) if nt_price > 0 else 0
            filled_qty_nt = tier_filled_shares.get(nt, 0)
            
            if filled_qty_nt >= nt_qty and nt_qty > 0:
                html_content += f"<span style='color: #0000FF; font-weight: bold;'>tier {nt} : ${nt_price:,.2f} | {filled_qty_nt} / {nt_qty}주</span><br><br>"
            else:
                html_content += f"tier {nt} : ${nt_price:,.2f} | {filled_qty_nt} / {nt_qty}주<br><br>"
        html_content += "</div>"
        st.markdown(html_content, unsafe_allow_html=True)
    else:
        st.info("마지막 40티어 도달")

with c_sell:
    st.markdown("### 🎯 Take Profit 가이드")
    if avg_price > 0 and total_shares > 0:
        p_10 = avg_price * 1.10
        p_20 = avg_price * 1.20
        qty_half = int(total_shares / 2)
        qty_all = int(total_shares)
        
        st.success(f"10% 절반 익절 (${p_10:,.2f})\n\n매도: {qty_half}주")
        st.success(f"20% 전량 익절 (${p_20:,.2f})\n\n매도: {qty_all}주 (사이클 종료)")
    else:
        st.info("보유 포지션 없음")

st.divider()

# --- 2. Lower Section: 40-Tier Master Grid Table ---
st.subheader("📊 40-Tier Master Grid & Target Price Table (Live Price Highlighted)")

tier_data = []
cum_shares = 0
prev_buy = reference_peak
cum_actual_shares = 0
cum_real_buy_shares = 0

for t, buy_p in temp_tiers:
    if t == 1:
        drop_pct = 0.0
    else:
        drop_pct = ((buy_p - reference_peak) / reference_peak) * 100
    
    take_profit_p = buy_p * 1.10
    suggested_shares = int(unit_capital // buy_p) if buy_p > 0 else 0
    cum_shares += suggested_shares
    
    input_bought_qty = tier_filled_shares.get(t, 0)
    cum_actual_shares += input_bought_qty
    cum_real_buy_shares += input_bought_qty
    
    tier_data.append({
        "Tier": t,
        "매수": round(buy_p, 2),
        "수량": suggested_shares,
        "매도": round(take_profit_p, 2),
        "매수기준": "-5.00%",
        "매도기준": "10.00%",
        "시드비율": f"{(1/40)*100:.2f}%",
        "배정시드": round(unit_capital, 2),
        "1Tier대비": f"{drop_pct:.2f}%",
        "매수 (입력)": input_bought_qty,
        "실수량": cum_actual_shares,
        "예상": cum_shares,
        "실매수": cum_real_buy_shares
    })

df_tiers = pd.DataFrame(tier_data)

def highlight_current_price_tier(row):
    t_num = row["Tier"]
    if t_num < target_tier_idx:
        return ['background-color: #d4edda; color: #155724'] * len(row)
    elif t_num == target_tier_idx:
        return ['background-color: #cce5ff; color: #004085; font-weight: bold'] * len(row)
    else:
        str_bg = 'background-color: #f8d7da; color: #721c24'
        return [str_bg] * len(row)

styled_df = df_tiers.style.apply(highlight_current_price_tier, axis=1).format({
    "매수": "{:.2f}",
    "매도": "{:.2f}",
    "배정시드": "{:,.2f}"
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
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    date_input_val = f_col1.date_input("Trade Date")
    price = f_col2.number_input("Execution Price ($)", min_value=0.01, value=float(round(target_tier_price, 2)), step=0.1)
    qty = f_col3.number_input("Execution Quantity (Shares)", min_value=1.0, value=float(max(1.0, recommended_buy_qty)), step=1.0)
    tier_add = f_col4.selectbox("Executed Tier Weight", [0.5, 1.0, 1.5, 2.0])
    
    submitted = st.form_submit_button("Save Trade")
    if submitted:
        new_trade = {
            "Date": str(date_input_val),
            "Type": "BUY",
            "Price": float(round(price, 2)),
            "Qty": float(qty),
            "Amount": float(round(price * qty, 2)),
            "Tier": float(tier_add)
        }
        st.session_state.trades.append(new_trade)
        save_trades(st.session_state.trades)
        st.session_state.trades = load_trades()
        st.rerun()

# --- Editable & Sortable Trade History Section ---
st.subheader("📋 Trade History (Click any column header to sort)")

if not df_trades.empty:
    df_trades["Date"] = df_trades["Date"].astype(str)
    
    delta_display_df = df_trades[["Date", "Type", "Price", "Qty", "Amount", "Tier"]].copy()
    
    edited_df = st.data_editor(
        delta_display_df,
        num_rows="dynamic",
        use_container_width=True,
    )

    updated_trades = edited_df.to_dict(orient="records")
    if updated_trades != st.session_state.trades:
        save_trades(updated_trades)
        st.session_state.trades = load_trades()
        st.rerun()

    if st.button("Clear All History (Cycle Reset)"):
        st.session_state.trades = []
        save_trades([])
        st.rerun()
else:
    st.info("No trade history recorded yet.")