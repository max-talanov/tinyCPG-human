#!/usr/bin/env python3
"""
species_config.py
Loader for the YAML species configurations (PLAN.md Phase 1, decisions D1, D2,
D6, D7). Used by cpg_2legs_fast.py; also runnable on its own to inspect or
validate the configs.

Layout (relative to this file):
  config/species/<name>.yaml   one file per species / profile (--species <name>),
                               including its conduction + synaptic delays

Rules:
  * A species file MUST contain its `delays:` section (model, jitter_ms, the
    full per-path table). Delays live in the same file as the species, so a
    species can never be combined with another species' delays (D2);
    --delay-model on the CLI is only accepted if it matches.
  * `extends: <other>.yaml` inherits another species file; mappings are merged
    recursively, the child wins -- a profile can override single delay paths.
    Intended for human_adult.yaml (D6, Phase 9).
  * `constants` groups UPPERCASE model constants; the groups are only for
    readability and are flattened. A name may appear once.
  * `cli_defaults` holds argparse defaults (dest names); explicit flags win.

Usage:
  python3 species_config.py rat            # print the resolved config as YAML
  python3 species_config.py --check        # validate every species file
"""
import argparse
import copy
import os
import sys

import yaml

HERE = os.path.dirname(os.path.realpath(__file__))
CONFIG_ROOT = os.path.join(HERE, "config")
SPECIES_DIR = os.path.join(CONFIG_ROOT, "species")

DELAY_MODELS = ("fixed", "length_velocity")
DELAY_PATH_KEYS = ("cut_to_rg", "bs_to_rg", "base_to_rg", "rg_to_m", "m_to_mus", "ia_path",
                   "ia_int_to_m", "rg_rec", "rg_recip", "motor_e2f", "motor_f2e", "commissural")
DELAY_FIELDS = ("syn_delay_ms", "length_m", "velocity_mps")
# A path gives its length either absolutely (length_m) or as a fraction of the
# species' body.height_m (length_frac_height; PLAN.md P2, D7) -- exactly one.
NEURON_PROFILES = ("abstract", "adult")


class ConfigError(ValueError):
    pass


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate keys. Plain YAML silently keeps the last
    one, so a stray second `model:` or path entry would override the real value
    without any error."""


def _no_duplicates(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key `{key}`", key_node.start_mark)
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


def available_species():
    if not os.path.isdir(SPECIES_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(SPECIES_DIR) if f.endswith(".yaml"))


def _read_yaml(path):
    try:
        with open(path) as fh:
            data = yaml.load(fh, Loader=_StrictLoader)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"invalid YAML in {path}: {e}")
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _load_chain(path, seen=()):
    """Load a species file and its `extends` parents (an `extends` path is
    relative to the file that declares it); parents are merged under children."""
    path = os.path.realpath(path)
    if path in seen:
        raise ConfigError(f"circular `extends`: {' -> '.join(seen + (path,))}")
    data = _read_yaml(path)
    base_dir = os.path.dirname(path)
    if "delays" in data and not isinstance(data["delays"], dict):
        raise ConfigError(f"{path}: `delays` must be the delay section itself (model, jitter_ms, "
                          f"paths), not a link to another file -- delays belong to the species file "
                          f"(PLAN.md D2)")
    chain = [path]
    parent = data.pop("extends", None)
    if parent is not None:
        pdata, pchain = _load_chain(os.path.join(base_dir, str(parent)), seen + (path,))
        data = _merge(pdata, data)
        chain = pchain + chain
    return data, chain


def _load_delays(d, path, body):
    """Validate the `delays:` section of the species file `path`; resolve
    length_frac_height against body.height_m into length_m."""
    model = d.get("model")
    if model not in DELAY_MODELS:
        raise ConfigError(f"{path}: `model` must be one of {DELAY_MODELS}, got {model!r}")
    paths = d.get("paths") or {}
    if model == "length_velocity":
        missing = [k for k in DELAY_PATH_KEYS if k not in paths]
        if missing:
            raise ConfigError(f"{path}: missing delay paths {missing}")
        extra = [k for k in paths if k not in DELAY_PATH_KEYS]
        if extra:
            raise ConfigError(f"{path}: unknown delay paths {extra} (known: {list(DELAY_PATH_KEYS)})")
        resolved = {}
        for k, p in paths.items():
            if not isinstance(p, dict):
                raise ConfigError(f"{path}: path `{k}` must be a mapping")
            p = dict(p)
            if ("length_m" in p) == ("length_frac_height" in p):
                raise ConfigError(f"{path}: path `{k}` needs exactly one of length_m, length_frac_height")
            for f in ("syn_delay_ms", "velocity_mps", "length_m", "length_frac_height"):
                if f in p and (not isinstance(p[f], (int, float)) or isinstance(p[f], bool)):
                    raise ConfigError(f"{path}: {k}.{f} must be a number")
            for f in ("syn_delay_ms", "velocity_mps"):
                if f not in p:
                    raise ConfigError(f"{path}: path `{k}` needs {f}")
            if p["velocity_mps"] <= 0:
                raise ConfigError(f"{path}: {k}.velocity_mps must be > 0")
            if "length_frac_height" in p:
                h = (body or {}).get("height_m")
                if not isinstance(h, (int, float)) or isinstance(h, bool) or h <= 0:
                    raise ConfigError(f"{path}: path `{k}` uses length_frac_height but body.height_m is not set")
                p["length_m"] = float(p["length_frac_height"]) * float(h)
            r = {f: float(p[f]) for f in DELAY_FIELDS}
            if "length_frac_height" in p:
                r["length_frac_height"] = float(p["length_frac_height"])
            r["delay_ms"] = r["syn_delay_ms"] + r["length_m"] / r["velocity_mps"] * 1000.0
            resolved[k] = r
        paths = resolved
    return {"model": model, "jitter_ms": float(d.get("jitter_ms", 0.2)), "paths": paths}


def _flatten_constants(groups, source):
    flat = {}
    for group, items in (groups or {}).items():
        if not isinstance(items, dict):
            raise ConfigError(f"{source}: constants.{group} must be a mapping of NAME: value")
        for name, value in items.items():
            if not str(name).isupper():
                raise ConfigError(f"{source}: constant `{name}` must be UPPERCASE (a model constant)")
            if name in flat:
                raise ConfigError(f"{source}: constant `{name}` appears in more than one group")
            flat[name] = value
    return flat


def load_species(name=None, path=None):
    """Resolve one species configuration. Give `name` (config/species/<name>.yaml)
    or an explicit `path`; `path` wins."""
    if path is None:
        if not name:
            raise ConfigError("no species given")
        path = os.path.join(SPECIES_DIR, f"{name}.yaml")
        if not os.path.isfile(path):
            raise ConfigError(f"unknown species `{name}`: no {path} "
                              f"(available: {', '.join(available_species()) or 'none'})")
    data, chain = _load_chain(path)
    src = chain[-1]
    if not data.get("species"):
        raise ConfigError(f"{src}: `species` is required")
    if not data.get("delays"):
        raise ConfigError(f"{src}: a `delays:` section is required -- a species cannot run without "
                          f"its own delays (PLAN.md decision D2)")
    profile = data.get("neuron_profile", "abstract")
    if profile not in NEURON_PROFILES:
        raise ConfigError(f"{src}: neuron_profile must be one of {NEURON_PROFILES}")
    cli = data.get("cli_defaults") or {}
    if not isinstance(cli, dict):
        raise ConfigError(f"{src}: cli_defaults must be a mapping")
    return {
        "species": str(data["species"]),
        "description": str(data.get("description", "")),
        "neuron_profile": profile,
        "body": dict(data.get("body") or {}),
        "constants": _flatten_constants(data.get("constants"), src),
        "cli_defaults": dict(cli),
        "delays": _load_delays(data["delays"], src, data.get("body")),
        "files": {"species": src, "chain": chain},
    }


def to_yaml(cfg):
    """Resolved configuration as YAML text (paths shown relative to the repo)."""
    def rel(p):
        return os.path.relpath(p, HERE)
    out = copy.deepcopy(cfg)
    out["files"] = {"species": rel(cfg["files"]["species"]),
                    "chain": [rel(p) for p in cfg["files"]["chain"]]}
    return yaml.safe_dump(out, sort_keys=False, default_flow_style=None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("species", nargs="?", help="species name (config/species/<name>.yaml)")
    ap.add_argument("--path", help="explicit species YAML path")
    ap.add_argument("--check", action="store_true", help="validate every species file")
    args = ap.parse_args()
    if args.check:
        ok = True
        for name in available_species():
            try:
                cfg = load_species(name)
                print(f"OK    {name}: delays={cfg['delays']['model']} "
                      f"({len(cfg['delays']['paths'])} paths), {len(cfg['constants'])} constants, "
                      f"{len(cfg['cli_defaults'])} cli defaults")
            except ConfigError as e:
                ok = False
                print(f"FAIL  {name}: {e}")
        return 0 if ok else 1
    try:
        print(to_yaml(load_species(args.species, args.path)), end="")
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
