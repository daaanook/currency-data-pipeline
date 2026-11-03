"""Report: analyse the data with SQL and pandas, save charts, CSV files and a summary."""
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # draw to files, no window needed
import matplotlib.pyplot as plt
import pandas as pd

log = logging.getLogger(__name__)

# Daily data with a 30-day moving average and the daily % change (window functions)
DAILY_SQL = """
SELECT date,
       code,
       rate_pln,
       ROUND(AVG(rate_pln) OVER (
           PARTITION BY code ORDER BY date
           ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 4) AS ma_30,
       ROUND(100.0 * (rate_pln - LAG(rate_pln) OVER (PARTITION BY code ORDER BY date))
             / LAG(rate_pln) OVER (PARTITION BY code ORDER BY date), 4) AS daily_change_pct
FROM exchange_rates
ORDER BY code, date
"""

# Monthly statistics per currency
MONTHLY_SQL = """
SELECT code,
       SUBSTR(date, 1, 7)         AS month,
       ROUND(AVG(rate_pln), 4)    AS avg_rate,
       ROUND(MIN(rate_pln), 4)    AS min_rate,
       ROUND(MAX(rate_pln), 4)    AS max_rate,
       COUNT(*)                   AS trading_days
FROM exchange_rates
GROUP BY code, month
ORDER BY code, month
"""

plt.rcParams.update({
    "figure.dpi": 110,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def build_summary(daily):
    """One row per currency: start, end, change, min, max and volatility."""
    rows = []
    for code, g in daily.groupby("code"):
        g = g.sort_values("date")
        first, last = g.iloc[0], g.iloc[-1]
        low, high = g.loc[g["rate_pln"].idxmin()], g.loc[g["rate_pln"].idxmax()]
        rows.append({
            "Currency": code,
            "From": first["date"].date(),
            "To": last["date"].date(),
            "Start rate": first["rate_pln"],
            "End rate": last["rate_pln"],
            "Change %": (last["rate_pln"] / first["rate_pln"] - 1) * 100,
            "Min rate": low["rate_pln"],
            "Min date": low["date"].date(),
            "Max rate": high["rate_pln"],
            "Max date": high["date"].date(),
            "Volatility % (std of daily change)": g["daily_change_pct"].std(),
        })
    return pd.DataFrame(rows)


def to_markdown_table(df):
    """Small markdown table writer (avoids an extra dependency)."""
    def fmt(v):
        return f"{v:.4f}" if isinstance(v, float) else str(v)
    lines = ["| " + " | ".join(df.columns) + " |",
             "|" + "|".join("---" for _ in df.columns) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(fmt(v) for v in row) + " |")
    return "\n".join(lines)


def chart_indexed(daily, path):
    pivot = daily.pivot(index="date", columns="code", values="rate_pln")
    indexed = pivot / pivot.apply(lambda s: s.dropna().iloc[0]) * 100
    fig, ax = plt.subplots(figsize=(10, 4.5))
    indexed.plot(ax=ax)
    ax.axhline(100, color="grey", linewidth=0.8, linestyle="--")
    ax.set_title("Exchange rates against PLN (start of period = 100)")
    ax.set_xlabel("")
    ax.set_ylabel("Index")
    ax.legend(title="")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_moving_average(daily, path):
    codes = daily["code"].unique()
    code = "EUR" if "EUR" in codes else codes[0]
    g = daily[daily["code"] == code]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(g["date"], g["rate_pln"], label=f"{code}/PLN daily", alpha=0.6)
    ax.plot(g["date"], g["ma_30"], label="30-day moving average", linewidth=2)
    ax.set_title(f"{code} to PLN: daily rate and 30-day moving average")
    ax.set_ylabel("PLN")
    ax.legend()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def chart_volatility(summary, path):
    col = "Volatility % (std of daily change)"
    s = summary.sort_values(col)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.barh(s["Currency"], s[col], color="#2e86ab")
    ax.set_title("Volatility: standard deviation of daily change (%)")
    ax.set_xlabel("%")
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def run_report(conn, out_dir="reports"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    daily = pd.read_sql_query(DAILY_SQL, conn, parse_dates=["date"])
    if daily.empty:
        log.warning("No data in the database, report skipped")
        return
    monthly = pd.read_sql_query(MONTHLY_SQL, conn)

    daily.to_csv(out / "rates_daily.csv", index=False)
    monthly.to_csv(out / "rates_monthly.csv", index=False)

    summary = build_summary(daily)
    chart_indexed(daily, out / "01_rates_indexed.png")
    chart_moving_average(daily, out / "02_moving_average.png")
    chart_volatility(summary, out / "03_volatility.png")

    text = (
        "# Exchange rate report (PLN)\n\n"
        f"Data: {daily['date'].min().date()} to {daily['date'].max().date()}, "
        f"{len(daily):,} daily rates, source: National Bank of Poland (NBP) API, table A.\n\n"
        + to_markdown_table(summary.round(4))
        + "\n"
    )
    (out / "summary.md").write_text(text, encoding="utf-8")
    log.info("Report saved to %s", out)
