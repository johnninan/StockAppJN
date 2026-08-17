"""CSV ingestion, normalization, and transaction validation."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import BinaryIO, TextIO

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("ticker", "date", "transaction_type", "quantity", "price")


@dataclass(frozen=True)
class ValidationResult:
    """Validated rows and row-specific errors from an uploaded CSV."""

    valid: pd.DataFrame
    invalid: pd.DataFrame
    fatal_errors: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.fatal_errors and self.invalid.empty and not self.valid.empty


def validate_transactions(source: BinaryIO | TextIO | BytesIO | StringIO) -> ValidationResult:
    """Read a CSV and return normalized valid rows plus clearly annotated invalid rows."""
    try:
        raw = pd.read_csv(source)
    except Exception as exc:
        return ValidationResult(pd.DataFrame(), pd.DataFrame(), (f"Could not read CSV: {exc}",))

    raw.columns = [str(column).strip().lower() for column in raw.columns]
    missing = [column for column in REQUIRED_COLUMNS if column not in raw.columns]
    if missing:
        return ValidationResult(
            pd.DataFrame(), raw, (f"Missing required columns: {', '.join(missing)}",)
        )
    if raw.empty:
        return ValidationResult(pd.DataFrame(), raw, ("The CSV contains no transactions.",))

    frame = raw.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame.insert(0, "source_row", np.arange(2, len(frame) + 2))
    frame["ticker"] = frame["ticker"].astype("string").str.strip().str.upper()
    frame["transaction_type"] = frame["transaction_type"].astype("string").str.strip().str.title()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["quantity"] = pd.to_numeric(frame["quantity"], errors="coerce")
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")

    errors: list[list[str]] = [[] for _ in range(len(frame))]
    for position, row in enumerate(frame.itertuples(index=False)):
        if pd.isna(row.ticker) or not str(row.ticker).strip():
            errors[position].append("ticker is blank")
        if pd.isna(row.date):
            errors[position].append("date is invalid")
        elif row.date.date() > pd.Timestamp.now().date():
            errors[position].append("date is in the future")
        if row.transaction_type not in {"Buy", "Sell"}:
            errors[position].append("transaction_type must be Buy or Sell")
        if pd.isna(row.quantity) or not np.isfinite(row.quantity) or row.quantity <= 0:
            errors[position].append("quantity must be a positive number")
        if pd.isna(row.price) or not np.isfinite(row.price) or row.price <= 0:
            errors[position].append("price must be a positive number")

    frame["validation_error"] = ["; ".join(items) for items in errors]
    invalid = frame.loc[frame["validation_error"] != ""].copy()
    valid = frame.loc[frame["validation_error"] == "", list(REQUIRED_COLUMNS)].copy()
    valid = valid.sort_values("date", kind="stable").reset_index(drop=True)
    return ValidationResult(valid, invalid.reset_index(drop=True))
