#!/usr/bin/env python3
"""
p7_ees_summary.py
PLAN.md P7 (EES): one row per run, for sweeps over --ees-hz / --ees-amp / --bs-drive-scale.

Per run (both legs pooled unless noted; the first --from-ms is skipped):
  ees_hz, ees_amp, bs   from the HDF5 attrs (EES off / intact = absent attrs: 0 / 1)
  ia_meas               measured Ia unit rate (Hz), incl. the stimulation pulses (EES runs)
  E, F                  mean extensor / flexor activation (act_e, act_f, 0-1.2)
  r(E,F)                correlation of Force-E and Force-F, mean over legs
  rhythm                alternation index: how much of the extensor activity is in bursts
                        rather than tonic, 1 - min/max of the 1 s moving mean of act_e
                        (0 = flat, tonic; 1 = fully modulated)
  f_Hz, rA(E,F)         dominant rhythm frequency (0.3-5 Hz FFT peak of act_e, both legs) and the
                        correlation of act_e with act_f (a tonic or noisy pattern gives a low |rA|)
  stride_s, E|stance    from the touchdowns of cut_on and the extensor-active fraction of stance
  tonic                 flag: extensor active > 85 % of the time (tonic extension)

Usage:
  python3 scripts/p7_ees_summary.py results/human_modes/p7_*/comfortable.h5
"""
import argparse
import os
import sys

import h5py
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpg_gait_phase_metrics import metrics  # noqa: E402


def rhythm_index(x, dt_ms, win_ms=1000.0):
    k = max(1, int(round(win_ms / dt_ms)))
    m = np.convolve(x, np.ones(k) / k, "valid")
    return float(1.0 - m.min() / m.max()) if m.size and m.max() > 1e-9 else float("nan")


def peak_hz(x, dt_ms):
    x = x - x.mean()
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    fr = np.fft.rfftfreq(len(x), dt_ms / 1000.0)
    ok = (fr >= 0.3) & (fr <= 5.0)
    return float(fr[ok][np.argmax(sp[ok])]) if ok.any() and sp[ok].max() > 0 else float("nan")


def row(path, from_ms):
    with h5py.File(path, "r") as f:
        a = dict(f.attrs)
        t = f["times_ms"][()]
        keep = t > from_ms
        dt = float(np.median(np.diff(t)))
        g = {s: f[f"leg_{s}"] for s in "LR"}
        e = np.mean([g[s]["act_e"][()][keep].mean() for s in "LR"])
        fl = np.mean([g[s]["act_f"][()][keep].mean() for s in "LR"])
        rh = np.nanmean([rhythm_index(g[s]["act_e"][()][keep], dt) for s in "LR"])
        ia = np.mean([g[s]["ia_meas_e"][()][keep].mean() for s in "LR"]) if "ia_meas_e" in g["L"] else float("nan")
        fhz = np.nanmean([peak_hz(g[s]["act_e"][()][keep], dt) for s in "LR"])
        rA = np.nanmean([np.corrcoef(g[s]["act_e"][()][keep], g[s]["act_f"][()][keep])[0, 1] for s in "LR"])
        eact = np.mean([(g[s]["act_e"][()][keep] > 0.5 * max(1e-9, np.percentile(g[s]["act_e"][()][keep], 95))).mean()
                        for s in "LR"])
    m = metrics(path, from_ms)
    return {
        "run": os.path.basename(os.path.dirname(path)),
        "ees_hz": float(a.get("ees_hz", 0.0)), "ees_amp": float(a.get("ees_amp", 0.0)),
        "ib": float(a.get("ees_amp_ib", 0.0)), "cut": float(a.get("ees_amp_cut", 0.0)),
        "bs": float(a.get("bs_drive_scale", 1.0)), "ia_meas": ia, "E": e, "F": fl,
        "rEF": np.nanmean([m["rEF_L"], m["rEF_R"]]), "rhythm": rh,
        "f_hz": fhz, "rA": rA,
        "stride_s": m.get("stride_meas", float("nan")) / 1000.0, "Eact": eact,
        "tonic": bool(eact > 0.85),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--from-ms", type=float, default=10000.0)
    a = ap.parse_args()
    rows = sorted((row(p, a.from_ms) for p in a.files), key=lambda r: (-r["bs"], r["ees_amp"], r["ib"], r["cut"], r["ees_hz"]))
    print(f"{'run':24s} {'bs':>4s} {'hz':>4s} {'amp':>4s} {'ib':>4s} {'cut':>4s} {'Ia_Hz':>6s} {'E':>5s} {'F':>5s} {'r(E,F)':>7s} "
          f"{'rhythm':>7s} {'f_Hz':>5s} {'rA':>5s} {'stride_s':>8s} {'Eact':>5s} tonic")
    for r in rows:
        print(f"{r['run']:24s} {r['bs']:4.1f} {r['ees_hz']:4.0f} {r['ees_amp']:4.1f} {r['ib']:4.1f} {r['cut']:4.1f} {r['ia_meas']:6.1f} "
              f"{r['E']:5.2f} {r['F']:5.2f} {r['rEF']:7.2f} {r['rhythm']:7.2f} {r['f_hz']:5.2f} {r['rA']:5.2f} {r['stride_s']:8.2f} "
              f"{r['Eact']:5.2f} {'yes' if r['tonic'] else ''}")


if __name__ == "__main__":
    main()
