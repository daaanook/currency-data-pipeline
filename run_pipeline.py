"""Run the whole pipeline: extract -> transform -> load -> report.

Examples:
    python3 run_pipeline.py
    python3 run_pipeline.py --currencies EUR USD --start 2025-01-01
    python3 run_pipeline.py --full      # reload everything, ignore what is already stored
"""
import argparse
import logging
from datetime import date, timedelta

from pipeline.extract import extract
from pipeline.load import connect, last_loaded_date, load
from pipeline.report import run_report
from pipeline.transform import transform

log = logging.getLogger("pipeline")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="NBP exchange rate pipeline")
    p.add_argument("--currencies", nargs="+", default=["EUR", "USD", "GBP", "CHF"])
    p.add_argument("--start", type=date.fromisoformat, default=date(2024, 1, 1))
    p.add_argument("--end", type=date.fromisoformat, default=date.today())
    p.add_argument("--db", default="data/rates.db")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--reports", default="reports")
    p.add_argument("--full", action="store_true", help="ignore stored data and reload the full range")
    return p.parse_args(argv)


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    conn = connect(args.db)

    total_new = 0
    for code in (c.upper() for c in args.currencies):
        start = args.start
        if not args.full:
            last = last_loaded_date(conn, code)
            if last:
                start = max(args.start, last + timedelta(days=1))
        if start > args.end:
            log.info("%s is up to date", code)
            continue

        log.info("%s: extracting %s to %s", code, start, args.end)
        payloads = extract(code, start, args.end, raw_dir=args.raw_dir)
        df = transform(payloads)
        new_rows = load(conn, df)
        total_new += new_rows
        log.info("%s: %d new rows loaded", code, new_rows)

    log.info("Pipeline finished: %d new rows in total", total_new)
    run_report(conn, args.reports)
    conn.close()


if __name__ == "__main__":
    main()
