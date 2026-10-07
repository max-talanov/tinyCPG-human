#!/usr/bin/env python3
"""
p7_chain_compare.py
PLAN.md P7b: recovery curves of session chains (run_p6_sessions.sh, TAG p7/chain/<name>/s<k>/<mode>.h5)
compared across conditions (support level, EES). Per session, last --last-ms of the run:
  rEF     r(Force-E, Force-F), mean of the legs
  FE      95th percentile of Force-E (a.u.)
  CUT     captured CUT->RG-E weight at the end of the session (pA), what the next session starts from
Also stride (ms) and stance fraction (cpg_gait_phase_metrics, last --last-ms) per session. Prints one table per metric (rows: chain, columns: session) and sessions to criterion (rEF <= -0.5),
and writes a figure with --fig.
Usage: python3 scripts/p7_chain_compare.py [--root results/human_modes/p7/chain] [--fig plots/p7/chain_compare.png]
"""
import argparse, glob, os, re
import sys
import h5py
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpg_gait_phase_metrics import metrics as phase_metrics

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "human_modes", "p7", "chain"))
ap.add_argument("--last-ms", type=float, default=20000.0)
ap.add_argument("--fig", default=None)
a = ap.parse_args()


def session(path):
    with h5py.File(path, "r") as f:
        t = f["times_ms"][()]
        k = t > t[-1] - a.last_ms
        r, fe = [], []
        for s in "LR":
            e, fl = f[f"leg_{s}/force_e"][()][k], f[f"leg_{s}/force_f"][()][k]
            r.append(np.corrcoef(e, fl)[0, 1] if e.std() > 1e-9 and fl.std() > 1e-9 else np.nan)
            fe.append(np.percentile(e, 95))
        g = f["leg_L/full_weights/cut_to_rge"]
        cut = np.mean([f[f"leg_{s}/full_weights/cut_to_rge/baseline"][()].mean() if "baseline" in f[f"leg_{s}/full_weights/cut_to_rge"]
                       else f[f"leg_{s}/full_weights/cut_to_rge/w"][()][-1].mean() for s in "LR"])
    pm = phase_metrics(path, float(t[-1]) - a.last_ms)
    return (float(np.nanmean(r)), float(np.mean(fe)), float(cut), float(pm.get("stride_meas", np.nan)),
            float(np.nanmean([pm.get("stance_L", np.nan), pm.get("stance_R", np.nan)])))


data = {}
for d in sorted(glob.glob(os.path.join(a.root, "*"))):
    name = os.path.basename(d)
    rows = {}
    for f in glob.glob(os.path.join(d, "s*", "*.h5")):
        if os.path.islink(f) or not os.path.exists(f.replace(".h5", ".log")):   # the symlinked source run
            continue
        k = int(re.search(r"/s(\d+)/", f).group(1))
        rows[k] = session(f)
    if rows:
        data[name] = [rows[k] for k in sorted(rows)]
n = max(len(v) for v in data.values())
for i, (key, fmt) in enumerate((("r(E,F)", "{:6.2f}"), ("Force-E p95", "{:6.1f}"), ("CUT->RG-E baseline (pA)", "{:6.1f}"),
                                ("stride (ms)", "{:6.0f}"), ("stance fraction", "{:6.2f}"))):
    print(f"\n{key}   session:" + "".join(f"{k + 1:6d}" for k in range(n)))
    for name, v in data.items():
        print(f"  {name:16s}   " + "".join(fmt.format(x[i]) for x in v))
print("\nsessions to criterion (r(E,F) <= -0.5, last --last-ms of the session):")
for name, v in data.items():
    c = next((k + 1 for k, x in enumerate(v) if x[0] <= -0.5), None)
    print(f"  {name:16s} {c if c else 'not reached in %d' % len(v)}")
if a.fig:
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    for name, v in data.items():
        ls = "-" if "noees" in name else ("--" if "ees30" in name else ":")
        col = "#2a78d6" if name.startswith("l0.5") else "#eb6834"
        ax[0].plot(range(1, len(v) + 1), [x[0] for x in v], ls, color=col, label=name)
        ax[1].plot(range(1, len(v) + 1), [x[2] for x in v], ls, color=col)
    ax[0].axhline(-0.5, color="#aaa", lw=0.8); ax[0].set_ylabel("r(Force-E, Force-F), end of session")
    ax[1].set_ylabel("captured CUT->RG-E (pA)")
    for x in ax: x.set_xlabel("session"); x.grid(alpha=0.3)
    ax[0].legend(fontsize=7)
    os.makedirs(os.path.dirname(a.fig), exist_ok=True); fig.savefig(a.fig, dpi=130)
