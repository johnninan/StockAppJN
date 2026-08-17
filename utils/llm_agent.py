"""Groq prompts and structured portfolio context preparation."""

from __future__ import annotations

import json
import os
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from groq import APIConnectionError, APIStatusError, AuthenticationError, Groq, RateLimitError

load_dotenv()

SYSTEM_PROMPT = """You are a careful personal portfolio analysis assistant. Use only the structured
data supplied by the application. Never invent prices, transactions, returns, market events, or news.
Financial calculations are authoritative and already computed in Python: interpret them, do not
recalculate them. Clearly state when requested information is unavailable. Provide analytical
observations, not personalized financial advice or definitive buy/sell instructions. Be concise and
specific, and mention that market data may be delayed when discussing current prices."""


class LLMServiceError(RuntimeError):
    """A safe, actionable Groq error suitable for display in the UI."""


def groq_is_configured() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def _client() -> Groq:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not configured. Add it to .env or your environment.")
    return Groq(api_key=key)


def _completion(**kwargs: Any) -> str:
    """Call Groq and convert SDK/network failures to stable user-facing errors."""
    try:
        response = _client().chat.completions.create(**kwargs)
    except AuthenticationError as exc:
        raise LLMServiceError(
            "Groq rejected GROQ_API_KEY. Replace it in .env, then restart the app."
        ) from exc
    except RateLimitError as exc:
        raise LLMServiceError("Groq rate limit reached. Please wait briefly and try again.") from exc
    except APIConnectionError as exc:
        raise LLMServiceError("Could not connect to Groq. Check your network and try again.") from exc
    except APIStatusError as exc:
        raise LLMServiceError(f"Groq returned an API error (HTTP {exc.status_code}).") from exc
    return response.choices[0].message.content or "No response was returned."


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.copy()
    for column in clean.select_dtypes(include=["datetime", "datetimetz"]).columns:
        clean[column] = clean[column].dt.strftime("%Y-%m-%d")
    return json.loads(clean.to_json(orient="records", date_format="iso"))


def prepare_portfolio_context(
    transactions: pd.DataFrame, holdings: pd.DataFrame, metrics: dict[str, Any],
    realized_sales: pd.DataFrame, xirr: float | None,
    recent_market_performance: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    """Create JSON-safe, calculated context; no raw market lookups occur here."""
    useful_holding_columns = [
        "ticker", "quantity", "average_cost_basis", "current_price", "market_value",
        "unrealized_gain_loss", "unrealized_gain_loss_pct", "allocation_pct",
    ]
    return {
        "as_of": pd.Timestamp.now().isoformat(),
        "transactions": _records(transactions),
        "current_holdings": _records(holdings.reindex(columns=useful_holding_columns)),
        "realized_sales": _records(realized_sales),
        "lifetime_metrics": {**metrics, "xirr_pct": None if xirr is None else xirr * 100},
        "market_data_complete": bool(
            holdings.empty or holdings["current_price"].notna().all()
        ),
        "recent_market_performance_pct": recent_market_performance,
    }


def portfolio_summary(holdings: pd.DataFrame, metrics: dict[str, Any]) -> str:
    """Generate a 2–3 sentence summary using only aggregate/holding calculations."""
    context = {
        "holdings": _records(holdings[[
            "ticker", "market_value", "unrealized_gain_loss", "unrealized_gain_loss_pct",
            "allocation_pct",
        ]]),
        "portfolio_totals": metrics,
    }
    return _completion(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), temperature=0.1,
        max_tokens=220,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Write exactly 2–3 sentences on unrealized performance, "
             "largest holdings/concentration, and diversification risk. Data:\n" + json.dumps(context)},
        ],
    )


def chat_response(context: dict[str, Any], messages: list[dict[str, str]]) -> str:
    """Answer a portfolio question with authoritative structured context."""
    prompt_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    prompt_messages.append({"role": "system", "content": "PORTFOLIO DATA:\n" + json.dumps(context)})
    prompt_messages.extend(messages[-12:])
    return _completion(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), temperature=0.15,
        max_tokens=800, messages=prompt_messages,
    )
