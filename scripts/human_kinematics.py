#!/usr/bin/env python3
"""
human_kinematics.py
Kinematics figures from the Delsys Trigno IMU exports in results/human_data/
(Baseline_1, Slow_1, Medium_1, Fast_1 .csv), with the Baseline file as the reference.

Baseline is quiet standing, so it is used as
  * gyro bias calibration: the standing gyro median of each sensor is subtracted
    from that sensor's walking data;
  * the zero / noise-floor reference drawn in every figure (angular velocity 0,
    segment angle 0, ROM ~ 0).

Segments (370 Hz IMUs): thigh = Femore, shank = Tibiale, foot = Piede, Sx = left,
Dx = right.  Sensor mounting differs between segments, so the sagittal axis of each
segment is the principal axis (PCA) of its gyro vector over the three walking files.
Axis SIGN is not known from mounting; it is fixed from the data:
  shank  : skew of the angular velocity positive (fast forward swing = positive peak)
  thigh, foot : positive correlation with the same-leg shank (thigh at its best lag)
so positive angular velocity = segment rotating forward (flexion-ward) for all three.
Stride cycles start at the shank mid-swing peak (0 %), not at heel strike.

Segment angle = integral of the sagittal angular velocity (0.3 Hz high-pass before and
after), minus the stride mean.  It is a relative angle: no absolute posture.

Usage: python3 scripts/human_kinematics.py [--data DIR] [--out DIR]
"""
import argparse
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks
from scipy.stats import skew

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "results", "human_data")

CONDS = ["Baseline", "Slow", "Medium", "Fast"]
WALK = CONDS[1:]
SEGS = [("Femore", "Thigh"), ("Tibiale", "Shank"), ("Piede", "Foot")]
SIDES = [("Sx", "Left"), ("Dx", "Right")]
NPTS = 101

# Reference palette (categorical slots 1-3 validate all-pairs) + neutral for Baseline.
COL = {"Baseline": "#8a8985", "Slow": "#2a78d6", "Medium": "#eb6834", "Fast": "#1baf7a"}
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "savefig.facecolor": "#fcfcfb", "legend.frameon": False,
})


# ---------------------------------------------------------------- loading
def load_imu(path, segments):
    """Return {sensor: {'t': s, 'gyro': (N,3) deg/s, 'acc': (N,3) G}} for `segments`."""
    lines = open(path).read().split("\n")
    names = [c.strip() for c in lines[3].split(";")]
    hdr = [c.strip() for c in lines[5].split(";")]
    starts = [(j, re.sub(r"\s*\(\d+\)", "", c)) for j, c in enumerate(names) if c]
    rows = [[float(x.replace(",", ".")) if x.strip() else np.nan for x in ln.split(";")]
            for ln in lines[8:] if ln.strip()]
    width = max(max(len(r) for r in rows), len(hdr))
    arr = np.full((len(rows), width), np.nan)
    for i, r in enumerate(rows):
        arr[i, :len(r)] = r
    out = {}
    for k, (j, name) in enumerate(starts):
        if name not in segments:
            continue
        end = starts[k + 1][0] if k + 1 < len(starts) else len(hdr)
        ch = {}
        for c in range(j, end, 2):
            v = arr[:, c + 1]
            t = arr[:, c]
            ok = ~np.isnan(v) & ~np.isnan(t)
            ch[hdr[c + 1]] = (t[ok], v[ok])
        t = ch["GYRO X (deg/s)"][0]
        out[name] = {
            "t": t,
            "gyro": np.c_[[ch[f"GYRO {a} (deg/s)"][1] for a in "XYZ"]].T,
            "acc": np.c_[[ch[f"ACC {a} (G)"][1] for a in "XYZ"]].T,
        }
    return out


# ---------------------------------------------------------------- processing
def active_window(gyro, fs):
    b, a = butter(2, 10 / (fs / 2))
    act = np.linalg.norm(filtfilt(b, a, gyro, axis=0), axis=1)
    sm = np.convolve(act, np.ones(int(fs)) / int(fs), "same")
    idx = np.where(sm > 15)[0]
    return idx[0], idx[-1]


def highpass(x, fs, fc=0.3):
    b, a = butter(2, fc / (fs / 2), "high")
    return filtfilt(b, a, x)


def lowpass(x, fs, fc=20):
    b, a = butter(2, fc / (fs / 2))
    return filtfilt(b, a, x)


def integrate(w, fs):
    """Angle (deg) from angular velocity (deg/s): HP -> cumulative sum -> HP."""
    return highpass(np.cumsum(highpass(w, fs)) / fs, fs)


def lagged_corr(x, y, fs, maxlag=0.4):
    """Sign and lag (s) of the peak |cross-correlation| between x and y."""
    n = int(maxlag * fs)
    best = (0.0, 0.0)
    for l in range(-n, n + 1, 3):
        c = np.corrcoef(x[n + l:len(x) - n + l], y[n:len(y) - n])[0, 1]
        if abs(c) > abs(best[0]):
            best = (c, l / fs)
    return best


def analyse(data):
    d = data
    sensors = [f"{sg} {sd}" for sd, _ in SIDES for sg, _ in SEGS]
    fs = {n: 1.0 / np.median(np.diff(d["Baseline"][sensors[0]]["t"])) for n in CONDS}
    fs = fs["Baseline"]

    # gyro bias from Baseline (standing)
    bias = {s: np.median(d["Baseline"][s]["gyro"], axis=0) for s in sensors}
    gyro = {(n, s): d[n][s]["gyro"] - bias[s] for n in CONDS for s in sensors}

    # walking window per condition and side (from the shank)
    win = {}
    for n in WALK:
        for sd, _ in SIDES:
            win[(n, sd)] = active_window(gyro[(n, f"Tibiale {sd}")], fs)

    # sagittal axis per sensor: PCA over the walking files
    axis = {}
    for s in sensors:
        sd = s.split()[1]
        G = np.vstack([gyro[(n, s)][slice(*win[(n, sd)])] for n in WALK])
        _, _, vt = np.linalg.svd(G - G.mean(0), full_matrices=False)
        axis[s] = vt[0]
    # sign: shank by skew, thigh/foot by correlation with same-leg shank
    for sd, _ in SIDES:
        sh = f"Tibiale {sd}"
        w_sh = np.concatenate([gyro[(n, sh)][slice(*win[(n, sd)])] @ axis[sh] for n in WALK])
        if skew(w_sh) < 0:
            axis[sh] = -axis[sh]
        for sg in ("Femore", "Piede"):
            s = f"{sg} {sd}"
            c = []
            for n in WALK:
                lo, hi = win[(n, sd)]
                c.append(lagged_corr(gyro[(n, s)][lo:hi] @ axis[s], gyro[(n, sh)][lo:hi] @ axis[sh], fs)[0])
            if np.mean(c) < 0:
                axis[s] = -axis[s]

    # sagittal angular velocity, angle, per condition
    w, ang = {}, {}
    for n in CONDS:
        for s in sensors:
            wn = lowpass(gyro[(n, s)] @ axis[s], fs)
            w[(n, s)] = wn
            ang[(n, s)] = integrate(wn, fs)

    # strides from shank mid-swing peaks (steady part only)
    strides = {}
    for n in WALK:
        for sd, _ in SIDES:
            lo, hi = win[(n, sd)]
            ws = w[(n, f"Tibiale {sd}")]
            seg = ws[lo:hi]
            pk, _ = find_peaks(seg, height=0.35 * np.percentile(seg, 99.5), distance=int(0.5 * fs))
            pk = pk + lo
            dur = np.diff(pk) / fs
            keep = np.abs(dur - np.median(dur)) < 0.25 * np.median(dur)
            pairs = [(pk[i], pk[i + 1]) for i in range(len(dur)) if keep[i]]
            pairs = pairs[1:-1] if len(pairs) > 4 else pairs      # drop initiation / termination
            strides[(n, sd)] = pairs

    return dict(fs=fs, w=w, ang=ang, strides=strides, win=win, axis=axis, sensors=sensors)


def cycle(x, a, b):
    return np.interp(np.linspace(a, b, NPTS), np.arange(len(x)), x)


def profiles(res):
    """{(cond, sensor): dict(w=(n,101), ang=(n,101), T=stride times)}"""
    out = {}
    for n in WALK:
        for s in res["sensors"]:
            sd = s.split()[1]
            W, A, T = [], [], []
            for a, b in res["strides"][(n, sd)]:
                W.append(cycle(res["w"][(n, s)], a, b))
                x = cycle(res["ang"][(n, s)], a, b)
                A.append(x - x.mean())
                T.append((b - a) / res["fs"])
            out[(n, s)] = dict(w=np.array(W), ang=np.array(A), T=np.array(T))
    return out


# ---------------------------------------------------------------- plotting
def legend_handles():
    return [plt.Line2D([], [], color=COL[c], lw=2, label=c if c != "Baseline" else "Baseline (standing)")
            for c in CONDS]


def fig_timeseries(res, out):
    fs = res["fs"]
    fig, axs = plt.subplots(3, 2, figsize=(12, 8.5), sharey="row", constrained_layout=True)
    for i, (sg, sgn) in enumerate(SEGS):
        for j, (sd, sdn) in enumerate(SIDES):
            ax = axs[i, j]
            s = f"{sg} {sd}"
            for n in CONDS:
                x = res["w"][(n, s)]
                if n == "Baseline":
                    t0 = 0
                else:
                    a = res["strides"][(n, sd)][0][0]
                    t0 = a - int(0.3 * fs)
                seg = x[t0:t0 + int(6 * fs)]
                ax.plot(np.arange(len(seg)) / fs, seg, color=COL[n], lw=1.6 if n == "Baseline" else 1.1,
                        zorder=1 if n == "Baseline" else 2)
            ax.axhline(0, color=COL["Baseline"], lw=0.8, zorder=0)
            ax.set_title(f"{sgn} - {sdn}", loc="left", fontsize=11, color=INK)
            if j == 0:
                ax.set_ylabel("sagittal angular velocity (deg/s)")
            if i == 2:
                ax.set_xlabel("time from first steady stride (s)")
    fig.suptitle("Angular velocity, first 6 s of steady walking vs. Baseline standing", x=0.01, ha="left",
                 fontsize=12)
    fig.legend(handles=legend_handles(), loc="outside upper right", ncol=4)
    fig.savefig(out, dpi=170)
    plt.close(fig)


def fig_profiles(res, prof, key, ylabel, title, out):
    fig, axs = plt.subplots(3, 2, figsize=(12, 8.5), sharey="row", sharex=True, constrained_layout=True)
    x = np.linspace(0, 100, NPTS)
    for i, (sg, sgn) in enumerate(SEGS):
        for j, (sd, sdn) in enumerate(SIDES):
            ax = axs[i, j]
            s = f"{sg} {sd}"
            ax.axhline(0, color=COL["Baseline"], lw=1.6, ls=(0, (4, 3)), zorder=1)   # Baseline reference
            for n in WALK:
                p = prof[(n, s)][key]
                m, sd_ = p.mean(0), p.std(0)
                ax.fill_between(x, m - sd_, m + sd_, color=COL[n], alpha=0.18, lw=0)
                ax.plot(x, m, color=COL[n], lw=2, zorder=3)
            ax.set_title(f"{sgn} - {sdn}", loc="left", fontsize=11, color=INK)
            if j == 0:
                ax.set_ylabel(ylabel)
            if i == 2:
                ax.set_xlabel("stride cycle (%), 0 = shank mid-swing peak")
            ax.set_xlim(0, 100)
    n_str = ", ".join(f"{n} {len(prof[(n, 'Tibiale Sx')]['T'])}L/{len(prof[(n, 'Tibiale Dx')]['T'])}R"
                      for n in WALK)
    fig.suptitle(f"{title}\nmean +/- SD; strides {n_str}", x=0.01, ha="left", fontsize=12)
    fig.legend(handles=legend_handles(), loc="outside upper right", ncol=4)
    fig.savefig(out, dpi=170)
    plt.close(fig)


def fig_summary(res, prof, out):
    fs = res["fs"]
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.6), constrained_layout=True)

    def grouped(ax, groups, value, ylabel, title):
        width = 0.19
        for gi, g in enumerate(groups):
            for ci, n in enumerate(CONDS):
                vals = value(n, g)
                if len(vals) == 0:
                    continue
                xpos = gi + (ci - 1.5) * (width + 0.02)
                ax.bar(xpos, np.mean(vals), width, color=COL[n], zorder=2)
                if n == "Baseline":
                    ax.text(xpos, np.mean(vals), f"{np.mean(vals):.1f}", ha="center", va="bottom",
                            fontsize=8, color=INK2)
                if len(vals) > 1:
                    ax.plot([xpos] * len(vals), vals, "o", ms=4, mfc="none", mec=INK, mew=0.9, zorder=3)
        ax.set_xticks(range(len(groups)))
        ax.set_xticklabels([g[1] if isinstance(g, tuple) else g for g in groups])
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", fontsize=11, color=INK)

    # ROM and peak angular velocity: mean over strides, one dot per leg
    def rom(n, g):
        if n == "Baseline":
            return [np.ptp(res["ang"][(n, f"{g[0]} {sd}")]) for sd, _ in SIDES]
        return [np.mean(np.ptp(prof[(n, f"{g[0]} {sd}")]["ang"], axis=1)) for sd, _ in SIDES]

    def peak(n, g):
        if n == "Baseline":
            return [np.max(np.abs(res["w"][(n, f"{g[0]} {sd}")])) for sd, _ in SIDES]
        return [np.mean(np.max(np.abs(prof[(n, f"{g[0]} {sd}")]["w"]), axis=1)) for sd, _ in SIDES]

    def stride_t(n, g):
        if n == "Baseline":
            return []
        return [np.mean(prof[(n, f"Tibiale {g[0]}")]["T"])]

    grouped(axs[0], SIDES, stride_t, "stride time (s)", "Stride time (Baseline: standing, no strides)")
    grouped(axs[1], SEGS, rom, "range of motion (deg)", "Segment angle range per stride")
    grouped(axs[2], SEGS, peak, "peak |angular velocity| (deg/s)", "Peak angular velocity per stride")
    for ax in axs:
        ax.grid(axis="x", visible=False)
    fig.suptitle("Speed summary (bars = mean of left and right, circles = each leg)", x=0.01, ha="left", fontsize=12)
    fig.legend(handles=legend_handles(), loc="outside upper right", ncol=4)
    fig.savefig(out, dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "plots", "kinematics"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    segments = {f"{sg} {sd}" for sg, _ in SEGS for sd, _ in SIDES}
    data = {n: load_imu(os.path.join(a.data, f"{n}_1.csv"), segments) for n in CONDS}
    res = analyse(data)
    prof = profiles(res)

    print("sagittal axes (sensor frame):")
    for s, v in res["axis"].items():
        print(f"  {s:12s}", np.round(v, 2))
    for n in WALK:
        for sd, _ in SIDES:
            T = prof[(n, f"Tibiale {sd}")]["T"]
            print(f"{n:7s} {sd}: {len(T)} strides, stride time {T.mean():.2f} +/- {T.std():.2f} s")
    print(f"Baseline noise floor: shank |w| max {np.abs(res['w'][('Baseline', 'Tibiale Sx')]).max():.2f} deg/s")

    fig_timeseries(res, os.path.join(a.out, "kin_1_angular_velocity_timeseries.png"))
    fig_profiles(res, prof, "w", "sagittal angular velocity (deg/s)",
                 "Angular velocity over the stride cycle", os.path.join(a.out, "kin_2_angular_velocity_stride.png"))
    fig_profiles(res, prof, "ang", "angle about stride mean (deg)",
                 "Segment angle over the stride cycle", os.path.join(a.out, "kin_3_segment_angle_stride.png"))
    fig_summary(res, prof, os.path.join(a.out, "kin_4_summary.png"))
    print("wrote figures to", a.out)


if __name__ == "__main__":
    main()
