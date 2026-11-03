"""Transform: turn the nested JSON from the API into a clean table."""
import logging

import pandas as pd

log = logging.getLogger(__name__)

COLUMNS = ["date", "code", "currency", "rate_pln"]


def to_dataframe(payloads):
    """Flatten the JSON payloads into one row per currency per day."""
    rows = [
        {
            "date": rate["effectiveDate"],
            "code": payload["code"],
            "currency": payload["currency"],
            "rate_pln": rate["mid"],
        }
        for payload in payloads
        for rate in payload.get("rates", [])
    ]
    return pd.DataFrame(rows, columns=COLUMNS)


def clean(df):
    """Fix types and remove invalid or duplicate rows."""
    if df.empty:
        return df
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["rate_pln"] = pd.to_numeric(df["rate_pln"], errors="coerce")

    before = len(df)
    df = df.dropna(subset=["date", "rate_pln"])
    df = df[df["rate_pln"] > 0]
    df = df.drop_duplicates(subset=["date", "code"], keep="last")
    removed = before - len(df)
    if removed:
        log.warning("Removed %d invalid or duplicate row(s)", removed)

    return df.sort_values(["code", "date"]).reset_index(drop=True)


def transform(payloads):
    return clean(to_dataframe(payloads))
