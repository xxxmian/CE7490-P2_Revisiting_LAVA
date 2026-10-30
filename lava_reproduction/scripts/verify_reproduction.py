#!/usr/bin/env python3
"""Re-simulate stored runs and compare them with results/ field by field.
Reconstruction suites (smoke, heldout, validation, sweep; 1,644 runs) are checked in full.
Improvement suites are checked on an evenly spaced sample (default 50 runs per suite; --sample -1 = all),
rebuilding each run's configuration from the suite manifest.
Integer and text fields must match exactly. Floating-point fields are compared by relative difference:
they are bit-identical on the platform that produced them and may differ in the last digits elsewhere.
Writes a plain-text log, by default results/verification_log.txt; exits non-zero on any mismatch."""
import argparse,csv,hashlib,json,platform,sys,time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from lava.model import trace
from lava.simulator import simulate
FLOATS={'threshold','empty_pct','empty_pct_arrivals','packing_density','max_cpu','max_mem','horizon'}
RECON=['smoke','heldout','validation','sweep'];IMPROVEMENT=['test','legacy','tau','robust','robust_control','robust_load']
TOL=1e-12

def check(args):
    c,row=args;seed=int(row['seed']);exact=True;bad=[];worst=0.
    out=simulate(trace(c,seed),c,seed,row['setting'],row['policy'],float(row['threshold']))
    for k,v in row.items():
        if k=='variant':continue  # bookkeeping column added by the runner, not a simulator output
        same=str(out[k])==v;exact&=same
        if k in FLOATS:
            rel=abs(out[k]-float(v))/max(1e-300,abs(float(v)));worst=max(worst,rel)
            if rel>TOL:bad.append(k)
        elif not same:bad.append(k)
    return exact,bad,worst

def sample(rows,n):
    if n<0 or n>=len(rows):return rows
    return [rows[i] for i in sorted({round(i*(len(rows)-1)/max(1,n-1)) for i in range(n)})]

def main():
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--workers',type=int,default=4);p.add_argument('--sample',type=int,default=50,help='runs per improvement suite (0 = skip, -1 = all)')
    p.add_argument('--log',default=str(root/'results/verification_log.txt'));a=p.parse_args()
    C=json.loads((root/'configs/report_scale.json').read_text());start=time.time()
    sources=sorted((root/'lava').glob('*.py'))
    lines=[f'verify_reproduction.py  {time.strftime("%Y-%m-%d %H:%M:%S %z")}',
           f'python {platform.python_version()} on {platform.platform()} ({platform.processor() or platform.machine()})',
           *[f'sha256 {f.relative_to(root)} {hashlib.sha256(f.read_bytes()).hexdigest()}' for f in sources],
           f'tolerance: integer/text fields exact; floats relative difference <= {TOL:g}','']
    failed=0
    with ProcessPoolExecutor(a.workers) as pool:
        for suite in RECON+(IMPROVEMENT if a.sample else []):
            folder=root/'results'/suite if suite in RECON else root/'results/improvement'/suite
            stored=list(csv.DictReader((folder/'raw.csv').open()));rows=stored if suite in RECON else sample(stored,a.sample)
            if suite in RECON:tasks=[(C,r) for r in rows]
            else:
                m=json.loads((folder/'manifest.json').read_text())
                tasks=[(dict(m['base_config'],**m['variants'][r['variant']]),r) for r in rows]
            res=list(pool.map(check,tasks,chunksize=4));bad=[(r['seed'],r['setting'],r['policy'],b) for r,(_,b,_) in zip(rows,res) if b]
            failed+=len(bad);kind='all' if len(rows)==len(stored) else f'of {len(stored)}'
            lines.append(f'{suite:15s} runs={len(rows):5d} {kind:9s} bit-identical={sum(e for e,_,_ in res):5d}  '
                         f'outside tolerance={len(bad)}  worst float relative difference={max(w for *_,w in res):.1e}'+(f'  first: {bad[0]}' if bad else ''))
            print(lines[-1],flush=True)
    lines+=['',f'RESULT: {"PASS" if not failed else f"FAIL ({failed} runs outside tolerance)"}  ({time.time()-start:.0f} s, {a.workers} workers)']
    Path(a.log).write_text('\n'.join(lines)+'\n');print(lines[-1]);sys.exit(1 if failed else 0)
if __name__=='__main__':main()
