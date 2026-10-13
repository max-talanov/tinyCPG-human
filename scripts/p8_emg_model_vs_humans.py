#!/usr/bin/env python3
"""
p8_emg_model_vs_humans.py
PLAN.md P8: EMG envelope timing of the model (act_e = extensor / gastrocnemius-like, act_f = flexor / TA-like) against the two
healthy controls and the four SCI patients, from the ensemble envelopes over the gait cycle (heel strike to heel strike).

Humans: validation/human_gait_reference.json (controls, Slow/Medium/Fast) and validation/human_sci_metrics.json (patients, per leg
and condition; EMG channels flagged bad are already excluded there). Model: model_metrics() of cpg_human_gait_metrics.py (cut_on
strides, left-leg act_e / act_f), the same burst rule (25 % of the ensemble peak).

Measured per envelope: peak position, dominant burst onset / offset / duration (% cycle), number of bursts, and the TA-GA
co-activation index (Falconer-Winter, %). Amplitudes (mean envelope, uV) are given for the humans only: the model activation is not
calibrated to uV, and --extensor-strength acts on force, after the activation, so the model's act_e does not change with it.

Writes validation/p8_emg_model_vs_humans.json and plots/p8/emg_model_vs_humans.png.
Usage: python3 scripts/p8_emg_model_vs_humans.py [--root arch2]
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cpg_human_gait_metrics as H  # noqa: E402


def env_row(ta, ga):
    ta, ga = np.asarray(ta, float), np.asarray(ga, float)
    out = {}
    for k, m in (("TA", ta), ("GA", ga)):
        b = H.bursts(m)
        out.update({f"{k}_peak": float(np.argmax(m[:H.NPTS - 1])), f"{k}_on": b["onset_pct"], f"{k}_off": b["offset_pct"],
                    f"{k}_dur": b["dur_pct"], f"{k}_nb": b["n_bursts"], f"{k}_uV": float(m.mean() * 1000.0)})
    out["coact"] = H.coactivation(ta, ga)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="arch2", help="model results root under results/human_modes (default arch2)")
    ap.add_argument("--from-ms", type=float, default=10000.0)
    a = ap.parse_args()
    ref = json.load(open(os.path.join(ROOT, "validation/human_gait_reference.json")))
    pat = json.load(open(os.path.join(ROOT, "validation/human_sci_metrics.json")))
    rows, prof = [], {}
    for sub in ("Ctr01", "Ctr02"):
        for sp in ("Slow", "Medium", "Fast"):
            e = ref[sub][sp]["ens"]
            r = env_row(e["TA"], e["GA"]); r.update(group="healthy", label=f"{sub} {sp}"); rows.append(r); prof[r["label"]] = (e["TA"], e["GA"])
    for exp, ed in pat.items():
        for cond, c in ed["conditions"].items():
            for side, sn in (("Sx", "L"), ("Dx", "R")):
                if f"TA_{side}" in c["ens"] and f"GA_{side}" in c["ens"]:
                    r = env_row(c["ens"][f"TA_{side}"], c["ens"][f"GA_{side}"])
                    worse = ed["worse_side"] == side
                    r.update(group="patient", label=f"{exp} {cond} {sn}{' (worse)' if worse else ''}"); rows.append(r)
                    prof[r["label"]] = (c["ens"][f"TA_{side}"], c["ens"][f"GA_{side}"])
    base = os.path.join(ROOT, "results/human_modes", a.root)
    model_files = [("model comfortable (healthy)", f"{base}/7a/comfortable.h5"), ("model slow", f"{base}/7a/slow.h5"),
                   ("model fast", f"{base}/7a/fast.h5"), ("model BWS 50%", f"{base}/7a/bws50.h5"), ("model BWS 90%", f"{base}/7a/bws90.h5"),
                   ("model s 0.5 REC, s10", f"{base}/chain/r0.5_noees/s10/bws50.h5"), ("model s 0.25 REC, s10", f"{base}/chain/r0.25_noees/s10/bws50.h5"),
                   ("model s 0.25 REC + EES, s10", f"{base}/chain/r0.25_ees10/s10/bws50.h5")]
    for lab, p in model_files:
        if not os.path.exists(p):
            continue
        m = H.model_metrics(p, a.from_ms)
        if m is None:
            continue
        r = env_row(m["ens"]["TA"], m["ens"]["GA"]); r.update(group="model", label=lab, stride_s=m["stride_s"])
        import h5py
        with h5py.File(p, "r") as f:
            keep = f["times_ms"][()] > a.from_ms
            r["GA_act"] = float(np.mean([f[f"leg_{sd}/act_e"][()][keep].mean() for sd in "LR"]))
            r["TA_act"] = float(np.mean([f[f"leg_{sd}/act_f"][()][keep].mean() for sd in "LR"]))
        rows.append(r)
        prof[lab] = (m["ens"]["TA"], m["ens"]["GA"])
    print(f"{'':36s} {'GA peak':>7s} {'GA on-off (dur)':>17s} {'nb':>2s} {'TA peak':>7s} {'TA on-off (dur)':>17s} {'nb':>2s} {'coact':>6s} {'GA uV':>6s} {'TA uV':>6s}")
    for r in rows:
        f = lambda v: "  -" if (v is None or (isinstance(v, float) and np.isnan(v))) else f"{v:.0f}"
        print(f"{r['label']:36s} {f(r['GA_peak']):>7s} {f(r['GA_on']) + '-' + f(r['GA_off']) + ' (' + f(r['GA_dur']) + ')':>17s} {r['GA_nb']:>2d} "
              f"{f(r['TA_peak']):>7s} {f(r['TA_on']) + '-' + f(r['TA_off']) + ' (' + f(r['TA_dur']) + ')':>17s} {r['TA_nb']:>2d} {r['coact']:6.0f} "
              f"{(r['GA_uV'] if r['group'] != 'model' else float('nan')):6.1f} {(r['TA_uV'] if r['group'] != 'model' else float('nan')):6.1f}")
    ref_m = next((r for r in rows if r["label"] == "model comfortable (healthy)"), None)
    if ref_m is not None:
        print("\nmodel mean activation relative to the healthy comfortable walk (act_e = GA-like, act_f = TA-like):")
        for r in rows:
            if r["group"] == "model":
                print(f"  {r['label']:32s} GA {r['GA_act'] / ref_m['GA_act']:.2f}   TA {r['TA_act'] / ref_m['TA_act']:.2f}")
        hm = {m: np.median([r[f"{m}_uV"] for r in rows if r["group"] == "healthy"]) for m in ("GA", "TA")}
        pm = {m: np.median([r[f"{m}_uV"] for r in rows if r["group"] == "patient"]) for m in ("GA", "TA")}
        print(f"patients' EMG relative to the controls (median of legs and conditions): GA {pm['GA'] / hm['GA']:.2f}, TA {pm['TA'] / hm['TA']:.2f}")
    for g in ("healthy", "patient"):
        sel = [r for r in rows if r["group"] == g]
        print(f"\n{g}: GA peak {np.median([r['GA_peak'] for r in sel]):.0f} % (range {min(r['GA_peak'] for r in sel):.0f}-{max(r['GA_peak'] for r in sel):.0f}), "
              f"TA peak {np.median([r['TA_peak'] for r in sel]):.0f} %, coactivation median {np.median([r['coact'] for r in sel]):.0f} % "
              f"(range {min(r['coact'] for r in sel):.0f}-{max(r['coact'] for r in sel):.0f}), GA {np.median([r['GA_uV'] for r in sel]):.1f} uV, TA {np.median([r['TA_uV'] for r in sel]):.1f} uV")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = np.linspace(0, 100, H.NPTS)
    fig, ax = plt.subplots(2, 3, figsize=(15, 7), sharex=True, sharey=True)
    col = {"healthy": "#2a9d8f", "patient": "#d1495b", "model": "#264653"}
    for i, (mu, idx) in enumerate((("GA (extensor; model act_e)", 1), ("TA (flexor; model act_f)", 0))):
        for j, g in enumerate(("healthy", "patient", "model")):
            a_ = ax[i, j]
            for r in [r for r in rows if r["group"] == g]:
                y = np.asarray(prof[r["label"]][idx], float)
                a_.plot(x, y / max(y.max(), 1e-12), color=col[g], lw=1.6 if g == "model" else 1.0, alpha=0.9 if g == "model" else 0.55)
            a_.axhline(H.BURST_FRAC, color="#aaa", lw=0.7, ls=":")
            a_.set_title(f"{mu} - {g}" + (" (comfortable, BWS, weak-extensor chains)" if g == "model" else ""), fontsize=9)
            a_.grid(alpha=.2)
            if j == 0:
                a_.set_ylabel("envelope / own peak")
            if i == 1:
                a_.set_xlabel("gait cycle (%)")
    fig.suptitle("EMG envelope over the gait cycle: healthy controls, SCI patients (per leg and condition), model", fontsize=11)
    fig.tight_layout()
    os.makedirs(os.path.join(ROOT, "plots/p8"), exist_ok=True)
    out = os.path.join(ROOT, "plots/p8/emg_model_vs_humans.png")
    fig.savefig(out, dpi=140)
    json.dump(rows, open(os.path.join(ROOT, "validation/p8_emg_model_vs_humans.json"), "w"), indent=1, default=float)
    print("wrote", out)


if __name__ == "__main__":
    main()
