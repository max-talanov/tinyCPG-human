#!/usr/bin/env python3
"""
p4_muscle_afferent_metrics.py
PLAN.md Phase 4 measurements: what the muscle and afferent model actually
produces, per stance/swing bout, from the per-leg ground-truth `cut_on`
(needs --gait-scheduler phase or --cut-trigger force).

Per run (both legs pooled, t > --from-ms):
  gait        measured stride (touch-down to touch-down), stance fraction,
              stance duration
  Force-E     per stance bout: time from touch-down to 50% / 90% of the bout's
              peak, force at lift-off as a fraction of the peak, fraction of
              stance above half the peak
  Force-F     the same per swing bout
  Ia-E, Ia-F  rate percentiles (5/50/95) in stance and swing, and the median
              split of the stance Ia-E rate into its terms: base, force
              (IA_K_FORCE * force; pooled model only), stretch (IA_K_STRETCH * stretch)
  Ib-E, Ib-F  the same for the tendon-organ population (--afferent-model split)
  inputs      the open-loop afferent rates the run used (CUT, heel->toe Ia-E
              groups, swing flexor afferent)

Samples are the model's update windows (~--rate-update-ms); rise times are
interpolated linearly between window ends, so they are only as fine as that.

Usage:
  python3 scripts/p4_muscle_afferent_metrics.py results/p4/*.h5 [--from-ms 20000]
"""
import argparse
import os

import h5py
import numpy as np
import yaml


def crossing_time(t, x, t0, level):
    """First time after t0 at which x reaches `level` (linear interpolation)."""
    idx = np.flatnonzero((t > t0) & (x >= level))
    if idx.size == 0:
        return np.nan
    i = idx[0]
    if i == 0 or t[i - 1] < t0:
        return t[i] - t0
    x0, x1 = x[i - 1], x[i]
    frac = (level - x0) / (x1 - x0) if x1 != x0 else 1.0
    return (t[i - 1] + frac * (t[i] - t[i - 1])) - t0


def bouts(on, t, t_start):
    """(start_ms, end_ms) of each complete bout where `on` is true. `t` are window
    end times; a window's start is the previous window's end."""
    start_t = np.concatenate([[0.0], t[:-1]])
    edges = np.diff(on.astype(int))
    ups = np.flatnonzero(edges == 1) + 1
    downs = np.flatnonzero(edges == -1) + 1
    out = []
    for u in ups:
        d = downs[downs > u]
        if d.size and start_t[u] >= t_start:
            out.append((start_t[u], start_t[d[0]]))
    return out


def bout_force(t, x, b):
    t0, t1 = b
    m = (t > t0) & (t <= t1)
    if m.sum() < 2:
        return None
    peak = x[m].max()
    if peak <= 1e-6:
        return None
    end_val = np.interp(t1, t, x)
    w = np.diff(np.concatenate([[t0], t[m]]))
    return {"t50": crossing_time(t, x, t0, 0.5 * peak), "t90": crossing_time(t, x, t0, 0.9 * peak),
            "end_frac": end_val / peak, "above_half": float(np.sum(w[x[m] > 0.5 * peak]) / np.sum(w)),
            "dur": t1 - t0}


def pct(x):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    return np.percentile(x, [5, 50, 95]) if x.size else np.full(3, np.nan)


def run(path, from_ms):
    with h5py.File(path, "r") as f:
        a = dict(f.attrs)
        t = f["times_ms"][()]
        keys = ["force_e", "force_f", "ia_e", "ia_f", "len_e", "cut_on"]
        split = "leg_L/ib_e" in f
        keys += ["ib_e", "ib_f"] if split else []
        leg = {s: {k: f[f"leg_{s}/{k}"][()] for k in keys} for s in "LR"}
    cfg = yaml.safe_load(a["config_species_yaml"]) if "config_species_yaml" in a else {}
    const = cfg.get("constants", {})
    k_force, k_stretch = const.get("IA_K_FORCE", 6.0), const.get("IA_K_STRETCH", 250.0)
    res = {"file": os.path.basename(path), "species": a.get("species", "?"),
           "trigger": a.get("cut_trigger", "timer"), "afferents": "split" if split else "pooled", "tau_scale": (const.get("MUSCLE_TAU_SCALE_E", 1.0),
                                                                   const.get("MUSCLE_TAU_SCALE_F", 1.0))}
    st, sw, strides, stance_frac = [], [], [], []
    ia = {"e_st": [], "e_sw": [], "f_st": [], "f_sw": []}
    ib = {"e_st": [], "e_sw": [], "f_st": [], "f_sw": []}
    terms = {"force": [], "stretch": []}
    for s in "LR":
        g = leg[s]
        if g["cut_on"].size != t.size:
            raise SystemExit(f"{path}: no per-leg cut_on (needs --gait-scheduler phase or --cut-trigger force)")
        on = g["cut_on"] > 0.5
        keep = t > from_ms
        dur = np.diff(np.concatenate([[0.0], t]))
        stance_frac.append(np.sum(dur[keep & on]) / np.sum(dur[keep]))
        sb = bouts(on, t, from_ms)
        swb = bouts(~on, t, from_ms)
        strides += list(np.diff([b[0] for b in sb]))
        st += [r for r in (bout_force(t, g["force_e"], b) for b in sb) if r]
        sw += [r for r in (bout_force(t, g["force_f"], b) for b in swb) if r]
        ia["e_st"] += list(g["ia_e"][keep & on]); ia["e_sw"] += list(g["ia_e"][keep & ~on])
        ia["f_st"] += list(g["ia_f"][keep & on]); ia["f_sw"] += list(g["ia_f"][keep & ~on])
        if split:
            ib["e_st"] += list(g["ib_e"][keep & on]); ib["e_sw"] += list(g["ib_e"][keep & ~on])
            ib["f_st"] += list(g["ib_f"][keep & on]); ib["f_sw"] += list(g["ib_f"][keep & ~on])
        terms["force"] += list((0.0 if split else k_force) * g["force_e"][keep & on])
        terms["stretch"] += list(k_stretch * np.maximum(0.0, g["len_e"][keep & on] - 1.0))
    res["stride_ms"] = float(np.median(strides)) if strides else np.nan
    res["stance_frac"] = float(np.mean(stance_frac))
    res["stance_ms"] = float(np.median([b["dur"] for b in st])) if st else np.nan
    for name, bl in (("E", st), ("F", sw)):
        res[name] = {k: float(np.nanmedian([b[k] for b in bl])) if bl else np.nan
                     for k in ("t50", "t90", "end_frac", "above_half", "dur")}
        res[name]["n"] = len(bl)
    res["ia"] = {k: pct(v) for k, v in ia.items()}
    res["ib"] = {k: pct(v) for k, v in ib.items()} if split else None
    res["ia_terms"] = {"base": const.get("IA_BASE_HZ", 10.0), "force": float(np.median(terms["force"])),
                       "stretch": float(np.median(terms["stretch"]))}
    gain = float(a.get("cut_feedback_gain", 1.0))
    res["inputs"] = {"cut_hz": gain * float(const.get("CUT_RATE_ON_HZ", 100.0)),
                     "ia_ext_hz": list(np.atleast_1d(a.get("ia_ext_hz", []))),
                     "flex_aff_hz": a.get("ia_ext_f_hz", np.nan)}
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--from-ms", type=float, default=20000.0)
    args = ap.parse_args()
    for p in args.files:
        r = run(p, args.from_ms)
        print(f"== {r['file']}  species={r['species']} trigger={r['trigger']} afferents={r['afferents']} "
              f"tau_scale E/F={r['tau_scale'][0]}/{r['tau_scale'][1]}")
        print(f"   gait     stride {r['stride_ms']:.0f} ms, stance fraction {r['stance_frac']:.2f}, "
              f"stance {r['stance_ms']:.0f} ms")
        for name, lab in (("E", "Force-E / stance"), ("F", "Force-F / swing")):
            b = r[name]
            print(f"   {lab:16s} n={b['n']:3d}  t50 {b['t50']:5.0f} ms  t90 {b['t90']:5.0f} ms  "
                  f"end/peak {b['end_frac']:.2f}  >half-peak {b['above_half']:.2f} of bout ({b['dur']:.0f} ms)")
        for k, lab in (("e_st", "Ia-E stance"), ("e_sw", "Ia-E swing"), ("f_st", "Ia-F stance"), ("f_sw", "Ia-F swing")):
            v = r["ia"][k]
            print(f"   {lab:12s} p5/50/95 {v[0]:5.0f} {v[1]:5.0f} {v[2]:5.0f} Hz")
        if r["ib"] is not None:
            for k, lab in (("e_st", "Ib-E stance"), ("e_sw", "Ib-E swing"), ("f_st", "Ib-F stance"), ("f_sw", "Ib-F swing")):
                v = r["ib"][k]
                print(f"   {lab:12s} p5/50/95 {v[0]:5.0f} {v[1]:5.0f} {v[2]:5.0f} Hz")
        it = r["ia_terms"]
        print(f"   Ia-E stance median terms: base {it['base']:.0f} + force {it['force']:.0f} + stretch {it['stretch']:.0f} Hz"
              + (" (+ lengthening velocity; split)" if r["ib"] is not None else ""))
        i = r["inputs"]
        print(f"   open-loop inputs: CUT {i['cut_hz']:.0f} Hz in stance, heel->toe Ia-E {i['ia_ext_hz']} Hz, "
              f"swing flexor afferent {i['flex_aff_hz']} Hz")


if __name__ == "__main__":
    main()
