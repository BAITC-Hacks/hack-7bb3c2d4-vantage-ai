#!/usr/bin/env python3
"""Regenerates every README figure from the committed outputs in out/.

    python3 tools/figures.py

Reads only. Nothing under out/ is written or modified. Every layout step that could vary
between runs is seeded, so the same inputs produce the same pixels.

Needs matplotlib, which brings Pillow with it. Neither is imported by the pipeline, so
neither is in requirements.txt: `python3 run.py` does not depend on this script, and the
figures it writes are committed alongside it.
"""
from __future__ import annotations

import json
import sys
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
from moneygraph.roles import THRESHOLDS  # noqa: E402  the figures must not drift from the rule bank

# HackAlem brand. Amber is reserved for the single element the eye should land on first in
# each figure and is used for nothing else. No green anywhere: green is Astana Hub's, not
# HackAlem's.
C = {
    "bg":        "#060B16",
    "fg":        "#EEF3FB",
    "cyan":      "#00C8FF",
    "blue":      "#009AF0",
    "amber":     "#FFB020",
    "muted":     "#8DA0BF",   # secondary type
    "grid":      "#1B2436",
    "panel":     "#0C1422",
    "pale":      "#B9E9FF",   # cyan tint, a third step on the light / mid / dark ladder
    "slate":     "#7C8CA8",
    "slate_dim": "#5E6D8A",
    "slate_low": "#47546F",
    # Held identical to --abstained_boundary and --abstained_single_observation in
    # web/index.html so the figure and the review screen name the same class in the same colour.
    "abstain_hi": "#6B5FA6",
    "abstain_lo": "#443C6E",
}

# Roles in the order the review screen lists them. Consolidator carries the amber because
# the collection points sitting above the known clients are what the case is asking for.
ROLE_COLOUR = {
    "consolidator":                 C["amber"],
    "coordinator":                  C["cyan"],
    "transit":                      C["blue"],
    "distributor":                  C["pale"],
    "terminal":                     C["slate"],
    "peripheral":                   C["slate_dim"],
    "abstained_boundary":           C["abstain_hi"],
    "abstained_single_observation": C["abstain_lo"],
}
ROLE_ORDER = list(ROLE_COLOUR)

# The structureless roles and the two abstentions are deliberately dim on the chart, which
# is too dim for type, so their captions borrow the muted grey instead.
DIM_ON_CHART = ("terminal", "peripheral",
                "abstained_boundary", "abstained_single_observation")
LABEL_COLOUR = {r: (C["muted"] if r in DIM_ON_CHART else ROLE_COLOUR[r]) for r in ROLE_ORDER}

SEED = 20260923          # the only stochastic step is the network layout jitter
TARGET_PX = 1600
QUANTISE_ABOVE_KB = 900  # a dense scatter compresses badly, so it is put on a palette

plt.rcParams.update({
    "font.family": "DejaVu Sans",          # ships with matplotlib, so identical everywhere
    "font.size": 9,
    "figure.facecolor": C["bg"],
    "axes.facecolor": C["bg"],
    "savefig.facecolor": C["bg"],
    "text.color": C["fg"],
    "axes.labelcolor": C["fg"],
    "axes.edgecolor": C["grid"],
    "xtick.color": C["muted"],
    "ytick.color": C["muted"],
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "legend.fontsize": 9,
    "axes.grid": False,
    "figure.autolayout": False,
    "path.simplify": False,                # the simplify tolerance can vary the output
})

# Vertical furniture, in inches, so the header sits the same distance from the top of
# every figure whatever its height.
H_TITLE, H_SUB0, H_SUB_STEP, H_GAP = 0.30, 0.60, 0.21, 0.26


def header_bottom(fig, n_sub: int) -> float:
    """Figure fraction of the first free row under the title block."""
    return 1.0 - (H_SUB0 + H_SUB_STEP * n_sub + H_GAP) / fig.get_figheight()


def titles(fig, title: str, sub: list[str]) -> None:
    h = fig.get_figheight()
    fig.text(0.035, 1 - H_TITLE / h, title, color=C["fg"], fontsize=13,
             fontweight="bold", va="top")
    for i, line in enumerate(sub):
        fig.text(0.035, 1 - (H_SUB0 + H_SUB_STEP * i) / h, line,
                 color=C["muted"], fontsize=9.5, va="top")


def tidy(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(C["grid"])
    ax.tick_params(length=3, width=0.8)


def _rgb(h: str) -> tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _brand_palette() -> "Image.Image":
    """A 256 entry palette built from the brand colours themselves.

    An adaptive palette drops the amber: five ringed accounts are far too few pixels to
    earn a bucket, and the highlight the whole figure turns on disappears. Ramping every
    brand colour over the background keeps each one exact and covers the blends, because
    every soft pixel in these figures is a brand colour laid over the background, over a
    panel or over a gridline.
    """
    entries: list[tuple[int, int, int]] = []

    def ramp(base: str, colour: str, steps: int) -> None:
        b, c = _rgb(base), _rgb(colour)
        for k in range(steps):
            t = k / (steps - 1)
            entries.append(tuple(int(round(b[j] + (c[j] - b[j]) * t)) for j in range(3)))

    # Derived rather than fixed: 48 entries are reserved for the grid and panel ramps below,
    # so adding a brand colour narrows every ramp instead of overflowing the 256 entry budget
    # and silently dropping whichever ramps happen to be built last.
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


# ---------------------------------------------------------------- 1. solution schema

def _stage(ax, x, w, y, h, title, lines, accent, emphasised=False):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=1.4",
        linewidth=1.9 if emphasised else 1.1,
        edgecolor=accent, facecolor=C["grid"] if emphasised else C["panel"], zorder=2))
    ax.text(x + w / 2, y + h - 4.0, title, ha="center", va="top", color=accent,
            fontsize=10, fontweight="bold", zorder=3)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 11.0 - i * 5.9, line, ha="center", va="top",
                color=C["fg"] if emphasised else C["muted"], fontsize=9, zorder=3)


def _arrow(ax, x0, x1, y):
    ax.add_patch(FancyArrowPatch(
        (x0, y), (x1, y), arrowstyle="-|>", mutation_scale=11,
        linewidth=1.2, color=C["blue"], shrinkA=0, shrinkB=0, zorder=1))


def figure_schema(integrity: dict, roles_df: pd.DataFrame, clusters: pd.DataFrame,
                  top: pd.DataFrame) -> None:
    fig = plt.figure(figsize=(9.2, 4.9))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    titles(fig, "Solution schema",
           ["Raw parquet to the three required CSVs and a review interface.",
            "One command, and no model call anywhere in the classification path."])

    w, gap, y, h = 13.5, 2.1, 25, 51
    xs = [1.8 + i * (w + gap) for i in range(5)]
    mid = y + h / 2

    _stage(ax, xs[0], w, y, h, "Raw parquet", [
        f"nodes  {integrity['nodes_declared']:,}",
        f"edges  {integrity['edges']:,}",
        f"tx  {integrity['transactions']:,}",
        f"{integrity['turnover_kzt'] / 1e6:,.1f}m KZT",
        "July 2026",
    ], C["cyan"])

    _stage(ax, xs[1], w, y, h, "Metrics", [
        "in / out degree",
        "in / out KZT",
        "PageRank",
        "HITS hub, auth",
        "pass-through",
        "dwell days",
    ], C["cyan"])

    _stage(ax, xs[2], w, y, h, "Rule bank", [
        f"{len(ROLE_ORDER)} roles",
        f"{len(THRESHOLDS)} thresholds",
        "pure Python",
        "no model call",
        "evidence keeps",
        "the figures",
    ], C["amber"], emphasised=True)

    _stage(ax, xs[3], w, y, h, "Clustering", [
        "Louvain, seed 42",
        f"{clusters.cluster_id.nunique()} communities",
        f"{integrity['weakly_connected_components']} weakly",
        "linked parts",
    ], C["cyan"])

    _stage(ax, xs[4], w, y, h, "Ranking", [
        "authority  0.35",
        "PageRank  0.25",
        "in_kzt  0.25",
        "in_deg  0.15",
        "roles off the",
        "case demoted",
    ], C["cyan"])

    # The outputs get their own frame: they are what the case is marked against.
    ox, ow = xs[4] + w + gap + 1.0, 16.4
    ax.add_patch(FancyBboxPatch(
        (ox, y - 3), ow, h + 6, boxstyle="round,pad=0,rounding_size=1.6",
        linewidth=1.9, edgecolor=C["amber"], facecolor=C["grid"], zorder=2))
    ax.text(ox + ow / 2, y + h + 1.2, "Outputs", ha="center", va="top",
            color=C["amber"], fontsize=10, fontweight="bold", zorder=3)
    outs = [
        ("nodes_roles.csv", f"{len(roles_df):,} rows"),
        ("clusters.csv", f"{len(clusters):,} rows"),
        ("top_nodes.csv", f"{len(top):,} rows"),
        ("review screen", "web/index.html"),
    ]
    for i, (name, sub) in enumerate(outs):
        yy = y + h - 7.0 - i * 12.2
        ax.text(ox + ow / 2, yy, name, ha="center", va="top", color=C["fg"],
                fontsize=9.5, fontweight="bold", zorder=3)
        ax.text(ox + ow / 2, yy - 5.3, sub, ha="center", va="top", color=C["muted"],
                fontsize=9, zorder=3)

    for i in range(4):
        _arrow(ax, xs[i] + w, xs[i + 1], mid)
    _arrow(ax, xs[4] + w, ox, mid)

    ax.text(1.8, 17.2,
            "Every role traces to one numeric rule, and the account's evidence string "
            "carries the figures that rule fired on.",
            color=C["muted"], fontsize=9, va="top")
    ax.text(1.8, 10.2,
            "The crawl followed outbound transfers only, so money arriving into the 81 known "
            "clients is not observable. That blind",
            color=C["muted"], fontsize=9, va="top")
    ax.text(1.8, 5.0, "spot is reported and quantified rather than filled in.",
            color=C["muted"], fontsize=9, va="top")

    save(fig, "solution-schema.png")


# ------------------------------------------------------------- 2. network overview

def figure_network(graph: dict, roles_df: pd.DataFrame) -> None:
    rng = np.random.default_rng(SEED)
    nodes = graph["nodes"]
    money = dict(zip(roles_df.gid.astype(str), roles_df.in_kzt + roles_df.out_kzt))

    # Hop on the horizontal axis, the review screen's own vertical slot on the other, plus
    # a seeded jitter so 789 accounts in one hop are not stacked on a single line.
    jx = rng.uniform(-0.19, 0.19, len(nodes))
    pos = {n["id"]: (n["hop"] + dx, n["y"]) for n, dx in zip(nodes, jx)}

    fig = plt.figure(figsize=(8.0, 5.4))
    h = fig.get_figheight()
    top = header_bottom(fig, 2)
    bottom = 1.30 / h
    ax = fig.add_axes([0.045, bottom, 0.935, top - bottom])

    # Edges thinned to a whisper. The structure has to read, not all 3,119 of them.
    kzt = np.array([e["kzt"] for e in graph["edges"]], dtype=float)
    lw = 0.12 + 0.62 * (np.log10(kzt + 1) / np.log10(kzt.max() + 1)) ** 3
    segs = [[pos[e["s"]], pos[e["t"]]] for e in graph["edges"]]
    ax.add_collection(LineCollection(segs, colors=C["blue"], linewidths=lw,
                                     alpha=0.085, zorder=1))

    mt = np.array([money.get(n["id"], 0.0) for n in nodes])
    size = 2.0 + 72.0 * np.sqrt(mt / mt.max())
    idx_by_role: dict[str, list[int]] = {r: [] for r in ROLE_ORDER}
    for i, n in enumerate(nodes):
        idx_by_role[n["role"]].append(i)

    counts = roles_df.role.value_counts().to_dict()
    handles = []
    # Drawn least interesting first, so the five consolidators finish on top.
    for role in reversed(ROLE_ORDER):
        idx = idx_by_role[role]
        if not idx:
            continue
        xs = [pos[nodes[i]["id"]][0] for i in idx]
        ys = [pos[nodes[i]["id"]][1] for i in idx]
        emph = role == "consolidator"
        if emph:
            # Five accounts at four pixels across would vanish, so they are ringed. The
            # ring is a pointer; the marker inside it keeps the true money-through size.
            ax.scatter(xs, ys, s=170, facecolors="none", edgecolors=C["amber"],
                       linewidths=1.2, alpha=0.85, zorder=9)
        h_ = ax.scatter(xs, ys, s=[size[i] for i in idx], c=ROLE_COLOUR[role],
                        linewidths=0.0, edgecolors="none",
                        alpha=1.0 if emph else 0.8,
                        zorder=10 if emph else 2 + ROLE_ORDER.index(role) * 0.1,
                        label=f"{role} ({counts.get(role, 0):,})")
        handles.append(h_)

    hop_n = roles_df.depth.value_counts().sort_index()
    ax.set_xticks(range(5))
    ax.set_xticklabels([f"hop {k}\n{hop_n.get(k, 0):,}" for k in range(5)])
    ax.set_xlim(-0.55, 4.55)
    ax.set_ylim(-0.03, 1.03)
    ax.set_yticks([])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(C["grid"])
    ax.tick_params(axis="x", length=0, pad=7, labelsize=9.5)

    titles(fig, "The network, laid out by hop from the seeds",
           [f"{len(nodes):,} accounts and {len(graph['edges']):,} transfer edges. "
            "Hop 0 is the 81 clients already known to the",
            "investigation, hop 4 is where the crawl stopped. Money moves left to right."])

    leg = fig.legend(handles=list(reversed(handles)), loc="lower center",
                     bbox_to_anchor=(0.5, 0.055), ncol=4, frameon=False,
                     labelcolor=C["fg"], handletextpad=0.5, columnspacing=1.8,
                     scatterpoints=1)
    for hd in leg.legend_handles:
        hd.set_sizes([34])
        hd.set_alpha(1.0)
    fig.text(0.5, 0.018, "marker area in proportion to money through the account. "
             "The five consolidators are ringed.",
             color=C["muted"], fontsize=9, ha="center")
    save(fig, "network-overview.png")


# ------------------------------------------------------------------- 3. role rules

def figure_roles(roles_df: pd.DataFrame) -> None:
    T = THRESHOLDS
    # Wording generated from THRESHOLDS, so the figure cannot drift from the rule bank.
    rules = {
        "consolidator": f"in_deg >= {T['consolidator_min_in_deg']}, "
                        f"pass-through <= {T['consolidator_max_pass_through']}",
        "coordinator":  f"in_deg >= {T['coordinator_min_in_deg']} and "
                        f"out_deg >= {T['coordinator_min_out_deg']}",
        "transit":      f"pass-through {T['transit_pass_through_lo']} to "
                        f"{T['transit_pass_through_hi']}",
        "distributor":  f"out_deg >= {T['distributor_min_out_deg']}",
        "terminal":     "no outgoing and depth < 4",
        "peripheral":   "no threshold met",
        # The two abstentions are named separately because they have separate causes, and a
        # reader who cannot see the cause reads a declined judgement as a missing one.
        "abstained_boundary": "hop-4 dead end: crawl stopped, not the money",
        "abstained_single_observation":
            f"< {T['min_tx_for_stable_ratio']} transfers: one pair is not a rate",
    }
    counts = roles_df.role.value_counts()
    order = list(counts.sort_values(ascending=True).index)

    fig = plt.figure(figsize=(9.2, 4.9))
    h = fig.get_figheight()
    top = header_bottom(fig, 2)
    bottom = 1.16 / h
    # Naming the two abstentions separately made the longest row label half as long again, so
    # the plot starts further in and gives up the same width to keep its right edge where it
    # was. 0.375 is set from the rendered result: it puts the longest rule caption on the same
    # left margin as the title block rather than 25 px outside it.
    ax = fig.add_axes([0.375, bottom, 0.565, top - bottom])

    ys = np.arange(len(order))
    vals = np.array([counts[r] for r in order], dtype=float)
    ax.barh(ys, vals, height=0.58, color=[ROLE_COLOUR[r] for r in order],
            edgecolor="none", zorder=3)
    ax.set_xscale("log")
    ax.set_xlim(1, vals.max() * 3.0)
    ax.set_ylim(-0.7, len(order) - 0.3)
    ax.set_xticks([1, 10, 100, 1000])
    ax.set_xticklabels(["1", "10", "100", "1,000"])
    ax.set_xlabel("accounts assigned the role (log scale)", labelpad=7)
    ax.set_yticks([])
    ax.xaxis.grid(True, color=C["grid"], linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    tidy(ax)

    for y, r, v in zip(ys, order, vals):
        ax.text(v * 1.16, y, f"{int(v):,}", va="center", ha="left",
                color=C["amber"] if r == "consolidator" else C["fg"],
                fontsize=9.5, fontweight="bold", zorder=4)
        ax.text(-0.028, y + 0.26, r, transform=ax.get_yaxis_transform(),
                va="center", ha="right", color=LABEL_COLOUR[r],
                fontsize=10, fontweight="bold")
        ax.text(-0.028, y - 0.27, rules[r], transform=ax.get_yaxis_transform(),
                va="center", ha="right", color=C["muted"], fontsize=9)

    titles(fig, "Role distribution and the rule that assigns each one",
           [f"All {len(roles_df):,} declared accounts receive a role. Thresholds are read "
            "from THRESHOLDS in",
            "src/moneygraph/roles.py, so the figure and the code cannot drift apart."])
    fig.text(0.035, 0.075,
             "Bars are sorted by count. Each account takes the first rule that fires, and "
             "keeps an evidence string carrying the",
             color=C["muted"], fontsize=9, va="bottom")
    fig.text(0.035, 0.028,
             "numbers it fired on. Five accounts meet the consolidator threshold, and those "
             "are the collection points the case asks for.",
             color=C["muted"], fontsize=9, va="bottom")
    save(fig, "roles.png")


# -------------------------------------------------------------------- 4. resilience

def figure_resilience(res: pd.DataFrame, n_nodes: int) -> None:
    fig = plt.figure(figsize=(8.6, 4.7))
    h = fig.get_figheight()
    top = header_bottom(fig, 2)
    bottom = 0.85 / h
    ax = fig.add_axes([0.085, bottom, 0.565, top - bottom])

    x = res.removed.to_numpy(dtype=float)
    series = [
        ("nodes_reachable_from_seeds", "accounts reachable from the seeds",
         C["fg"], "s", "--"),
        ("largest_component", "largest connected component", C["cyan"], "o", "-"),
    ]
    for col, label, colour, marker, style in series:
        ax.plot(x, res[col], color=colour, linewidth=1.7, linestyle=style, marker=marker,
                markersize=5, markeredgecolor=C["bg"], markeredgewidth=0.8,
                label=label, zorder=4)

    # The biggest single step in either curve, found from the file rather than chosen.
    best = None
    for col, label, _, _, _ in series:
        v = res[col].to_numpy(dtype=float)
        drops = v[:-1] - v[1:]
        i = int(np.argmax(drops))
        if best is None or drops[i] > best[0]:
            best = (float(drops[i]), col, label, i)
    drop, col, label, i = best
    yv = res[col].to_numpy(dtype=float)
    ax.plot(x[i:i + 2], yv[i:i + 2], color=C["amber"], linewidth=3.6,
            solid_capstyle="round", zorder=5)
    ax.scatter(x[i:i + 2], yv[i:i + 2], s=44, color=C["amber"], edgecolors=C["bg"],
               linewidths=0.9, zorder=6)
    ax.annotate(
        f"largest single step: accounts {int(x[i]) + 1} to {int(x[i + 1])}\n"
        f"take {label}\ndown by {int(drop):,}",
        xy=(float(np.mean(x[i:i + 2])), float(np.mean(yv[i:i + 2]))),
        xytext=(5.2, 2900), color=C["amber"], fontsize=9, ha="left", va="top",
        linespacing=1.45, zorder=7,
        arrowprops=dict(arrowstyle="-", color=C["amber"], linewidth=1.0,
                        shrinkA=4, shrinkB=3))

    ax.set_xticks(res.removed.tolist())
    ax.set_xticklabels([f"{v:,}" for v in res.removed])
    ax.set_xlim(-1.1, 21.5)
    ax.set_ylim(0, 2950)
    ax.set_yticks([0, 500, 1000, 1500, 2000, 2500])
    ax.set_yticklabels(["0", "500", "1,000", "1,500", "2,000", "2,500"])
    ax.set_xlabel("top ranked accounts removed", labelpad=6)
    ax.set_ylabel("accounts", labelpad=6)
    ax.yaxis.grid(True, color=C["grid"], linewidth=0.7)
    ax.set_axisbelow(True)
    tidy(ax)
    ax.legend(loc="lower left", frameon=False, labelcolor=C["fg"], fontsize=9,
              bbox_to_anchor=(0.005, 0.015), handlelength=2.6)

    titles(fig, "What acting on the ranking would do to the network",
           ["From out/resilience.csv. Accounts are removed in ranked order and the "
            "structure is remeasured",
            "at each step. Nothing here is modelled: each row is the graph recounted."])

    first, last = res.iloc[0], res.iloc[-1]
    rows = [
        ("largest component", f"{int(first.largest_component):,} to "
                              f"{int(last.largest_component):,}"),
        ("reachable from the seeds", f"{int(first.nodes_reachable_from_seeds):,} to "
                                     f"{int(last.nodes_reachable_from_seeds):,}"),
        ("separate components", f"{int(first.n_components):,} to "
                                f"{int(last.n_components):,}"),
    ]
    fig.text(0.685, top - 0.02,
             f"Removing {int(last.removed)} of {n_nodes:,} accounts,\n"
             f"{100.0 * last.removed / n_nodes:.1f}% of the network:",
             color=C["fg"], fontsize=9.5, va="top", linespacing=1.5)
    for k, (lbl, val) in enumerate(rows):
        yy = top - 0.155 - k * 0.115
        fig.text(0.685, yy, lbl, color=C["muted"], fontsize=9, va="top")
        fig.text(0.685, yy - 0.047, val, color=C["cyan"], fontsize=10.5,
                 fontweight="bold", va="top")
    fig.text(0.685, 0.20,
             "A ranking is only worth acting on\nif acting on it changes the\n"
             "structure. This is what changes.",
             color=C["fg"], fontsize=9, va="top", linespacing=1.55)
    save(fig, "resilience.png")


# -------------------------------------------------------------------- 5. formations

# The column names come from the "Output columns" section of docs/FORMATIONS.md, and the
# figure has been drawn from the real out/formations.csv that run.py writes. The schema is
# still checked at run time rather than assumed, because this script reads a file another
# stage owns: if a column is renamed there, the figure is skipped with the missing names
# printed. Nothing is drawn when the file is absent, since an invented formations chart
# would be worse than none.
FORMATION_NEEDS = ["formation_id", "kind", "n_members", "kzt_through",
                   "breaking_point_gid", "breaking_point_method",
                   "breaking_point_effect", "score", "rank"]


def figure_formations(path: Path) -> bool:
    """Top formations and their breaking points. Returns False if it could not be drawn."""
    if not path.exists():
        print(f"  SKIPPED formations.png: {path.relative_to(REPO)} does not exist. "
              "No figure is drawn rather than one being invented.")
        return False

    allf = pd.read_csv(path)
    missing = [c for c in FORMATION_NEEDS if c not in allf.columns]
    if missing:
        print(f"  SKIPPED formations.png: out/formations.csv is missing {missing}. "
              "Check FORMATION_NEEDS in tools/figures.py against the real schema.")
        return False
    if allf.empty:
        print("  SKIPPED formations.png: out/formations.csv has no rows.")
        return False

    f = allf.nsmallest(10, "rank").sort_values("rank").reset_index(drop=True)

    fig = plt.figure(figsize=(9.2, 5.4))
    h = fig.get_figheight()
    top = header_bottom(fig, 2)
    # Room for the axis label and the two caption lines below it without them crowding.
    bottom = 1.25 / h
    # The left column carries the longest row label in any of these figures, the 108 member
    # fan-out, which reached within eight pixels of the canvas edge. The plot starts further
    # in and gives up the same width so the right edge does not move.
    ax = fig.add_axes([0.365, bottom, 0.50, top - bottom])

    ys = np.arange(len(f))[::-1]
    vals = f.score.to_numpy(dtype=float)
    # Amber for the top ranked formation, which is the row the figure exists to point at.
    ax.barh(ys, vals, height=0.6, edgecolor="none", zorder=3,
            color=[C["amber"] if i == 0 else C["cyan"] for i in range(len(f))])

    for y, i in zip(ys, range(len(f))):
        r = f.iloc[i]
        gid6 = str(int(r.breaking_point_gid))[-6:]
        if r.breaking_point_method == "flow":
            # A loop has no cut vertex, so its breaking point is measured in money, not members.
            effect = f"{r.breaking_point_effect / 1e6:,.1f}m KZT"
        else:
            effect = f"{int(r.breaking_point_effect)} of {int(r.n_members) - 1}"
        ax.text(-0.025, y + 0.26, f"#{int(r['rank'])}  {r.formation_id}  {r.kind}",
                transform=ax.get_yaxis_transform(), va="center", ha="right",
                color=C["amber"] if i == 0 else C["fg"], fontsize=9.5, fontweight="bold")
        ax.text(-0.025, y - 0.27,
                f"{int(r.n_members)} accounts, breaks at ...{gid6}, {effect}",
                transform=ax.get_yaxis_transform(), va="center", ha="right",
                color=C["muted"], fontsize=9)
        ax.text(vals[i] + vals.max() * 0.022, y, f"{r.kzt_through / 1e6:,.1f}m KZT",
                va="center", ha="left", color=C["amber"] if i == 0 else C["fg"],
                fontsize=9, zorder=4)

    ax.set_xlim(0, vals.max() * 1.42)
    ax.set_ylim(-0.7, len(f) - 0.3)
    ax.set_yticks([])
    ax.set_xlabel("formation score, weighted and documented in docs/FORMATIONS.md",
                  labelpad=6)
    ax.xaxis.grid(True, color=C["grid"], linewidth=0.7)
    ax.set_axisbelow(True)
    tidy(ax)

    mix = ", ".join(f"{n:,} {k}" for k, n in allf.kind.value_counts().items())
    line = f"From out/formations.csv. {len(allf):,} formations found: {mix}."
    if len(line) > 112:  # a long kind mix would run off the right edge
        line = (f"From out/formations.csv. {len(allf):,} formations found across "
                f"{allf.kind.nunique()} kinds.")
    titles(fig, "Top formations and their breaking points",
           [line,
            "A formation is a set of accounts that only makes sense together."])
    # Two lines, as elsewhere in this file: one unwrapped fig.text of this length overruns
    # the right edge of a 1,600 px canvas and ends mid-word.
    fig.text(0.035, 0.072,
             "The breaking point is the account whose removal disconnects the most of it. "
             "Bar length is the formation score;",
             color=C["muted"], fontsize=9, va="bottom")
    fig.text(0.035, 0.025,
             "the figure beside each bar is the money touching the formation.",
             color=C["muted"], fontsize=9, va="bottom")
    save(fig, "formations.png")
    return True


# ----------------------------------------------------------- 6. ranking disagreement

def figure_rank_disagreement(dem: pd.DataFrame) -> None:
    fig = plt.figure(figsize=(9.2, 5.6))
    h = fig.get_figheight()
    top = header_bottom(fig, 3)
    bottom = 1.22 / h
    ax = fig.add_axes([0.10, bottom, 0.46, top - bottom])

    ylo, yhi = 0.85, 300.0
    span = np.log10(yhi) - np.log10(ylo)

    def frac(rank: float) -> float:
        return 1.0 - (np.log10(rank) - np.log10(ylo)) / span

    def unfrac(f: float) -> float:
        return float(10 ** (np.log10(ylo) + (1.0 - f) * span))

    x_lead, x_text = 1.155, 1.175

    rows = list(dem.itertuples(index=False))
    placed = spread([frac(r.rank_priority) for r in rows], gap=0.055, lo=0.015, hi=0.985)

    for r, fy in zip(rows, placed):
        agree = r.rank_gap == 0
        colour = C["amber"] if agree else C["blue"]
        ax.plot([0, 1], [r.rank_pagerank, r.rank_priority], color=colour,
                linewidth=2.0 if agree else 1.0, alpha=1.0 if agree else 0.5,
                zorder=5 if agree else 2, solid_capstyle="round")
        ax.scatter([0, 1], [r.rank_pagerank, r.rank_priority], s=28 if agree else 16,
                   color=colour, edgecolors=C["bg"], linewidths=0.7,
                   zorder=6 if agree else 3)
        # Drawn as a bounded segment rather than an annotation arrow, which aims at the
        # text anchor and so runs through the label on a steep leader.
        ax.plot([1.005, x_lead], [r.rank_priority, unfrac(fy)],
                color=C["amber"] if agree else C["slate_low"],
                linewidth=0.8 if agree else 0.7, alpha=1.0 if agree else 0.65,
                zorder=4 if agree else 1, clip_on=False, solid_capstyle="butt")
        ax.text(x_text, unfrac(fy),
                f"{r.role}  ...{str(int(r.gid))[-6:]}   #{int(r.rank_priority)}",
                va="center", ha="left", fontsize=9,
                color=C["amber"] if agree else C["muted"],
                fontweight="bold" if agree else "normal", zorder=6, clip_on=False)

    ax.set_yscale("log")
    ax.invert_yaxis()
    ax.set_xlim(-0.12, 1.12)
    ax.set_ylim(yhi, ylo)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["ranked by\nweighted PageRank", "ranked by\nthe evidence rules"],
                       fontsize=9.5)
    ax.set_yticks([1, 2, 5, 10, 20, 50, 100, 200])
    ax.set_yticklabels(["1", "2", "5", "10", "20", "50", "100", "200"])
    ax.set_ylabel("ranking position (log scale)", labelpad=6)
    ax.yaxis.grid(True, color=C["grid"], linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", length=0, pad=8)
    tidy(ax)
    ax.spines["bottom"].set_visible(False)

    titles(fig, "Where centrality and the evidence rules disagree",
           ["From out/pagerank_vs_evidence.csv. The 15 accounts a weighted PageRank "
            "ranking puts at the top,",
            "and where the rule bank places those same accounts."])
    fig.text(0.035, 1 - (H_SUB0 + H_SUB_STEP * 2) / h,
             "Amber marks the one account both rankings agree on.",
             color=C["amber"], fontsize=9.5, va="top")

    moved = int((dem.rank_gap != 0).sum())
    worst = dem.loc[dem.rank_gap.idxmin()]
    fig.text(0.035, 0.085,
             f"{moved} of the top {len(dem)} by PageRank fall outside the top 15 once the "
             f"evidence rules are applied. The furthest moves from position "
             f"{int(worst.rank_pagerank)} to {int(worst.rank_priority)}:",
             color=C["muted"], fontsize=9, va="bottom")
    fig.text(0.035, 0.034,
             f"{worst.role}, in_deg {int(worst.in_deg)}, out_deg {int(worst.out_deg)}. "
             "PageRank measures where flow concentrates. It does not separate collecting "
             "from paying out.",
             color=C["muted"], fontsize=9, va="bottom")
    save(fig, "rank-disagreement.png")


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

    print("figures from out/:")
    figure_schema(integrity, roles_df, clusters, top)
    figure_network(graph, roles_df)
    figure_roles(roles_df)
    figure_resilience(res, integrity["nodes_declared"])
    figure_formations(OUT / "formations.csv")
    figure_rank_disagreement(dem)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
