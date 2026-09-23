"""The month as a sequence of days.

The transaction table carries a date on every transfer, and the rest of the pipeline reads
the month as one static edge list. This stage keeps the dates: one row per (date, src, dst)
for the CSV, and one entry per calendar day for the review screen's replay, including the
days on which nothing moved, so a gap in the month is visible as a gap rather than skipped.
"""
from __future__ import annotations

import pandas as pd

from .dataio import Dataset

# The window the case data covers. Every day in it appears in days(), even an empty one.
PERIOD_START = "2026-07-01"
PERIOD_END = "2026-07-31"


def build(d: Dataset) -> pd.DataFrame:
    """Transfers aggregated per (date, src, dst): date, src, dst, sum_kzt, n_tx."""
    tx = d.tx.copy()
    tx["date"] = pd.to_datetime(tx["date"]).dt.strftime("%Y-%m-%d")
    out = (tx.groupby(["date", "src", "dst"], sort=True)
             .agg(sum_kzt=("sum_kzt", "sum"), n_tx=("sum_kzt", "size"))
             .reset_index()
             .sort_values(["date", "src", "dst"], kind="mergesort")
             .reset_index(drop=True))
    out["src"] = out["src"].astype("int64")
    out["dst"] = out["dst"].astype("int64")
    out["sum_kzt"] = out["sum_kzt"].astype(float)
    out["n_tx"] = out["n_tx"].astype(int)
    return out[["date", "src", "dst", "sum_kzt", "n_tx"]]


def days(df: pd.DataFrame) -> list[dict]:
    """One entry per calendar day of the window, empty days included.

    Client ids leave as strings: an 18-digit id exceeds the JavaScript safe integer range
    and two different accounts would compare equal once parsed as numbers.
    """
    by_day = {k: g for k, g in df.groupby("date", sort=True)}
    out = []
    for day in pd.date_range(PERIOD_START, PERIOD_END, freq="D"):
        key = day.strftime("%Y-%m-%d")
        g = by_day.get(key)
        if g is None or not len(g):
            out.append({"date": key, "kzt": 0.0, "n_tx": 0, "active": 0, "transfers": []})
            continue
        transfers = [{"s": str(int(r.src)), "t": str(int(r.dst)),
                      "kzt": float(r.sum_kzt), "n": int(r.n_tx)}
                     for r in g.itertuples(index=False)]
        active = len(set(g.src.astype("int64")) | set(g.dst.astype("int64")))
        out.append({
            "date": key,
            "kzt": float(g.sum_kzt.sum()),
            "n_tx": int(g.n_tx.sum()),
            "active": int(active),
            "transfers": transfers,
        })
    return out
