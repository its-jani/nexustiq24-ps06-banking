import io
from datetime import date, datetime

import pytest

from app.ingest import IngestionError, parse_csv, REQUIRED_COLUMNS

HEADER = "date,description,payee,amount,channel"


def _csv(rows):
    return io.StringIO("\n".join([HEADER] + rows))


def test_parse_minimal_valid_csv():
    txs = parse_csv(_csv([
        "2024-01-05,Grocery,Whole Foods,-123.45,card",
        "2024-01-06,Salary,Acme Corp,2000.00,direct_deposit",
    ]))
    assert len(txs) == 2
    t0, t1 = txs
    assert t0.date == datetime(2024, 1, 5)
    assert t0.amount == -123.45
    assert t0.channel == "card"
    assert t0.row == 2  # 1-based input CSV row (header is row 1)


def test_row_traceability_is_1_based_input_index():
    txs = parse_csv(_csv([
        "  ",  # blank row skipped, does not shift row numbers
        "2024-01-05,Grocery,Market,-10.00,card",
    ]))
    assert txs[0].row == 3


def test_extra_columns_are_tolerated():
    txs = parse_csv(io.StringIO(
        "date,description,payee,amount,channel,extra\n"
        "2024-01-05,Bill,Utility,25.00,ach,JUNK\n"
    ))
    assert len(txs) == 1
    assert txs[0].amount == 25.00


def test_header_case_and_spaces_are_tolerated():
    txs = parse_csv(io.StringIO(
        "Date, Description ,Payee, Amount,Channel\n"
        "2024-01-05,Bill,Utility,25.00,ach\n"
    ))
    assert len(txs) == 1


def test_blank_payee_and_blank_description_allowed():
    txs = parse_csv(_csv(["2024-01-05,,,-50.00,atm"]))
    assert txs[0].payee == ""
    assert txs[0].description == ""


def test_us_date_format_accepted():
    txs = parse_csv(_csv(["01/05/2024,Grocery,Store,-10.00,card"]))
    assert txs[0].date == datetime(2024, 1, 5)


def test_datetime_with_time_accepted():
    txs = parse_csv(_csv(["2024-01-05 14:30:00,Grocery,Store,-10.00,card"]))
    assert txs[0].date == datetime(2024, 1, 5, 14, 30)


def test_missing_required_column_rejected():
    with pytest.raises(IngestionError) as exc:
        parse_csv(io.StringIO("date,payee,amount,channel\n2024-01-05,X,1,card\n"))
    assert "amount" in str(exc.value)


def test_bad_amount_raises_with_row_number():
    with pytest.raises(IngestionError) as exc:
        parse_csv(_csv(["2024-01-05,Grocery,Store,not-a-number,card"]))
    assert "row 2" in str(exc.value)


def test_bad_date_raises_with_row_number():
    with pytest.raises(IngestionError) as exc:
        parse_csv(_csv(["2024-13-45,Grocery,Store,-10.00,card"]))
    assert "row 2" in str(exc.value)


def test_empty_file_rejected():
    with pytest.raises(IngestionError):
        parse_csv(io.StringIO(""))


def test_missing_header_rejected():
    with pytest.raises(IngestionError):
        parse_csv(io.StringIO(""))


def test_required_columns_export():
    assert REQUIRED_COLUMNS == ["date", "description", "payee", "amount", "channel"]