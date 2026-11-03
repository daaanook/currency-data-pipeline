"""Basic tests. Run with:  python3 -m pytest"""
from datetime import date

from pipeline.extract import date_chunks
from pipeline.load import connect, last_loaded_date, load
from pipeline.transform import transform

SAMPLE = [{
    "table": "A", "currency": "euro", "code": "EUR",
    "rates": [
        {"no": "1", "effectiveDate": "2025-01-02", "mid": 4.2},
        {"no": "2", "effectiveDate": "2025-01-03", "mid": 4.3},
        {"no": "2", "effectiveDate": "2025-01-03", "mid": 4.3},   # duplicate
        {"no": "3", "effectiveDate": "2025-01-06", "mid": -1.0},  # invalid rate
    ],
}]


def test_date_chunks_cover_range_without_gaps():
    chunks = list(date_chunks(date(2023, 1, 1), date(2025, 6, 30)))
    assert chunks[0][0] == date(2023, 1, 1)
    assert chunks[-1][1] == date(2025, 6, 30)
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert (next_start - prev_end).days == 1
    assert all((end - start).days + 1 <= 367 for start, end in chunks)


def test_transform_removes_duplicates_and_invalid_rows():
    df = transform(SAMPLE)
    assert len(df) == 2
    assert df["rate_pln"].gt(0).all()
    assert list(df.columns) == ["date", "code", "currency", "rate_pln"]


def test_load_is_idempotent():
    conn = connect(":memory:")
    df = transform(SAMPLE)
    assert load(conn, df) == 2
    assert load(conn, df) == 0  # second run adds nothing
    assert last_loaded_date(conn, "EUR") == date(2025, 1, 3)
    assert last_loaded_date(conn, "USD") is None
