#!/usr/bin/env python3
"""Compare original execsnoop with literal bound 20: ten alternating trials/version."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import difflib
import hashlib
import io
import json
import logging
import os
import signal
import statistics
import subprocess
import sys
import time
import traceback

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[1]
REPO = ROOT.parents[1]
sys.dont_write_bytecode = True
sys.setrecursionlimit(20000)
sys.path.insert(0, str(ROOT / 'source_level_opt/support'))
sys.path.insert(0, str(REPO / 'c2rust_translation'))
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/heimdall-clang-limitation-mpl')
import benchmark_helpers as helper
VARIANTS = ('original_self', 'literal20_self')
ENTRY = 'tracepoint__syscalls__sys_enter_execve'
TRIALS = 10

def now(): return datetime.now(timezone.utc).isoformat()
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(state):
    temp = OUTPUT / '.checkpoint.json'
    temp.write_text(json.dumps(state, indent=2) + '\n'); temp.replace(OUTPUT / 'checkpoint.json')
    with (OUTPUT / 'raw_trials.csv').open('w', newline='') as stream:
        fields = ['trial', 'variant', 'started_utc', 'status', 'seconds', 'error']
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(state['measurements'])

def summarize(state):
    result = {'trials_per_version': TRIALS, 'variants': {}}
    for variant in VARIANTS:
        ms = [m for m in state['measurements'] if m['variant'] == variant]
        samples = [m['seconds'] for m in ms if m['status'] == 'success']
        row = {'attempts': len(ms), 'successful': len(samples), 'failures': [m for m in ms if m['status'] != 'success'], 'raw_seconds': samples}
        if samples:
            row.update(median=statistics.median(samples), mean=statistics.mean(samples),
                       stdev=statistics.stdev(samples) if len(samples) > 1 else 0, minimum=min(samples), maximum=max(samples))
        result['variants'][variant] = row
    if all(result['variants'][v].get('successful') for v in VARIANTS):
        a,b = [result['variants'][v]['median'] for v in VARIANTS]
        result.update(reduction_percent=100*(1-b/a), speedup=a/b)
        if all(result['variants'][v]['successful'] == TRIALS for v in VARIANTS):
            result['reduction_ci95_percent'] = helper.bootstrap_reduction(*[result['variants'][v]['raw_seconds'] for v in VARIANTS])
    (OUTPUT / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    return result

def plots_and_report(state):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    summary=summarize(state)
    rows=[summary['variants'][v] for v in VARIANTS]
    if all(r.get('successful') for r in rows):
        medians=[r['median'] for r in rows]; sds=[r['stdev'] for r in rows]
        fig,ax=plt.subplots(figsize=(9,6))
        ax.bar([0,1],medians,width=.6,color=['#4472C4','#2A9D8F'],yerr=sds,capsize=5)
        upper=max(max(r['raw_seconds']) for r in rows)
        for i,r in enumerate(rows):
            xs=[i+(((k*37)%101)/100-.5)*.3 for k in range(len(r['raw_seconds']))]
            ax.scatter(xs,r['raw_seconds'],color='black',alpha=.4,s=18,zorder=3)
            ax.text(i,max(max(r['raw_seconds']),r['median']+r['stdev'])+upper*.035,
                    f"Median {r['median']:.4f} s\nSD {r['stdev']:.4f} s",ha='center',va='bottom')
        ax.set_xticks([0,1],[f"Original + Clang -O2\n{rows[0]['successful']}/10 successful",f"Literal bound 20 + Clang -O2\n{rows[1]['successful']}/10 successful"])
        ax.set_ylabel('Heimdall self-verification time (seconds)')
        ax.set_title('execsnoop: original vs literal loop bound 20\nBars: median; whiskers: +/-1 sample SD (not confidence intervals)')
        ax.set_ylim(0,max(upper,max(m+s for m,s in zip(medians,sds)))*1.25)
        ax.grid(axis='y',linestyle=':',alpha=.4); ax.set_axisbelow(True)
        fig.text(.5,.015,'Specialized to max_args = 20. Failed attempts are not assigned a runtime.',ha='center',fontsize=9)
        fig.tight_layout(rect=[0,.04,1,1]); fig.savefig(OUTPUT/'runtime.png',dpi=180); fig.savefig(OUTPUT/'runtime.svg'); plt.close(fig)
        fig,ax=plt.subplots(figsize=(8,4.8))
        for variant,label,color in zip(VARIANTS,['Original','Literal 20'],['#4472C4','#2A9D8F']):
            ms=[m for m in state['measurements'] if m['variant']==variant]
            ax.plot([m['trial'] for m in ms],[m['seconds'] if m['status']=='success' else float('nan') for m in ms],marker='o',label=label,color=color)
        ax.set_xlabel('Paired trial number');ax.set_ylabel('Verification time (seconds)');ax.set_title('All successful runtimes in trial order')
        ax.set_xticks(range(1,11));ax.legend();ax.grid(linestyle=':',alpha=.4);fig.tight_layout()
        fig.savefig(OUTPUT/'trial-trends.png',dpi=180);fig.savefig(OUTPUT/'trial-trends.svg');plt.close(fig)
    lines=['# execsnoop: original vs literal bound 20','',
           'Ten alternating timed trials per version after one warmup per version. Timing uses the existing benchmark_helpers.verify_pair and verify_equivalence.run_verification, excluding imports, compilation, garbage collection and log writes. Both new objects use identical Clang -O2 flags. The configured timeout remains 60 seconds; it is an alarm, not assumed to be a strict wall-time cap. No failed trial is replaced and no outlier is removed. This comparison is original versus literal 20, not cached max_args versus literal 20.','',
           'The only C source edit replaces `i < TOTAL_MAX_ARGS && i < max_args` with `i < 20`; the loop body and #pragma unroll are preserved. The source and ELF initializer for max_args are checked to equal 20. This is configuration specialization: equivalence requires max_args = 20, and does not cover loader overrides to other values. No extra verifier witness or input constraints are introduced. An equivalence check in this model does not prove that external loader contract.','',
           '| Version | Successful attempts | Median seconds | Sample SD seconds | BPF instruction slots (all executable sections) |','|---|---:|---:|---:|---:|']
    for variant,label in zip(VARIANTS,['Original','Literal bound 20']):
        r=summary['variants'][variant]
        lines.append(f"| {label} | {r['successful']}/{TRIALS} | {r.get('median','unavailable')} | {r.get('stdev','unavailable')} | {state.get('objects',{}).get(variant,{}).get('instruction_slots','unavailable')} |")
    if 'reduction_percent' in summary:
        lines+=['',f"Successful-run median reduction: {summary['reduction_percent']:.2f}% (negative means slower). Speedup ratio: {summary['speedup']:.3f}x."]
    if 'reduction_ci95_percent' in summary:
        lines += [f"Paired bootstrap 95% interval for median reduction (10,000 resamples): {summary['reduction_ci95_percent']}. Ten pairs are a small sample; this interval does not establish stationarity or independent timing observations."]
    if state.get('preparation_error'): lines+=['','Preparation failed; inspect checkpoint.json and verification.log. No timed measurements were fabricated.']
    lines+=['',f"Started {state['started_utc']}; finished {state.get('finished_utc','not finished')}. Full compiler invocation, hashes, preparation results and raw errors are saved in checkpoint.json. Existing sources, binaries and prior results are unchanged."]
    (OUTPUT/'REPORT.md').write_text('\n'.join(lines)+'\n')

def main():
    if '--plots-only' in sys.argv:
        plots_and_report(json.loads((OUTPUT/'checkpoint.json').read_text()));return 0
    if (OUTPUT/'checkpoint.json').exists(): raise SystemExit('Saved measurements exist; inspect them before any resume. No automatic reruns.')
    manifest=json.loads((ROOT/'real-programs.json').read_text())
    case=next(c for c in manifest['cases'] if c['id']=='execsnoop_bound')
    original=ROOT/'cases/execsnoop_bound.bpf.c'
    source=original.read_text()
    assert digest(original)==case['baseline_sha256']
    old='i < TOTAL_MAX_ARGS && i < max_args'
    assert source.count(old)==1 and '#define DEFAULT_MAXARGS 20' in source
    rewritten=source.replace(old,'i < 20')
    paths={'original_self':OUTPUT/'execsnoop_original.bpf.c','literal20_self':OUTPUT/'execsnoop_literal20.bpf.c'}
    paths['original_self'].write_text(source);paths['literal20_self'].write_text(rewritten)
    (OUTPUT/'optimization.patch').write_text(''.join(difflib.unified_diff(source.splitlines(True),rewritten.splitlines(True),fromfile='execsnoop_original.bpf.c',tofile='execsnoop_literal20.bpf.c')))
    clang=helper.find_clang()
    old_repo=manifest['flags'][manifest['flags'].index('-I')+1].rsplit('/runtime-testing/include',1)[0]
    flags=[f.replace(old_repo,str(REPO)) for f in manifest['flags']]
    state={'started_utc':now(),'trials_per_version':TRIALS,'entry':ENTRY,'timeout_seconds':manifest['timeout_seconds'],
           'contract':'max_args = 20 for both versions','compiler':subprocess.check_output([clang,'--version'],text=True),
           'flags':flags,'baseline_path':str(original),'baseline_sha256':digest(original),'objects':{},'preparation':[],'measurements':[]}
    save(state)
    from elftools.elf.elffile import ELFFile
    for variant,path in paths.items():
        obj=path.with_suffix('.o')
        cmd=[clang,*flags,'-iquote',str(REPO/case['original_directory']),'-x','c','-c','-o',str(obj),'-']
        compile_result=subprocess.run(cmd,input=path.read_text(),text=True,capture_output=True)
        (OUTPUT/(variant+'_compile.log')).write_text(compile_result.stdout+compile_result.stderr)
        if compile_result.returncode: raise RuntimeError(compile_result.stderr)
        assert ENTRY in helper.entries(obj)
        with obj.open('rb') as stream:
            elf=ELFFile(stream);symbol=next(s for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name=='max_args')
            data=elf.get_section(symbol['st_shndx']).data(); offset=symbol['st_value']
            assert int.from_bytes(data[offset:offset+4],'little',signed=True)==20
        state['objects'][variant]={'path':str(obj),'sha256':digest(obj),'source_sha256':digest(path),'command':cmd,
                                    'instruction_slots':sum(len(code)//8 for code in helper.executable_code(obj).values()),'max_args_initializer':20}
        save(state)
    import verify_equivalence as verifier
    logging.getLogger('angr').setLevel(logging.ERROR);logging.getLogger('cle').setLevel(logging.ERROR)
    signal.signal(signal.SIGALRM,helper.timeout_handler)
    a,b=[Path(state['objects'][v]['path']) for v in VARIANTS]
    with (OUTPUT/'verification.log').open('a') as log:
        try:
            for label,left,right in [('equivalence_original_literal20',a,b),('warmup_original',a,a),('warmup_literal20',b,b)]:
                seconds=helper.verify_pair(verifier,left,right,ENTRY,label,state['timeout_seconds'],log)
                state['preparation'].append({'label':label,'status':'success','seconds':seconds});save(state)
                print(json.dumps(state['preparation'][-1]),flush=True)
        except Exception:
            state['preparation_error']=traceback.format_exc();state['finished_utc']=now();save(state);plots_and_report(state)
            print(state['preparation_error'],flush=True);return 1
        for trial in range(1,TRIALS+1):
            for variant in (VARIANTS if trial%2 else VARIANTS[::-1]):
                item={'trial':trial,'variant':variant,'started_utc':now(),'status':'success','seconds':None,'error':''}
                obj=Path(state['objects'][variant]['path']);assert digest(obj)==state['objects'][variant]['sha256']
                try: item['seconds']=helper.verify_pair(verifier,obj,obj,ENTRY,f'trial_{trial}_{variant}',state['timeout_seconds'],log)
                except Exception as error:
                    item['status']='timeout' if isinstance(error,TimeoutError) else 'failed';item['error']=f'{type(error).__name__}: {error}'
                state['measurements'].append(item);save(state);print(json.dumps(item),flush=True)
            summarize(state)
    state['finished_utc']=now();save(state);plots_and_report(state)
    print(f"Finished: {OUTPUT/'REPORT.md'}",flush=True)
    return 0
if __name__=='__main__': raise SystemExit(main())
