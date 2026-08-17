"""Data Upload tab."""

import pandas as pd
import streamlit as st

from utils.data_processing import validate_transactions
from utils.portfolio_math import PortfolioAccountingError, calculate_fifo


def render() -> None:
    st.subheader("Transaction history")
    st.caption("Upload a CSV with ticker, date, transaction_type, quantity, and price.")
    uploaded = st.file_uploader("Choose transaction CSV", type=["csv"])
    if uploaded is None:
        st.info("Upload your transaction history to populate every dashboard tab.")
        return
    result = validate_transactions(uploaded)
    if result.fatal_errors:
        for error in result.fatal_errors:
            st.error(error)
        st.session_state.transactions = None
        return
    if not result.invalid.empty:
        st.error(f"Found {len(result.invalid)} invalid row(s). Fix them and upload again.")
        st.dataframe(result.invalid, use_container_width=True, hide_index=True)
        st.session_state.transactions = None
        return
    try:
        calculate_fifo(result.valid)
    except PortfolioAccountingError as exc:
        st.error(str(exc))
        st.session_state.transactions = None
        return

    fingerprint = uploaded.getvalue()
    if st.session_state.get("upload_fingerprint") != fingerprint:
        st.session_state.transactions = result.valid
        st.session_state.upload_name = uploaded.name
        st.session_state.upload_fingerprint = fingerprint
        st.session_state.chat_messages = []
        for key in ("portfolio_result", "valued_holdings", "metrics", "xirr"):
            st.session_state.pop(key, None)
        st.rerun()
    frame: pd.DataFrame = st.session_state.transactions
    columns = st.columns(4)
    columns[0].metric("Transactions", f"{len(frame):,}")
    columns[1].metric("Unique tickers", frame["ticker"].nunique())
    columns[2].metric("Earliest", frame["date"].min().strftime("%b %d, %Y"))
    columns[3].metric("Most recent", frame["date"].max().strftime("%b %d, %Y"))
    display = frame.copy()
    display["date"] = display["date"].dt.date
    st.success("Transaction history validated and sorted chronologically.")
    st.dataframe(display, use_container_width=True, hide_index=True)
