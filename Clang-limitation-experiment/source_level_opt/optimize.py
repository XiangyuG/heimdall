#!/usr/bin/env python3
"""Generate a conservative source-optimized companion from a standalone case."""
import argparse
import json
from pathlib import Path
import sys

from ast_utils import ROOT, Source
import fuse_loops
import combine_aligned_loads
import cache_invariant_bound

PASSES = {"loop_fusion": fuse_loops, "aligned_load": combine_aligned_loads,
          "invariant_bound": cache_invariant_bound}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="case filename or source path")
    parser.add_argument("--optimizer", choices=["auto", *PASSES], default="auto")
    args = parser.parse_args()
    path = Path(args.source)
    if not path.is_file():
        path = ROOT / "cases" / args.source
    try:
        if not path.is_file() or not path.name.endswith(".bpf.c") or "_SOURCE_OPT" in path.name:
            raise ValueError("expected an original .bpf.c source")
        source = Source(path)
        replacements, reports = [], {}
        for name, module in PASSES.items():
            if args.optimizer not in {"auto", name}:
                continue
            changes, skipped = module.transform(source)
            replacements.extend(changes)
            reports[name] = {"replacement_count": len(changes), "skipped": skipped}
        if not replacements:
            print(json.dumps({"source": str(path), "passes": reports}), file=sys.stderr)
            raise ValueError("no supported optimization found; no output written")
        data = source.apply(replacements)
        output = ROOT / "source_level_opt/generated" / (path.name[:-6] + "_SOURCE_OPT.bpf.c")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        print(json.dumps({"source": str(path.resolve()), "output": str(output), "passes": reports}, indent=2))
        return 0
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
