#!/usr/bin/env python3
"""
p3b_size_invariance.py
PLAN.md Phase 3b acceptance: does the network behave the same under both wiring
rules at production size (switch check), and at any population size under
--conn-rule indegree (size sweep)?

Input: results/p3b/<rule>_n<scale>_s<seed>.h5 from ./run_p3b_local.sh (human
medium, timer-paced). Stride and stance are set by the clock there, so the
metrics are what the network does with them:

  r(E,F) L/R    extensor/flexor force correlation per leg, steady window
  r(EL,ER)      left/right extensor force correlation (anti-phase < 0)
  r(E,F) early  both legs, 4-9 s (speed of early learning)
  E|stance      fraction of stance with the extensor active (force_e above half
                its 95th percentile), both legs
  Force-E/F p95 force amplitude, both legs
  RG-E/F rate   mean population rate (Hz per neuron), both legs
  w CUT->RG-E, w Ia->RG-E, w Ia->RG-F   end-of-run mean plastic weight (pA)

Samples are duration-weighted (the phase scheduler logs irregular windows).

Verdict per metric and comparison: PASS if |difference of seed means| <=
max(2 x pooled seed SD, floor); floor = 0.05 for correlations and fractions,
5% of the reference mean otherwise (3 seeds give a noisy SD).
  switch check : indegree x1   vs bernoulli x1
  size sweep   : indegree x0.3 (and x3 if present) vs indegree x1
  contrast     : bernoulli x0.3 vs bernoulli x1 (the old size dependence)

Usage:
  python3 scripts/p3b_size_invariance.py results/p3b/*.h5 [--out plots/p3b/p3b_size_invariance.png]
"""
import argparse
import os
import re
from collections import defaultdict

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
NAME_RE = re.compile(r"(bernoulli|indegree)_n([0-9.]+)_s(\d+)\.h5$")

# (key, label, kind) kind: corr / frac -> absolute floor; value -> relative floor
METRICS = [("r_ef", "r(E,F) steady", "corr"), ("r_lr", "r(EL,ER) steady", "corr"),
           ("r_ef_early", "r(E,F) 4–9 s", "corr"), ("e_stance", "E active | stance", "frac"),
           ("fe95", "Force-E p95", "value"), ("ff95", "Force-F p95", "value"),
           ("rge", "RG-E rate (Hz)", "value"), ("rgf", "RG-F rate (Hz)", "value"),
           ("w_cut", "w CUT→RG-E (pA)", "value"), ("w_iae", "w Ia→RG-E (pA)", "value"),
           ("w_iaf", "w Ia→RG-F (pA)", "value")]


def wcorr(a, b, w):
    if a.size < 3 or a.std() < 1e-9 or b.std() < 1e-9 or np.sum(w) <= 0:
        return float("nan")
    am, bm = np.average(a, weights=w), np.average(b, weights=w)
    cov = np.average((a - am) * (b - bm), weights=w)
    return float(cov / np.sqrt(np.average((a - am) ** 2, weights=w) * np.average((b - bm) ** 2, weights=w)))


def run_metrics(path, steady_ms, early):
    with h5py.File(path, "r") as f:
        t = f["times_ms"][()]
        leg = {s: {k: f[f"leg_{s}/{k}"][()] for k in ("force_e", "force_f", "rge", "rgf", "cut_on")}
               for s in "LR"}
        wts = {s: {k: f[f"leg_{s}/weights/{k}_mean"][()] for k in ("cut->rge", "ia->rge", "ia->rgf")
                   if f"leg_{s}/weights/{k}_mean" in f} for s in "LR"}
    dur = np.diff(np.concatenate([[0.0], t]))
    st = t > steady_ms
    ea = (t > early[0]) & (t <= early[1])
    m = {}
    m["r_ef"] = np.mean([wcorr(leg[s]["force_e"][st], leg[s]["force_f"][st], dur[st]) for s in "LR"])
    m["r_lr"] = wcorr(leg["L"]["force_e"][st], leg["R"]["force_e"][st], dur[st])
    m["r_ef_early"] = np.mean([wcorr(leg[s]["force_e"][ea], leg[s]["force_f"][ea], dur[ea]) for s in "LR"])
    es = []
    for s in "LR":
        fe = leg[s]["force_e"][st]
        act = fe > 0.5 * np.percentile(fe, 95)
        on = leg[s]["cut_on"][st] > 0.5 if leg[s]["cut_on"].size == t.size else np.ones_like(act)
        es.append(np.sum(dur[st][act & on]) / max(1e-9, np.sum(dur[st][on])))
    m["e_stance"] = float(np.mean(es))
    m["fe95"] = float(np.mean([np.percentile(leg[s]["force_e"][st], 95) for s in "LR"]))
    m["ff95"] = float(np.mean([np.percentile(leg[s]["force_f"][st], 95) for s in "LR"]))
    m["rge"] = float(np.mean([np.average(leg[s]["rge"][st], weights=dur[st]) for s in "LR"]))
    m["rgf"] = float(np.mean([np.average(leg[s]["rgf"][st], weights=dur[st]) for s in "LR"]))
    for key, k in (("w_cut", "cut->rge"), ("w_iae", "ia->rge"), ("w_iaf", "ia->rgf")):
        vals = [wts[s][k][np.isfinite(wts[s][k])][-1] for s in "LR" if k in wts[s]]
        m[key] = float(np.mean(vals)) if vals else float("nan")
    return m


def verdict(ref, other, kind):
    a, b = np.array(ref), np.array(other)
    d = float(b.mean() - a.mean())
    sd = float(np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)) if len(a) > 1 and len(b) > 1 else 0.0
    floor = 0.05 if kind in ("corr", "frac") else 0.05 * abs(a.mean())
    tol = max(2 * sd, floor)
    return d, tol, abs(d) <= tol


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--steady-from-ms", type=float, default=60000.0)
    ap.add_argument("--out", default=os.path.join("plots", "p3b", "p3b_size_invariance.png"))
    args = ap.parse_args()

    groups = defaultdict(dict)  # (rule, scale) -> seed -> metrics
    for p in args.files:
        m = NAME_RE.search(os.path.basename(p))
        if not m:
            continue
        rule, scale, seed = m.group(1), float(m.group(2)), int(m.group(3))
        groups[(rule, scale)][seed] = run_metrics(p, args.steady_from_ms, (4000.0, 9000.0))
    if not groups:
        raise SystemExit("no results/p3b/<rule>_n<scale>_s<seed>.h5 files given")
    order = sorted(groups, key=lambda g: (g[0] != "bernoulli", g[1]))

    print(f"steady window t > {args.steady_from_ms / 1000:.0f} s; mean ± SD over seeds")
    head = f"{'metric':20s}" + "".join(f"{r[:4]} x{s:<5g} (n={len(groups[(r, s)])})".rjust(24) for r, s in order)
    print(head)
    for key, lab, _ in METRICS:
        row = f"{lab:20s}"
        for g in order:
            v = np.array([groups[g][sd][key] for sd in sorted(groups[g])])
            row += f"{v.mean():10.3f} ± {v.std(ddof=1) if len(v) > 1 else 0:<9.3f}".rjust(24)
        print(row)

    comps = [("switch check", ("bernoulli", 1.0), ("indegree", 1.0))]
    comps += [(f"size sweep x{s:g}", ("indegree", 1.0), ("indegree", s))
              for r, s in order if r == "indegree" and s != 1.0]
    comps += [(f"contrast (old) x{s:g}", ("bernoulli", 1.0), ("bernoulli", s))
              for r, s in order if r == "bernoulli" and s != 1.0]
    print("\nverdicts: PASS if |Δ mean| <= max(2 x pooled SD, floor)")
    summary = {}
    for name, ga, gb in comps:
        if ga not in groups or gb not in groups:
            continue
        fails = []
        print(f"  {name}: {gb[0]} x{gb[1]:g} vs {ga[0]} x{ga[1]:g}")
        for key, lab, kind in METRICS:
            a = [groups[ga][s][key] for s in sorted(groups[ga])]
            b = [groups[gb][s][key] for s in sorted(groups[gb])]
            d, tol, ok = verdict(a, b, kind)
            if not np.isfinite(d):
                print(f"    {lab:20s} n/a (window empty or flat)")
                continue
            if not ok:
                fails.append(lab)
            print(f"    {lab:20s} Δ={d:+9.3f}  tol={tol:7.3f}  {'PASS' if ok else 'FAIL'}")
        summary[name] = (fails, sum(1 for key, _, _ in METRICS
                                    if np.isfinite(verdict([groups[ga][x][key] for x in groups[ga]],
                                                           [groups[gb][x][key] for x in groups[gb]], "corr")[0])))
        print(f"    -> {'PASS' if not fails else 'FAIL on ' + ', '.join(fails)}")

    # figure: one panel per metric, groups on x, seeds as dots, mean as a bar
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    ncol = 4
    nrow = int(np.ceil(len(METRICS) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol, 2.5 * nrow), facecolor=SURFACE)
    col = {("bernoulli", 1.0): MUTED, ("indegree", 1.0): BLUE}
    for ax, (key, lab, _) in zip(axes.flat, METRICS):
        ax.set_facecolor(SURFACE)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(MUTED)
        ax.tick_params(colors=INK_2, labelsize=7.5, length=2.5)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        for i, g in enumerate(order):
            v = np.array([groups[g][sd][key] for sd in sorted(groups[g])])
            c = col.get(g, AQUA if g[0] == "indegree" else ORANGE)
            ax.bar(i, v.mean(), width=0.6, color=c, alpha=0.35, zorder=2)
            ax.plot(np.full(v.size, i) + np.linspace(-0.12, 0.12, v.size), v, "o", color=c,
                    markersize=4, zorder=3)
        ax.set_xticks(range(len(order)), [f"{r[:4]}\n×{s:g}" for r, s in order], fontsize=7.5)
        ax.set_title(lab, fontsize=9, color=INK, loc="left")
    for ax in list(axes.flat)[len(METRICS):]:
        ax.axis("off")
    ok = "   ".join(f"{n}: {n_ok - len(f)}/{n_ok} pass" for n, (f, n_ok) in summary.items())
    fig.suptitle("Phase 3b: human medium, wiring rule × population size (seeds as dots)",
                 x=0.01, y=0.995, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.text(0.01, 0.945, f"bern = pairwise_bernoulli (old), inde = fixed in-degree (P3b); steady window "
             f"t > {args.steady_from_ms / 1000:.0f} s.   {ok}", fontsize=8.5, color=INK_2, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    fig.savefig(args.out, dpi=150, facecolor=SURFACE)
    print(f"\n[p3b] wrote {args.out}")


if __name__ == "__main__":
    main()
