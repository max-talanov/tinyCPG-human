#!/usr/bin/env python3
"""
human_kinematics_patients.py
Per-patient version of human_kinematics.py for the Trigno IMU exports in
results/human_data/2026-10-05/ExpNN/ (Baseline_Exp_NN_1.csv + Trial_Exp_NN[_<cond>]_k.csv).

For each patient: one Baseline (standing) and several walking trials. Trials are
grouped by the condition tag in the file name (none -> "Trial", e.g. "leftsupport",
"withoutsupport"); strides are pooled within a group. The processing is the one of
human_kinematics.py (Baseline = gyro bias + zero reference, PCA sagittal axis,
stride cycle from the shank mid-swing peak, angle = integrated angular velocity).

Axis SIGN: taken from the healthy control session (--ref-dir, default Ctr02, same
sensors) when the patient's PCA axis is within ~30 deg of the control's; otherwise
the rules of human_kinematics.py (shank skew, thigh/foot correlation with shank).

Usage: python3 scripts/human_kinematics_patients.py [--data DIR] [--ref-dir DIR] [--out DIR]
"""
import argparse
import glob
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import find_peaks
from scipy.stats import skew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import human_kinematics as hk  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "results", "human_data", "2026-10-05")
REF = os.path.join(HERE, "..", "results", "human_data", "2026-09-28", "Ctr02")
OUT = os.path.join(HERE, "..", "plots", "kinematics", "patients")

SEGS, SIDES, NPTS = hk.SEGS, hk.SIDES, hk.NPTS
SENSORS = [f"{sg} {sd}" for sd, _ in SIDES for sg, _ in SEGS]
GROUP_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]      # categorical slots 1-3
BASE_COL = hk.COL["Baseline"]
INK2 = hk.INK2


def _load(path):
    return hk.load_imu(path, set(SENSORS))


# ---------------------------------------------------------------- analysis
def trial_group(path):
    m = re.match(r"Trial_Exp_\d+(?:_([A-Za-z]+))?_(\d+)\.csv", os.path.basename(path))
    return (m.group(1) or "Trial", int(m.group(2)))


def analyse_patient(folder, ref_axis):
    files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    base = [f for f in files if os.path.basename(f).startswith("Baseline")][0]
    trials = [f for f in files if f != base]
    with ProcessPoolExecutor() as ex:
        loaded = list(ex.map(_load, [base] + trials))
    data = dict(zip([base] + trials, loaded))
    fs = 1.0 / np.median(np.diff(data[base][SENSORS[0]]["t"]))

    bias = {s: np.median(data[base][s]["gyro"], axis=0) for s in SENSORS}
    key = {f: trial_group(f) for f in trials}
    gyro = {(f, s): data[f][s]["gyro"] - bias[s] for f in trials for s in SENSORS}
    win = {(f, sd): hk.active_window(gyro[(f, f"Tibiale {sd}")], fs) for f in trials for sd, _ in SIDES}

    axis, flipped_by = {}, {}
    for s in SENSORS:
        sd = s.split()[1]
        G = np.vstack([gyro[(f, s)][slice(*win[(f, sd)])] for f in trials])
        _, _, vt = np.linalg.svd(G - G.mean(0), full_matrices=False)
        axis[s] = vt[0]
    for sd, _ in SIDES:
        sh = f"Tibiale {sd}"
        for s in [sh] + [f"{sg} {sd}" for sg in ("Femore", "Piede")]:
            cosang = float(axis[s] @ ref_axis[s]) if ref_axis else 0.0
            if abs(cosang) > 0.87:                         # within ~30 deg of the control axis
                if cosang < 0:
                    axis[s] = -axis[s]
                flipped_by[s] = f"ref({cosang:+.2f})"
        if sh not in flipped_by:
            w_sh = np.concatenate([gyro[(f, sh)][slice(*win[(f, sd)])] @ axis[sh] for f in trials])
            if skew(w_sh) < 0:
                axis[sh] = -axis[sh]
            flipped_by[sh] = "skew"
        for sg in ("Femore", "Piede"):
            s = f"{sg} {sd}"
            if s in flipped_by:
                continue
            c = [hk.lagged_corr(gyro[(f, s)][slice(*win[(f, sd)])] @ axis[s],
                                gyro[(f, sh)][slice(*win[(f, sd)])] @ axis[sh], fs)[0] for f in trials]
            if np.mean(c) < 0:
                axis[s] = -axis[s]
            flipped_by[s] = "corr"

    w, ang = {}, {}
    for f in trials + [base]:
        for s in SENSORS:
            g = (data[f][s]["gyro"] - bias[s]) if f != base else data[f][s]["gyro"] - bias[s]
            wn = hk.lowpass(g @ axis[s], fs)
            w[(f, s)] = wn
            ang[(f, s)] = hk.integrate(wn, fs)

    strides = {}
    for f in trials:
        for sd, _ in SIDES:
            lo, hi = win[(f, sd)]
            seg = w[(f, f"Tibiale {sd}")][lo:hi]
            pk, _ = find_peaks(seg, height=0.35 * np.percentile(seg, 99.5), distance=int(0.5 * fs))
            pk = pk + lo
            dur = np.diff(pk) / fs
            keep = np.abs(dur - np.median(dur)) < 0.25 * np.median(dur)
            pairs = [(pk[i], pk[i + 1]) for i in range(len(dur)) if keep[i]]
            strides[(f, sd)] = pairs[1:-1] if len(pairs) > 4 else pairs

    groups = sorted({key[f][0] for f in trials}, key=lambda g: (g != "Trial", g))
    prof = {}                                  # (group, sensor) -> dict(w, ang, T, trial)
    for g in groups:
        for s in SENSORS:
            sd = s.split()[1]
            W, A, T, tid = [], [], [], []
            for f in trials:
                if key[f][0] != g:
                    continue
                for a, b in strides[(f, sd)]:
                    W.append(hk.cycle(w[(f, s)], a, b))
                    x = hk.cycle(ang[(f, s)], a, b)
                    A.append(x - x.mean())
                    T.append((b - a) / fs)
                    tid.append(key[f][1])
            prof[(g, s)] = dict(w=np.array(W), ang=np.array(A), T=np.array(T), trial=np.array(tid))
    return dict(fs=fs, w=w, ang=ang, strides=strides, win=win, axis=axis, signs=flipped_by,
                base=base, trials=trials, key=key, groups=groups, prof=prof)


# ---------------------------------------------------------------- plotting
def colors(res):
    c = {"Baseline": BASE_COL}
    for i, g in enumerate(res["groups"]):
        c[g] = GROUP_COLORS[i % len(GROUP_COLORS)]
    return c


def handles(res, col):
    h = [plt.Line2D([], [], color=BASE_COL, lw=2, label="Baseline (standing)")]
    h += [plt.Line2D([], [], color=col[g], lw=2, label=g) for g in res["groups"]]
    return h


def fig_timeseries(res, col, title, out):
    fs = res["fs"]
    fig, axs = plt.subplots(3, 2, figsize=(12, 8.5), sharey="row", constrained_layout=True)
    first = {g: min((f for f in res["trials"] if res["key"][f][0] == g), key=lambda f: res["key"][f][1])
             for g in res["groups"]}
    for i, (sg, sgn) in enumerate(SEGS):
        for j, (sd, sdn) in enumerate(SIDES):
            ax = axs[i, j]
            s = f"{sg} {sd}"
            seg = res["w"][(res["base"], s)][:int(6 * fs)]
            ax.plot(np.arange(len(seg)) / fs, seg, color=BASE_COL, lw=1.6, zorder=1)
            for g in res["groups"]:
                f = first[g]
                if not res["strides"][(f, sd)]:
                    continue
                t0 = res["strides"][(f, sd)][0][0] - int(0.3 * fs)
                seg = res["w"][(f, s)][t0:t0 + int(6 * fs)]
                ax.plot(np.arange(len(seg)) / fs, seg, color=col[g], lw=1.1, zorder=2)
            ax.axhline(0, color=BASE_COL, lw=0.8, zorder=0)
            ax.set_title(f"{sgn} - {sdn}", loc="left", fontsize=11, color=hk.INK)
            if j == 0:
                ax.set_ylabel("sagittal angular velocity (deg/s)")
            if i == 2:
                ax.set_xlabel("time from first steady stride (s)")
    fig.suptitle(f"{title}\nAngular velocity, first 6 s of steady walking (first trial of each group) vs. Baseline",
                 x=0.01, ha="left", fontsize=12)
    fig.legend(handles=handles(res, col), loc="outside upper right", ncol=3)
    fig.savefig(out, dpi=170)
    plt.close(fig)


def fig_profiles(res, col, key, ylabel, title, out):
    prof = res["prof"]
    fig, axs = plt.subplots(3, 2, figsize=(12, 8.5), sharey="row", sharex=True, constrained_layout=True)
    x = np.linspace(0, 100, NPTS)
    for i, (sg, sgn) in enumerate(SEGS):
        for j, (sd, sdn) in enumerate(SIDES):
            ax = axs[i, j]
            s = f"{sg} {sd}"
            ax.axhline(0, color=BASE_COL, lw=1.6, ls=(0, (4, 3)), zorder=1)
            for g in res["groups"]:
                p = prof[(g, s)][key]
                if len(p) == 0:
                    continue
                m, sd_ = p.mean(0), p.std(0)
                ax.fill_between(x, m - sd_, m + sd_, color=col[g], alpha=0.18, lw=0)
                ax.plot(x, m, color=col[g], lw=2, zorder=3)
            ax.set_title(f"{sgn} - {sdn}", loc="left", fontsize=11, color=hk.INK)
            if j == 0:
                ax.set_ylabel(ylabel)
            if i == 2:
                ax.set_xlabel("stride cycle (%), 0 = shank mid-swing peak")
            ax.set_xlim(0, 100)
    n_str = ", ".join(f"{g} {len(prof[(g, 'Tibiale Sx')]['T'])}L/{len(prof[(g, 'Tibiale Dx')]['T'])}R"
                      for g in res["groups"])
    fig.suptitle(f"{title}\nmean +/- SD; strides {n_str}", x=0.01, ha="left", fontsize=12)
    fig.legend(handles=handles(res, col), loc="outside upper right", ncol=3)
    fig.savefig(out, dpi=170)
    plt.close(fig)


def fig_summary(res, col, title, out):
    prof, groups = res["prof"], res["groups"]
    conds = ["Baseline"] + groups
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.6), constrained_layout=True)
    width = 0.8 / len(conds)

    def grouped(ax, glist, value, ylabel, ttl):
        for gi, g in enumerate(glist):
            for ci, c in enumerate(conds):
                vals = value(c, g)
                if len(vals) == 0:
                    continue
                xpos = gi + (ci - (len(conds) - 1) / 2) * (width + 0.02)
                ax.bar(xpos, np.mean(vals), width, color=col[c], zorder=2)
                if c == "Baseline":
                    ax.text(xpos, np.mean(vals), f"{np.mean(vals):.1f}", ha="center", va="bottom",
                            fontsize=8, color=INK2)
                elif len(vals) > 1:
                    ax.plot([xpos] * len(vals), vals, "o", ms=3.5, mfc="none", mec=hk.INK, mew=0.8, zorder=3)
        ax.set_xticks(range(len(glist)))
        ax.set_xticklabels([g[1] if isinstance(g, tuple) else g for g in glist])
        ax.set_ylabel(ylabel)
        ax.set_title(ttl, loc="left", fontsize=11, color=hk.INK)
        ax.grid(axis="x", visible=False)

    def per_trial(c, s, fn):
        p = prof[(c, s)]
        return [fn(p, t) for t in np.unique(p["trial"])]

    def stride_t(c, g):
        if c == "Baseline":
            return []
        return per_trial(c, f"Tibiale {g[0]}", lambda p, t: p["T"][p["trial"] == t].mean())

    def rom(c, g):
        if c == "Baseline":
            return [np.ptp(res["ang"][(res["base"], f"{g[0]} {sd}")]) for sd, _ in SIDES]
        return [v for sd, _ in SIDES
                for v in per_trial(c, f"{g[0]} {sd}", lambda p, t: np.ptp(p["ang"][p["trial"] == t], axis=1).mean())]

    def peak(c, g):
        if c == "Baseline":
            return [np.max(np.abs(res["w"][(res["base"], f"{g[0]} {sd}")])) for sd, _ in SIDES]
        return [v for sd, _ in SIDES
                for v in per_trial(c, f"{g[0]} {sd}", lambda p, t: np.abs(p["w"][p["trial"] == t]).max(axis=1).mean())]

    grouped(axs[0], SIDES, stride_t, "stride time (s)", "Stride time (circles = trials)")
    grouped(axs[1], SEGS, rom, "range of motion (deg)", "Segment angle range per stride")
    grouped(axs[2], SEGS, peak, "peak |angular velocity| (deg/s)", "Peak angular velocity per stride")
    fig.suptitle(f"{title}\nbars = mean over trials (and legs); circles = each trial (and leg)", x=0.01, ha="left",
                 fontsize=12)
    fig.legend(handles=handles(res, col), loc="outside upper right", ncol=3)
    fig.savefig(out, dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--ref-dir", default=REF, help="healthy control folder (Baseline_1.csv, Slow_1.csv, ...)")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    ref_axis = None
    if os.path.isdir(a.ref_dir):
        ref = {n: hk.load_imu(os.path.join(a.ref_dir, f"{n}_1.csv"), set(SENSORS)) for n in hk.CONDS}
        ref_axis = hk.analyse(ref)["axis"]
    else:
        print("no reference session found; axis signs from the skew/correlation rules")

    for folder in sorted(glob.glob(os.path.join(a.data, "Exp*"))):
        name = os.path.basename(folder)
        out = os.path.join(a.out, name)
        os.makedirs(out, exist_ok=True)
        res = analyse_patient(folder, ref_axis)
        col = colors(res)
        print(f"\n{name}: groups {res['groups']}, axis sign from {sorted(set(res['signs'].values()))}")
        for g in res["groups"]:
            for sd, _ in SIDES:
                T = res["prof"][(g, f"Tibiale {sd}")]["T"]
                if len(T):
                    print(f"  {g:15s} {sd}: {len(T):3d} strides, stride time {T.mean():.2f} +/- {T.std():.2f} s")
                else:
                    print(f"  {g:15s} {sd}: no strides detected")
        title = f"Patient {name}"
        fig_timeseries(res, col, title, os.path.join(out, "kin_1_angular_velocity_timeseries.png"))
        fig_profiles(res, col, "w", "sagittal angular velocity (deg/s)",
                     f"{title} - angular velocity over the stride cycle",
                     os.path.join(out, "kin_2_angular_velocity_stride.png"))
        fig_profiles(res, col, "ang", "angle about stride mean (deg)",
                     f"{title} - segment angle over the stride cycle",
                     os.path.join(out, "kin_3_segment_angle_stride.png"))
        fig_summary(res, col, f"{title} - speed/ROM summary", os.path.join(out, "kin_4_summary.png"))
    print("\nwrote figures to", a.out)


if __name__ == "__main__":
    main()
