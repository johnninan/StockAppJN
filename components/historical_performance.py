"""Historical Performance tab."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render(metrics: dict[str, float] | None, xirr: float | None, history: pd.DataFrame) -> None:
    st.subheader("Historical performance")
    if metrics is None:
        st.info("Upload a valid transaction CSV in the Data Upload tab first.")
        return
    cards = st.columns(4)
    cards[0].metric("Total investment", f"${metrics['total_investment']:,.2f}")
    cards[1].metric("Total sell proceeds", f"${metrics['total_sell_proceeds']:,.2f}")
    cards[2].metric("Current portfolio value", f"${metrics['current_portfolio_value']:,.2f}")
    cards[3].metric(
        "Total return", f"${metrics['total_return']:,.2f}",
        f"{metrics['total_return_pct']:+.2f}%" if pd.notna(metrics["total_return_pct"]) else None,
    )
    st.metric("Annualized XIRR", f"{xirr * 100:+.2f}%" if xirr is not None else "Unavailable")
    if xirr is None:
        st.caption("XIRR needs at least one negative and one positive dated cash flow with a valid root.")
    st.markdown("#### Portfolio history")
    if history.empty:
        st.warning("Historical price data is unavailable, so the chart could not be reconstructed.")
        return
    figure = go.Figure()
    colors = ["#3b82f6", "#f59e0b", "#10b981"]
    for column, color in zip(history.columns, colors):
        figure.add_trace(go.Scatter(x=history.index, y=history[column], name=column,
                                    mode="lines", line={"color": color}))
    figure.update_layout(
        hovermode="x unified", yaxis_tickprefix="$", yaxis_tickformat=",.0f",
        margin={"t": 20, "b": 20, "l": 20, "r": 20},
        legend={"orientation": "h", "y": 1.08},
    )
    st.plotly_chart(figure, use_container_width=True)
    st.caption("Market value uses adjusted daily closes; cash invested and sell proceeds are cumulative transaction cash flows.")
