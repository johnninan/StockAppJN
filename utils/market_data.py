"""Cached, fault-tolerant yfinance market-data access."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf


@st.cache_data(ttl=900, show_spinner=False)
def get_latest_prices(tickers: tuple[str, ...]) -> tuple[dict[str, float | None], dict[str, str]]:
    """Get latest adjusted/regular closing prices without letting one symbol fail all."""
    prices: dict[str, float | None] = {}
    errors: dict[str, str] = {}
    for ticker in sorted(set(tickers)):
        try:
            history = yf.Ticker(ticker).history(period="5d", auto_adjust=True)
            close = history["Close"].dropna()
            if close.empty:
                raise ValueError("no recent closing price returned")
            prices[ticker] = float(close.iloc[-1])
        except Exception as exc:
            prices[ticker] = None
            errors[ticker] = str(exc)
    return prices, errors


@st.cache_data(ttl=3600, show_spinner=False)
def get_historical_prices(
    tickers: tuple[str, ...], start: date, end: date
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Download adjusted daily closes ticker-by-ticker and return a single frame."""
    series, errors = {}, {}
    for ticker in sorted(set(tickers)):
        try:
            data = yf.download(
                ticker, start=start, end=end + timedelta(days=1), auto_adjust=True,
                progress=False, threads=False,
            )
            close = data["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            close = close.dropna()
            if close.empty:
                raise ValueError("no historical prices returned")
            series[ticker] = close.rename(ticker)
        except Exception as exc:
            errors[ticker] = str(exc)
    frame = pd.concat(series.values(), axis=1).sort_index() if series else pd.DataFrame()
    if not frame.empty:
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
    return frame, errors


def build_portfolio_history(transactions: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Reconstruct daily holdings value and cumulative transaction cash flows."""
    if prices.empty:
        return pd.DataFrame()
    tx = transactions.copy()
    tx["date"] = pd.to_datetime(tx["date"]).dt.normalize()
    calendar = prices.index
    quantities = pd.DataFrame(0.0, index=calendar, columns=prices.columns)
    invested = pd.Series(0.0, index=calendar)
    proceeds = pd.Series(0.0, index=calendar)
    for row in tx.itertuples(index=False):
        eligible = calendar[calendar >= pd.Timestamp(row.date)]
        if eligible.empty or row.ticker not in quantities.columns:
            continue
        day = eligible[0]
        signed_quantity = float(row.quantity) * (1 if row.transaction_type == "Buy" else -1)
        quantities.loc[day, row.ticker] += signed_quantity
        amount = float(row.quantity) * float(row.price)
        (invested if row.transaction_type == "Buy" else proceeds).loc[day] += amount
    quantities = quantities.cumsum()
    values = (quantities * prices.ffill()).sum(axis=1)
    return pd.DataFrame({
        "Portfolio Market Value": values,
        "Cumulative Cash Invested": invested.cumsum(),
        "Cumulative Sell Proceeds": proceeds.cumsum(),
    })


@st.cache_data(ttl=900, show_spinner=False)
def recent_performance(tickers: tuple[str, ...], period: str = "1mo") -> dict[str, float | None]:
    """Return price percentage changes for contextual recent-movement questions."""
    output: dict[str, float | None] = {}
    for ticker in sorted(set(tickers)):
        try:
            close = yf.Ticker(ticker).history(period=period, auto_adjust=True)["Close"].dropna()
            output[ticker] = float((close.iloc[-1] / close.iloc[0] - 1) * 100) if len(close) >= 2 else None
        except Exception:
            output[ticker] = None
    return output

