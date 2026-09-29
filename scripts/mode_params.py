#!/usr/bin/env python3
"""Print one mode of a modes YAML (config/modes/human.yaml) as shell assignments,
for run_human_modes.sh: python3 scripts/mode_params.py <modes.yaml> <mode>"""
import sys

import yaml

m = yaml.safe_load(open(sys.argv[1]))["modes"].get(sys.argv[2])
if m is None:
    print(f"echo 'unknown mode {sys.argv[2]}' >&2; exit 2")
    sys.exit(0)
fo = m["force"]
print(f"STRIDE={m['stride_ms']} STANCE={m['stance_fraction']} GAIN={m['loading']} "
      f"CAP={fo['cap_ms']} FON={fo['fatigue_onset_ms']} FREC={fo['fatigue_recovery_ms']} "
      f"LEAD={fo['lead_offset_ms']} OFF={fo['off_frac']} TAUTAG={fo['tau_tag_ms']} "
      f"SWF={fo.get('swing_end_f_frac', 0.35)} SWTAU={fo.get('swing_afferent_tau_ms', 0.0)} "
      f"ASYM={fo.get('leg_fatigue_asym_frac', 0.0)} INITFROM={m.get('init_from', '')} INITSCALE={m.get('init_scale', 1.0)} TICKM={m.get('tick_ms', '')}")
