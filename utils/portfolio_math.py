"""Deterministic FIFO portfolio accounting and performance metrics."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd
from scipy.optimize import brentq

EPSILON = 1e-9


class PortfolioAccountingError(ValueError):
    """Raised when a transaction history cannot be accounted for safely."""


@dataclass(frozen=True)
class PortfolioResult:
    holdings: pd.DataFrame
    realized_sales: pd.DataFrame
    total_investment: float
    total_sell_proceeds: float
    total_realized_gain: float


def calculate_fifo(transactions: pd.DataFrame) -> PortfolioResult:
    """Process chronologically sorted transactions using FIFO lots."""
    lots: dict[str, deque[list[float]]] = defaultdict(deque)
    realized: list[dict[str, object]] = []
    ordered = transactions.sort_values("date", kind="stable")
    total_buys = total_sales = 0.0

    for row in ordered.itertuples(index=False):
        ticker, quantity, price = str(row.ticker), float(row.quantity), float(row.price)
        if row.transaction_type == "Buy":
            lots[ticker].append([quantity, price])
            total_buys += quantity * price
            continue
        available = sum(lot[0] for lot in lots[ticker])
        if quantity > available + EPSILON:
            raise PortfolioAccountingError(
                f"Invalid sale for {ticker} on {pd.Timestamp(row.date).date()}: "
                f"attempted {quantity:g} shares but only {available:g} were available."
            )
        remaining, sale_cost = quantity, 0.0
        while remaining > EPSILON:
            lot_quantity, lot_price = lots[ticker][0]
            used = min(remaining, lot_quantity)
            sale_cost += used * lot_price
            remaining -= used
            lot_quantity -= used
            if lot_quantity <= EPSILON:
                lots[ticker].popleft()
            else:
                lots[ticker][0][0] = lot_quantity
        proceeds = quantity * price
        total_sales += proceeds
        realized.append({
            "ticker": ticker, "date": pd.Timestamp(row.date), "quantity": quantity,
            "proceeds": proceeds, "cost_basis": sale_cost,
            "realized_gain_loss": proceeds - sale_cost,
        })

    holding_rows = []
    for ticker, ticker_lots in sorted(lots.items()):
        quantity = sum(lot[0] for lot in ticker_lots)
        if quantity <= EPSILON:
            continue
        cost = sum(lot[0] * lot[1] for lot in ticker_lots)
        holding_rows.append({
            "ticker": ticker, "quantity": quantity, "remaining_cost_basis": cost,
            "average_cost_basis": cost / quantity,
        })
    holdings = pd.DataFrame(holding_rows, columns=[
        "ticker", "quantity", "remaining_cost_basis", "average_cost_basis"
    ])
    sales = pd.DataFrame(realized, columns=[
        "ticker", "date", "quantity", "proceeds", "cost_basis", "realized_gain_loss"
    ])
    return PortfolioResult(holdings, sales, total_buys, total_sales, float(sales.get(
        "realized_gain_loss", pd.Series(dtype=float)
    ).sum()))


def value_holdings(holdings: pd.DataFrame, prices: Mapping[str, float | None]) -> pd.DataFrame:
    """Attach market prices and deterministic unrealized metrics to open holdings."""
    valued = holdings.copy()
    valued["current_price"] = valued["ticker"].map(prices).astype(float)
    valued["market_value"] = valued["quantity"] * valued["current_price"]
    valued["unrealized_gain_loss"] = valued["market_value"] - valued["remaining_cost_basis"]
    valued["unrealized_gain_loss_pct"] = (
        valued["unrealized_gain_loss"] / valued["remaining_cost_basis"] * 100
    )
    total_value = valued["market_value"].sum(min_count=1)
    valued["allocation_pct"] = valued["market_value"] / total_value * 100
    return valued


def performance_summary(result: PortfolioResult, current_value: float) -> dict[str, float]:
    """Return portfolio-wide economic performance metrics."""
    total_return = result.total_sell_proceeds + current_value - result.total_investment
    return {
        "total_investment": result.total_investment,
        "total_sell_proceeds": result.total_sell_proceeds,
        "current_portfolio_value": current_value,
        "total_return": total_return,
        "total_return_pct": (
            total_return / result.total_investment * 100 if result.total_investment else np.nan
        ),
    }


def calculate_xirr(transactions: pd.DataFrame, current_value: float, as_of: date | None = None) -> float | None:
    """Calculate annualized money-weighted return using actual dated cash flows."""
    as_of = as_of or datetime.now(UTC).date()
    cashflows = [
        (pd.Timestamp(row.date).date(), (-1 if row.transaction_type == "Buy" else 1)
         * float(row.quantity) * float(row.price))
        for row in transactions.sort_values("date", kind="stable").itertuples(index=False)
    ]
    if current_value > 0:
        cashflows.append((as_of, current_value))
    if not cashflows or not any(v < 0 for _, v in cashflows) or not any(v > 0 for _, v in cashflows):
        return None
    origin = min(day for day, _ in cashflows)

    def npv(rate: float) -> float:
        return sum(value / (1 + rate) ** ((day - origin).days / 365.0) for day, value in cashflows)

    grid = np.concatenate((np.linspace(-0.9999, 0, 200), np.logspace(-4, 4, 500)))
    previous_rate, previous_value = float(grid[0]), npv(float(grid[0]))
    for rate in grid[1:]:
        value = npv(float(rate))
        if np.isfinite(value) and previous_value * value < 0:
            try:
                return float(brentq(npv, previous_rate, float(rate), maxiter=500))
            except (ValueError, RuntimeError, OverflowError):
                pass
        previous_rate, previous_value = float(rate), value
    return None
