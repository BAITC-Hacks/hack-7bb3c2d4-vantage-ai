"""Investigation priority.

The ranking answers "who do we look at first", so it combines how central the node is
to the flow with how much money is reachable through it. The weights are explicit and
documented rather than tuned until the answer looked good.
"""
from __future__ import annotations

import pandas as pd

WEIGHTS = {"authority": 0.35, "pagerank": 0.25, "in_kzt": 0.25, "in_deg": 0.15}

# Roles that are structurally interesting to an analyst. Terminals and peripheral
# nodes are not promoted: the case is about who sits above the known clients.
PROMOTED = {"consolidator", "coordinator", "transit", "distributor"}


def rank(feats: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = feats.copy()

    def norm(s):
        lo, hi = s.min(), s.max()
        return (s - lo) / (hi - lo) if hi > lo else s * 0.0

    score = (WEIGHTS["authority"] * norm(df.authority_score)
             + WEIGHTS["pagerank"] * norm(df.pagerank)
             + WEIGHTS["in_kzt"] * norm(df.in_kzt)
             + WEIGHTS["in_deg"] * norm(df.in_deg))
    score = score.where(df.role.isin(PROMOTED), score * 0.3)
    df["priority_score"] = score.round(4)

    top = df.nlargest(25, "priority_score").reset_index(drop=True)
    top.insert(0, "rank", range(1, len(top) + 1))
    top["why"] = top.apply(
        lambda r: (f"{r.role}: receives from {int(r.in_deg)} payers, {r.in_kzt:,.0f} KZT in, "
                   f"{r.out_kzt:,.0f} KZT out; collector score {max(r.authority_score, 0):.4f}, "
                   f"flow share {r.pagerank:.5f}"), axis=1)
    return df, top[["rank", "gid", "role", "priority_score", "why"]]
