#!/usr/bin/env python3
"""
cpg_human_gait_metrics.py
Gait metrics from human recordings and from model HDF5, in one format (PLAN.md Phase 8).

Human data: Delsys Trigno exports, one folder per subject (Ctr01, Ctr02 in
results/human_data/2026-09-28/), files {Baseline,Slow,Medium,Fast}_{1,2,3}.csv.
  Sensors: foot / shank / thigh / pelvis IMUs (370 Hz), and 8 EMG+IMU sensors (EMG 1259 Hz):
  tibialis anterior (TA), gastrocnemius (GA), biceps femoris short head, vastus, L and R.
  No soleus, no force plates, no walking speed: speed is the label Slow/Medium/Fast only.
  Baseline = quiet standing (EMG noise floor, not used for gait metrics).

Events (foot gyro, sagittal axis = the one with the large swing burst; no force plate, so
stance and double support are IMU estimates, uncertainty ~ +-30-50 ms):
  TO  zero crossing after the sharp positive foot-gyro peak (push-off -> swing); it lines up
      with the foot-accelerometer toe-off spike to ~10 ms
  HS  first heel-impact spike of the foot accelerometer (|acc|, 15 Hz high-pass, > 40 % of
      the window maximum) in the 0.25 s around the gyro swing lobe returning through -25 %
      of its minimum. The gyro alone puts HS ~40 ms early, which lengthens stance by ~3 %.
Cycle = HS to next HS of the same foot (0 % = heel strike). First/last stride of each
walking bout and strides >25 % off the median stride time are dropped.

Metrics (per subject x speed; medians over strides, both legs pooled unless noted):
  stride_s       HS-to-HS time
  stance_frac    (TO - HS) / stride
  ds_frac        double support / stride, from both feet (initial + terminal)
  lr_phase_pct   contralateral HS as % of the ipsilateral stride (50 = perfect alternation)
  EMG TA, GA     envelope (20-450 Hz band-pass, rectify, 6 Hz low-pass), ensemble mean over
                 strides: peak_pct, active_frac, and the dominant burst onset/offset/duration
                 (% cycle; burst = envelope above 25 % of its own peak)
  coact_TA_GA    Falconer-Winter co-activation index of the TA and GA ensemble envelopes (%)

Model (--model h5 files, mode from the file name slow / comfortable / fast): the same
metrics from the left leg, with cut_on as stance, touch-downs (0 -> 1) as HS, and the
motor-pool activations act_f -> TA (flexor) and act_e -> GA (extensor) as the EMG proxy.
The first --from-ms is skipped (settling).

Comparison: model value vs. the range of the subject medians ("range", the P8 acceptance
criterion; with 2 subjects this is narrow) and vs. that range widened by the within-subject
stride SD ("band"; +-5 % cycle for the cyclic burst on/off/peak metrics, which are compared
modulo 100). Status: IN range / band / OUT.

Usage:
  python3 scripts/cpg_human_gait_metrics.py                       # human reference only
  python3 scripts/cpg_human_gait_metrics.py --model results/human_modes/<tag>/*.h5
Output: validation/human_gait_reference.json (human) + plots/human_gait/*.png
"""
import argparse
import glob
import io
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
DATA = os.path.join(ROOT, "results", "human_data", "2026-09-28")

SPEEDS = ["Slow", "Medium", "Fast"]
MODE_OF = {"slow": "Slow", "comfortable": "Medium", "fast": "Fast"}
MUSCLES = {"TA": "Tibiale Ant", "GA": "Gastro"}      # TA <-> model flexor, GA <-> model extensor
SIDES = ["Sx", "Dx"]                                  # left, right
NPTS = 101
BURST_FRAC = 0.25

COL = {"Slow": "#2a78d6", "Medium": "#eb6834", "Fast": "#1baf7a"}
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
def load_trigno(path):
    """{sensor: {channel: (t_s, values)}}; ';' separated, decimal comma, one block per sensor."""
    lines = open(path).read().replace(",", ".").split("\n")
    names = [c.strip() for c in lines[3].split(";")]
    hdr = [c.strip() for c in lines[5].split(";")]
    arr = np.genfromtxt(io.StringIO("\n".join(lines[8:])), delimiter=";")
    starts = [(j, re.sub(r"\s*\(\d+\)", "", c)) for j, c in enumerate(names) if c]
    out = {}
    for k, (j, name) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(hdr)
        ch = {}
        for c in range(j, end, 2):
            t, v = arr[:, c], arr[:, c + 1]
            ok = ~np.isnan(t) & ~np.isnan(v)
            ch[hdr[c + 1]] = (t[ok], v[ok])
        out[name] = ch
    return out


def lowpass(x, fs, fc, order=2):
    b, a = butter(order, fc / (fs / 2))
    return filtfilt(b, a, x)


def fs_of(t):
    return 1.0 / np.median(np.diff(t))


# ---------------------------------------------------------------- gait events (foot gyro)
def foot_events(t, gz, acc):
    """Heel strikes and toe-offs (s) of one foot from the sagittal foot gyro and the foot |acc|."""
    fs = fs_of(t)
    w = lowpass(gz, fs, 25)
    hp = np.abs(filtfilt(*butter(2, 15 / (fs / 2), "high"), acc))
    if abs(np.percentile(w, 0.5)) > np.percentile(w, 99.5):      # sharp peak positive
        w = -w
    top = np.percentile(w, 99.5)
    pk, _ = find_peaks(w, height=0.6 * top, distance=int(0.5 * fs))
    to, hs = [], []
    for i, p in enumerate(pk):
        z = np.where(w[p:] < 0)[0]
        if z.size == 0:
            continue
        i_to = p + z[0]
        lim = pk[i + 1] if i + 1 < len(pk) else min(len(w), p + int(0.9 * fs))
        if lim - i_to < int(0.15 * fs):
            continue
        i_min = i_to + np.argmin(w[i_to:lim])
        if w[i_min] > -0.2 * top:                                # no swing lobe: not a stride
            continue
        r = np.where(w[i_min:lim] > 0.25 * w[i_min])[0]
        if r.size == 0:
            continue
        i_x = i_min + r[0]
        lo, hi = max(i_x - int(0.1 * fs), i_min), min(i_x + int(0.15 * fs), len(w))
        spk = np.where(hp[lo:hi] > 0.4 * hp[lo:hi].max())[0]
        to.append(t[i_to])
        hs.append(t[lo + spk[0]])
    return np.array(hs), np.array(to)


def strides_of(hs, to, other_hs, other_to):
    """Stride list for one foot: HS-to-HS cycles with TO between them, DS and L/R phase."""
    out = []
    # (to[k], hs[k]) are the start and end of swing k, so stance of a stride is hs[i] -> to[i+1].
    for i in range(len(hs) - 1):
        a, b = hs[i], hs[i + 1]
        tos = to[(to > a) & (to < b)]
        if tos.size != 1:
            continue
        T = b - a
        t_o = tos[0]
        # initial DS: HS_a to the first contralateral TO after it
        c_to = other_to[(other_to > a) & (other_to < t_o)]
        c_hs = other_hs[(other_hs > a) & (other_hs < b)]
        if c_to.size < 1 or c_hs.size < 1:
            continue
        ds_i = c_to[0] - a
        # terminal DS: last contralateral HS before this foot's TO
        c_hs_pre = c_hs[c_hs < t_o]
        if c_hs_pre.size < 1:
            continue
        ds_t = t_o - c_hs_pre[-1]
        out.append(dict(a=a, b=b, T=T, stance=(t_o - a) / T, ds=(ds_i + ds_t) / T,
                        lr=100.0 * (c_hs[0] - a) / T))
    return out


def clean(strs, bouts_gap=1.6):
    """Drop first/last stride of every bout and strides >25 % off the median stride time."""
    if not strs:
        return []
    med = np.median([s["T"] for s in strs])
    keep, run = [], [strs[0]]
    for s in strs[1:]:
        if s["a"] - run[-1]["b"] > 0.05 * med:                   # gap: new bout
            keep += run[1:-1]
            run = [s]
        else:
            run.append(s)
    keep += run[1:-1]
    return [s for s in keep if abs(s["T"] - med) < 0.25 * med]


# ---------------------------------------------------------------- EMG envelope and burst metrics
def emg_envelope(t, v):
    fs = fs_of(t)
    b, a = butter(2, [20 / (fs / 2), 450 / (fs / 2)], "band")
    x = np.abs(filtfilt(b, a, v - np.median(v)))
    return np.maximum(lowpass(x, fs, 6), 0.0)


def cycle_profile(t, x, strs):
    """(n_strides, NPTS) of x over each HS-to-HS cycle."""
    return np.array([np.interp(np.linspace(s["a"], s["b"], NPTS), t, x) for s in strs])


def bursts(m):
    """Dominant burst of an ensemble envelope m (NPTS, cyclic): onset/offset/duration in % cycle."""
    n = NPTS - 1
    m = m[:n]
    peak = m.max()
    if peak <= 0:
        return dict(onset_pct=np.nan, offset_pct=np.nan, dur_pct=np.nan, n_bursts=0)
    act = m >= BURST_FRAC * peak
    r = int(np.argmin(m))                                        # rotate so the cycle starts quiet
    ar = np.roll(act, -r)
    edges = np.diff(np.concatenate([[0], ar.astype(int), [0]]))
    on, off = np.where(edges == 1)[0], np.where(edges == -1)[0]
    if on.size == 0:
        return dict(onset_pct=np.nan, offset_pct=np.nan, dur_pct=np.nan, n_bursts=0)
    mr = np.roll(m, -r)
    area = [mr[a:b].sum() for a, b in zip(on, off)]
    k = int(np.argmax(area))
    return dict(onset_pct=float((on[k] + r) % n), offset_pct=float((off[k] + r) % n),
                dur_pct=float(off[k] - on[k]), n_bursts=int(on.size))


def coactivation(a, b):
    """Falconer-Winter co-activation index (%) of two normalised envelopes."""
    a, b = a / max(a.max(), 1e-12), b / max(b.max(), 1e-12)
    return float(100.0 * 2 * np.minimum(a, b).sum() / max((a + b).sum(), 1e-12))


def env_metrics(prof_by_muscle):
    """Ensemble-mean envelope metrics from {name: (n, NPTS)} profiles."""
    out, ens = {}, {}
    for k, p in prof_by_muscle.items():
        m = p.mean(0)
        ens[k] = m
        b = bursts(m)
        out[f"{k}_peak_pct"] = float(np.argmax(m[:NPTS - 1]))
        out[f"{k}_active_frac"] = float((m[:NPTS - 1] >= BURST_FRAC * m.max()).mean())
        out.update({f"{k}_{kk}": v for kk, v in b.items()})
    if "TA" in ens and "GA" in ens:
        out["coact_TA_GA"] = coactivation(ens["TA"], ens["GA"])
    return out, ens


# ---------------------------------------------------------------- human reference
def analyse_file(path):
    """Strides (both legs) and per-muscle cycle profiles of one walking trial."""
    d = load_trigno(path)
    ev = {}
    for sd in SIDES:
        t, gz = d[f"Piede {sd}"]["GYRO Z (deg/s)"]
        acc = np.linalg.norm(np.c_[[d[f"Piede {sd}"][f"ACC {c} (G)"][1] for c in "XYZ"]].T, axis=1)
        ev[sd] = foot_events(t, gz, acc)
    strs = {sd: clean(strides_of(*ev[sd], *ev["Dx" if sd == "Sx" else "Sx"])) for sd in SIDES}
    prof = {m: [] for m in MUSCLES}
    for sd in SIDES:
        for m, nm in MUSCLES.items():
            t, v = d[f"{nm} {sd}"]["EMG 1 (mV)"]
            if strs[sd]:
                prof[m].append(cycle_profile(t, emg_envelope(t, v), strs[sd]))
    return strs, {m: (np.vstack(p) if p else np.empty((0, NPTS))) for m, p in prof.items()}, ev


def human_reference(data_dir):
    """{subject: {speed: dict(metrics.., n_strides, sd_.., ens)}} for every Ctr* folder."""
    ref = {}
    for sdir in sorted(glob.glob(os.path.join(data_dir, "Ctr*"))):
        subj = os.path.basename(sdir)
        ref[subj] = {}
        for sp in SPEEDS:
            strs_all, prof = [], {m: [] for m in MUSCLES}
            for f in sorted(glob.glob(os.path.join(sdir, f"{sp}_*.csv"))):
                strs, pr, _ = analyse_file(f)
                strs_all += strs["Sx"] + strs["Dx"]
                for m in MUSCLES:
                    if pr[m].size:
                        prof[m].append(pr[m])
            if not strs_all:
                continue
            row = {"n_strides": len(strs_all)}
            for k in ("T", "stance", "ds", "lr"):
                v = np.array([s[k] for s in strs_all])
                name = {"T": "stride_s", "stance": "stance_frac", "ds": "ds_frac", "lr": "lr_phase_pct"}[k]
                row[name] = float(np.median(v))
                row[f"sd_{name}"] = float(v.std())
            em, ens = env_metrics({m: np.vstack(p) for m, p in prof.items() if p})
            row.update(em)
            row["ens"] = {m: ens[m].tolist() for m in ens}
            ref[subj][sp] = row
    return ref


# ---------------------------------------------------------------- model metrics
def model_metrics(path, from_ms):
    import h5py
    with h5py.File(path, "r") as f:
        t = f["times_ms"][()] / 1000.0
        L = {k: f[f"leg_L/{k}"][()] for k in ("cut_on", "act_e", "act_f")}
        R = {k: f[f"leg_R/{k}"][()] for k in ("cut_on",)}
    keep = t > from_ms / 1000.0
    t = t[keep]
    on_l, on_r = L["cut_on"][keep] > 0.5, R["cut_on"][keep] > 0.5
    td = lambda on: t[1:][np.diff(on.astype(int)) == 1]
    lo = lambda on: t[1:][np.diff(on.astype(int)) == -1]
    hs_l, to_l, hs_r, to_r = td(on_l), lo(on_l), td(on_r), lo(on_r)
    strs = clean(strides_of(hs_l, to_l, hs_r, to_r))
    if not strs:
        return None
    row = {"n_strides": len(strs)}
    for k, name in (("T", "stride_s"), ("stance", "stance_frac"), ("ds", "ds_frac"), ("lr", "lr_phase_pct")):
        v = np.array([s[k] for s in strs])
        row[name] = float(np.median(v))
        row[f"sd_{name}"] = float(v.std())
    prof = {"TA": cycle_profile(t, L["act_f"][keep], strs), "GA": cycle_profile(t, L["act_e"][keep], strs)}
    em, ens = env_metrics(prof)
    row.update(em)
    row["ens"] = {m: ens[m].tolist() for m in ens}
    return row


# ---------------------------------------------------------------- comparison
METRICS = ["stride_s", "stance_frac", "ds_frac", "lr_phase_pct",
           "GA_onset_pct", "GA_offset_pct", "GA_peak_pct", "TA_onset_pct", "TA_offset_pct",
           "TA_peak_pct", "coact_TA_GA"]


CIRC = {m for m in METRICS if m.endswith("_pct") and m != "lr_phase_pct"}   # % of a cyclic gait cycle
CIRC_TOL = 5.0                                                                # band for cyclic metrics, % cycle


def arc(vals):
    """Shortest arc (start, length) in % cycle covering the values (cyclic, period 100)."""
    v = sorted(x % 100.0 for x in vals)
    gaps = [((v[(i + 1) % len(v)] - v[i]) % 100.0 or 100.0, i) for i in range(len(v))]
    g, i = max(gaps)                                    # largest gap lies outside the arc
    return v[(i + 1) % len(v)], 100.0 - g if len(v) > 1 else 0.0


def human_range(ref, sp, metric):
    """(lo, hi, band_lo, band_hi) of the subject medians; the band adds the within-subject stride
    SD (cyclic burst metrics: +-CIRC_TOL % cycle). Cyclic metrics: lo/hi are arc start/end mod 100."""
    vals = [(r[sp][metric], r[sp].get(f"sd_{metric}", 0.0)) for r in ref.values() if sp in r and metric in r[sp]]
    if not vals:
        return None
    m = [v for v, _ in vals]
    if metric in CIRC:
        st, ln = arc(m)
        return st, (st + ln) % 100.0, (st - CIRC_TOL) % 100.0, (st + ln + CIRC_TOL) % 100.0
    sd = max(s for _, s in vals)
    return min(m), max(m), min(m) - sd, max(m) + sd


def inside(v, lo, hi, cyc):
    if not cyc:
        return lo <= v <= hi
    return (v - lo) % 100.0 <= (hi - lo) % 100.0


def compare(ref, model_rows):
    lines = [f"{'mode':12s} {'metric':14s} {'model':>8s}  {'human range':>17s}  {'band (+-SD)':>17s}  status"]
    for mode, row in model_rows:
        sp = MODE_OF.get(mode)
        if sp is None:
            continue
        for k in METRICS:
            hr = human_range(ref, sp, k)
            if hr is None or k not in row or not np.isfinite(row[k]):
                continue
            v, cyc = row[k], k in CIRC
            st = "IN range" if inside(v, hr[0], hr[1], cyc) else "IN band" if inside(v, hr[2], hr[3], cyc) else "OUT"
            lines.append(f"{mode:12s} {k:14s} {v:8.3f}  {hr[0]:7.3f}..{hr[1]:7.3f}  {hr[2]:7.3f}..{hr[3]:7.3f}  {st}")
    return "\n".join(lines)


# ---------------------------------------------------------------- figures
def fig_envelopes(ref, model_rows, out):
    x = np.linspace(0, 100, NPTS)
    fig, axs = plt.subplots(2, 3, figsize=(13, 6.5), sharex=True, sharey=True, constrained_layout=True)
    mrow = {MODE_OF[m]: r for m, r in model_rows if m in MODE_OF}
    for j, sp in enumerate(SPEEDS):
        for i, mu in enumerate(("TA", "GA")):
            ax = axs[i, j]
            for si, (subj, r) in enumerate(ref.items()):
                if sp in r and mu in r[sp]["ens"]:
                    m = np.array(r[sp]["ens"][mu])
                    ax.plot(x, m / m.max(), color=COL[sp], lw=2, ls="-" if si == 0 else (0, (5, 2)),
                            label=subj)
            if sp in mrow:
                m = np.array(mrow[sp]["ens"][mu])
                ax.plot(x, m / max(m.max(), 1e-12), color=INK, lw=1.6, label="model")
            ax.axhline(BURST_FRAC, color=GRID, lw=1)
            ax.set_xlim(0, 100)
            if j == 0:
                ax.set_ylabel(f"{mu} envelope (norm.)" + ("\n(model: flexor act_f)" if mu == "TA" else "\n(model: extensor act_e)"))
            if i == 0:
                ax.set_title(sp, loc="left", fontsize=11, color=INK)
            if i == 1:
                ax.set_xlabel("gait cycle (%), 0 = heel strike")
    axs[0, 0].legend(loc="upper right", fontsize=8)
    fig.suptitle("EMG envelope over the gait cycle (ensemble mean, both legs); thin line = 25 % burst threshold",
                 x=0.01, ha="left", fontsize=12)
    fig.savefig(out, dpi=170)
    plt.close(fig)


def fig_timing(ref, model_rows, out):
    keys = [("stride_s", "stride time (s)"), ("stance_frac", "stance fraction"),
            ("ds_frac", "double support fraction"), ("lr_phase_pct", "L/R phase (%)")]
    fig, axs = plt.subplots(1, 4, figsize=(14, 3.8), constrained_layout=True)
    mrow = {MODE_OF[m]: r for m, r in model_rows if m in MODE_OF}
    for ax, (k, lab) in zip(axs, keys):
        for j, sp in enumerate(SPEEDS):
            for si, (subj, r) in enumerate(ref.items()):
                if sp in r:
                    ax.errorbar(j + (si - 0.5) * 0.12, r[sp][k], yerr=r[sp][f"sd_{k}"], fmt="o", color=COL[sp],
                                mfc=COL[sp] if si == 0 else "none", capsize=3)
            if sp in mrow:
                ax.plot(j + 0.3, mrow[sp][k], "s", color=INK, ms=7)
        ax.set_xticks(range(3))
        ax.set_xticklabels(SPEEDS)
        ax.set_title(lab, loc="left", fontsize=11, color=INK)
        ax.grid(axis="x", visible=False)
    fig.suptitle("Gait timing: human subjects (circles, filled = Ctr01; median +- SD over strides), model (squares)",
                 x=0.01, ha="left", fontsize=12)
    fig.savefig(out, dpi=170)
    plt.close(fig)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--model", nargs="*", default=[], help="model HDF5 files (slow/comfortable/fast in the name)")
    ap.add_argument("--from-ms", type=float, default=10000.0)
    ap.add_argument("--out", default=os.path.join(ROOT, "plots", "human_gait"))
    ap.add_argument("--json", default=os.path.join(ROOT, "validation", "human_gait_reference.json"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    ref = human_reference(a.data)
    print("human reference (median over strides, both legs):")
    print(f"{'subject':7s} {'speed':7s} {'n':>3s} {'stride_s':>8s} {'stance':>7s} {'DS':>6s} {'LRphase':>8s} "
          f"{'GA on-off':>10s} {'TA on-off':>10s} {'coact':>6s}")
    for subj, r in ref.items():
        for sp in SPEEDS:
            if sp not in r:
                continue
            x = r[sp]
            print(f"{subj:7s} {sp:7s} {x['n_strides']:3d} {x['stride_s']:8.3f} {x['stance_frac']:7.3f} "
                  f"{x['ds_frac']:6.3f} {x['lr_phase_pct']:8.1f} "
                  f"{x['GA_onset_pct']:4.0f}-{x['GA_offset_pct']:<4.0f}  {x['TA_onset_pct']:4.0f}-{x['TA_offset_pct']:<4.0f}  "
                  f"{x['coact_TA_GA']:6.1f}")
    os.makedirs(os.path.dirname(a.json), exist_ok=True)
    with open(a.json, "w") as f:
        json.dump(ref, f, indent=1)
    print("wrote", a.json)

    model_rows = []
    for p in sorted(sum((glob.glob(g) for g in a.model), [])):
        mode = os.path.splitext(os.path.basename(p))[0]
        m = model_metrics(p, a.from_ms)
        if m is None:
            print(f"{p}: no complete strides after {a.from_ms:.0f} ms (needs cut_on)")
            continue
        model_rows.append((mode, m))
    if model_rows:
        print()
        print(compare(ref, model_rows))
    fig_envelopes(ref, model_rows, os.path.join(a.out, "human_gait_emg_envelopes.png"))
    fig_timing(ref, model_rows, os.path.join(a.out, "human_gait_timing.png"))
    print("wrote figures to", a.out)


if __name__ == "__main__":
    main()
