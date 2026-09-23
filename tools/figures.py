#!/usr/bin/env python3
"""Regenerates every README figure from the committed outputs in out/.

    python3 tools/figures.py

Reads only. Nothing under out/ is written or modified. Every layout step that could vary
between runs is seeded, so the same inputs produce the same pixels.

Needs matplotlib, which brings Pillow with it. Neither is imported by the pipeline, so
neither is in requirements.txt: `python3 run.py` does not depend on this script, and the
figures it writes are committed alongside it.

House style: editorial. Each title is a sentence that states the finding. Direct labels
instead of legends. No chart borders, no top or right spines, faint gridlines or none.
Amber is used for exactly one element per figure, the thing the eye should land on.
Nothing below 10pt. Every number is read from out/.
"""
from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image  # ships with matplotlib, so this adds no new requirement

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "out"
IMG = REPO / "docs" / "img"

sys.path.insert(0, str(REPO / "src"))
from moneygraph.roles import THRESHOLDS  # noqa: E402  the one caption that quotes a rule reads it

# HackAlem brand. No green anywhere: green is Astana Hub's, not HackAlem's.
C = {
    "bg":     "#060B16",
    "fg":     "#EEF3FB",
    "cyan":   "#00C8FF",
    "blue":   "#009AF0",
    "amber":  "#FFB020",
    "muted":  "#8DA0BF",   # secondary type
    "grid":   "#1B2436",
    "panel":  "#0C1422",
    "slate":  "#5E6D8A",   # muted marks
    "dim":    "#3A4560",   # the quietest mark colour that still reads on the background
}

SEED = 20260923          # the only stochastic step is the network layout jitter
TARGET_PX = 1600
QUANTISE_ABOVE_KB = 900  # a dense scatter compresses badly, so it is put on a palette

plt.rcParams.update({
    "font.family": "DejaVu Sans",          # ships with matplotlib, so identical everywhere
    "font.size": 11,
    "figure.facecolor": C["bg"],
    "axes.facecolor": C["bg"],
    "savefig.facecolor": C["bg"],
    "text.color": C["fg"],
    "axes.labelcolor": C["muted"],
    "axes.edgecolor": C["grid"],
    "xtick.color": C["muted"],
    "ytick.color": C["muted"],
    "xtick.labelsize": 11,
    "ytick.labelsize": 11,
    "axes.labelsize": 11,
    "axes.grid": False,
    "figure.autolayout": False,
    "path.simplify": False,                # the simplify tolerance can vary the output
})

LEFT = 0.05                                # the shared left margin, figure fraction


def title(fig, sentence: str, sub: str | None = None, width: int = 62) -> float:
    """Sentence title at the top left, optional one-line note under it.

    Returns the figure fraction where the plot may start.
    """
    h = fig.get_figheight()
    lines = textwrap.wrap(sentence, width)
    y = 1 - 0.30 / h
    fig.text(LEFT, y, "\n".join(lines), color=C["fg"], fontsize=16, fontweight="bold",
             va="top", linespacing=1.3)
    used = 0.30 + 0.32 * len(lines)
    if sub:
        sub_lines = textwrap.wrap(sub, 100)
        fig.text(LEFT, 1 - (used + 0.08) / h, "\n".join(sub_lines), color=C["muted"],
                 fontsize=11, va="top", linespacing=1.4)
        used += 0.25 * len(sub_lines) + 0.07
    return 1 - (used + 0.35) / h


def tidy(ax, keep_bottom: bool = True, keep_left: bool = False) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_visible(keep_left)
    ax.spines["bottom"].set_visible(keep_bottom)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(C["grid"])
    ax.tick_params(length=0, pad=8)


def _rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _brand_palette() -> "Image.Image":
    """A 256 entry palette ramped from every brand colour over the background.

    An adaptive palette drops the amber on a dense scatter because too few pixels carry it.
    Ramping each brand colour over the background keeps every colour exact.
    """
    entries: list[tuple[int, int, int]] = []

    def ramp(base: str, colour: str, steps: int) -> None:
        b, c = _rgb(base), _rgb(colour)
        for k in range(steps):
            t = k / (steps - 1)
            entries.append(tuple(int(round(b[j] + (c[j] - b[j]) * t)) for j in range(3)))

    base_steps = (256 - 48) // len(C)
    for key in C:
        ramp("#060B16", C[key], base_steps)
    for key in ("fg", "muted", "cyan", "amber"):
        ramp(C["grid"], C[key], 8)
    for key in ("fg", "muted"):
        ramp(C["panel"], C[key], 8)

    entries = entries[:256] + [_rgb(C["bg"])] * max(0, 256 - len(entries))
    pal = Image.new("P", (1, 1))
    pal.putpalette([v for e in entries for v in e])
    return pal


def save(fig, name: str) -> None:
    """Writes at a fixed pixel width so scaling in the README is predictable."""
    dpi = TARGET_PX / fig.get_figwidth()
    w = int(round(fig.get_figwidth() * dpi))
    h = int(round(fig.get_figheight() * dpi))
    path = IMG / name
    fig.savefig(path, dpi=dpi, facecolor=C["bg"], metadata={"Software": None},
                pil_kwargs={"optimize": True, "compress_level": 9})
    plt.close(fig)

    kb = path.stat().st_size / 1024
    if kb > QUANTISE_ABOVE_KB:
        with Image.open(path) as im:
            q = im.convert("RGB").quantize(palette=_brand_palette(),
                                           dither=Image.Dither.NONE)
            q.save(path, optimize=True)
        kb = path.stat().st_size / 1024
    print(f"  wrote {path.relative_to(REPO)}  {w}x{h}px  {kb:.0f} KB")


def spread(values: list[float], gap: float, lo: float = 0.0, hi: float = 1.0) -> list[float]:
    """Pushes label positions apart deterministically, keeping their original order."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = list(values)
    prev = lo - gap
    for i in order:
        out[i] = prev = max(out[i], prev + gap)
    overflow = out[order[-1]] - hi
    if overflow > 0:
        prev = hi + gap
        for i in reversed(order):
            out[i] = prev = min(out[i] - overflow, prev - gap)
    return out


def m_kzt(v: float) -> str:
    return f"{v / 1e6:,.1f}m"


# ---------------------------------------------------------------- 1. solution schema

def figure_schema(integrity: dict, roles_df: pd.DataFrame, clusters: pd.DataFrame,
                  top: pd.DataFrame, formations: pd.DataFrame | None) -> None:
    fig = plt.figure(figsize=(10, 5.0))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    title(fig, "One command turns the raw crawl into three files and a screen an "
               "investigator can act on",
          "No model call anywhere in the path. Every role traces to a numeric rule.")

    n_struct = f"{len(formations):,}" if formations is not None else "the"
    steps = [
        ("Load the\ncrawl",
         f"{integrity['nodes_declared']:,} accounts\n{integrity['transactions']:,} transfers\n"
         f"{integrity['turnover_kzt'] / 1e6:,.0f}m KZT\none month"),
        ("Measure each\naccount",
         "money in, money out\nhow many it deals with\nhow long money stays"),
        ("Apply the\nrules",
         f"{roles_df.role.nunique()} plain rules\nno model\nevery account\nexplained in numbers"),
        ("Find the\nstructures",
         f"{n_struct} structures\nfunnels, fan-outs, loops\neach with a\nbreaking point"),
        ("Hand over:\n3 files and\na screen",
         f"roles for all {len(roles_df):,}\n{len(clusters):,} clusters\n"
         f"{len(top):,} priority targets\na review screen"),
    ]

    w, gap, y, h = 17.6, 2.4, 16, 52
    xs = [2.2 + i * (w + gap) for i in range(5)]
    for i, (head, body) in enumerate(steps):
        last = i == len(steps) - 1
        accent = C["amber"] if last else C["blue"]
        ax.add_patch(FancyBboxPatch(
            (xs[i], y), w, h, boxstyle="round,pad=0,rounding_size=1.6",
            linewidth=2.0 if last else 1.2, edgecolor=accent,
            facecolor=C["panel"], zorder=2))
        ax.text(xs[i] + 1.6, y + h - 3.2, f"{i + 1}", ha="left", va="top",
                color=C["muted"], fontsize=11, zorder=3)
        ax.text(xs[i] + w / 2, y + h - 9.5, head, ha="center", va="top",
                color=C["amber"] if last else C["fg"], fontsize=13, fontweight="bold",
                linespacing=1.25, zorder=3)
        ax.text(xs[i] + w / 2, y + h - 30, body, ha="center", va="top",
                color=C["fg"] if last else C["muted"], fontsize=10.5, linespacing=1.55,
                zorder=3)
        if i < 4:
            ax.add_patch(FancyArrowPatch(
                (xs[i] + w + 0.3, y + h / 2), (xs[i + 1] - 0.3, y + h / 2),
                arrowstyle="-|>", mutation_scale=13, linewidth=1.3,
                color=C["slate"], shrinkA=0, shrinkB=0, zorder=1))

    ax.text(2.2, 9.5, "The crawl followed money outwards from 81 known accounts. Who paid "
                      "them is not in the data,\nand the system says so rather than guess.",
            color=C["muted"], fontsize=11, va="top", linespacing=1.5)
    save(fig, "solution-schema.png")


# ------------------------------------------------------------------------- 2. journey

def figure_journey(integrity: dict, roles_df: pd.DataFrame, top: pd.DataFrame,
                   formations: pd.DataFrame | None) -> None:
    fig = plt.figure(figsize=(10, 4.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    n_struct = len(formations) if formations is not None else 0
    n_break = int(formations.breaking_point_gid.notna().sum()) if formations is not None else 0
    per = "1" if n_break == n_struct and n_struct else f"{n_break:,}"

    title(fig, f"{integrity['seeds']} names go in, {len(top)} accounts to look at first "
               "come out, each with the one place its structure breaks")

    stages = [
        (f"{integrity['seeds']}", "names given",
         "the accounts the\ninvestigator already had"),
        (f"{integrity['nodes_declared']:,}", "accounts crawled",
         "four hops of outbound\ntransfers, one month"),
        (f"{n_struct:,}", "structures found",
         "funnels, fan-outs, loops,\nchains and bridges"),
        (f"{len(top)}", "priority targets",
         "ranked on evidence,\nnot on centrality"),
        (per, "breaking point\neach",
         "the account whose\nremoval breaks it"),
    ]
    xs = np.linspace(11, 86, 5)
    for i, (num, what, why) in enumerate(stages):
        hero = i == 3
        ax.text(xs[i], 62, num, ha="center", va="center",
                color=C["amber"] if hero else C["fg"], fontsize=34, fontweight="bold")
        ax.text(xs[i], 44, what, ha="center", va="center", linespacing=1.2,
                color=C["amber"] if hero else C["fg"], fontsize=13, fontweight="bold")
        ax.text(xs[i], 28, why, ha="center", va="top", color=C["muted"], fontsize=11,
                linespacing=1.5)
        if i < 4:
            mid = (xs[i] + xs[i + 1]) / 2
            ax.text(mid, 62, "›", ha="center", va="center", color=C["slate"],
                    fontsize=30)
    save(fig, "journey.png")


# ------------------------------------------------------------- 3. network overview

def figure_network(graph: dict, roles_df: pd.DataFrame, integrity: dict) -> None:
    rng = np.random.default_rng(SEED)
    nodes = graph["nodes"]
    money = dict(zip(roles_df.gid.astype(str), roles_df.in_kzt + roles_df.out_kzt))

    jx = rng.uniform(-0.19, 0.19, len(nodes))
    pos = {n["id"]: (n["hop"] + dx, n["y"]) for n, dx in zip(nodes, jx)}

    fig = plt.figure(figsize=(10, 6.2))
    h = fig.get_figheight()
    top = title(fig, f"Money moves outward from {integrity['seeds']} known accounts for "
                     f"four hops, and {integrity['dead_ends_truncated_depth4']} accounts "
                     "sit where the crawl stopped",
                f"{len(nodes):,} accounts, {len(graph['edges']):,} transfers. "
                "Marker size is money through the account.")
    bottom = 0.85 / h
    ax = fig.add_axes([LEFT, bottom, 0.90, top - bottom - 0.02])

    kzt = np.array([e["kzt"] for e in graph["edges"]], dtype=float)
    lw = 0.12 + 0.62 * (np.log10(kzt + 1) / np.log10(kzt.max() + 1)) ** 3
    segs = [[pos[e["s"]], pos[e["t"]]] for e in graph["edges"]]
    ax.add_collection(LineCollection(segs, colors=C["blue"], linewidths=lw,
                                     alpha=0.09, zorder=1))

    mt = np.array([money.get(n["id"], 0.0) for n in nodes])
    size = 3.0 + 80.0 * np.sqrt(mt / mt.max())
    hop = np.array([n["hop"] for n in nodes])
    xs = np.array([pos[n["id"]][0] for n in nodes])
    ys = np.array([pos[n["id"]][1] for n in nodes])

    inner = hop < 4
    ax.scatter(xs[inner], ys[inner], s=size[inner], c=C["slate"], linewidths=0,
               alpha=0.85, zorder=3)
    ax.scatter(xs[~inner], ys[~inner], s=size[~inner], c=C["amber"], linewidths=0,
               alpha=0.9, zorder=4)

    hop_n = roles_df.depth.value_counts().sort_index()
    labels = [f"known accounts\n{hop_n.get(0, 0):,}"] + \
             [f"{k} hop{'s' if k > 1 else ''} out\n{hop_n.get(k, 0):,}" for k in range(1, 5)]
    ax.set_xticks(range(5))
    ax.set_xticklabels(labels, linespacing=1.5)
    ax.set_xlim(-0.55, 4.55)
    ax.set_ylim(-0.03, 1.22)
    ax.set_yticks([])
    tidy(ax)
    ax.tick_params(axis="x", length=0, pad=10)

    ax.annotate(f"{integrity['dead_ends_truncated_depth4']} accounts: the crawl stopped "
                "here, not the money",
                xy=(4.0, 1.03), xytext=(3.55, 1.17), color=C["amber"], fontsize=12,
                fontweight="bold", ha="right", va="center",
                arrowprops=dict(arrowstyle="-", color=C["amber"], linewidth=1.0,
                                shrinkA=2, shrinkB=2))
    save(fig, "network-overview.png")


# -------------------------------------------------------------------------- 4. roles

def figure_roles(roles_df: pd.DataFrame, integrity: dict) -> None:
    T = THRESHOLDS
    plain = {
        "terminal":     "money stops here",
        "peripheral":   "no pattern found",
        "transit":      "passes money straight through",
        "distributor":  "pays out to many",
        "coordinator":  "collects and pays out",
        "consolidator": "collects from many, keeps most",
        "abstained_boundary":           "dead end only because the crawl stopped",
        "abstained_single_observation": f"fewer than {T['min_tx_for_stable_ratio']} "
                                        "transfers, too few to judge",
    }
    counts = roles_df.role.value_counts()
    judged = [r for r in counts.index if not r.startswith("abstained")]
    judged = sorted(judged, key=lambda r: counts[r], reverse=True)
    abst = ["abstained_boundary", "abstained_single_observation"]
    order = judged + abst                      # abstentions grouped at the bottom

    dead = integrity["dead_ends"]
    pct = 100.0 * dead / integrity["nodes_declared"]
    trunc = integrity["dead_ends_truncated_depth4"]

    fig = plt.figure(figsize=(10, 6.4))
    h = fig.get_figheight()
    top = title(fig, f"{pct:.0f}% of accounts are dead ends, and {trunc} of those are only "
                     "dead ends because the crawl stopped",
                f"All {len(roles_df):,} accounts get a role. Two of the eight roles "
                "are the system declining to guess.")
    bottom = 0.75 / h
    ax = fig.add_axes([0.40, bottom, 0.50, top - bottom - 0.02])

    n = len(order)
    ys = np.arange(n)[::-1].astype(float)
    ys[-2:] -= 0.55                            # a visible gap before the abstention group
    vals = np.array([counts[r] for r in order], dtype=float)
    colours = [C["amber"] if r == "abstained_boundary" else
               (C["dim"] if r in abst else C["blue"]) for r in order]
    ax.barh(ys, vals, height=0.62, color=colours, edgecolor="none", zorder=3)

    for y, r, v in zip(ys, order, vals):
        hero = r == "abstained_boundary"
        ax.text(v + vals.max() * 0.015, y, f"{int(v):,}", va="center", ha="left",
                color=C["amber"] if hero else C["fg"], fontsize=12,
                fontweight="bold" if hero else "normal", zorder=4)
        ax.text(-0.02, y + 0.2, r.replace("_", " "), transform=ax.get_yaxis_transform(),
                va="center", ha="right", fontsize=11, fontweight="bold",
                color=C["muted"] if r in abst else C["fg"])
        ax.text(-0.02, y - 0.24, plain[r], transform=ax.get_yaxis_transform(),
                va="center", ha="right", color=C["muted"], fontsize=10.5)

    # The bracket that groups the two abstentions.
    yb0, yb1 = ys[-1] - 0.42, ys[-2] + 0.42
    xb = vals.max() * 0.62
    ax.plot([xb, xb], [yb0, yb1], color=C["muted"], linewidth=1.0, zorder=5)
    ax.plot([xb - vals.max() * 0.012, xb], [yb0, yb0], color=C["muted"], linewidth=1.0)
    ax.plot([xb - vals.max() * 0.012, xb], [yb1, yb1], color=C["muted"], linewidth=1.0)
    ax.text(xb + vals.max() * 0.02, (yb0 + yb1) / 2, "the system declined to guess",
            va="center", ha="left", color=C["fg"], fontsize=12)

    ax.set_xlim(0, vals.max() * 1.14)
    ax.set_ylim(ys[-1] - 0.7, ys[0] + 0.6)
    ax.set_yticks([])
    ax.set_xticks([0, 250, 500, 750, 1000])
    ax.set_xticklabels(["0", "250", "500", "750", "1,000"])
    ax.set_xlabel("accounts", labelpad=8)
    tidy(ax)
    save(fig, "roles.png")


# ---------------------------------------------------------------------- 5. resilience

def figure_resilience(res: pd.DataFrame, n_nodes: int) -> None:
    x = res.removed.to_numpy(dtype=float)
    y = res.nodes_reachable_from_seeds.to_numpy(dtype=float)
    first, last = int(y[0]), int(y[-1])

    fig = plt.figure(figsize=(10, 5.6))
    h = fig.get_figheight()
    top = title(fig, f"Removing just the top {int(x[-1])} ranked accounts cuts "
                     f"{first - last} accounts off from the seeds",
                "Accounts are removed in ranked order and the network recounted at each "
                "step. Nothing is modelled.")
    bottom = 0.85 / h
    ax = fig.add_axes([0.10, bottom, 0.82, top - bottom - 0.02])

    ax.plot(x, y, color=C["cyan"], linewidth=2.4, zorder=4, solid_capstyle="round")
    ax.scatter(x[:-1], y[:-1], s=42, color=C["cyan"], edgecolors=C["bg"], linewidths=1.0,
               zorder=5)
    ax.scatter([x[-1]], [y[-1]], s=90, color=C["amber"], edgecolors=C["bg"],
               linewidths=1.0, zorder=6)
    ax.text(x[0] + 0.25, y[0] + 45, f"{first:,} accounts followable from the seeds",
            color=C["fg"], fontsize=11, va="bottom", ha="left")
    ax.text(x[-1] - 0.45, y[-1] - 40, f"{last:,}", color=C["amber"], fontsize=20,
            fontweight="bold", ha="right", va="top")
    ax.text(x[-1] - 0.45, y[-1] - 165, f"still followable once the\ntop {int(x[-1])} are gone",
            color=C["amber"], fontsize=11, ha="right", va="top", linespacing=1.4)

    ax.set_xticks(x.tolist())
    ax.set_xticklabels([f"{int(v)}" for v in x])
    ax.set_xlim(-0.6, 21.2)
    ax.set_ylim(1500, 2400)
    ax.set_yticks([1500, 1750, 2000, 2250])
    ax.set_yticklabels(["1,500", "1,750", "2,000", "2,250"])
    ax.set_xlabel("top ranked accounts removed", labelpad=8)
    ax.set_ylabel("accounts still followable", labelpad=10)
    ax.yaxis.grid(True, color=C["grid"], linewidth=0.7)
    ax.set_axisbelow(True)
    tidy(ax)
    save(fig, "resilience.png")


# ----------------------------------------------------------- 6. ranking disagreement

def figure_rank_disagreement(dem: pd.DataFrame) -> None:
    n = len(dem)
    fell = int((dem.rank_priority > n).sum())
    agree_n = int((dem.rank_gap == 0).sum())

    fig = plt.figure(figsize=(10, 6.0))
    h = fig.get_figheight()
    top = title(fig, f"{fell} of the {n} accounts PageRank would chase fall out of the "
                     f"top {n} once the rules are applied",
                "PageRank finds where money concentrates. It cannot tell collecting "
                "from paying out.")
    bottom = 0.95 / h
    ax = fig.add_axes([0.11, bottom, 0.50, top - bottom - 0.02])

    ylo, yhi = 0.85, 300.0
    span = np.log10(yhi) - np.log10(ylo)

    def frac(rank: float) -> float:
        return 1.0 - (np.log10(rank) - np.log10(ylo)) / span

    def unfrac(f: float) -> float:
        return float(10 ** (np.log10(ylo) + (1.0 - f) * span))

    rows = list(dem.itertuples(index=False))
    placed = spread([frac(r.rank_priority) for r in rows], gap=0.06, lo=0.015, hi=0.985)

    x_lead, x_text = 1.12, 1.14
    for r, fy in zip(rows, placed):
        agree = r.rank_gap == 0
        colour = C["amber"] if agree else C["slate"]
        ax.plot([0, 1], [r.rank_pagerank, r.rank_priority], color=colour,
                linewidth=2.6 if agree else 1.2, alpha=1.0 if agree else 0.7,
                zorder=5 if agree else 2, solid_capstyle="round")
        ax.scatter([0, 1], [r.rank_pagerank, r.rank_priority], s=48 if agree else 22,
                   color=colour, edgecolors=C["bg"], linewidths=0.8,
                   zorder=6 if agree else 3)
        ax.plot([1.01, x_lead], [r.rank_priority, unfrac(fy)], color=colour,
                linewidth=0.8, alpha=1.0 if agree else 0.5, zorder=1, clip_on=False)
        label = (f"#{int(r.rank_priority)}  {r.role}" if not agree else
                 f"#{int(r.rank_priority)}  {r.role}, the one both agree on")
        ax.text(x_text, unfrac(fy), label, va="center", ha="left", fontsize=11,
                color=C["amber"] if agree else C["muted"],
                fontweight="bold" if agree else "normal", zorder=6, clip_on=False)

    ax.set_yscale("log")
    ax.set_xlim(-0.08, 1.08)
    ax.set_ylim(yhi, ylo)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["ranked by PageRank", "ranked by the rules"], fontsize=12)
    ax.set_yticks([1, 2, 5, 10, 20, 50, 100, 200])
    ax.set_yticklabels(["1st", "2nd", "5th", "10th", "20th", "50th", "100th", "200th"])
    ax.set_ylabel("position in the ranking", labelpad=10)
    ax.yaxis.grid(True, color=C["grid"], linewidth=0.7)
    ax.set_axisbelow(True)
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    tidy(ax, keep_bottom=False)
    ax.tick_params(axis="x", pad=12)
    assert agree_n == 1, "the title copy assumes exactly one agreement"
    save(fig, "rank-disagreement.png")


# ---------------------------------------------------------------------- 7. formations

FORMATION_NEEDS = ["formation_id", "kind", "n_members", "kzt_through",
                   "breaking_point_gid", "breaking_point_method",
                   "breaking_point_effect", "score", "rank"]
KIND_PLAIN = {"funnel": "funnel", "fan_out": "fan-out", "reciprocal_loop": "loop",
              "chain": "chain", "bridge": "bridge"}


def load_formations(path: Path) -> pd.DataFrame | None:
    """Returns None, with the reason printed, when the figure cannot be drawn honestly."""
    if not path.exists():
        print(f"  SKIPPED formations: {path.relative_to(REPO)} does not exist.")
        return None
    f = pd.read_csv(path)
    missing = [c for c in FORMATION_NEEDS if c not in f.columns]
    if missing:
        print(f"  SKIPPED formations: out/formations.csv is missing {missing}.")
        return None
    if f.empty:
        print("  SKIPPED formations: out/formations.csv has no rows.")
        return None
    return f


def figure_formations(allf: pd.DataFrame) -> None:
    f = allf.nsmallest(8, "rank").sort_values("rank").reset_index(drop=True)

    fig = plt.figure(figsize=(10, 6.2))
    h = fig.get_figheight()
    top = title(fig, "Every structure has a breaking point: the one account whose "
                     "removal disconnects the rest of it",
                f"The top 8 of {len(allf):,} structures found. Bar length is the "
                "structure's score; the amount is the money touching it.")
    bottom = 0.75 / h
    ax = fig.add_axes([0.36, bottom, 0.50, top - bottom - 0.02])

    ys = np.arange(len(f))[::-1]
    vals = f.score.to_numpy(dtype=float)
    ax.barh(ys, vals, height=0.66, edgecolor="none", zorder=3,
            color=[C["amber"] if i == 0 else C["blue"] for i in range(len(f))])

    for y, i in zip(ys, range(len(f))):
        r = f.iloc[i]
        gid6 = str(int(r.breaking_point_gid))[-6:]
        hero = i == 0
        ax.text(-0.02, y + 0.2, f"{KIND_PLAIN.get(r.kind, r.kind)} of {int(r.n_members)} "
                                f"accounts",
                transform=ax.get_yaxis_transform(), va="center", ha="right",
                color=C["amber"] if hero else C["fg"], fontsize=12, fontweight="bold")
        ax.text(-0.02, y - 0.24, f"breaks at ...{gid6}",
                transform=ax.get_yaxis_transform(), va="center", ha="right",
                color=C["muted"], fontsize=10.5)
        ax.text(vals[i] + vals.max() * 0.02, y, f"{m_kzt(r.kzt_through)} KZT",
                va="center", ha="left", color=C["amber"] if hero else C["fg"],
                fontsize=11, zorder=4)

    ax.set_xlim(0, vals.max() * 1.35)
    ax.set_ylim(-0.7, len(f) - 0.3)
    ax.set_yticks([])
    ax.set_xticks([0, 0.2, 0.4, 0.6])
    ax.set_xlabel("structure score, 0 to 1", labelpad=8)
    tidy(ax)
    save(fig, "formations.png")


# ---------------------------------------------------------------------- 8. blind spot

def figure_blind_spot(roles_df: pd.DataFrame, integrity: dict) -> None:
    seeds = roles_df[roles_df.depth == 0]
    sent = float(seeds.out_kzt.sum())
    seen = float(seeds.in_kzt.sum())
    gap = sent - seen
    n_seeds = integrity["seeds"]

    fig = plt.figure(figsize=(10, 4.8))
    h = fig.get_figheight()
    top = title(fig, f"Whoever funds the {n_seeds} seed accounts is not in this data, "
                     "and that is a property of the crawl",
                "The crawl followed money outwards from the seeds. Money arriving at "
                "them was only recorded when another crawled account sent it.")
    bottom = 0.55 / h
    ax = fig.add_axes([0.24, bottom, 0.66, top - bottom - 0.08])

    ax.barh([1, 0], [sent, seen], height=0.56, color=[C["blue"], C["slate"]],
            edgecolor="none", zorder=3)
    ax.text(-0.02, 1, f"the {n_seeds} seeds sent out", transform=ax.get_yaxis_transform(),
            va="center", ha="right", color=C["fg"], fontsize=13)
    ax.text(-0.02, 0, "seen arriving at them", transform=ax.get_yaxis_transform(),
            va="center", ha="right", color=C["fg"], fontsize=13)
    ax.text(sent + sent * 0.015, 1, f"{m_kzt(sent)} KZT", va="center", ha="left",
            color=C["fg"], fontsize=13, fontweight="bold")
    ax.text(seen + sent * 0.015, 0, f"{m_kzt(seen)} KZT", va="center", ha="left",
            color=C["fg"], fontsize=13, fontweight="bold")

    # The gap, drawn as a bracket on the lower row where the money would have been.
    yb = -0.05
    ax.plot([seen, sent], [yb - 0.42, yb - 0.42], color=C["amber"], linewidth=1.6,
            zorder=4, solid_capstyle="butt")
    for xx in (seen, sent):
        ax.plot([xx, xx], [yb - 0.42, yb - 0.32], color=C["amber"], linewidth=1.6)
    ax.text((seen + sent) / 2, yb - 0.56, f"{m_kzt(gap)} KZT with no recorded payer",
            ha="center", va="top", color=C["amber"], fontsize=14, fontweight="bold")

    ax.set_xlim(0, sent * 1.22)
    ax.set_ylim(-1.35, 1.55)
    ax.set_yticks([])
    ax.set_xticks([])
    tidy(ax, keep_bottom=False)
    save(fig, "blind-spot.png")


# --------------------------------------------------------------------------- driver

def main() -> int:
    IMG.mkdir(parents=True, exist_ok=True)
    integrity = json.loads((OUT / "integrity.json").read_text(encoding="utf-8"))
    roles_df = pd.read_csv(OUT / "nodes_roles.csv")
    clusters = pd.read_csv(OUT / "clusters.csv")
    top = pd.read_csv(OUT / "top_nodes.csv")
    res = pd.read_csv(OUT / "resilience.csv")
    dem = pd.read_csv(OUT / "pagerank_vs_evidence.csv")
    graph = json.loads((OUT / "graph.json").read_text(encoding="utf-8"))
    formations = load_formations(OUT / "formations.csv")

    print("figures from out/:")
    figure_schema(integrity, roles_df, clusters, top, formations)
    figure_journey(integrity, roles_df, top, formations)
    figure_network(graph, roles_df, integrity)
    figure_resilience(res, integrity["nodes_declared"])
    figure_rank_disagreement(dem)
    if formations is not None:
        figure_formations(formations)
    figure_roles(roles_df, integrity)
    figure_blind_spot(roles_df, integrity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
