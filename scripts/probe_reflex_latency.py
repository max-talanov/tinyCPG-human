#!/usr/bin/env python3
"""
probe_reflex_latency.py
Reflex-latency probe (PLAN.md Phase 2): the shortest causal latency from a
synchronous Ia-E afferent volley to the left-leg RG-E, M-E and muscle (mus-E)
spikes, for one species configuration.

Method. Model runs are bit-reproducible for a fixed seed and thread count
(PLAN.md §7 B11/B12). The script runs the rat-sh/debug.sh configuration once as a
control (probe structure present, no volley: --probe-reflex-at-ms -1) and once
per volley time. Up to the volley both runs are identical, so the first spike
that differs afterwards is the earliest effect of the volley:
    latency = t(first differing spike) - t(volley)
The model has no monosynaptic Ia -> motoneuron connection; Ia reaches the
motoneurons through RG-E (and inhibits the antagonist through Ia interneurons),
so this is the model's shortest Ia -> muscle loop, compared with the human
soleus stretch / H-reflex latency (~30-35 ms). Several volley times across the
gait cycle are used because a volley that arrives while RG-E is inhibited acts
later; the minimum over volleys is the reflex latency.

Usage:
  python3 scripts/probe_reflex_latency.py --species human
  python3 scripts/probe_reflex_latency.py --species rat --volley-ms 2000 2250 2500 2750
"""
import argparse
import os
import subprocess
import sys
import tempfile

import h5py
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
MODEL = os.path.join(REPO, "cpg_2legs_fast.py")
POPS = ("rg_e", "m_e", "mus_e")

# The rat-sh/debug.sh configuration (debug-small, paced gait), minus --species/--out/--sim-ms.
DEBUG_ARGS = [
    "--debug-small", "--paced-gait", "--step-period-ms", "1000", "--stance-fraction", "0.5",
    "--n-ia-groups", "3", "--ia-ext-hz", "60", "80", "100", "--ia-ext-f-hz", "80",
    "--dt-ms", "10", "--sweep-pairs", "22:0.30", "--sweep-run-idx", "0",
    "--sweep-dist", "lognormal_cv", "--seed", "12345", "--nest-verbosity", "M_WARNING",
    "--max-weight-conns", "1000", "--save-weights", "none", "--delay-jitter-ms", "0.2",
    "--weight-sample-ms", "500", "--rate-update-ms", "50", "--simulate-chunk-ms", "50",
    "--bs-base-hz", "6", "--bs-noise-std-hz", "0.25", "--enforce-tonic-bs",
]


def run(workdir, tag, species, volley, sim_ms, threads, extra):
    out = os.path.join(workdir, f"{tag}.h5")
    cmd = [sys.executable, "-u", MODEL, *DEBUG_ARGS, "--species", species, "--threads", str(threads),
           "--sim-ms", str(sim_ms), "--out", out, "--probe-reflex-at-ms", str(volley), *extra]
    res = subprocess.run(cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if res.returncode != 0:
        sys.exit(f"[probe] model run `{tag}` failed:\n" + res.stdout[-3000:])
    with h5py.File(out, "r") as f:
        return {p: (f[f"probe/{p}_times"][()], f[f"probe/{p}_senders"][()]) for p in POPS}


def first_divergence(ctrl, probe, t0):
    """Earliest spike time >= t0 at which the two (time, sender) event lists differ."""
    tc, sc = ctrl
    tp, sp = probe
    mc, mp = tc >= t0, tp >= t0
    tc, sc, tp, sp = tc[mc], sc[mc], tp[mp], sp[mp]
    n = min(len(tc), len(tp))
    diff = np.flatnonzero((tc[:n] != tp[:n]) | (sc[:n] != sp[:n]))
    if diff.size:
        i = int(diff[0])
        return float(min(tc[i], tp[i]))
    if len(tc) != len(tp):
        return float(tc[n] if len(tc) > n else tp[n])
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--species", default="human")
    ap.add_argument("--volley-ms", type=float, nargs="+",
                    default=[2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900],
                    help="volley times (ms); default spans one 1000 ms stride after 2 s of settling")
    ap.add_argument("--window-ms", type=float, default=150.0, help="simulated time after the last volley")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--workdir", default=None, help="keep run files here (default: temporary dir)")
    ap.add_argument("extra", nargs="*", help="extra model arguments after --")
    args = ap.parse_args()

    sim_ms = max(args.volley_ms) + args.window_ms
    tmp = None
    workdir = args.workdir
    if workdir is None:
        tmp = tempfile.TemporaryDirectory(prefix="reflex-probe-")
        workdir = tmp.name
    os.makedirs(workdir, exist_ok=True)

    print(f"[probe] species={args.species} threads={args.threads} sim={sim_ms:.0f} ms "
          f"volleys={len(args.volley_ms)} (rat-sh/debug.sh configuration)")
    ctrl = run(workdir, "control", args.species, -1, sim_ms, args.threads, args.extra)
    rows = []
    for v in args.volley_ms:
        pr = run(workdir, f"volley_{int(v)}", args.species, v, sim_ms, args.threads, args.extra)
        lat = {}
        for p in POPS:
            t = first_divergence(ctrl[p], pr[p], v)
            lat[p] = None if t is None else t - v
        rows.append((v, lat))
        cells = "  ".join(f"{p}={'—' if lat[p] is None else f'{lat[p]:6.1f}'} ms" for p in POPS)
        print(f"  volley @ {v:7.1f} ms: {cells}")

    print("[probe] minimum over volleys (shortest causal latency):")
    for p in POPS:
        vals = [lat[p] for _, lat in rows if lat[p] is not None]
        print(f"  {p:6s}: " + (f"{min(vals):6.1f} ms  (median {np.median(vals):6.1f} ms, "
                                f"{len(vals)}/{len(rows)} volleys had an effect)" if vals else "no effect"))
    if tmp is not None:
        tmp.cleanup()


if __name__ == "__main__":
    main()
