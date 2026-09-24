#!/usr/bin/env python3
"""
cpg_param_table.py
Generate a paper-ready parameter table for the tinyCPG model.

Parses NAME = value definitions from cpg_2legs_fast.py, groups them into
themed sections (populations, connectivity, neuron params, plasticity,
muscle proxies, sensory, gait), and emits Markdown, LaTeX, or CSV.

Each parameter row carries a literature citation when applicable.

Usage:
  python3 cpg_param_table.py --src cpg_2legs_fast.py --format md  > params.md
  python3 cpg_param_table.py --src cpg_2legs_fast.py --format latex > params.tex
  python3 cpg_param_table.py --src cpg_2legs_fast.py --format csv  > params.csv
"""

import argparse
import re
import sys
from typing import Dict, List, Tuple


# ---------- bio-citation table (hand-curated; keep alongside code) ----------
# Maps parameter name → (units, description, citation)
PARAM_META: Dict[str, Tuple[str, str, str]] = {
    # Populations
    "N_RG_E":          ("neurons", "Rhythm-generator extensor half-centre size",     "Rybak et al. 2015"),
    "N_RG_F":          ("neurons", "Rhythm-generator flexor half-centre size",       "Rybak et al. 2015"),
    "N_MOTOR_E":       ("neurons", "Extensor motor pool size",                       "McCrea & Rybak 2008"),
    "N_MOTOR_F":       ("neurons", "Flexor motor pool size",                         "McCrea & Rybak 2008"),
    "N_MUS_E":         ("relays",  "Extensor muscle proxy parrot count",             "—"),
    "N_MUS_F":         ("relays",  "Flexor muscle proxy parrot count",               "—"),
    "N_IA_E":          ("neurons", "Extensor Ia afferent Poisson generators",        "Loeb 1981; Prochazka 1999"),
    "N_IA_F":          ("neurons", "Flexor Ia afferent Poisson generators",          "Loeb 1981; Prochazka 1999"),
    "N_IA_INT":        ("neurons", "Ia inhibitory interneurons (antagonist)",        "Jankowska 1992"),
    "N_INE":           ("neurons", "RG-E → InE → RG-F suppressing INs",              "Zhang et al. 2022"),
    "N_INF":           ("neurons", "RG-F → InF → RG-E suppressing INs",              "Zhang et al. 2022"),
    "N_CUT":           ("neurons", "Cutaneous/Group-II afferent generators",         "Pearson 1995; Rossignol 2006"),
    "N_BS":            ("neurons", "Brainstem reticulospinal drive generators",      "Drew & Rossignol 1986"),

    # Reciprocal inhibition (Zhang 2022 asymmetry)
    "W_INF2RGE":       ("pA",      "InF → RG-E synaptic weight (STRONG)",            "Zhang et al. 2022"),
    "W_INE2RGF":       ("pA",      "InE → RG-F synaptic weight (WEAK)",              "Zhang et al. 2022"),
    "W_RG2INE":        ("pA",      "RG-E → InE excitatory drive",                    "Rybak et al. 2015"),
    "W_RG2INF":        ("pA",      "RG-F → InF excitatory drive",                    "Rybak et al. 2015"),
    "P_RG_RECIP_F":    ("prob",    "F→InF→E pathway connection probability",         "Zhang et al. 2022"),
    "P_RG_RECIP_E":    ("prob",    "E→InE→F pathway connection probability",         "Zhang et al. 2022"),

    # Closed-loop Ia feedback (THIS WORK)
    "W_IA2IN":         ("pA",      "Ia afferent → reciprocal IN (closed-loop)",      "THIS WORK"),
    "P_IA2IN":         ("prob",    "Ia → IN connection probability",                 "THIS WORK"),
    "W_IA_IN2INT":     ("pA",      "Ia parrot → Ia inhibitory IN",                   "Jankowska 1992"),
    "W_IA_INT2ANT":    ("pA",      "Ia inhibitory IN → antagonist motor pool",       "Jankowska 1992"),

    # Cutaneous reflex
    "CUT_RATE_ON_HZ":  ("Hz",      "Cutaneous afferent peak firing rate",            "Loeb 1981; Pearson 1995"),
    "CUT_RATE_OFF_HZ": ("Hz",      "Cutaneous baseline (off-phase)",                 "—"),

    # Commissural L↔R
    "W_COMM_F_INH":    ("pA",      "Flexor commissural inhibition (L↔R)",            "Kiehn 2016; Talpalar 2013"),
    "P_COMM_F":        ("prob",    "Flexor commissural connection probability",      "Kiehn 2016"),
    "W_COMM_E_INH":    ("pA",      "Extensor commissural inhibition (weak)",         "Kiehn 2016"),
    "P_COMM_E":        ("prob",    "Extensor commissural connection probability",    "Kiehn 2016"),

    # Brainstem drive
    "BS_REGULAR_HZ":   ("Hz",      "Tonic reticulospinal drive rate (20–80 Hz bio)", "Drew & Rossignol 1986"),
    "BS_RATE_BASE_HZ": ("Hz",      "Baseline BS rate before STDP shaping",           "—"),
    "BS_NOISE_STD_HZ": ("Hz",      "Gaussian noise on tonic BS",                     "—"),

    # Izhikevich neuron parameters
    "RGF_A":           ("—",       "RG-F Izhikevich a (intrinsic-bursting set)",     "Izhikevich 2003 (IB)"),
    "RGF_B":           ("—",       "RG-F Izhikevich b",                              "Izhikevich 2003 (IB)"),
    "RGF_C":           ("mV",      "RG-F Izhikevich c (post-spike reset)",           "Izhikevich 2003 (IB)"),
    "RGF_D":           ("—",       "RG-F Izhikevich d (recovery jump)",              "Izhikevich 2003 (IB)"),
    "I_E_RGE":         ("pA",      "Extensor tonic input current",                   "—"),
    "I_E_RGF":         ("pA",      "Flexor tonic input current",                     "—"),

    # STDP plasticity
    "TAU_PLUS":        ("ms",      "STDP positive time constant",                    "Bi & Poo 1998"),
    "LAMBDA":          ("—",       "STDP learning rate",                             "Morrison et al. 2007"),
    "ALPHA":           ("—",       "STDP asymmetry (LTD / LTP ratio)",               "Bi & Poo 1998"),
    "MU_PLUS":         ("—",       "STDP positive nonlinearity exponent",            "Morrison et al. 2007"),
    "MU_MINUS":        ("—",       "STDP negative nonlinearity exponent",            "Morrison et al. 2007"),
    "WMAX":            ("pA",      "STDP weight ceiling (CUT→RG)",                   "—"),
    "WMAX_BS":         ("pA",      "STDP weight ceiling (BS→RG)",                    "THIS WORK"),

    # Muscle proxies / Hill-like dynamics
    "TAU_ACT_RISE_MS": ("ms",      "Activation rise time constant",                  "Zajac 1989; Winters 1995"),
    "TAU_ACT_DECAY_MS":("ms",      "Activation decay time constant",                 "Zajac 1989"),
    "ACT_SAT_K":       ("—",       "Activation saturation slope",                    "Winters 1995"),
    "ACT_GATE_POWER":  ("—",       "RG-rate gate exponent",                          "THIS WORK"),
    "ACT_MAX":         ("a.u.",    "Activation ceiling",                             "—"),
    "TAU_FORCE_RISE_MS":("ms",     "Force rise time constant",                       "Zajac 1989"),
    "TAU_FORCE_DECAY_MS":("ms",    "Force decay (relaxation) time constant",         "Zajac 1989"),
    "FORCE_MAX":       ("a.u.",    "Force ceiling",                                  "—"),
    "FORCE_SAT_K":     ("—",       "Force saturation slope",                         "—"),
    "TAU_LENGTH_MS":   ("ms",      "Muscle length filter time constant",             "—"),
    "L0":              ("a.u.",    "Resting muscle length",                          "—"),
    "SHORTEN_GAIN":    ("—",       "Force → shortening coefficient",                 "—"),
    "STRETCH_GAIN":    ("—",       "CUT → extensor stretch coefficient",             "—"),

    # Ia spindle rate-coding
    "IA_BASE_HZ":      ("Hz",      "Ia baseline firing rate",                        "Prochazka 1999"),
    "IA_K_FORCE":      ("Hz/F",    "Ia → force sensitivity",                         "Prochazka 1999"),
    "IA_K_STRETCH":    ("Hz/L",    "Ia → stretch sensitivity",                       "Prochazka 1999"),
    "IA_RATE_MAX_HZ":  ("Hz",      "Ia ceiling rate",                                "Prochazka 1999"),
}


# Categories — order = display order in the table
CATEGORIES: List[Tuple[str, List[str]]] = [
    ("Populations", [
        "N_RG_E", "N_RG_F", "N_MOTOR_E", "N_MOTOR_F", "N_MUS_E", "N_MUS_F",
        "N_IA_E", "N_IA_F", "N_IA_INT", "N_INE", "N_INF", "N_CUT", "N_BS",
    ]),
    ("Reciprocal inhibition (Zhang 2022 asymmetry)", [
        "W_INF2RGE", "W_INE2RGF", "W_RG2INE", "W_RG2INF",
        "P_RG_RECIP_F", "P_RG_RECIP_E",
    ]),
    ("Closed-loop Ia feedback (NEW)", [
        "W_IA2IN", "P_IA2IN", "W_IA_IN2INT", "W_IA_INT2ANT",
    ]),
    ("Cutaneous reflex", [
        "CUT_RATE_ON_HZ", "CUT_RATE_OFF_HZ",
    ]),
    ("Commissural L↔R", [
        "W_COMM_F_INH", "P_COMM_F", "W_COMM_E_INH", "P_COMM_E",
    ]),
    ("Brainstem drive", [
        "BS_REGULAR_HZ", "BS_RATE_BASE_HZ", "BS_NOISE_STD_HZ",
    ]),
    ("Izhikevich neurons", [
        "RGF_A", "RGF_B", "RGF_C", "RGF_D", "I_E_RGE", "I_E_RGF",
    ]),
    ("STDP plasticity", [
        "TAU_PLUS", "LAMBDA", "ALPHA", "MU_PLUS", "MU_MINUS", "WMAX", "WMAX_BS",
    ]),
    ("Activation + force (Hill-like proxies)", [
        "TAU_ACT_RISE_MS", "TAU_ACT_DECAY_MS", "ACT_SAT_K", "ACT_GATE_POWER", "ACT_MAX",
        "TAU_FORCE_RISE_MS", "TAU_FORCE_DECAY_MS", "FORCE_MAX", "FORCE_SAT_K",
        "TAU_LENGTH_MS", "L0", "SHORTEN_GAIN", "STRETCH_GAIN",
    ]),
    ("Ia spindle rate-coding (NEW)", [
        "IA_BASE_HZ", "IA_K_FORCE", "IA_K_STRETCH", "IA_RATE_MAX_HZ",
    ]),
]


def _parse_constants(src_path: str) -> Dict[str, str]:
    """Extract NAME = VALUE definitions from the model file (top-level only)."""
    out: Dict[str, str] = {}
    rgx = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.+?)(?:\s*#.*)?$")
    in_function = False
    indent_depth = 0
    with open(src_path) as f:
        for line in f:
            # Detect function entry/exit (top-level only)
            stripped = line.rstrip("\n")
            if re.match(r"^def\s", stripped):
                in_function = True
                continue
            if in_function and stripped and not stripped.startswith((" ", "\t")):
                in_function = False
            if in_function:
                continue
            m = rgx.match(stripped)
            if not m:
                continue
            name = m.group(1)
            val = m.group(2).strip().rstrip(",")
            # Strip trailing inline expressions like " // 2"
            out[name] = val
    return out


def _fmt_value(v: str) -> str:
    """Pretty-print a value: 'np.pi' → 'π', strip unnecessary '.0', etc."""
    v = v.strip()
    if v.endswith(".0"):
        v = v[:-2]
    return v


def _render_markdown(sections: List[Tuple[str, List[Tuple[str, str, str, str, str]]]]) -> str:
    lines = ["# tinyCPG parameter table", ""]
    for cat_name, rows in sections:
        lines.append(f"## {cat_name}")
        lines.append("")
        lines.append("| Parameter | Value | Units | Description | Source |")
        lines.append("|---|---|---|---|---|")
        for name, val, units, desc, src in rows:
            lines.append(f"| `{name}` | {val} | {units} | {desc} | {src} |")
        lines.append("")
    return "\n".join(lines)


def _render_latex(sections: List[Tuple[str, List[Tuple[str, str, str, str, str]]]]) -> str:
    out = [r"% Auto-generated by cpg_param_table.py",
           r"\begin{table}[ht]",
           r"\centering",
           r"\caption{Parameters of the tinyCPG spinal CPG model.}",
           r"\label{tab:params}",
           r"\begin{tabular}{llll p{4.5cm} l}",
           r"\hline",
           r"\textbf{Parameter} & \textbf{Value} & \textbf{Units} & \textbf{Description} & \textbf{Source} \\",
           r"\hline"]
    for cat_name, rows in sections:
        out.append(r"\multicolumn{5}{l}{\textit{" + cat_name + r"}} \\")
        for name, val, units, desc, src in rows:
            esc = lambda s: s.replace("_", r"\_").replace("&", r"\&").replace("→", r"$\to$")
            out.append(f"  {esc(name)} & {esc(val)} & {esc(units)} & {esc(desc)} & {esc(src)} \\\\")
        out.append(r"\hline")
    out.extend([r"\end{tabular}", r"\end{table}"])
    return "\n".join(out)


def _render_csv(sections: List[Tuple[str, List[Tuple[str, str, str, str, str]]]]) -> str:
    out = ["category,parameter,value,units,description,source"]
    for cat_name, rows in sections:
        for name, val, units, desc, src in rows:
            # Escape commas/quotes by quoting fields with commas
            esc = lambda s: f'"{s}"' if ("," in s or '"' in s) else s
            out.append(",".join([esc(cat_name), esc(name), esc(val), esc(units), esc(desc), esc(src)]))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=str, default="cpg_2legs_fast.py")
    ap.add_argument("--format", choices=["md", "latex", "csv"], default="md")
    ap.add_argument("--out", type=str, default="-",
                    help="Output file path or '-' for stdout.")
    args = ap.parse_args()

    constants = _parse_constants(args.src)

    # Build per-section rows; warn about parameters listed in CATEGORIES but
    # missing from source (or vice-versa).
    sections: List[Tuple[str, List[Tuple[str, str, str, str, str]]]] = []
    seen_names = set()
    for cat_name, names in CATEGORIES:
        rows = []
        for n in names:
            if n not in constants:
                print(f"[warn] {n} listed in CATEGORIES but not found in {args.src}",
                      file=sys.stderr)
                continue
            units, desc, src = PARAM_META.get(n, ("?", "?", "—"))
            rows.append((n, _fmt_value(constants[n]), units, desc, src))
            seen_names.add(n)
        sections.append((cat_name, rows))

    # Report constants not categorized (so we can decide whether to add them)
    extra = sorted(set(constants.keys()) - seen_names)
    if extra:
        print(f"[info] {len(extra)} constants not in any category (skipped): {extra[:10]}"
              + ("..." if len(extra) > 10 else ""), file=sys.stderr)

    if args.format == "md":
        text = _render_markdown(sections)
    elif args.format == "latex":
        text = _render_latex(sections)
    else:
        text = _render_csv(sections)

    if args.out == "-":
        sys.stdout.write(text + "\n")
    else:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(f"[param-table] wrote {args.out} ({args.format})", file=sys.stderr)


if __name__ == "__main__":
    main()
