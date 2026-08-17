"""Consolidated Portfolio View tab."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from utils.llm_agent import LLMServiceError, groq_is_configured, portfolio_summary


def _money(value: float) -> str:
    return "Unavailable" if pd.isna(value) else f"${value:,.2f}"


def render(holdings: pd.DataFrame | None, market_errors: dict[str, str]) -> None:
    st.subheader("Consolidated portfolio")
    if holdings is None:
        st.info("Upload a valid transaction CSV in the Data Upload tab first.")
        return
    if market_errors:
        st.warning("Prices unavailable for: " + ", ".join(sorted(market_errors)))
    if holdings.empty:
        st.info("Your transaction history contains no open positions.")
        return
    priced = holdings.dropna(subset=["current_price"]).copy()
    missing_count = len(holdings) - len(priced)
    total_value = float(priced["market_value"].sum())
    total_basis = float(holdings["remaining_cost_basis"].sum())
    priced_basis = float(priced["remaining_cost_basis"].sum())
    total_gain = total_value - priced_basis
    total_pct = total_gain / priced_basis * 100 if priced_basis else np.nan
    cards = st.columns(4)
    cards[0].metric("Portfolio value", _money(total_value))
    cards[1].metric("Remaining cost basis", _money(total_basis))
    cards[2].metric("Unrealized gain/loss", _money(total_gain), f"{total_pct:+.2f}%")
    cards[3].metric("Priced positions", f"{len(priced)}/{len(holdings)}")
    if missing_count:
        st.caption(
            "Market value and unrealized return include priced positions only; remaining cost "
            "basis includes every open position."
        )

    if not priced.empty and total_value > 0:
        figure = px.pie(
            priced, names="ticker", values="market_value", hole=0.55,
            title="Allocation by current market value",
        )
        figure.update_traces(textposition="inside", textinfo="label+percent")
        figure.update_layout(
            margin={"t": 55, "b": 10, "l": 10, "r": 10}, legend_title_text="Ticker"
        )
        st.plotly_chart(figure, use_container_width=True)

    shown = holdings.rename(columns={
        "ticker": "Ticker", "quantity": "Quantity", "average_cost_basis": "Avg Cost",
        "current_price": "Current Price", "market_value": "Market Value",
        "unrealized_gain_loss": "Unrealized Gain/Loss",
        "unrealized_gain_loss_pct": "Gain/Loss %",
    })
    st.dataframe(
        shown[["Ticker", "Quantity", "Avg Cost", "Current Price", "Market Value",
               "Unrealized Gain/Loss", "Gain/Loss %"]],
        use_container_width=True, hide_index=True,
        column_config={
            "Quantity": st.column_config.NumberColumn(format="%.4f"),
            "Avg Cost": st.column_config.NumberColumn(format="$%.2f"),
            "Current Price": st.column_config.NumberColumn(format="$%.2f"),
            "Market Value": st.column_config.NumberColumn(format="$%.2f"),
            "Unrealized Gain/Loss": st.column_config.NumberColumn(format="$%.2f"),
            "Gain/Loss %": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )
    st.markdown("#### AI portfolio summary")
    if not groq_is_configured():
        st.info("Set GROQ_API_KEY to enable the AI summary.")
    elif st.button("Generate portfolio summary", type="primary"):
        totals = {"market_value": total_value, "remaining_cost_basis": total_basis,
                  "unrealized_gain_loss": total_gain, "unrealized_gain_loss_pct": total_pct}
        try:
            with st.spinner("Analyzing calculated portfolio data…"):
                st.session_state.ai_summary = portfolio_summary(priced, totals)
        except LLMServiceError as exc:
            st.error(str(exc))
    if st.session_state.get("ai_summary"):
        st.write(st.session_state.ai_summary)
