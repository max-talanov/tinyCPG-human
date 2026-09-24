#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cpg_plot_from_hdf5.py
Read the HDF5 produced by cpg_2legs_nest_to_hdf5.py and generate plots locally.

Example:
  python3 cpg_plot_from_hdf5.py --in cpg_run.h5 --smooth-sec 1.0
"""

import argparse
import numpy as np
import h5py
import matplotlib.pyplot as plt


def _fill_nans_forward(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float).copy()
    if not np.isnan(x).any():
        return x
    idx = np.where(~np.isnan(x))[0]
    if idx.size == 0:
        return x
    x[:idx[0]] = x[idx[0]]
    for i in range(idx.size - 1):
        a, b = idx[i], idx[i + 1]
        if b > a + 1:
            x[a + 1:b] = x[a]
    x[idx[-1] + 1:] = x[idx[-1]]
    return x


def moving_average(x, win: int):
    x = _fill_nans_forward(np.asarray(x, dtype=float))
    win = int(max(1, win))
    if win <= 1:
        return x
    kernel = np.ones(win, dtype=float) / win
    return np.convolve(x, kernel, mode="same")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input HDF5 file from HPC")
    ap.add_argument("--smooth-sec", type=float, default=1.0, help="Smoothing window for weights (seconds)")
    ap.add_argument("--plot-individual", action="store_true",
                    help="If set and full weight matrices exist, overlay individual connection weight traces (semi-transparent) on the full-weight band plot.")
    ap.add_argument("--max-individual", type=int, default=50,
                    help="Max number of individual weight traces to overlay per projection (default: 50).")
    ap.add_argument("--save-prefix", type=str, default="", help="If set, save PNGs as <prefix>_legX_*.png")
    ap.add_argument("--show", action="store_true", help="Show plots interactively (default: false if saving)")
    args = ap.parse_args()

    with h5py.File(args.inp, "r") as h5:
        times_ms = np.array(h5["times_ms"])
        dt_ms = float(h5.attrs.get("dt_ms", np.median(np.diff(times_ms)) if len(times_ms) > 1 else 10.0))

        print("=== Run metadata ===")
        for k in ["created_utc", "nest_version", "sim_ms", "dt_ms", "phases", "bs_osc_hz", "local_threads", "mpi_processes"]:
            if k in h5.attrs:
                print(f"{k}: {h5.attrs[k]}")
        if "stats" in h5:
            s = h5["stats"].attrs
            print("--- stats ---")
            for k in sorted(s.keys()):
                print(f"{k}: {s[k]}")
        print("====================")

        win = max(1, int((args.smooth_sec * 1000.0) / dt_ms))
        print(f"[Plot] weight smoothing: {args.smooth_sec:.3f}s -> {win} samples")

        legs = sorted([k.split("_", 1)[1] for k in h5.keys() if k.startswith("leg_")])
        has_full = "weights_times_ms" in h5
        wtimes_ms = np.array(h5["weights_times_ms"]) if has_full else None
        if has_full:
            print(f"[Plot] full weight samples: {len(wtimes_ms)}")

        for side in legs:
            g = h5[f"leg_{side}"]
            w = g["weights"]

            def maybe_save(fig, name):
                if args.save_prefix:
                    fig.savefig(f"{args.save_prefix}_leg{side}_{name}.png", dpi=160)

            # BS drive
            fig = plt.figure(figsize=(14, 5))
            plt.plot(times_ms, g["bs_e"][:], label="BS E")
            plt.plot(times_ms, g["bs_f"][:], label="BS F")
            plt.xlabel("time (ms)"); plt.ylabel("Hz")
            plt.title(f"Brainstem drive — leg {side}")
            plt.legend(); plt.tight_layout()
            maybe_save(fig, "bs")

            # Weight learning trends (mean ± std, smoothed). Plot whatever projections exist.
            fig = plt.figure(figsize=(14, 7))
            mean_keys = sorted([k for k in w.keys() if k.endswith("_mean")])
            if len(mean_keys) == 0:
                plt.text(0.5, 0.5, "No weight trends found in HDF5 (leg_{side}/weights)", ha="center", va="center")
            else:
                for mk in mean_keys:
                    base = mk[:-5]  # strip '_mean'
                    sk = f"{base}_std"
                    m = moving_average(w[mk][:], win)
                    if sk in w:
                        s = moving_average(w[sk][:], win)
                        plt.fill_between(times_ms, m - s, m + s, alpha=0.15)
                    plt.plot(times_ms, m, label=f"{base} mean ({args.smooth_sec:.1f}s MA)")
            plt.xlabel("time (ms)"); plt.ylabel("weight (pA)")
            plt.title(f"STDP learning — weight trends (leg {side})")
            plt.legend(); plt.tight_layout()
            maybe_save(fig, "w_trends")

            # Optional: full weight vectors (percentile bands over connections)
            if has_full and "full_weights" in g:
                gfw = g["full_weights"]
                fig = plt.figure(figsize=(14, 7))
                any_plotted = False
                for proj in sorted(gfw.keys()):
                    # Pick a stable color per projection from Matplotlib's default cycle
                    color = f"C{list(sorted(gfw.keys())).index(proj) % 10}"
                    if "w" not in gfw[proj]:
                        continue
                    wmat = np.asarray(gfw[proj]["w"])  # shape [T, N]
                    if wmat.ndim != 2:
                        continue
                    # Compute summary across connections (axis=1)
                    mean_t = np.nanmean(wmat, axis=1) if wmat.shape[1] > 0 else np.full((wmat.shape[0],), np.nan)
                    p10 = np.nanpercentile(wmat, 10, axis=1) if wmat.shape[1] > 0 else np.full((wmat.shape[0],), np.nan)
                    p90 = np.nanpercentile(wmat, 90, axis=1) if wmat.shape[1] > 0 else np.full((wmat.shape[0],), np.nan)
                    plt.plot(wtimes_ms, mean_t, label=f"{proj} mean", color=color)
                    plt.fill_between(wtimes_ms, p10, p90, alpha=0.12, color=color)

                    # Optional: overlay individual connection weight traces (semi-transparent)
                    if args.plot_individual and wmat.shape[1] > 0:
                        n_conn = int(wmat.shape[1])
                        n_show = int(max(0, args.max_individual))
                        if n_show > 0:
                            n_show = min(n_show, n_conn)
                            # Pick evenly-spaced indices to represent the population without randomness.
                            idx = np.linspace(0, n_conn - 1, n_show, dtype=int)
                            # Plot without legend entries to keep legend readable.
                            for j in idx:
                                plt.plot(wtimes_ms, wmat[:, j], alpha=0.08, linewidth=0.8, label=None, color=color)

                    any_plotted = True
                extra = " + individual" if args.plot_individual else ""
                plt.title(f"STDP learning — full weight bands (10–90%){extra} (leg {side})")
                plt.xlabel("time (ms)"); plt.ylabel("weight (pA)")
                plt.legend(); plt.tight_layout()
                maybe_save(fig, "w_full_bands")

                # Final weight histograms (one subplot-like sequence using separate figs to keep style simple)
                for proj in sorted(gfw.keys()):
                    color = f"C{list(sorted(gfw.keys())).index(proj) % 10}"
                    if "w" not in gfw[proj]:
                        continue
                    wmat = np.asarray(gfw[proj]["w"])  # [T, N]
                    if wmat.ndim != 2 or wmat.shape[0] == 0 or wmat.shape[1] == 0:
                        continue
                    wfinal = wmat[-1]
                    fig = plt.figure(figsize=(10, 5))
                    plt.hist(wfinal, bins=60, color=color, alpha=0.85)
                    plt.xlabel("weight (pA)"); plt.ylabel("count")
                    plt.title(f"Final weight distribution — {proj} (leg {side})")
                    plt.tight_layout()
                    maybe_save(fig, f"w_hist_{proj}")


            # Muscle
            fig = plt.figure(figsize=(14, 5))
            plt.plot(times_ms, g["mus_e"][:], label="mus-E rate")
            plt.plot(times_ms, g["mus_f"][:], label="mus-F rate")
            plt.xlabel("time (ms)"); plt.ylabel("Hz/neuron")
            plt.title(f"Muscle relay rates — leg {side}")
            plt.legend(); plt.tight_layout()
            maybe_save(fig, "mus_rate")

            # Rhythm generator (RG) population rates
            if "rge" in g and "rgf" in g:
                fig = plt.figure(figsize=(14, 5))
                plt.plot(times_ms, g["rge"][:], label="RG-E rate")
                plt.plot(times_ms, g["rgf"][:], label="RG-F rate")
                plt.xlabel("time (ms)"); plt.ylabel("Hz/neuron")
                plt.title(f"Rhythm generator rates — leg {side}")
                plt.legend(); plt.tight_layout()
                maybe_save(fig, "rg_rate")
            else:
                # Backward compatibility with older HDF5 files
                pass

            # Activation
            fig = plt.figure(figsize=(14, 5))
            plt.plot(times_ms, g["act_e"][:], label="Activation E")
            plt.plot(times_ms, g["act_f"][:], label="Activation F")
            plt.xlabel("time (ms)"); plt.ylabel("a.u.")
            plt.title(f"Activation proxy — leg {side}")
            plt.legend(); plt.tight_layout()
            maybe_save(fig, "activation")

            # Force
            fig = plt.figure(figsize=(14, 5))
            plt.plot(times_ms, g["force_e"][:], label="Force E")
            plt.plot(times_ms, g["force_f"][:], label="Force F")
            plt.xlabel("time (ms)"); plt.ylabel("force (a.u.)")
            plt.title(f"Force proxy — leg {side}")
            plt.legend(); plt.tight_layout()
            maybe_save(fig, "force")

            # Length
            fig = plt.figure(figsize=(14, 5))
            plt.plot(times_ms, g["len_e"][:], label="Length E")
            plt.plot(times_ms, g["len_f"][:], label="Length F")
            plt.axhline(1.0, linestyle="--", linewidth=1)
            plt.xlabel("time (ms)"); plt.ylabel("length (a.u.)")
            plt.title(f"Length proxy — leg {side}")
            plt.legend(); plt.tight_layout()
            maybe_save(fig, "length")

            # Ia
            fig = plt.figure(figsize=(14, 5))
            plt.plot(times_ms, g["ia_e"][:], label="Ia-E rate")
            plt.plot(times_ms, g["ia_f"][:], label="Ia-F rate")
            plt.xlabel("time (ms)"); plt.ylabel("Hz")
            plt.title(f"Ia generator rates — leg {side}")
            plt.legend(); plt.tight_layout()
            maybe_save(fig, "ia")

        if args.show or not args.save_prefix:
            plt.show()


if __name__ == "__main__":
    main()