"""Load: store the clean data in a SQLite database. Loading is safe to repeat."""
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS exchange_rates (
    date      TEXT NOT NULL,
    code      TEXT NOT NULL,
    currency  TEXT,
    rate_pln  REAL NOT NULL,
    loaded_at TEXT NOT NULL,
    PRIMARY KEY (date, code)
);
"""


def connect(db_path):
    """Open the database (creating the folder and the table if needed)."""
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def last_loaded_date(conn, code):
    """Latest date already stored for a currency, or None. Used for incremental loads."""
    row = conn.execute(
        "SELECT MAX(date) FROM exchange_rates WHERE code = ?", (code,)
    ).fetchone()
    return date.fromisoformat(row[0]) if row and row[0] else None


def load(conn, df):
    """Insert rows. A row with the same (date, code) is replaced, so no duplicates appear.

    Returns the number of new rows added to the table.
    """
    if df.empty:
        return 0
    before = conn.execute("SELECT COUNT(*) FROM exchange_rates").fetchone()[0]
    loaded_at = datetime.now().isoformat(timespec="seconds")
    rows = [
        (d.strftime("%Y-%m-%d"), code, currency, float(rate), loaded_at)
        for d, code, currency, rate in df[["date", "code", "currency", "rate_pln"]].itertuples(index=False)
    ]
    with conn:
        conn.executemany(
            "INSERT OR REPLACE INTO exchange_rates (date, code, currency, rate_pln, loaded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    after = conn.execute("SELECT COUNT(*) FROM exchange_rates").fetchone()[0]
    return after - before
