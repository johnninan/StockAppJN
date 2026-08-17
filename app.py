"""Personal Stock Analyst Streamlit entry point."""

from datetime import UTC, datetime

import pandas as pd
import streamlit as st

from components import ai_analyst, data_upload, historical_performance, portfolio_view
from utils.market_data import build_portfolio_history, get_historical_prices, get_latest_prices
from utils.portfolio_math import calculate_fifo, calculate_xirr, performance_summary, value_holdings

st.set_page_config(page_title="Personal Stock Analyst", page_icon="📈", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1400px;}
[data-testid="stMetric"] {background: rgba(100,116,139,.08); border: 1px solid rgba(100,116,139,.18); padding: 1rem; border-radius: .75rem;}
[data-testid="stMetricDelta"] svg {display: none;}
</style>
""", unsafe_allow_html=True)

DEFAULTS = {
    "transactions": None, "upload_name": None, "chat_messages": [],
    "portfolio_result": None, "valued_holdings": None, "metrics": None, "xirr": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

st.title("Personal Stock Analyst")
st.caption("FIFO portfolio accounting, interactive performance analysis, and grounded AI insights")

transactions = st.session_state.transactions
market_errors: dict[str, str] = {}
history = pd.DataFrame()
if transactions is not None:
    result = calculate_fifo(transactions)
    open_tickers = tuple(result.holdings["ticker"]) if not result.holdings.empty else ()
    all_tickers = tuple(sorted(transactions["ticker"].unique()))
    if open_tickers:
        with st.spinner("Retrieving latest market prices…"):
            prices, market_errors = get_latest_prices(open_tickers)
        holdings = value_holdings(result.holdings, prices)
    else:
        holdings = value_holdings(result.holdings, {})
    current_value = float(holdings["market_value"].sum(skipna=True)) if not holdings.empty else 0.0
    metrics = performance_summary(result, current_value)
    xirr = calculate_xirr(transactions, current_value)
    st.session_state.portfolio_result = result
    st.session_state.valued_holdings = holdings
    st.session_state.metrics = metrics
    st.session_state.xirr = xirr
    if all_tickers:
        start = transactions["date"].min().date()
        historical_prices, _ = get_historical_prices(
            all_tickers, start, datetime.now(UTC).date()
        )
        history = build_portfolio_history(transactions, historical_prices)

with st.sidebar:
    st.header("Portfolio file")
    if transactions is None:
        st.info("No validated file loaded")
    else:
        st.success(st.session_state.upload_name or "CSV loaded")
        st.write(f"**Transactions:** {len(transactions):,}")
        st.write(f"**Tickers:** {transactions['ticker'].nunique():,}")
        st.write(f"**Through:** {transactions['date'].max():%b %d, %Y}")
    st.divider()
    st.caption("Market prices are supplied by Yahoo Finance and may be delayed. AI observations are not financial advice.")

tabs = st.tabs(["1  Data Upload", "2  Portfolio", "3  Historical Performance", "4  AI Analyst"])
with tabs[0]:
    data_upload.render()
with tabs[1]:
    portfolio_view.render(st.session_state.valued_holdings, market_errors)
with tabs[2]:
    historical_performance.render(st.session_state.metrics, st.session_state.xirr, history)
with tabs[3]:
    ai_analyst.render(
        st.session_state.transactions, st.session_state.valued_holdings, st.session_state.metrics,
        st.session_state.portfolio_result, st.session_state.xirr,
    )
