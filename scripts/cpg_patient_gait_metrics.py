#!/usr/bin/env python3
"""
cpg_patient_gait_metrics.py
Gait and EMG metrics per patient, per leg and per condition, from the Delsys Trigno recordings of
the SCI patients in results/human_data/2026-10-05/ExpNN/ (PLAN.md Phase 8, SCI arm).
Reuses the loader, foot-event detector and EMG envelope of cpg_human_gait_metrics.py, but
the healthy pairing of strides and legs breaks on these gaits (double support above stance),
so everything here is computed per leg first.

Conditions (walker, support, ankle lock) and the worse side come from validation/human_sci_meta.json
(from the enrollment log; IDs only). Sides: Sx = left, Dx = right.

Events: foot gyro / accelerometer as in cpg_human_gait_metrics.py (toe-off = gyro zero crossing
after the swing peak, heel strike = first impact spike). No force plate: stance is an IMU estimate.

Per condition (strides pooled over its trials; first and last event of every pass dropped):
  stride_s, cv        per-leg HS-to-HS time, median and SD/median
  stance, swing       per-leg (TO - HS)/stride, from that foot alone
  ds, flight          fraction of the steady walking window with both feet in stance / both in swing,
                      from the per-foot stance intervals (no stride pairing)
  step_asym           100 (stepLR - stepRL)/(stepLR + stepRL), steps from one heel strike to the next
                      contralateral one (unreliable if |stepLR + stepRL - stride| > 15 %: reported NaN)
  step_asym_to        the same asymmetry from toe-off times (toe-off does not depend on the heel-impact
                      spike, which jumps between two spikes on several patient feet)
  swing_s, swing_cv   per-leg heel strike minus the preceding toe-off; a large SD/median (> 0.25) means
                      the heel strike is not reliably placed, so stance, ds and step_asym are soft
  EMG per leg (TA, GA, VL, BF): mean envelope (uV) over the walking window, and for TA and GA the
                      ensemble peak phase and dominant burst on/off (% cycle) as in the healthy script.
                      Amplitudes are raw uV, not normalised, so L/R ratios are meaningful.
  amp_ratio_worse     amplitude of the worse side / the other side (< 1: the worse side is weaker)

EMG channel quality, per trial and channel: bad if > 0.1 % of samples clip (|x| > 5.4 mV) or the
quietest-fifth noise level exceeds 4x that channel's standing baseline and 25 uV. Bad channel-trials
are left out of every EMG metric and listed.

Usage:
  python3 scripts/cpg_patient_gait_metrics.py                 # all patients
  python3 scripts/cpg_patient_gait_metrics.py --patient Exp02
Output: validation/human_sci_metrics.json, plots/human_sci/{events_ExpNN,emg_ExpNN}.png
"""
import argparse
import glob
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpg_human_gait_metrics as g  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "results", "human_data", "2026-10-05")
META = os.path.join(ROOT, "validation", "human_sci_meta.json")
HEALTHY = os.path.join(ROOT, "validation", "human_gait_reference.json")

MUSCLES = {"TA": "Tibiale Ant", "GA": "Gastro", "VL": "Vasto", "BF": "Bic Fem SH"}
CLIP_UV, CLIP_FRAC = 5400.0, 1e-3
NOISE_X, NOISE_MIN_UV = 4.0, 25.0
COL = {"Sx": "#2a78d6", "Dx": "#eb6834"}
INK, INK2, GRID = g.INK, g.INK2, g.GRID


def load(path):
    """load_trigno with the sensor-name typo of the patient files fixed ('Vasto sx')."""
    return {k.replace("Vasto sx", "Vasto Sx"): v for k, v in g.load_trigno(path).items()}


# ---------------------------------------------------------------- EMG quality
def spread_uv(v):
    return 1.48 * np.median(np.abs(v - np.median(v))) * 1000.0


def rest_noise_uv(t, v, win_s=0.5):
    """Noise level at rest: 20th percentile of the windowed robust spread (uV)."""
    n = max(8, int(win_s * g.fs_of(t)))
    k = len(v) // n
    if k < 5:
        return spread_uv(v)
    w = v[:k * n].reshape(k, n)
    mad = 1.48 * np.median(np.abs(w - np.median(w, axis=1, keepdims=True)), axis=1) * 1000.0
    return float(np.percentile(mad, 20))


def channel_ok(t, v, base_uv):
    clip = float(np.mean(np.abs(v) * 1000.0 > CLIP_UV))
    noise = rest_noise_uv(t, v)
    bad_noise = noise > max(NOISE_X * base_uv, NOISE_MIN_UV)
    return (clip <= CLIP_FRAC and not bad_noise), clip, noise


# ---------------------------------------------------------------- gait events with a data-driven sign
def foot_events_auto(t, gz, acc):
    """Foot events with the gyro polarity chosen from the data. The sensor orientation differs
    between sessions and the healthy rule (sharp peak larger than the lobe) fails on some patient
    feet. True stance has the foot nearly still, true swing has it moving: of the two polarities,
    keep the one whose detected stance intervals have the lowest median |gyro| relative to its
    swing intervals. Returns (hs, to, sign, ratio)."""
    w = np.abs(g.lowpass(gz, g.fs_of(t), 25))
    best = None
    for sign in (1, -1):
        hs, to = g.foot_events(t, gz, acc, sign=sign)
        iv = stance_intervals(hs, to)
        if len(iv) < 4 or len(hs) < 4:
            continue
        inside = np.zeros(len(t), bool)
        for a, b in iv:
            inside |= (t >= a) & (t < b)
        win = (t >= iv[0][0]) & (t <= iv[-1][1])
        if (win & ~inside).sum() < 10 or (win & inside).sum() < 10:
            continue
        ratio = float(np.median(w[win & inside]) / max(np.median(w[win & ~inside]), 1e-9))
        if best is None or ratio < best[3]:
            best = (hs, to, sign, ratio)
    return best if best is not None else (np.array([]), np.array([]), 0, np.nan)


# ---------------------------------------------------------------- strides and legs
def stance_intervals(hs, to):
    """Stance intervals [HS_k, TO_(k+1)] of one foot (to[k] and hs[k] bound swing k)."""
    out = []
    for k in range(len(hs) - 1):
        nxt = to[to > hs[k]]
        if nxt.size and nxt[0] < hs[k + 1]:
            out.append((hs[k], nxt[0]))
    return out


def leg_strides(hs, to):
    """Per-leg strides (HS to HS) with their own stance fraction; first/last event dropped,
    strides more than 30 % off the median stride time dropped."""
    hs, to = hs[1:-1], to[1:-1]
    if len(hs) < 3:
        return []
    out = []
    for k in range(len(hs) - 1):
        nxt = to[(to > hs[k]) & (to < hs[k + 1])]
        if nxt.size == 1:
            T = hs[k + 1] - hs[k]
            out.append(dict(a=hs[k], b=hs[k + 1], T=T, stance=(nxt[0] - hs[k]) / T))
    if not out:
        return []
    med = np.median([s["T"] for s in out])
    return [s for s in out if abs(s["T"] - med) < 0.3 * med]


def support_fractions(ev):
    """Fractions of the steady window with both feet in stance (ds) and both in swing (flight)."""
    iv = {sd: stance_intervals(ev[sd][0][1:-1], ev[sd][1][1:-1]) for sd in g.SIDES}
    if not iv["Sx"] or not iv["Dx"]:
        return np.nan, np.nan
    t0 = max(iv["Sx"][0][0], iv["Dx"][0][0])
    t1 = min(iv["Sx"][-1][1], iv["Dx"][-1][1])
    if t1 <= t0:
        return np.nan, np.nan
    tt = np.arange(t0, t1, 0.005)
    st = {sd: np.zeros(len(tt), bool) for sd in g.SIDES}
    for sd in g.SIDES:
        for a, b in iv[sd]:
            st[sd] |= (tt >= a) & (tt < b)
    return float(np.mean(st["Sx"] & st["Dx"])), float(np.mean(~st["Sx"] & ~st["Dx"]))


def step_times(ev):
    """Median steps Sx->Dx and Dx->Sx (s) from heel strikes, steady events only."""
    L, R = ev["Sx"][0][1:-1], ev["Dx"][0][1:-1]
    if len(L) < 3 or len(R) < 3:
        return np.nan, np.nan, np.nan
    sl = [R[R > x][0] - x for x in L if (R > x).any()]
    sr = [L[L > x][0] - x for x in R if (L > x).any()]
    stride = np.median(np.concatenate([np.diff(L), np.diff(R)]))
    a, b = np.median([s for s in sl if s < stride]), np.median([s for s in sr if s < stride])
    return float(a), float(b), float(stride)


def swing_durations(hs, to):
    """HS minus the toe-off that precedes it (to[k], hs[k] bound swing k), steady events only."""
    hs, to = hs[1:-1], to[1:-1]
    n = min(len(hs), len(to))
    d = hs[:n] - to[:n]
    return d[(d > 0.05) & (d < 2.0)]


def step_times_to(ev):
    """Median steps Sx->Dx and Dx->Sx (s) between toe-offs of the two feet."""
    L, R = ev["Sx"][1][1:-1], ev["Dx"][1][1:-1]
    if len(L) < 3 or len(R) < 3:
        return np.nan, np.nan, np.nan
    sl = [R[R > x][0] - x for x in L if (R > x).any()]
    sr = [L[L > x][0] - x for x in R if (L > x).any()]
    stride = np.median(np.concatenate([np.diff(L), np.diff(R)]))
    return float(np.median([x for x in sl if x < stride])), float(np.median([x for x in sr if x < stride])), float(stride)


# ---------------------------------------------------------------- one trial
def analyse_trial(path, base_uv):
    d = load(path)
    ev, evinfo = {}, {}
    for sd in g.SIDES:
        t, gz = d[f"Piede {sd}"]["GYRO Z (deg/s)"]
        acc = np.linalg.norm(np.c_[[d[f"Piede {sd}"][f"ACC {c} (G)"][1] for c in "XYZ"]].T, axis=1)
        hs, to, sign, ratio = foot_events_auto(t, gz, acc)
        ev[sd] = (hs, to)
        evinfo[sd] = dict(sign=int(sign), still_ratio=ratio)
    strs = {sd: leg_strides(*ev[sd]) for sd in g.SIDES}
    ds, fl = support_fractions(ev)
    sLR, sRL, stride = step_times(ev)
    tLR, tRL, tstride = step_times_to(ev)
    swing = {sd: swing_durations(*ev[sd]) for sd in g.SIDES}
    t0 = min(ev["Sx"][0][1], ev["Dx"][0][1]) if min(map(len, (ev["Sx"][0], ev["Dx"][0]))) > 1 else None
    t1 = max(ev["Sx"][0][-2], ev["Dx"][0][-2]) if t0 is not None else None
    emg, prof, quality = {}, {}, {}
    for m, nm in MUSCLES.items():
        for sd in g.SIDES:
            t, v = d[f"{nm} {sd}"]["EMG 1 (mV)"]
            ok, clip, noise = channel_ok(t, v, base_uv[(m, sd)])
            quality[f"{m}_{sd}"] = dict(ok=bool(ok), clip=clip, noise_uv=noise)
            if not ok or t0 is None:
                continue
            env = g.emg_envelope(t, v)
            w = (t >= t0) & (t <= t1)
            emg[(m, sd)] = float(np.mean(env[w]) * 1000.0)
            if m in ("TA", "GA") and strs[sd]:
                prof[(m, sd)] = g.cycle_profile(t, env, strs[sd])
    return dict(strs=strs, ds=ds, flight=fl, step_lr=sLR, step_rl=sRL, stride=stride,
                to_lr=tLR, to_rl=tRL, to_stride=tstride, swing=swing,
                emg=emg, prof=prof, quality=quality, ev=ev, evinfo=evinfo, d=d)


# ---------------------------------------------------------------- one patient
def analyse_patient(folder, meta):
    exp = os.path.basename(folder)
    base = load(glob.glob(os.path.join(folder, "Baseline_*.csv"))[0])
    base_uv = {(m, sd): spread_uv(base[f"{nm} {sd}"]["EMG 1 (mV)"][1]) for m, nm in MUSCLES.items() for sd in g.SIDES}
    worse = meta[exp]["worse_side"]
    groups = {}
    for f in sorted(glob.glob(os.path.join(folder, "Trial_*.csv"))):
        stem = os.path.basename(f)[:-4]
        cond = meta[exp]["conditions"].get(stem, "unlabelled")
        groups.setdefault(cond, []).append((stem, analyse_trial(f, base_uv)))
    res = {}
    for cond, trials in groups.items():
        row = {"trials": [s for s, _ in trials], "excluded_emg": [], "n_strides": {},
               "gyro_sign": {sd: [tr["evinfo"][sd]["sign"] for _, tr in trials] for sd in g.SIDES},
               "still_ratio": {sd: [round(tr["evinfo"][sd]["still_ratio"], 2) for _, tr in trials] for sd in g.SIDES}}
        for sd in g.SIDES:
            S = [s for _, tr in trials for s in tr["strs"][sd]]
            row["n_strides"][sd] = len(S)
            if not S:
                continue
            T = np.array([s["T"] for s in S])
            row[f"stride_s_{sd}"] = float(np.median(T))
            row[f"cv_{sd}"] = float(T.std() / np.median(T))
            row[f"stance_{sd}"] = float(np.median([s["stance"] for s in S]))
        for k in ("ds", "flight"):
            v = [tr[k] for _, tr in trials if np.isfinite(tr[k])]
            row[k] = float(np.median(v)) if v else float("nan")
        asym = []
        for _, tr in trials:
            a, b, st = tr["step_lr"], tr["step_rl"], tr["stride"]
            if np.isfinite(a) and np.isfinite(b) and abs(a + b - st) < 0.15 * st:
                asym.append(100.0 * (a - b) / (a + b))
        asym_to = []
        for _, tr in trials:
            a, b, st = tr["to_lr"], tr["to_rl"], tr["to_stride"]
            if np.isfinite(a) and np.isfinite(b) and abs(a + b - st) < 0.15 * st:
                asym_to.append(100.0 * (a - b) / (a + b))
        row["step_asym_to"] = float(np.median(asym_to)) if asym_to else float("nan")
        for sd in g.SIDES:
            sw = np.concatenate([tr["swing"][sd] for _, tr in trials]) if trials else np.array([])
            if sw.size > 2:
                row[f"swing_s_{sd}"] = float(np.median(sw))
                row[f"swing_cv_{sd}"] = float(sw.std() / np.median(sw))
        row["step_asym"] = float(np.median(asym)) if asym else float("nan")
        row["step_asym_valid_trials"] = f"{len(asym)}/{len(trials)}"
        for m in MUSCLES:
            for sd in g.SIDES:
                v = [tr["emg"][(m, sd)] for _, tr in trials if (m, sd) in tr["emg"]]
                row[f"emg_{m}_{sd}_uV"] = float(np.median(v)) if v else float("nan")
                for stem, tr in trials:
                    if not tr["quality"][f"{m}_{sd}"]["ok"]:
                        row["excluded_emg"].append(f"{stem}:{m}_{sd}")
        ens = {}
        for m in ("TA", "GA"):
            for sd in g.SIDES:
                P = [tr["prof"][(m, sd)] for _, tr in trials if (m, sd) in tr["prof"]]
                if P:
                    mm = np.vstack(P).mean(0)
                    b = g.bursts(mm)
                    row[f"{m}_{sd}_peak_pct"] = float(np.argmax(mm[:g.NPTS - 1]))
                    row[f"{m}_{sd}_onset_pct"], row[f"{m}_{sd}_offset_pct"] = b["onset_pct"], b["offset_pct"]
                    ens[f"{m}_{sd}"] = mm.tolist()
        if worse in g.SIDES:
            other = "Dx" if worse == "Sx" else "Sx"
            for m in MUSCLES:
                a, b = row.get(f"emg_{m}_{worse}_uV", np.nan), row.get(f"emg_{m}_{other}_uV", np.nan)
                row[f"amp_ratio_worse_{m}"] = float(a / b) if np.isfinite(a) and np.isfinite(b) and b > 0 else float("nan")
        row["ens"] = ens
        res[cond] = row
    return res, groups, worse


# ---------------------------------------------------------------- figures
def fig_events(exp, groups, out):
    """Foot gyro of the first trial of every condition with the detected heel strikes and toe-offs."""
    conds = list(groups)
    fig, axs = plt.subplots(len(conds), 2, figsize=(14, 2.6 * len(conds)), squeeze=False, constrained_layout=True)
    for i, c in enumerate(conds):
        stem, tr = groups[c][0]
        for j, sd in enumerate(g.SIDES):
            ax = axs[i, j]
            t, gz = tr["d"][f"Piede {sd}"]["GYRO Z (deg/s)"]
            ax.plot(t, gz, color=COL[sd], lw=0.6)
            hs, to = tr["ev"][sd]
            ax.plot(hs, np.interp(hs, t, gz), "v", color=INK, ms=5, label="heel strike")
            ax.plot(to, np.interp(to, t, gz), "^", color="#1baf7a", ms=5, label="toe-off")
            ax.set_title(f"{stem[6:]} - foot {'left' if sd == 'Sx' else 'right'}  ({c})", loc="left", fontsize=9, color=INK)
            ax.set_ylabel("gyro Z (deg/s)")
    axs[0, 0].legend(loc="upper left", fontsize=8)
    fig.suptitle(f"{exp}: detected gait events on the foot gyro (first trial of each condition)", x=0.01, ha="left", fontsize=11)
    fig.savefig(out, dpi=110)
    plt.close(fig)


def fig_emg(exp, res, worse, healthy, out):
    x = np.linspace(0, 100, g.NPTS)
    fig, axs = plt.subplots(2, len(res), figsize=(4.6 * len(res), 6), sharex=True, squeeze=False, constrained_layout=True)
    for j, (c, row) in enumerate(res.items()):
        for i, m in enumerate(("TA", "GA")):
            ax = axs[i, j]
            if healthy is not None and m in healthy["ens"]:
                h = np.array(healthy["ens"][m])
                ax.plot(x, h / h.max(), color=GRID, lw=5, label="healthy, slow (Ctr01)")
            for sd in g.SIDES:
                if f"{m}_{sd}" in row["ens"]:
                    e = np.array(row["ens"][f"{m}_{sd}"])
                    amp = row.get(f"emg_{m}_{sd}_uV", np.nan)
                    ax.plot(x, e / e.max(), color=COL[sd], lw=1.8,
                            label=f"{'left' if sd == 'Sx' else 'right'}{' (worse)' if sd == worse else ''}, {amp:.0f} uV")
            ax.set_xlim(0, 100)
            ax.set_title(f"{m} - {c}" if i == 0 else m, loc="left", fontsize=10, color=INK)
            ax.legend(fontsize=7, loc="upper right")
            if j == 0:
                ax.set_ylabel("envelope (norm. to own peak)")
            if i == 1:
                ax.set_xlabel("gait cycle (%), 0 = heel strike of that leg")
    fig.suptitle(f"{exp}: EMG over the gait cycle per leg and condition (mean uV in the legend)", x=0.01, ha="left", fontsize=11)
    fig.savefig(out, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--patient", nargs="*", default=None)
    ap.add_argument("--out", default=os.path.join(ROOT, "plots", "human_sci"))
    ap.add_argument("--json", default=os.path.join(ROOT, "validation", "human_sci_metrics.json"))
    a = ap.parse_args()
    meta = json.load(open(META))
    healthy = json.load(open(HEALTHY)).get("Ctr01", {}).get("Slow") if os.path.exists(HEALTHY) else None
    folders = [f for f in sorted(glob.glob(os.path.join(a.data, "Exp*"))) if not a.patient or os.path.basename(f) in a.patient]
    allres = {}
    os.makedirs(a.out, exist_ok=True)
    for folder in folders:
        exp = os.path.basename(folder)
        res, groups, worse = analyse_patient(folder, meta)
        allres[exp] = {"worse_side": worse, "conditions": res}
        print(f"\n{exp}  (worse side: {worse})")
        print(f"  {'condition':12s} {'n L/R':>7s} {'stride L/R (s)':>15s} {'cv L/R':>9s} {'stance L/R':>11s} {'DS':>5s} {'flight':>6s} {'asymHS%':>8s} {'asymTO%':>8s} {'swing L/R (s)':>14s} {'swCV L/R':>10s}")
        for c, r in res.items():
            sl, sr = r.get("stride_s_Sx", np.nan), r.get("stride_s_Dx", np.nan)
            print(f"  {c:12s} {r['n_strides'].get('Sx', 0):3d}/{r['n_strides'].get('Dx', 0):<3d} {sl:7.2f}/{sr:<7.2f} "
                  f"{r.get('cv_Sx', np.nan):4.2f}/{r.get('cv_Dx', np.nan):<4.2f} "
                  f"{r.get('stance_Sx', np.nan):5.2f}/{r.get('stance_Dx', np.nan):<5.2f} {r['ds']:5.2f} {r['flight']:6.2f} {r['step_asym']:8.1f} {r['step_asym_to']:8.1f} "
                  f"{r.get('swing_s_Sx', np.nan):6.2f}/{r.get('swing_s_Dx', np.nan):<6.2f} {r.get('swing_cv_Sx', np.nan):4.2f}/{r.get('swing_cv_Dx', np.nan):<4.2f}")
            print("    EMG uV  " + "  ".join(f"{m} {r[f'emg_{m}_Sx_uV']:.0f}/{r[f'emg_{m}_Dx_uV']:.0f}" for m in MUSCLES)
                  + (f"   worse/other: " + " ".join(f"{m} {r.get(f'amp_ratio_worse_{m}', np.nan):.2f}" for m in MUSCLES) if worse in g.SIDES else ""))
            print(f"    gyro sign L {r['gyro_sign']['Sx']}  R {r['gyro_sign']['Dx']};  still-ratio (stance/swing |gyro|) L {r['still_ratio']['Sx']}  R {r['still_ratio']['Dx']}")
            if r["excluded_emg"]:
                print("    EMG excluded: " + ", ".join(r["excluded_emg"]))
        fig_events(exp, groups, os.path.join(a.out, f"events_{exp}.png"))
        fig_emg(exp, res, worse, healthy, os.path.join(a.out, f"emg_{exp}.png"))
    os.makedirs(os.path.dirname(a.json), exist_ok=True)
    json.dump(allres, open(a.json, "w"), indent=1)
    print("\nwrote", a.json, "and figures in", a.out)


if __name__ == "__main__":
    main()
