#!/usr/bin/env python3
"""
p8_mn5_vs_humans.py
PLAN.md P8 on the MN5 production chains (run_p7_chain_mn5.sh, architecture-round wiring): gait timing (stride, stance, double support) and
EMG-envelope timing / co-activation of every chain condition at session 15 (mean over the seeds), against the four SCI patients
(validation/human_sci_metrics.json) and the two healthy controls (validation/human_gait_reference.json). The healthy model reference is the
seed's trained comfortable source (<root>/src/s<seed>/comfortable.h5). Same measures as p8_model_vs_patients.py / p8_emg_model_vs_humans.py.
Writes validation/p8_mn5_vs_humans.json, plots/p8/mn5_vs_patients.png and plots/p8/mn5_emg_vs_humans.png.
Usage: python3 scripts/p8_mn5_vs_humans.py [--root results/2026-10-15/p7/human_modes/p7_arch] [--session 15]
"""
import argparse
import glob
import json
import os
import sys

import h5py
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cpg_human_gait_metrics as H  # noqa: E402
from p8_emg_model_vs_humans import env_row  # noqa: E402
from p8_model_vs_patients import mrow, patients  # noqa: E402
from p7_mn5_summary import CONDS  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="results/2026-10-15/p7/human_modes/p7_arch")
    ap.add_argument("--seeds", type=int, nargs="+", default=[12345, 54321, 777])
    ap.add_argument("--session", type=int, default=15)
    ap.add_argument("--from-ms", type=float, default=10000.0)
    a = ap.parse_args()
    pats = patients()
    ref = json.load(open(os.path.join(ROOT, "validation/human_gait_reference.json")))
    pat = json.load(open(os.path.join(ROOT, "validation/human_sci_metrics.json")))

    def files(d, k):
        if d == "source":
            return [f"{a.root}/src/s{s}/comfortable.h5" for s in a.seeds]
        out = []
        for s in a.seeds:
            g = glob.glob(f"{a.root}/chain/s{s}/{d}/s{k}/bws*.h5")
            out += g[:1]
        return out

    conds = [("healthy source (comfortable)", "source", 0)] + [(n, d, a.session) for n, d in CONDS] + [(f"{n} (s1)", d, 1) for n, d in CONDS if "control" in n]
    rows = []
    for name, d, k in conds:
        fs = files(d, k)
        if not fs:
            continue
        g = [mrow(f, a.from_ms) for f in fs]
        em = []
        for f in fs:
            m = H.model_metrics(f, a.from_ms)
            if m is None:
                continue
            r = env_row(m["ens"]["TA"], m["ens"]["GA"])
            with h5py.File(f, "r") as h:
                keep = h["times_ms"][()] > a.from_ms
                r["GA_act"] = float(np.mean([h[f"leg_{sd}/act_e"][()][keep].mean() for sd in "LR"]))
            em.append(r)
        row = {"label": name, "n": len(fs)}
        for key in ("stride", "stance", "ds", "rEF"):
            row[key] = float(np.nanmean([x[key] for x in g]))
        for key in ("GA_peak", "GA_on", "GA_off", "GA_dur", "TA_peak", "TA_on", "TA_off", "TA_dur", "coact", "GA_act"):
            v = [x[key] for x in em if x.get(key) is not None]
            row[key] = float(np.nanmean(v)) if v and not np.all(np.isnan(v)) else float("nan")
        rows.append(row)

    print("Patients: " + "; ".join(f"{r['id']} {r['cond']} {r['stride']:.2f}s/{r['stance']:.2f}/{r['ds']:.2f}" for r in pats))
    print(f"\n{'model (mean of seeds)':34s} {'n':>1s} {'stride s':>8s} {'stance':>6s} {'DS':>5s} {'r(EF)':>6s} | {'GA peak':>7s} {'GA on-off':>9s} {'TA peak':>7s} {'TA on-off':>9s} {'coact':>5s}")
    for r in rows:
        print(f"{r['label']:34s} {r['n']:>1d} {r['stride']:8.2f} {r['stance']:6.2f} {r['ds']:5.2f} {r['rEF']:6.2f} | "
              f"{r['GA_peak']:7.0f} {r['GA_on']:4.0f}-{r['GA_off']:<4.0f} {r['TA_peak']:7.0f} {r['TA_on']:4.0f}-{r['TA_off']:<4.0f} {r['coact']:5.0f}")
    hu = []
    for sub in ("Ctr01", "Ctr02"):
        for sp in ("Slow", "Medium", "Fast"):
            e = ref[sub][sp]["ens"]; hu.append(env_row(e["TA"], e["GA"]))
    pe = []
    for exp, ed in pat.items():
        for cond, c in ed["conditions"].items():
            for side in ("Sx", "Dx"):
                if f"TA_{side}" in c["ens"] and f"GA_{side}" in c["ens"]:
                    pe.append(env_row(c["ens"][f"TA_{side}"], c["ens"][f"GA_{side}"]))
    for nm, sel in (("controls", hu), ("patients", pe)):
        print(f"{nm}: GA peak median {np.median([r['GA_peak'] for r in sel]):.0f} %, TA peak {np.median([r['TA_peak'] for r in sel]):.0f} %, "
              f"co-activation median {np.median([r['coact'] for r in sel]):.0f} % (range {min(r['coact'] for r in sel):.0f}-{max(r['coact'] for r in sel):.0f})")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(os.path.join(ROOT, "plots/p8"), exist_ok=True)
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
    for a_, key, lab in ((ax[0], "stance", "stance fraction"), (ax[1], "ds", "double support")):
        for r in rows:
            c = "#222" if "source" in r["label"] else ("#2a7fbb" if "REC" in r["label"] else ("#e9a23b" if "fixed" in r["label"] else "#9aa6b2"))
            a_.scatter(r["stride"], r[key], c=c, s=30)
        for r in pats:
            a_.scatter(r["stride"], r[key], c="#d1495b", marker="D", s=46)
        a_.set_xlabel("stride (s)"); a_.set_ylabel(lab); a_.grid(alpha=.25)
    ax[0].scatter([], [], c="#d1495b", marker="D", label="patients (IMU)"); ax[0].scatter([], [], c="#222", label="healthy source")
    ax[0].scatter([], [], c="#9aa6b2", label="control / EES"); ax[0].scatter([], [], c="#e9a23b", label="fixed weakness"); ax[0].scatter([], [], c="#2a7fbb", label="REC")
    ax[0].legend(fontsize=7)
    for r in rows:
        ax[2].scatter(r["coact"], r["rEF"], c="#2a7fbb" if "REC" in r["label"] else "#9aa6b2", s=30)
    for r in pe:
        ax[2].axvline(r["coact"], color="#d1495b", alpha=.12)
    ax[2].set_xlabel("TA-GA co-activation (%)  (red lines: patient legs)"); ax[2].set_ylabel("model r(E,F)"); ax[2].grid(alpha=.25)
    fig.suptitle(f"MN5 production chains, session {a.session} (mean of {len(a.seeds)} seeds) vs four SCI patients", fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(ROOT, "plots/p8/mn5_vs_patients.png"), dpi=140)
    json.dump({"rows": rows, "patients": pats}, open(os.path.join(ROOT, "validation/p8_mn5_vs_humans.json"), "w"), indent=1, default=float)
    print("wrote plots/p8/mn5_vs_patients.png")


if __name__ == "__main__":
    main()
