#!/usr/bin/env python3
"""Create focused figures from recorded NEW data, never report reference values."""
from pathlib import Path
import sys,json,csv,statistics,html
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lava.charts import plot
root=Path(__file__).resolve().parents[1]
out=root/'results/figures';out.mkdir(exist_ok=True)
sweep=json.loads((root/'results/sweep/summary.json').read_text())
curve=sorted([r for r in sweep if r['policy']=='lava' and r['setting'] not in ['oracle','synthetic']],key=lambda r:float(r['setting']))
plot(curve,out/'accuracy_sweep.svg','RECONSTRUCTION: LAVA accuracy sweep, seeds 0-19, paired 95% CI')
heldout=json.loads((root/'results/heldout/summary.json').read_text())
plot([r for r in heldout if r['setting']=='synthetic' and r['policy'] in ['lava','vm_ca','host_ca']],out/'default_predictor.svg','RECONSTRUCTION: default predictor, seeds 20-39, paired 95% CI')
validation=json.loads((root/'results/validation/summary.json').read_text())
vr=[dict(r,setting=f'tau={r["threshold"]}') for r in validation if r['policy']=='host_ca' and r['baseline']=='lava']
plot(vr,out/'threshold_ablation.svg','RECONSTRUCTION: threshold validation, seeds 200-205 only')
rows=list(csv.DictReader((root/'results/heldout/raw.csv').open()))
values=[]
for policy in ['vm_ca','host_ca']:
 sr=[r for r in rows if r['policy']==policy and r['setting']=='synthetic']
 for field,label in [('cross_baseline_into_lava','Baseline to LAVA host'),('cross_lava_into_baseline','LAVA to baseline host')]:
  values.append((policy+' | '+label,statistics.mean(float(r[field]) for r in sr)))
scale=max(1,max(v for _,v in values));s=['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="310"><rect width="100%" height="100%" fill="white"/>','<text x="20" y="30" font-family="sans-serif" font-size="18">RECONSTRUCTION: mean cross-mode placements per 2,500-VM trace</text>']
for i,(label,value) in enumerate(values):
 y=65+50*i
 s.extend([f'<text x="20" y="{y+16}" font-family="sans-serif" font-size="14">{html.escape(label)}</text>',f'<rect x="400" y="{y}" width="{480*value/scale}" height="25" fill="#267a89"/>',f'<text x="{410+480*value/scale}" y="{y+17}" font-family="sans-serif" font-size="14">{value:.2f}</text>'])
s.append('<text x="400" y="295" font-family="sans-serif" font-size="13">Counts (not confidence intervals); held-out seeds 20-39</text></svg>')
(out/'contamination.svg').write_text('\n'.join(s))
print(out)
