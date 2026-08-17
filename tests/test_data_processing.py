from io import StringIO

from utils.data_processing import validate_transactions


def test_normalizes_and_sorts():
    result = validate_transactions(StringIO(
        "ticker,date,transaction_type,quantity,price\n"
        " msft ,2024-02-01,bUy,2,100\nAapl,2024-01-01,SELL,1,120\n"
    ))
    assert result.invalid.empty
    assert result.valid["ticker"].tolist() == ["AAPL", "MSFT"]
    assert result.valid["transaction_type"].tolist() == ["Sell", "Buy"]


def test_flags_bad_rows():
    result = validate_transactions(StringIO(
        "ticker,date,transaction_type,quantity,price\nAAPL,nope,Hold,-1,x\n"
    ))
    assert result.valid.empty
    assert "date is invalid" in result.invalid.iloc[0]["validation_error"]

