#!/usr/bin/env python3
"""
regression_compare.py
Regression check for cpg_2legs_fast.py HDF5 outputs (PLAN.md, Phase 0).

The rat model must stay byte-identical while the human migration lands
(PLAN.md, guiding principle 1). "Byte-identical" here means identical
*content*: every dataset (shape, dtype, values) and every attribute, in every
group. File bytes themselves are not comparable, because the writer stamps
volatile metadata such as `created_utc` into the root attributes. Those are
skipped by default (--ignore-attr adds more), as are provenance attributes
prefixed `config_` (the resolved species config, PLAN.md P1).

Two subcommands:

  compare A.h5 B.h5   Walk both files and report every difference: missing
                      or extra objects, shape/dtype changes, value
                      differences (max |diff| and first differing index),
                      attribute changes. Exact by default; --rtol/--atol
                      switch numeric datasets to np.allclose. Exit code 0 =
                      identical, 1 = different, 2 = usage/IO error.

  digest FILE.h5      Print a SHA-256 over the file's content (object paths,
                      dtypes, shapes, raw values, attributes; volatile
                      attributes excluded). Two files with the same digest
                      pass `compare` exactly. regress.sh stores these digests
                      in the committed manifest so the (git-ignored) golden
                      .h5 files are not needed to detect a regression, only
                      to explain one.

Usage:
  python3 scripts/regression_compare.py compare golden.h5 new.h5
  python3 scripts/regression_compare.py compare golden.h5 new.h5 --atol 1e-6
  python3 scripts/regression_compare.py digest results/debug.h5
"""
import argparse
import hashlib
import sys

import h5py
import numpy as np

# Root attributes that change on every run regardless of model behaviour.
VOLATILE_ATTRS = ("created_utc",)
# Provenance attributes (PLAN.md P1): the resolved species config written by
# cpg_2legs_fast.py. They describe the inputs, not the model output -- a real
# parameter change still shows up in the datasets -- so they are skipped.
PROVENANCE_PREFIXES = ("config_",)

MAX_REPORTED = 50  # cap on printed differences; the count is always reported


def collect(h5):
    """Return {path: h5py object} for every group and dataset, root included."""
    objs = {"/": h5}
    h5.visititems(lambda name, obj: objs.__setitem__("/" + name, obj))
    return objs


def attrs_of(obj, ignore):
    return {k: obj.attrs[k] for k in sorted(obj.attrs.keys())
            if k not in ignore and not k.startswith(PROVENANCE_PREFIXES)}


def values_equal(a, b):
    a = np.asarray(a)
    b = np.asarray(b)
    if a.shape != b.shape or a.dtype != b.dtype:
        return False
    if a.dtype.kind in "fc":
        return bool(np.array_equal(a, b, equal_nan=True))
    return bool(np.array_equal(a, b))


def compare_datasets(path, da, db, rtol, atol, diffs):
    if da.shape != db.shape:
        diffs.append(f"{path}: shape {da.shape} != {db.shape}")
        return
    if da.dtype != db.dtype:
        diffs.append(f"{path}: dtype {da.dtype} != {db.dtype}")
        return
    a = da[()]
    b = db[()]
    if values_equal(a, b):
        return
    if da.dtype.kind in "fciub" and (rtol or atol):
        if np.allclose(a, b, rtol=rtol, atol=atol, equal_nan=True):
            return
    if da.dtype.kind in "fciu":
        a_arr = np.asarray(a, dtype=np.float64)
        b_arr = np.asarray(b, dtype=np.float64)
        delta = np.abs(a_arr - b_arr)
        delta = np.where(np.isnan(a_arr) & np.isnan(b_arr), 0.0, delta)
        n_bad = int(np.count_nonzero(delta)) if delta.ndim else int(delta != 0)
        first = np.unravel_index(int(np.nanargmax(delta != 0)), delta.shape) if delta.ndim else ()
        diffs.append(f"{path}: {n_bad}/{delta.size} values differ, "
                     f"max|diff|={float(np.nanmax(delta)):.6g}, first at index {tuple(int(i) for i in first)}")
    else:
        diffs.append(f"{path}: values differ ({da.dtype})")


def compare_files(path_a, path_b, ignore, rtol, atol):
    diffs = []
    with h5py.File(path_a, "r") as fa, h5py.File(path_b, "r") as fb:
        oa, ob = collect(fa), collect(fb)
        for p in sorted(set(oa) - set(ob)):
            diffs.append(f"{p}: only in {path_a}")
        for p in sorted(set(ob) - set(oa)):
            diffs.append(f"{p}: only in {path_b}")
        for p in sorted(set(oa) & set(ob)):
            xa, xb = oa[p], ob[p]
            if isinstance(xa, h5py.Dataset) != isinstance(xb, h5py.Dataset):
                diffs.append(f"{p}: group in one file, dataset in the other")
                continue
            if isinstance(xa, h5py.Dataset):
                compare_datasets(p, xa, xb, rtol, atol, diffs)
            aa, ab = attrs_of(xa, ignore), attrs_of(xb, ignore)
            for k in sorted(set(aa) | set(ab)):
                if k not in aa or k not in ab:
                    diffs.append(f"{p} @{k}: attribute only in {path_a if k in aa else path_b}")
                elif not values_equal(aa[k], ab[k]):
                    diffs.append(f"{p} @{k}: {aa[k]!r} != {ab[k]!r}")
    return diffs


def digest_file(path, ignore):
    h = hashlib.sha256()
    with h5py.File(path, "r") as f:
        objs = collect(f)
        for p in sorted(objs):
            obj = objs[p]
            h.update(p.encode())
            if isinstance(obj, h5py.Dataset):
                arr = np.ascontiguousarray(obj[()])
                h.update(f"D|{arr.dtype.str}|{arr.shape}".encode())
                if arr.dtype.kind == "O":
                    h.update(repr(arr.tolist()).encode())
                else:
                    h.update(arr.tobytes())
            else:
                h.update(b"G")
            for k, v in attrs_of(obj, ignore).items():
                v = np.asarray(v)
                h.update(f"A|{k}|{v.dtype.str}|{v.shape}".encode())
                h.update(repr(v.tolist()).encode() if v.dtype.kind == "O" else v.tobytes())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compare", help="report differences between two HDF5 outputs")
    c.add_argument("a")
    c.add_argument("b")
    c.add_argument("--rtol", type=float, default=0.0)
    c.add_argument("--atol", type=float, default=0.0)

    d = sub.add_parser("digest", help="print a content SHA-256 of one HDF5 output")
    d.add_argument("file")

    for p in (c, d):
        p.add_argument("--ignore-attr", action="append", default=[],
                       help="extra attribute name to skip (repeatable); "
                            f"always skipped: {', '.join(VOLATILE_ATTRS)}")

    args = ap.parse_args()
    ignore = set(VOLATILE_ATTRS) | set(args.ignore_attr)

    try:
        if args.cmd == "digest":
            print(digest_file(args.file, ignore))
            return 0
        diffs = compare_files(args.a, args.b, ignore, args.rtol, args.atol)
    except (OSError, KeyError) as e:
        print(f"[regression_compare] error: {e}", file=sys.stderr)
        return 2

    if not diffs:
        tol = f" (rtol={args.rtol}, atol={args.atol})" if (args.rtol or args.atol) else " (exact)"
        print(f"[regression_compare] IDENTICAL{tol}: {args.a} == {args.b}")
        return 0
    print(f"[regression_compare] DIFFERENT: {len(diffs)} difference(s) between {args.a} and {args.b}")
    for line in diffs[:MAX_REPORTED]:
        print("  " + line)
    if len(diffs) > MAX_REPORTED:
        print(f"  ... and {len(diffs) - MAX_REPORTED} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())
