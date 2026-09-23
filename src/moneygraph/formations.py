"""Formations: groups of accounts that only make sense when read together.

A ranked list of accounts gives an investigator a name. A formation gives them a
structure they can act on: a collection point with the accounts feeding it, a transit
route, a pair recycling funds, a dispersal point, a single account holding a community
together. Each formation carries its breaking point, the one member whose removal takes
the most of the structure with it, so the list answers "what do we do" and not only
"who is it".

Every rule below is a threshold in RULES and every score term a weight in WEIGHTS, so a
formation can be recomputed by hand from the figures in its own row. Nothing here is a
model call and nothing is tuned to a specific account.

The module returns dataframes. Writing files is run.py's job.
"""
from __future__ import annotations

import math

import networkx as nx
import pandas as pd

from .dataio import Dataset
from . import flows

# Detection thresholds. The same contract as roles.THRESHOLDS: change a number here and
# the documented rule changes with it, because nothing is duplicated in the code below.
RULES = {
    # Funnel: a collection point and the payers that send it most of what they send.
    "funnel_min_feeders": 3,
    "funnel_min_feeder_share": 0.5,
    # Chain: consecutive accounts that forward most of what arrives and are not hubs.
    "chain_min_forward_share": 0.5,
    "chain_max_interior_degree": 3,
    "chain_min_interior": 2,
    "chain_min_members": 3,
    "chain_max_component": 12,
    # Reciprocal loop: money returning to where it came from, directly or round a cycle.
    "loop_max_cycle_len": 4,
    "loop_min_returned_share": 0.05,
    # Fan-out: a distributor and the receivers with no outgoing transfer of their own.
    # Some of those receivers sit at the four-hop crawl boundary, where nothing downstream
    # was ever collected, so the wording separates the two and does not call them all
    # terminals. The threshold name is kept because it is quoted in the documentation.
    "fanout_min_terminals": 8,
    # Bridge: a cut vertex and the part of its community that only reaches the rest
    # through it. A detached side of one node is a pendant account, not a structure.
    "bridge_min_community": 12,
    "bridge_min_detached": 3,
}

# Score weights, summing to 1.0. Each term is already on 0..1 before weighting, either
# because it is a share or because it is min-max normalised across all formations.
WEIGHTS = {
    "kzt_through": 0.30,      # log1p of money touching the formation, min-max normalised
    "fragility": 0.25,        # share of the formation the breaking point takes with it
    "seed_proximity": 0.15,   # 1 / (1 + hops from the nearest known client)
    "retained_share": 0.10,   # share of that money that never leaves the formation
    "size": 0.10,             # log1p of member count, min-max normalised
    "seed_count": 0.10,       # known clients inside, min-max normalised
}

# How much of the final score each kind keeps. A funnel or a chain is something an
# analyst can act on. A fan-out into dead ends is partly the shape of the crawl itself,
# and a bridge is a topological observation before it is a finding, so both are damped.
KIND_WEIGHTS = {
    "funnel": 1.00,
    "chain": 0.95,
    "reciprocal_loop": 0.85,
    "fan_out": 0.80,
    "bridge": 0.70,
}

KIND_PREFIX = {
    "funnel": "FUN",
    "chain": "CHN",
    "reciprocal_loop": "LOOP",
    "fan_out": "FAN",
    "bridge": "BRG",
}

FORMATION_COLUMNS = [
    "formation_id", "kind", "n_members", "n_seeds", "min_hop_from_seed",
    "kzt_through", "kzt_retained_share", "breaking_point_gid", "breaking_point_method",
    "breaking_point_effect", "score", "rank", "hypothesis", "evidence",
]
MEMBERSHIP_COLUMNS = ["formation_id", "gid", "role_in_formation", "member_evidence"]

# Kinds with a natural entry node, where dominator analysis is meaningful. A funnel is
# rooted at its collection point but the money runs the other way, so it is analysed on
# the reversed subgraph.
ROOTED_KINDS = {"funnel": True, "chain": False, "fan_out": False}


def build(d: Dataset, feats: pd.DataFrame, roles_df: pd.DataFrame,
          clusters_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Detect, measure and rank formations.

    Returns (formations_df, membership_df) with the column order fixed above.
    """
    g = d.graph
    ctx = _context(d, feats, roles_df)

    candidates: list[dict] = []
    candidates += _funnels(g, ctx)
    candidates += _chains(g, ctx)
    candidates += _loops(d, ctx)
    candidates += _fan_outs(g, ctx)
    candidates += _bridges(g, ctx, _community_sizes(clusters_df, ctx))

    # A node may sit in several formations. Only an identical (kind, member set) is a
    # duplicate, and those are collapsed so the same structure is not counted twice.
    seen: set[tuple] = set()
    unique: list[dict] = []
    for c in sorted(candidates, key=lambda x: (x["kind"], tuple(x["members"]), x["entry"])):
        key = (c["kind"], tuple(c["members"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)

    per_kind: dict[str, int] = {}
    measured: list[dict] = []
    for c in unique:
        per_kind[c["kind"]] = per_kind.get(c["kind"], 0) + 1
        c["formation_id"] = f"{KIND_PREFIX[c['kind']]}-{per_kind[c['kind']]:03d}"
        measured.append(_measure(g, ctx, c))

    if not measured:
        return (pd.DataFrame(columns=FORMATION_COLUMNS),
                pd.DataFrame(columns=MEMBERSHIP_COLUMNS))

    fdf = pd.DataFrame(measured)
    fdf = _score(fdf)

    rows, members = [], []
    for c, r in zip(measured, fdf.to_dict(orient="records")):
        rows.append({
            "formation_id": r["formation_id"],
            "kind": r["kind"],
            "n_members": r["n_members"],
            "n_seeds": r["n_seeds"],
            "min_hop_from_seed": r["min_hop_from_seed"],
            "kzt_through": round(r["kzt_through"], 2),
            "kzt_retained_share": round(r["kzt_retained_share"], 4),
            "breaking_point_gid": r["breaking_point_gid"],
            "breaking_point_method": r["breaking_point_method"],
            "breaking_point_effect": round(r["breaking_point_effect"], 2),
            "score": r["score"],
            "rank": r["rank"],
            "hypothesis": _hypothesis(r),
            "evidence": _evidence(r),
        })
        members += _membership(ctx, c, r)

    formations = pd.DataFrame(rows, columns=FORMATION_COLUMNS).sort_values(
        ["rank", "formation_id"]).reset_index(drop=True)
    membership = pd.DataFrame(members, columns=MEMBERSHIP_COLUMNS).sort_values(
        ["formation_id", "gid"]).reset_index(drop=True)
    return formations, membership


# ---------------------------------------------------------------- shared context


def _context(d: Dataset, feats: pd.DataFrame, roles_df: pd.DataFrame) -> dict:
    """One merged lookup so each detector reads the same numbers as every other."""
    g = d.graph
    base = feats if "gid" in feats.columns else roles_df
    node = base[["gid"]].copy()
    for src in (feats, roles_df):
        if src is None:
            continue
        for col in ("depth", "is_seed", "role", "cluster_id", "component_id"):
            if col in src.columns and col not in node.columns:
                node = node.merge(src[["gid", col]], on="gid", how="left")
    if "depth" not in node.columns:
        node = node.merge(d.nodes[["gid", "depth"]], on="gid", how="left")
    if "is_seed" not in node.columns:
        node = node.merge(d.nodes[["gid", "is_seed"]], on="gid", how="left")
    if "role" not in node.columns:
        # Fallback only, and deliberately not one of the abstention class names: those are
        # verdicts roles.py reached, whereas this means no role table was passed at all.
        node["role"] = "unknown"
    if "cluster_id" not in node.columns:
        # Fallback only: without Louvain communities a bridge is measured against the
        # weakly connected component it sits in, which is a coarser but honest split.
        wcc = {n: i for i, c in enumerate(
            sorted(nx.weakly_connected_components(g), key=lambda s: (-len(s), min(s))))
            for n in c}
        node["cluster_id"] = node.gid.map(wcc).fillna(-1).astype(int)

    out_adj: dict[int, list] = {int(n): [] for n in g.nodes()}
    in_adj: dict[int, list] = {int(n): [] for n in g.nodes()}
    for a, b, at in g.edges(data=True):
        a, b, amount = int(a), int(b), float(at["sum_kzt"])
        out_adj[a].append((b, amount))
        in_adj[b].append((a, amount))

    return {
        "out_adj": out_adj,
        "in_adj": in_adj,
        "depth": {int(k): int(v) for k, v in zip(node.gid, node.depth.fillna(9))},
        "is_seed": {int(k): bool(v) for k, v in zip(node.gid, node.is_seed.fillna(False))},
        "role": {int(k): str(v) for k, v in zip(node.gid, node.role.fillna("unknown"))},
        "cluster": {int(k): int(v) for k, v in zip(node.gid, node.cluster_id.fillna(-1))},
        "in_kzt": {int(k): float(v) for k, v in dict(g.in_degree(weight="sum_kzt")).items()},
        "out_kzt": {int(k): float(v) for k, v in dict(g.out_degree(weight="sum_kzt")).items()},
        "in_deg": {int(k): int(v) for k, v in dict(g.in_degree()).items()},
        "out_deg": {int(k): int(v) for k, v in dict(g.out_degree()).items()},
    }


def _cand(kind: str, members, entry: int, **extra) -> dict:
    c = {"kind": kind, "members": tuple(sorted(int(m) for m in members)), "entry": int(entry)}
    c.update(extra)
    return c


# ---------------------------------------------------------------- detectors


def _funnels(g: nx.DiGraph, ctx: dict) -> list[dict]:
    """A collection point plus every payer that sends it a dominant share of its outflow."""
    lo = RULES["funnel_min_feeder_share"]
    out = []
    for c in sorted(g.nodes()):
        if g.in_degree(c) < RULES["funnel_min_feeders"]:
            continue
        feeders = []
        for f in sorted(g.predecessors(c)):
            total = ctx["out_kzt"].get(int(f), 0.0)
            if total > 0 and g[f][c]["sum_kzt"] / total >= lo:
                feeders.append(int(f))
        if len(feeders) >= RULES["funnel_min_feeders"]:
            out.append(_cand("funnel", [int(c)] + feeders, int(c), anchor=int(c)))
    return out


def _chains(g: nx.DiGraph, ctx: dict) -> list[dict]:
    """A run of accounts that each forward most of what arrives, read seed end first."""
    cap = RULES["chain_max_interior_degree"]
    fwd = RULES["chain_min_forward_share"]
    interior = set()
    for n in sorted(g.nodes()):
        n = int(n)
        if not (1 <= ctx["in_deg"].get(n, 0) <= cap and 1 <= ctx["out_deg"].get(n, 0) <= cap):
            continue
        arrived = ctx["in_kzt"].get(n, 0.0)
        if arrived > 0 and ctx["out_kzt"].get(n, 0.0) / arrived >= fwd:
            interior.add(n)

    h = g.subgraph(interior)
    runs: list[tuple] = []
    for comp in sorted(nx.weakly_connected_components(h), key=lambda s: (-len(s), min(s))):
        if len(comp) < RULES["chain_min_interior"]:
            continue
        # Enumeration is factorial in component size, so components are capped. On this
        # data the largest is five nodes, well inside the cap.
        if len(comp) > RULES["chain_max_component"]:
            continue
        runs += _runs_in(h.subgraph(comp))

    out = []
    for run in runs:
        members = list(run)
        head, tail = run[0], run[-1]
        pred = _pick_upstream(g, ctx, head, set(members))
        if pred is not None:
            members.insert(0, pred)
        succ = _pick_downstream(g, ctx, tail, set(members))
        if succ is not None:
            members.append(succ)
        if len(members) < RULES["chain_min_members"]:
            continue
        out.append(_cand("chain", members, members[0], path=tuple(members)))
    return out


def _runs_in(comp: nx.DiGraph) -> list[tuple]:
    """Maximal simple directed paths in a small component, longest first, no subsets."""
    found: list[tuple] = []

    def walk(path: list, visited: set):
        nxt = [s for s in sorted(comp.successors(path[-1])) if s not in visited]
        if not nxt:
            found.append(tuple(path))
            return
        for s in nxt:
            walk(path + [s], visited | {s})

    for start in sorted(comp.nodes()):
        walk([int(start)], {int(start)})

    kept: list[tuple] = []
    for p in sorted(found, key=lambda x: (-len(x), x)):
        if len(p) < RULES["chain_min_interior"]:
            continue
        if any(set(p) <= set(k) for k in kept):
            continue
        kept.append(p)
    return kept


def _pick_upstream(g, ctx, node, taken: set):
    """The payer one step back, preferring a known client, then the largest transfer."""
    cands = [int(p) for p in g.predecessors(node) if int(p) not in taken]
    if not cands:
        return None
    return sorted(cands, key=lambda p: (not ctx["is_seed"].get(p, False),
                                        -g[p][node]["sum_kzt"], p))[0]


def _pick_downstream(g, ctx, node, taken: set):
    """The receiver one step on, preferring one with no onward transfer in the window."""
    cands = [int(s) for s in g.successors(node) if int(s) not in taken]
    if not cands:
        return None
    return sorted(cands, key=lambda s: (ctx["out_deg"].get(s, 0) != 0,
                                        -g[node][s]["sum_kzt"], s))[0]


def _loops(d: Dataset, ctx: dict) -> list[dict]:
    """Reciprocal pairs and short cycles, taken from flows.py rather than recomputed."""
    out = []
    pairs = flows.reciprocal_pairs(d)
    if len(pairs):
        for r in pairs.itertuples(index=False):
            if r.returned_share < RULES["loop_min_returned_share"]:
                continue
            out.append(_cand("reciprocal_loop", [int(r.gid_a), int(r.gid_b)],
                             int(r.gid_a), loop_len=2))
    loops = flows.cycles(d, max_len=RULES["loop_max_cycle_len"])
    if len(loops):
        for r in loops.itertuples(index=False):
            gids = [int(x) for x in str(r.path).split(" -> ")]
            gids = gids[:-1] if len(gids) > 1 and gids[0] == gids[-1] else gids
            if len(gids) < 2:
                continue
            out.append(_cand("reciprocal_loop", gids, min(gids), loop_len=len(gids)))
    return out


def _fan_outs(g: nx.DiGraph, ctx: dict) -> list[dict]:
    """A distributor plus the receivers with no outgoing transfer of their own.

    Selection stays on out-degree, because an account at the crawl boundary is still part
    of the shape money was pushed into. What the boundary changes is what can be claimed
    about it, so the split is made in the wording rather than in the membership: see
    `_receiver_split`.
    """
    out = []
    for n in sorted(g.nodes()):
        n = int(n)
        if ctx["out_deg"].get(n, 0) < RULES["fanout_min_terminals"]:
            continue
        terminals = sorted(int(s) for s in g.successors(n) if ctx["out_deg"].get(int(s), 0) == 0)
        if len(terminals) >= RULES["fanout_min_terminals"]:
            out.append(_cand("fan_out", [n] + terminals, n, anchor=n))
    return out


def _community_sizes(clusters_df: pd.DataFrame, ctx: dict) -> dict[int, int]:
    """Community sizes for the bridge rule.

    Counted from the node assignment, so a bridge is always measured against the split the
    node table actually carries. The published cluster table is preferred when it describes
    exactly the same communities, which keeps clusters.csv and this module in step and
    fails safe when a caller passes a table built from a different clustering.
    """
    counted: dict[int, int] = {}
    for cid in ctx["cluster"].values():
        counted[int(cid)] = counted.get(int(cid), 0) + 1
    if (clusters_df is not None and len(clusters_df)
            and {"cluster_id", "n_nodes"} <= set(clusters_df.columns)):
        published = {int(a): int(b) for a, b in zip(clusters_df.cluster_id, clusters_df.n_nodes)}
        if published == counted:
            return published
    return counted


def _bridges(g: nx.DiGraph, ctx: dict, sizes: dict[int, int]) -> list[dict]:
    """A cut vertex and the side of its community that reaches the rest only through it."""
    by_cluster: dict[int, list[int]] = {}
    for n in sorted(g.nodes()):
        by_cluster.setdefault(ctx["cluster"].get(int(n), -1), []).append(int(n))

    out = []
    for cid in sorted(by_cluster):
        gids = by_cluster[cid]
        if sizes.get(cid, len(gids)) < RULES["bridge_min_community"]:
            continue
        u = _undirected(g, gids)
        for ap in sorted(nx.articulation_points(u)):
            rest = u.copy()
            rest.remove_node(ap)
            parts = sorted((sorted(c) for c in nx.connected_components(rest)),
                           key=lambda c: (-len(c), c[0]))
            if len(parts) < 2:
                continue
            detached = sorted(x for p in parts[1:] for x in p)
            if len(detached) < RULES["bridge_min_detached"]:
                continue
            out.append(_cand("bridge", [int(ap)] + detached, int(ap),
                             community=int(cid), community_size=sizes.get(cid, len(gids))))
    return out


def _undirected(g: nx.DiGraph, gids) -> nx.Graph:
    keep = sorted(int(x) for x in gids)
    u = nx.Graph()
    u.add_nodes_from(keep)
    for a, b in g.subgraph(keep).edges():
        if a != b:
            u.add_edge(int(a), int(b))
    return u


# ---------------------------------------------------------------- measurement


def _measure(g: nx.DiGraph, ctx: dict, c: dict) -> dict:
    members = list(c["members"])
    mset = set(members)
    n = len(members)

    internal = inbound = outbound = 0.0
    for m in members:
        for dst, amount in ctx["out_adj"].get(m, ()):
            if dst in mset:
                internal += amount
            else:
                outbound += amount
        for src, amount in ctx["in_adj"].get(m, ()):
            if src not in mset:
                inbound += amount
    through = internal + inbound + outbound

    bp_gid, method, effect, fragility = _breaking_point(g, ctx, c, internal)

    return {
        "formation_id": c["formation_id"],
        "kind": c["kind"],
        "members": tuple(members),
        "entry": c["entry"],
        "n_members": n,
        "n_seeds": sum(1 for m in members if ctx["is_seed"].get(m, False)),
        "min_hop_from_seed": min(ctx["depth"].get(m, 9) for m in members),
        "kzt_internal": internal,
        "kzt_inbound": inbound,
        "kzt_outbound": outbound,
        "kzt_through": through,
        "kzt_retained_share": (internal / through) if through > 0 else 0.0,
        "breaking_point_gid": bp_gid,
        "breaking_point_method": method,
        "breaking_point_effect": effect,
        "fragility": fragility,
        "community_size": c.get("community_size", 0),
        "loop_len": c.get("loop_len", 0),
        **_receiver_split(ctx, c),
    }


def _receiver_split(ctx: dict, c: dict) -> dict:
    """How many fan-out receivers were observed to the end, and how many were never followed.

    A receiver is selected for a fan-out because it has no outgoing edge, but an account at
    the four-hop crawl boundary has no outgoing edge because collection stopped there. Those
    two cases look identical in the degree and mean opposite things, so they are counted
    apart here and reported apart in the wording. roles.py has already made that call for
    every node, so the split reads its verdict rather than second-guessing it.
    """
    if c["kind"] != "fan_out":
        return {"n_receivers_observed": 0, "n_receivers_at_boundary": 0}
    entry = int(c["entry"])
    at_boundary = sum(1 for m in c["members"]
                      if int(m) != entry and ctx["role"].get(int(m)) == "abstained_boundary")
    return {"n_receivers_observed": len(c["members"]) - 1 - at_boundary,
            "n_receivers_at_boundary": at_boundary}


def _breaking_point(g: nx.DiGraph, ctx: dict, c: dict, internal: float):
    """The member whose removal takes the most of the formation with it.

    Dominator analysis is tried first where the formation is directed and rooted, because
    it answers the directional question exactly: which single member sits on every route
    from the entry. Where no member dominates another, an articulation point on the
    undirected projection is used instead. A loop has neither, so the fallback is the
    member carrying the most money inside the formation.

    Returns (gid, method, effect, fragility). The effect is a member count for the first
    two methods and KZT for the third; the method column says which.
    """
    members = list(c["members"])
    mset = set(members)
    entry = int(c["entry"])
    n = len(members)

    # A bridge is defined by the cut vertex that articulation analysis found in its
    # community, so that vertex is its breaking point by construction and the effect is
    # the whole detached side. Stating this is more honest than rediscovering it.
    if c["kind"] == "bridge":
        return entry, "articulation", float(n - 1), 1.0

    if c["kind"] in ROOTED_KINDS:
        h = g.subgraph(mset)
        directed = h.reverse(copy=True) if ROOTED_KINDS[c["kind"]] else h
        reach = nx.descendants(directed, entry) if entry in directed else set()
        if len(reach) >= 2:
            idom = nx.immediate_dominators(directed, entry)
            counts = {}
            for v in sorted(reach):
                dominated = 0
                for w in reach:
                    if w == v:
                        continue
                    cur = w
                    while cur != entry:
                        nxt = idom.get(cur, entry)
                        if nxt == cur:
                            break
                        cur = nxt
                        if cur == v:
                            dominated += 1
                            break
                counts[v] = dominated
            best = max(counts, key=lambda v: (counts[v], -v))
            if counts[best] > 0:
                return int(best), "dominator", float(counts[best]), counts[best] / max(n - 1, 1)

    u = _undirected(g, members)
    aps = sorted(int(x) for x in nx.articulation_points(u))
    if aps and entry in u:
        before = set(nx.node_connected_component(u, entry)) - {entry}
        best, best_effect = None, -1
        for ap in aps:
            rest = u.copy()
            rest.remove_node(ap)
            after = (set(nx.node_connected_component(rest, entry)) - {entry}
                     if ap != entry and entry in rest else set())
            effect = len((before - {ap}) - after)
            if effect > best_effect:
                best, best_effect = ap, effect
        if best is not None and best_effect > 0:
            return int(best), "articulation", float(best_effect), best_effect / max(n - 1, 1)

    # No cut vertex: every member still reaches the others without any one of them.
    # The question becomes how much money stops, not how many accounts are cut off.
    carried = {}
    for m in members:
        carried[m] = sum(a for s_, a in ctx["in_adj"].get(m, ()) if s_ in mset)
        carried[m] += sum(a for t, a in ctx["out_adj"].get(m, ()) if t in mset)
    best = max(sorted(carried), key=lambda m: (carried[m], -m))
    frag = carried[best] / internal if internal > 0 else 0.0
    return int(best), "flow", float(carried[best]), min(frag, 1.0)


# ---------------------------------------------------------------- scoring


def _score(fdf: pd.DataFrame) -> pd.DataFrame:
    df = fdf.copy()

    def norm(s: pd.Series) -> pd.Series:
        lo, hi = s.min(), s.max()
        return (s - lo) / (hi - lo) if hi > lo else s * 0.0

    # Money through a formation spans two orders of magnitude, so it is compressed with
    # log1p before normalising. Otherwise the single largest fan-out flattens every
    # other term to zero and the ranking becomes a list of the biggest payers again.
    terms = {
        "kzt_through": norm(df.kzt_through.map(math.log1p)),
        "fragility": df.fragility.clip(0, 1),
        "seed_proximity": 1.0 / (1.0 + df.min_hop_from_seed),
        "retained_share": df.kzt_retained_share.clip(0, 1),
        "size": norm(df.n_members.map(math.log1p)),
        "seed_count": norm(df.n_seeds.astype(float)),
    }
    raw = sum(WEIGHTS[k] * v for k, v in terms.items())
    df["score"] = (raw * df.kind.map(KIND_WEIGHTS).fillna(1.0)).round(4)
    # Rank without reordering: the caller pairs these rows with the candidates they were
    # built from by position, so the frame must keep the order it arrived in.
    order = df.sort_values(["score", "formation_id"], ascending=[False, True]).index
    df["rank"] = pd.Series(range(1, len(df) + 1), index=order)
    return df


# ---------------------------------------------------------------- wording


def _hypothesis(r: dict) -> str:
    """One sentence, generated from this formation's own figures, phrased as a hypothesis.

    Same voice as hypotheses.py: what the numbers are consistent with and what an analyst
    should check, never a statement about a person.
    """
    n, kzt = r["n_members"], r["kzt_through"]
    share, hop = r["kzt_retained_share"], r["min_hop_from_seed"]
    bp, eff = r["breaking_point_gid"], r["breaking_point_effect"]
    kind = r["kind"]

    if kind == "funnel":
        return (f"The figures suggest {n - 1} accounts sending a dominant share of their outflow "
                f"into {bp}, {kzt:,.0f} KZT touching the set with {share:.0%} of it staying inside, "
                f"which is worth checking as one collection point rather than {n - 1} unrelated payers.")
    if kind == "chain":
        return (f"Funds appear to move through {n} accounts in sequence starting {hop} hop(s) from a "
                f"known client, {kzt:,.0f} KZT touching the run and {share:.0%} of it staying inside, "
                f"which is consistent with a transit route and worth checking step by step.")
    if kind == "reciprocal_loop":
        return (f"These {n} accounts return funds to each other, {kzt:,.0f} KZT touching the set with "
                f"{share:.0%} of it never leaving, which is worth checking against what each "
                f"leg was said to be for.")
    if kind == "fan_out":
        # The two counts are kept apart because they carry opposite weight. A receiver
        # observed to the end retained what it was sent; a receiver at the crawl boundary
        # was never followed, so the same zero out-degree says nothing about it either way.
        seen, edge = r["n_receivers_observed"], r["n_receivers_at_boundary"]
        if edge == 0:
            reach = (f"{n - 1} receivers, every one of them observed to the end with no onward "
                     f"transfer in the window")
        elif seen == 0:
            reach = (f"{n - 1} receivers, none of which was followed any further because all "
                     f"{edge} sit at the four-hop crawl boundary, so whether the money stopped "
                     f"there is unknown rather than observed")
        elif edge > seen:
            reach = (f"{n - 1} receivers, of which {edge} sit at the four-hop crawl boundary and "
                     f"were never followed, leaving only {seen} actually observed to retain what "
                     f"they were sent, so most of this shape is unobserved rather than measured")
        else:
            reach = (f"{n - 1} receivers, {seen} of them observed to the end with no onward "
                     f"transfer in the window and {edge} at the four-hop crawl boundary where "
                     f"nothing downstream was collected")
        return (f"One account spreads {kzt:,.0f} KZT across {reach}, {share:.0%} of the money "
                f"staying inside the set, which is worth checking as a dispersal point before "
                f"the receivers are treated separately.")
    return (f"These {n - 1} accounts reach the rest of their community only through {bp}, whose "
            f"removal would detach {eff:,.0f} of them from {kzt:,.0f} KZT of observed flow, which is "
            f"worth checking as a shared route rather than a coincidence of the crawl.")


def _evidence(r: dict) -> str:
    """At most 220 characters, every phrase carrying the figure that produced it."""
    if r["breaking_point_method"] == "flow":
        cut = f"stops {r['breaking_point_effect']:,.0f} of {r['kzt_internal']:,.0f} KZT internal"
    else:
        cut = f"cuts {r['breaking_point_effect']:.0f} of {r['n_members'] - 1} members"
    # A fan-out's receiver count is two different measurements added together, so the row
    # carries both rather than the total alone.
    split = ("" if r["kind"] != "fan_out" else
             f"receivers={r['n_receivers_observed']} observed/"
             f"{r['n_receivers_at_boundary']} at crawl boundary; ")
    s = (f"{r['kind']}: n={r['n_members']}, seeds={r['n_seeds']}, hop={r['min_hop_from_seed']}, "
         f"through={r['kzt_through']:,.0f} KZT, retained={r['kzt_retained_share']:.2f}; "
         f"{split}"
         f"break {r['breaking_point_gid']} by {r['breaking_point_method']} {cut}; "
         f"fragility={r['fragility']:.2f}, score={r['score']:.4f}")
    return s[:220]


def _membership(ctx: dict, c: dict, r: dict) -> list[dict]:
    kind, entry = c["kind"], int(c["entry"])
    mset = set(c["members"])
    rows = []
    for m in c["members"]:
        m = int(m)
        rows.append({
            "formation_id": r["formation_id"],
            "gid": m,
            "role_in_formation": _member_role(kind, m, entry, c),
            "member_evidence": _member_evidence(ctx, r, m, mset)[:200],
        })
    return rows


def _member_role(kind: str, m: int, entry: int, c: dict) -> str:
    if kind == "funnel":
        return "consolidator" if m == entry else "feeder"
    if kind == "chain":
        path = c.get("path", c["members"])
        if m == path[0]:
            return "origin"
        if m == path[-1]:
            return "chain_terminal"
        return "step"
    if kind == "fan_out":
        return "distributor" if m == entry else "receiver"
    if kind == "bridge":
        return "cut_vertex" if m == entry else "detached"
    return "loop_member"


def _member_evidence(ctx: dict, r: dict, m: int, mset: set) -> str:
    into = sum(a for s_, a in ctx["in_adj"].get(m, ()) if s_ in mset)
    away = sum(a for t, a in ctx["out_adj"].get(m, ()) if t in mset)
    total_out = ctx["out_kzt"].get(m, 0.0)
    share = (away / total_out) if total_out > 0 else 0.0
    flag = " [breaking point]" if m == r["breaking_point_gid"] else ""
    return (f"{ctx['role'].get(m, 'unknown')}, depth={ctx['depth'].get(m, 9)}, "
            f"seed={bool(ctx['is_seed'].get(m, False))}; inside this formation receives "
            f"{into:,.0f} KZT and sends {away:,.0f} KZT ({share:.0%} of its {total_out:,.0f} "
            f"KZT outflow){flag}")
