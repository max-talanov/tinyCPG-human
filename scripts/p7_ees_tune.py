#!/usr/bin/env python3
"""
p7_ees_tune.py
PLAN.md P7b: one row per single-session run of an EES tuning scan (injured start, 60 s): does the
stimulation help the extensor and the training signal? Columns (last --last-ms of the run):
  Ia/Ib/CUT  recruited fraction per pulse; hz   pulse rate (from the HDF5 attrs)
  rEF        r(Force-E, Force-F), mean of the legs      FE   95th percentile of Force-E (a.u.)
  act_e      mean extensor activation                   CUTb captured CUT->RG-E baseline at the end (pA)
  dCUT       CUTb minus the session-start weight (pA)   the in-session gain: the learning signal
  d_*        difference to the no-EES run of the same mode in the same scan (rows named noees*)
Usage: python3 scripts/p7_ees_tune.py results/human_modes/p7/ees_tune/<stage>/*/bws50.h5
"""
import argparse, os
import h5py
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("files", nargs="+")
ap.add_argument("--last-ms", type=float, default=20000.0)
a = ap.parse_args()


def row(path):
    with h5py.File(path, "r") as f:
        at = dict(f.attrs)
        t = f["times_ms"][()]
        k = t > t[-1] - a.last_ms
        r, fe, ae = [], [], []
        for s in "LR":
            e, fl = f[f"leg_{s}/force_e"][()][k], f[f"leg_{s}/force_f"][()][k]
            r.append(np.corrcoef(e, fl)[0, 1])
            fe.append(np.percentile(e, 95))
            ae.append(f[f"leg_{s}/act_e"][()][k].mean())
        cutb = np.mean([f[f"leg_{s}/full_weights/cut_to_rge/baseline"][()].mean() for s in "LR"])
        w0 = np.mean([f[f"leg_{s}/full_weights/cut_to_rge/w"][()][0].mean() for s in "LR"])
    return dict(name=os.path.basename(os.path.dirname(path)), mode=os.path.basename(path)[:-3],
                hz=at.get("ees_hz", 0.0), ia=at.get("ees_amp", 0.0) if at.get("ees_hz", 0) else 0.0,
                ib=at.get("ees_amp_ib", 0.0), cut=at.get("ees_amp_cut", 0.0),
                rEF=float(np.nanmean(r)), FE=float(np.mean(fe)), act_e=float(np.mean(ae)), CUTb=float(cutb), dCUT=float(cutb - w0))


rows = [row(p) for p in a.files]
ref = {r["mode"]: r for r in rows if r["hz"] == 0}
print(f"{'run':24s} {'mode':6s} {'hz':>4s} {'Ia':>4s} {'Ib':>4s} {'CUT':>4s} {'rEF':>6s} {'FE':>5s} {'act_e':>6s} {'CUTb':>6s} {'dCUT':>6s} | {'d_rEF':>6s} {'d_FE':>5s} {'d_dCUT':>6s}")
for r in sorted(rows, key=lambda r: (r["mode"], r["hz"], r["name"])):
    b = ref.get(r["mode"])
    d = (r["rEF"] - b["rEF"], r["FE"] - b["FE"], r["dCUT"] - b["dCUT"]) if b else (np.nan,) * 3
    print(f"{r['name']:24s} {r['mode']:6s} {r['hz']:4.0f} {r['ia']:4.2f} {r['ib']:4.2f} {r['cut']:4.2f} {r['rEF']:6.2f} {r['FE']:5.1f} {r['act_e']:6.2f} "
          f"{r['CUTb']:6.1f} {r['dCUT']:6.1f} | {d[0]:6.2f} {d[1]:5.1f} {d[2]:6.1f}")
