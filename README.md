# Personal Stock Analyst

A local, AI-powered Streamlit dashboard for validating U.S. stock transactions, calculating FIFO holdings and returns, reconstructing historical performance, and discussing calculated portfolio data with Groq.

## Features

- Strict CSV validation with chronological normalization and oversell protection
- FIFO remaining cost basis and realized gain/loss accounting
- Current prices and adjusted historical data from Yahoo Finance
- Portfolio economic return and actual-date XIRR
- Interactive Plotly allocation and historical charts
- Groq portfolio summary and persistent session chat grounded in structured calculations

Market data may be unavailable or delayed. The application provides analytical observations, not financial advice.

## Requirements

- [`uv`](https://docs.astral.sh/uv/) installed
- A Groq API key for AI features (the rest of the dashboard works without it)
- Network access for Yahoo Finance and Groq

## Setup and run

From this directory:

```bash
uv sync
```

Copy `.env.example` to `.env`, then replace the placeholder with your Groq key. Do not commit `.env`.

```bash
uv run streamlit run app.py
```

Open the local URL printed by Streamlit, then upload `sample_transactions.csv` or your own CSV.

## CSV format

```csv
ticker,date,transaction_type,quantity,price
AAPL,2024-01-10,Buy,10,185.20
MSFT,2024-02-15,Buy,5,410.50
AAPL,2024-06-20,Sell,3,210.00
```

`Buy` and `Sell` are case-insensitive. Dates must be valid and not in the future; quantity and price must be positive numbers. The complete file is rejected if any row is invalid or any chronological sale exceeds shares then available.

## Project layout

```text
.
├── app.py
├── pyproject.toml
├── .env.example
├── README.md
├── sample_transactions.csv
├── utils/
│   ├── data_processing.py
│   ├── portfolio_math.py
│   ├── market_data.py
│   └── llm_agent.py
└── components/
    ├── data_upload.py
    ├── portfolio_view.py
    ├── historical_performance.py
    └── ai_analyst.py
```

## Verification

```bash
uv run ruff check .
uv run pytest
```

