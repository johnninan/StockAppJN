import pandas as pd
import pytest

from utils.portfolio_math import (
    PortfolioAccountingError,
    calculate_fifo,
    calculate_xirr,
    performance_summary,
    value_holdings,
)


def transactions(rows):
    frame = pd.DataFrame(rows, columns=["ticker", "date", "transaction_type", "quantity", "price"])
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def test_fifo_partial_lot_sale():
    result = calculate_fifo(transactions([
        ("AAPL", "2024-01-01", "Buy", 10, 100),
        ("AAPL", "2024-02-01", "Buy", 10, 120),
        ("AAPL", "2024-03-01", "Sell", 12, 150),
    ]))
    holding = result.holdings.iloc[0]
    assert holding["quantity"] == pytest.approx(8)
    assert holding["remaining_cost_basis"] == pytest.approx(960)
    assert result.total_realized_gain == pytest.approx(560)


def test_oversell_is_rejected_chronologically():
    with pytest.raises(PortfolioAccountingError):
        calculate_fifo(transactions([
            ("AAPL", "2024-02-01", "Buy", 10, 100),
            ("AAPL", "2024-01-01", "Sell", 1, 110),
        ]))


def test_xirr_simple_one_year_return():
    frame = transactions([("AAPL", "2024-01-01", "Buy", 10, 100)])
    rate = calculate_xirr(frame, 1100, as_of=pd.Timestamp("2025-01-01").date())
    assert rate == pytest.approx(0.10, abs=0.001)


def test_closed_position_and_economic_return():
    result = calculate_fifo(transactions([
        ("AAPL", "2024-01-01", "Buy", 2, 100),
        ("AAPL", "2024-02-01", "Sell", 2, 125),
    ]))
    assert result.holdings.empty
    assert result.total_realized_gain == pytest.approx(50)
    assert performance_summary(result, 0)["total_return"] == pytest.approx(50)


def test_missing_price_does_not_crash_valuation():
    result = calculate_fifo(transactions([("AAPL", "2024-01-01", "Buy", 2, 100)]))
    valued = value_holdings(result.holdings, {"AAPL": None})
    assert pd.isna(valued.iloc[0]["current_price"])
    assert pd.isna(valued.iloc[0]["market_value"])
