#!/usr/bin/env python3
"""Assess discovered optimizations against unchanged real programs; never run timing trials."""
import argparse
import importlib.util
import json
import logging
import signal
import sys
from pathlib import Path
import optimize_program as optimizer

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'real-programs.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append')
    parser.add_argument('--frozen-configuration', action='store_true')
    parser.add_argument('--stack-addresses-unobserved', action='store_true')
    parser.add_argument('--verify', action='store_true', help='one selected-entry equivalence check, no timing trials')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    repo = ROOT.parents[1]
    old_repo = manifest['flags'][manifest['flags'].index('-I')+1].rsplit('/runtime-testing/include',1)[0]
    flags = [f.replace(old_repo, str(repo)) for f in manifest['flags']]
    clang = optimizer.find_clang()
    benchmark = verifier = None
    if args.verify:
        spec = importlib.util.spec_from_file_location('benchmark',ROOT/'source_level_opt/support/benchmark_helpers.py')
        benchmark = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(benchmark)
        sys.path.insert(0,str(repo/'c2rust_translation'))
        import verify_equivalence as verifier
        logging.getLogger('angr').setLevel(logging.ERROR)
        logging.getLogger('cle').setLevel(logging.ERROR)
        signal.signal(signal.SIGALRM,benchmark.timeout_handler)
    args.output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for case in manifest['cases']:
        if args.case and case['id'] not in args.case:
            continue
        directory=args.output/case['id'];directory.mkdir(exist_ok=True)
        row={'id':case['id'],'expected':case['expected_instructions'],
             'frozen_configuration':args.frozen_configuration,
             'stack_addresses_unobserved':args.stack_addresses_unobserved}
        try:
            source=ROOT/'cases'/(case['id']+'.bpf.c')
            # Manifest selects the comparison family and original build context.
            # No recipe, target count, case ID or entry enters candidate discovery.
            passes=['invariant_bound'] if case.get('requirement') else ['local_alignment','map_alignment']
            build_flags=flags+['-iquote',str(repo/case['original_directory'])]
            data, report=optimizer.optimize(source,build_flags,clang,passes,
                args.frozen_configuration,args.stack_addresses_unobserved)
            (directory/'companion.bpf.c').write_bytes(data)
            (directory/'discovery.json').write_text(json.dumps(report,indent=2)+'\n')
            row['actual']=[report['baseline_slots'],report['optimized_slots']]
            row['matches_expected']=row['actual']==row['expected']
            row['code_changed']=report['executable_code_changed']
            if args.verify:
                left,right=directory/'original.o',directory/'optimized.o'
                optimizer.compile_code(source.read_bytes(),source,build_flags,clang,left)
                optimizer.compile_code(data,source,build_flags,clang,right)
                with (directory/'equivalence.log').open('w') as log:
                    benchmark.verify_pair(verifier,left,right,case['entry'],'equivalence',manifest['timeout_seconds'],log)
                row['equivalence']='passed for selected entry'
            else:
                row['equivalence']='not run'
        except Exception as error:
            row['error']=f'{type(error).__name__}: {error}'
        rows.append(row)
        (args.output/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(json.dumps(row),flush=True)
    return 0 if rows and all('error' not in r for r in rows) else 1


if __name__=='__main__':
    raise SystemExit(main())
