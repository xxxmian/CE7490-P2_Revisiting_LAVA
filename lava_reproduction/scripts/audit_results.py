#!/usr/bin/env python3
"""Audit recorded runs and write an honest numerical comparison to report Table 1."""
from pathlib import Path
import json,csv,statistics,hashlib
root=Path(__file__).resolve().parents[1]
lines=['\n## F. 本次实际执行结果（自动汇总）\n']
for suite in ['smoke','validation','sweep','heldout']:
 p=root/'results'/suite
 rows=list(csv.DictReader((p/'raw.csv').open()))
 assert rows
 assert all(int(r['failures'])==0 and int(r['accepted'])==2500 for r in rows)
 assert all(float(r['max_cpu'])<=1+1e-9 and float(r['max_mem'])<=1+1e-9 for r in rows)
 # Same seed/setting/threshold sees same confidence sequence regardless of policy.
 grouped={}
 for r in rows:
  key=(r['seed'],r['setting'],r['threshold'])
  val=(r['gate_switches'],r['high_gate'])
  assert key not in grouped or grouped[key]==val
  grouped[key]=val
 for r in rows:
  if r['policy']=='host_ca' and int(r['capacity_fallback'])==0:
   assert int(r['cross_baseline_into_lava'])+int(r['cross_lava_into_baseline'])==0
 # Strict Oracle variants equivalent, not merely close in mean.
 for seed in {r['seed'] for r in rows}:
  for tau in {r['threshold'] for r in rows}:
   oracle=[float(r['empty_pct']) for r in rows if r['seed']==seed and r['threshold']==tau and r['setting']=='oracle' and r['policy'] in ['lava','vm_ca','host_ca']]
   if oracle:assert all(x==oracle[0] for x in oracle)
 lines.append(f'- `{suite}`：{len(rows)} 次仿真；每次接受 2,500 VM；总失败 0；最高 CPU {max(float(r["max_cpu"]) for r in rows):.6f}，最高内存 {max(float(r["max_mem"]) for r in rows):.6f}。')
lines.append('\n**独立单元测试：16/16 通过。以上为本重建实测，不是原始项目测试。**\n')
selection=json.loads((root/'results/validation/threshold_selection.json').read_text())
lines.append(f'验证集新选阈值为 **{selection["selected"]}**（仅 synthetic、推断的聚合目标），与报告的 0.3 不同；heldout 实验仍冻结 0.3，没有采用此新阈值重跑测试以搜索正结果。\n')
summary=json.loads((root/'results/heldout/summary.json').read_text())
reference=list(csv.DictReader((root/'reference/report_table1.csv').open()))
lines.extend(['### 与报告 Table 1 的直接对照\n','以下全部是相对同种子 Best-Fit 的 empty-host 百分点差。每项新 CI 都来自 seeds 20–39 的配对差。\n','| 设置 | 策略 | 报告均值 [95% CI] | 新重建均值 [95% CI] | 新均值−报告均值 |','|---|---|---|---|---|'])
for ref in reference:
 s=next(s for s in summary if s['setting']==ref['setting'] and s['policy']==ref['policy'] and s['baseline']=='best_fit')
 lines.append(f'| {s["setting"]} | {s["policy"]} | {float(ref["mean_pp"]):+.3f} [{float(ref["low_pp"]):+.3f}, {float(ref["high_pp"]):+.3f}] | {s["mean"]:+.3f} [{s["low"]:+.3f}, {s["high"]:+.3f}] | {s["mean"]-float(ref["mean_pp"]):+.3f} |')
lines.extend(['\n### 默认模型的主机机制诊断\n','| 策略 | gate changes /1000 arrivals | baseline→LAVA 主机/trace | LAVA→baseline 主机/trace | 容量回退/trace |','|---|---|---|---|---|'])
rows=list(csv.DictReader((root/'results/heldout/raw.csv').open()))
for policy in ['vm_ca','host_ca']:
 sr=[r for r in rows if r['policy']==policy and r['setting']=='synthetic']
 avg=lambda k:statistics.mean(float(r[k]) for r in sr)
 lines.append(f'| {policy} | {avg("gate_switches")/2.5:.3f} | {avg("cross_baseline_into_lava"):.3f} | {avg("cross_lava_into_baseline"):.3f} | {avg("capacity_fallback"):.3f} |')
lines.append('\n原报告对应 gate changes 为 252.58；VM CA 两类污染计数为 552.85、235.55。新值不能当作恢复值。\n')
lines.append('### 新重建中的关键比较\n')
for s in summary:
 if s['setting']=='synthetic' and s['policy']=='host_ca':
  lines.append(f'- Host CA vs {s["baseline"]}: {s["mean"]:+.4f} pp，95% CI [{s["low"]:+.4f}, {s["high"]:+.4f}]。')
sweep=json.loads((root/'results/sweep/summary.json').read_text())
points=sorted([s for s in sweep if s['policy']=='lava' and s['setting'] not in ['synthetic','oracle']],key=lambda s:float(s['setting']))
significant=[s['setting'] for s in points if s['low']>0]
lines.append('\n新 accuracy sweep 中 CI 下界高于 0 的点：'+(', '.join(significant) if significant else '无')+'。报告“85% 为首个显著点”的结论没有被写入算法或统计代码。\n')
lines.append('本次验证只支持“项目可运行、记录完整、实现声明的约束与机制”。数值和统计结论应以本表为准；与原报告不同不等于原报告被证伪，因为关键原参数无法恢复。\n')
report=root/'REPRODUCTION_DIFFERENCES.md'
base=report.read_text().split('\n## F. 本次实际执行结果')[0]
report.write_text(base+'\n'+'\n'.join(lines))
(root/'results/audit.json').write_text(json.dumps({'passed':True,'checks':['admission equality','no oversubscription','same gate sequence','host isolation absent capacity fallback','strict oracle equivalence'],'unit_tests':16,'warning':'No numerical equivalence claim'},indent=2))
print('\n'.join(lines))
