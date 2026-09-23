"""Amount echoes: money that leaves an account in the same shape it arrived.

Three patterns, each read from individual transfers rather than from the monthly edge
list, because the pattern lives in the amount and the day and both are lost by the
aggregate. Every row is a hypothesis for an analyst to check against the account's
other activity. None of them is a finding on its own: a relay of 30,000 KZT can be rent
passed on, and a fan split can be payroll.

  relay      g receives one transfer of X on day d and sends one transfer within
             ECHO_TOLERANCE of X to a single account on day d or d+1.
  split      g receives one transfer of X on day d and sends two or more transfers on
             days d..d+1 whose sum is within ECHO_TOLERANCE of X.
  fan_split  g sends the same exact amount to three or more distinct receivers on
             one day.

A transfer takes part in at most one relay or split, consumed greedily with the largest
incoming amount first, so the same money is never counted twice. Fan splits are read
independently, because they rest on the outgoing side alone.

Score, in 0..1: 0.8 * out_kzt / max(out_kzt over all echoes) + 0.2 * exactness, where
exactness is 1 for an exact match and falls linearly to 0 at the tolerance edge. Rank is
therefore by size first and by how precisely the amount was echoed second.
"""
from __future__ import annotations

from itertools import combinations

import pandas as pd

from .dataio import Dataset

# Each cutoff is a plain number so a row can be re-checked by hand from the CSV.
THRESHOLDS = {
    # Relative gap allowed between the amount in and the amount out for a relay or a split.
    "ECHO_TOLERANCE": 0.02,
    # Below this absolute gap, in KZT, an echo is reported as exact rather than within tolerance.
    "exact_max_gap_kzt": 1.0,
    # Latest day, counted from the day of receipt, on which the outgoing side may fall.
    "max_lag_days": 1,
    # A split needs at least this many outgoing transfers to be a split at all.
    "split_min_out_tx": 2,
    # Outgoing transfers considered per day for the subset check, largest first, to bound runtime.
    "split_max_out_per_day": 6,
    # A fan split needs the same amount to reach at least this many distinct receivers on one day.
    "fan_split_min_targets": 3,
}
ECHO_TOLERANCE = THRESHOLDS["ECHO_TOLERANCE"]

COLUMNS = ["echo_id", "kind", "gid", "date", "in_kzt", "out_kzt", "lag_days",
           "n_sources", "n_targets", "sources", "targets", "match", "score", "evidence"]


def _short(gid: int) -> str:
    return "…" + str(int(gid))[-7:]


def _kzt(x: float) -> str:
    return f"{x:,.0f} KZT"


def _within(a: float, b: float) -> bool:
    return abs(a - b) <= ECHO_TOLERANCE * a


def _match(in_kzt: float, out_kzt: float) -> str:
    return "exact" if abs(in_kzt - out_kzt) < THRESHOLDS["exact_max_gap_kzt"] else "within_2pct"


def _exactness(in_kzt: float, out_kzt: float) -> float:
    if in_kzt <= 0:
        return 1.0
    gap = abs(in_kzt - out_kzt) / in_kzt
    return max(0.0, 1.0 - min(gap, ECHO_TOLERANCE) / ECHO_TOLERANCE)


def _subset_matching(cands: list[tuple], target: float) -> list[tuple] | None:
    """Smallest subset of at least split_min_out_tx candidates whose sum is within
    tolerance of target. cands is bounded by the caller, so enumeration stays small."""
    lo, hi = target * (1 - ECHO_TOLERANCE), target * (1 + ECHO_TOLERANCE)
    for k in range(THRESHOLDS["split_min_out_tx"], len(cands) + 1):
        best = None
        for combo in combinations(cands, k):
            s = sum(c[3] for c in combo)
            if lo <= s <= hi:
                gap = abs(s - target)
                if best is None or gap < best[0]:
                    best = (gap, combo)
        if best is not None:
            return list(best[1])
    return None


def build(d: Dataset, tl: pd.DataFrame) -> pd.DataFrame:
    """Echo rows sorted by score, echo_id assigned after sorting. tl is the daily aggregate
    from timeline.build; the detection itself reads d.tx, the individual transfers."""
    tx = d.tx.copy()
    tx["date"] = pd.to_datetime(tx["date"]).dt.normalize()
    tx["src"] = tx["src"].astype("int64")
    tx["dst"] = tx["dst"].astype("int64")
    tx["sum_kzt"] = tx["sum_kzt"].astype(float)
    tx = tx.reset_index(drop=True)
    turnover = float(tx.sum_kzt.sum())

    # (idx, src, dst, amount) per transfer, keyed by (sender, day) for the outgoing side.
    rows = [(int(i), int(s), int(t), float(a), dte)
            for i, s, t, a, dte in zip(tx.index, tx.src, tx.dst, tx.sum_kzt, tx.date)]
    out_by_day: dict[tuple, list] = {}
    for r in rows:
        out_by_day.setdefault((r[1], r[4]), []).append(r)
    for k in out_by_day:
        out_by_day[k].sort(key=lambda r: -r[3])

    consumed: set[int] = set()
    echoes: list[dict] = []
    legs: list[list[dict]] = []
    lag_range = range(0, THRESHOLDS["max_lag_days"] + 1)

    # Largest incoming amount first, so the biggest echo claims its transfers before a
    # smaller one can borrow them.
    for idx, src, g, x, day in sorted(rows, key=lambda r: (-r[3], r[0])):
        if idx in consumed:
            continue
        day_str = day.strftime("%Y-%m-%d")

        # Relay: one outgoing transfer within tolerance, same day preferred, closest amount.
        relay = None
        for lag in lag_range:
            for o in out_by_day.get((g, day + pd.Timedelta(days=lag)), []):
                if o[0] in consumed or o[0] == idx or not _within(x, o[3]):
                    continue
                cand = (abs(o[3] - x), lag, o)
                if relay is None or cand[:2] < relay[:2]:
                    relay = cand
            if relay is not None:
                break
        if relay is not None:
            gap, lag, o = relay
            consumed.update({idx, o[0]})
            m = _match(x, o[3])
            when = "the same day" if lag == 0 else "the next day"
            where = f"back to {_short(o[2])}" if o[2] == src else f"to {_short(o[2])}"
            echoes.append({
                "kind": "relay", "gid": g, "date": day_str, "in_kzt": x, "out_kzt": o[3],
                "lag_days": lag, "n_sources": 1, "n_targets": 1,
                "sources": str(src), "targets": str(o[2]), "match": m,
                "exactness": _exactness(x, o[3]),
                "evidence": (f"received {_kzt(x)} on {day_str} from {_short(src)} and sent "
                             f"{_kzt(o[3])} {when} {where} "
                             f"({'exact' if m == 'exact' else 'within 2%'})"),
            })
            legs.append([{"s": str(src), "t": str(g), "kzt": x, "date": day_str},
                         {"s": str(g), "t": str(o[2]), "kzt": o[3],
                          "date": o[4].strftime("%Y-%m-%d")}])
            continue

        # Split: up to split_max_out_per_day outgoing transfers per day, largest first,
        # each no bigger than the incoming amount plus tolerance.
        cands = []
        for lag in lag_range:
            pool = [o for o in out_by_day.get((g, day + pd.Timedelta(days=lag)), [])
                    if o[0] not in consumed and o[0] != idx
                    and o[3] <= x * (1 + ECHO_TOLERANCE)]
            cands.extend(pool[:THRESHOLDS["split_max_out_per_day"]])
        if len(cands) < THRESHOLDS["split_min_out_tx"]:
            continue
        if sum(c[3] for c in cands) < x * (1 - ECHO_TOLERANCE):
            continue
        subset = _subset_matching(cands, x)
        if subset is None:
            continue
        total = sum(c[3] for c in subset)
        consumed.add(idx)
        consumed.update(c[0] for c in subset)
        targets = sorted({c[2] for c in subset})
        lag = max((c[4] - day).days for c in subset)
        m = _match(x, total)
        span = day_str if lag == 0 else f"{day_str}..{(day + pd.Timedelta(days=lag)).strftime('%Y-%m-%d')}"
        echoes.append({
            "kind": "split", "gid": g, "date": day_str, "in_kzt": x, "out_kzt": total,
            "lag_days": lag, "n_sources": 1, "n_targets": len(targets),
            "sources": str(src), "targets": " ".join(str(t) for t in targets), "match": m,
            "exactness": _exactness(x, total),
            "evidence": (f"received {_kzt(x)} on {day_str} from {_short(src)} and sent "
                         f"{_kzt(total)} in {len(subset)} transfers over {span} to "
                         f"{len(targets)} accounts ({'exact' if m == 'exact' else 'within 2%'})"),
        })
        legs.append([{"s": str(src), "t": str(g), "kzt": x, "date": day_str}] +
                    [{"s": str(g), "t": str(c[2]), "kzt": c[3], "date": c[4].strftime("%Y-%m-%d")}
                     for c in sorted(subset, key=lambda c: (c[4], -c[3], c[2]))])

    # Fan split: the same exact amount to three or more distinct receivers on one day.
    fan = (tx.groupby(["src", "date", "sum_kzt"])
             .agg(n_targets=("dst", "nunique"), n_tx=("dst", "size"))
             .reset_index())
    fan = fan[fan.n_targets >= THRESHOLDS["fan_split_min_targets"]]
    for r in fan.itertuples(index=False):
        sel = tx[(tx.src == r.src) & (tx.date == r.date) & (tx.sum_kzt == r.sum_kzt)]
        targets = sorted(set(sel.dst.astype("int64")))
        day_str = r.date.strftime("%Y-%m-%d")
        total = float(r.sum_kzt) * len(targets)
        echoes.append({
            "kind": "fan_split", "gid": int(r.src), "date": day_str, "in_kzt": 0.0,
            "out_kzt": total, "lag_days": 0, "n_sources": 0, "n_targets": len(targets),
            "sources": "", "targets": " ".join(str(t) for t in targets), "match": "exact",
            "exactness": 1.0,
            "evidence": (f"sent {_kzt(float(r.sum_kzt))} each to {len(targets)} distinct accounts "
                         f"on {day_str}, {_kzt(total)} in total (exact)"),
        })
        legs.append([{"s": str(int(r.src)), "t": str(t), "kzt": float(r.sum_kzt), "date": day_str}
                     for t in targets])

    if not echoes:
        df = pd.DataFrame(columns=COLUMNS)
        df.attrs["legs"] = {}
        df.attrs["turnover_kzt"] = turnover
        return df

    df = pd.DataFrame(echoes)
    df["_legs"] = legs
    max_out = float(df.out_kzt.max())
    df["score"] = (0.8 * df.out_kzt / max_out + 0.2 * df.exactness).round(4)
    df = (df.sort_values(["score", "out_kzt", "gid", "date"],
                         ascending=[False, False, True, True], kind="mergesort")
            .reset_index(drop=True))
    df["echo_id"] = [f"ECH-{i + 1:03d}" for i in range(len(df))]
    df["evidence"] = df.evidence.str.slice(0, 200)
    legs_by_id = dict(zip(df.echo_id, df._legs))
    df = df[COLUMNS].copy()
    df.attrs["legs"] = legs_by_id
    df.attrs["turnover_kzt"] = turnover
    return df


def legs(df: pd.DataFrame, tl: pd.DataFrame) -> list[dict]:
    """Per-echo transfer legs for the screen: {"echo_id", "legs": [{"s","t","kzt","date"}]}.

    Legs are recorded at detection time from the individual transfers. When the frame has
    lost them (read back from CSV, for instance) they are rebuilt from the daily aggregate,
    which is the closest the timeline can get to the transfers that fired the rule.
    """
    stored = df.attrs.get("legs") or {}
    out = []
    for r in df.itertuples(index=False):
        if r.echo_id in stored:
            out.append({"echo_id": r.echo_id, "legs": stored[r.echo_id]})
            continue
        want = []
        for s in str(r.sources).split():
            want.append((s, str(r.gid)))
        for t in str(r.targets).split():
            want.append((str(r.gid), t))
        rebuilt = []
        for s, t in want:
            sel = tl[(tl.src.astype(str) == s) & (tl.dst.astype(str) == t)]
            for row in sel.itertuples(index=False):
                rebuilt.append({"s": s, "t": t, "kzt": float(row.sum_kzt), "date": row.date})
        out.append({"echo_id": r.echo_id, "legs": rebuilt})
    return out


def records(df: pd.DataFrame, tl: pd.DataFrame) -> list[dict]:
    """JSON-ready rows for graph.json, every client id a string, legs attached."""
    leg_map = {x["echo_id"]: x["legs"] for x in legs(df, tl)}
    out = []
    for r in df.to_dict(orient="records"):
        r = dict(r)
        r["gid"] = str(int(r["gid"]))
        r["sources"] = str(r["sources"])
        r["targets"] = str(r["targets"])
        r["legs"] = leg_map.get(r["echo_id"], [])
        out.append(r)
    return out
