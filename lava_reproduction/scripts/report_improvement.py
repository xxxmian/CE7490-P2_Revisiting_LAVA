#!/usr/bin/env python3
"""Regenerate the measured-results section of IMPROVEMENT.md from recorded data."""
from pathlib import Path
import json,csv,statistics,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lava.stats import paired_diffs,t_test
root=Path(__file__).resolve().parents[1];res=root/'results/improvement'
load=lambda s:json.loads((res/s/'summary.json').read_text())
test,legacy,tau,robust=load('test'),load('legacy'),load('tau'),load('robust');control,heavy=load('robust_control'),load('robust_load')
ACC=['0.25','0.5','0.75','0.85','1.0'];NAME={'best_fit':'Best-Fit','la_binary':'LA-Binary','nilas':'NILAS','lava':'LAVA','vm_ca':'VM-CA','host_ca':'Host-CA',
 'nilas_bayes':'NILAS-Bayes','lava_bayes':'LAVA-Bayes','vm_ca_bayes':'VM-CA-Bayes','host_ca_bayes':'Host-CA-Bayes'}
def pick(rows,policy,baseline,setting,metric='empty_pct',**kw):
    return next(r for r in rows if r['policy']==policy and r['baseline']==baseline and r['setting']==setting and r['metric']==metric and all(r[k]==v for k,v in kw.items()))
def ci(r,digits=3):return f"{r['mean']:+.{digits}f} [{r['low']:+.{digits}f}, {r['high']:+.{digits}f}]"
def bold(r,text):return f'**{text}**' if r['low']>0 else text
def gate(suite,variant='protocol'):
    rows=list(csv.DictReader((res/suite/'raw.csv').open()));out={}
    for r in rows:
        if r['variant']==variant:out.setdefault((r['setting'],r['policy']),[]).append(int(r['high_gate'])/int(r['accepted']))
    return {k:100*statistics.mean(v) for k,v in out.items()}
SUITES=['test','legacy','tau','robust','robust_control','robust_load']
manifest={s:json.loads((res/s/'manifest.json').read_text()) for s in SUITES}
fails=sum(int(r['failures']) for s in SUITES for r in csv.DictReader((res/s/'raw.csv').open()))
L=['\n## 6. 实测结果（由 `scripts/report_improvement.py` 自动生成，请勿手改）\n']
L.append('运行环境：'+'；'.join(f"`{s}` {m['runs']} 次仿真、{m['n_seeds']} 个种子、{m['elapsed_s']:.0f} s（{m['workers']} 进程，{m['platform'].split('-with')[0]}，Python {m['python']}，{m['cpus']} 逻辑 CPU）" for s,m in manifest.items())+f'。合计 {sum(m["runs"] for m in manifest.values()):,} 次仿真，所有运行接受全部 VM，调度失败为 {fails}。`robust_control`、`robust_load` 是评审后补跑的描述性实验（`scripts/run_robust_extra.py`），复用未改动的注册代码。\n')
L+=['### 6.1 预注册主假设族（seeds 1000–1099，n=100，Holm 校正）\n','| 准确率 | VM-CA-Bayes − LAVA，pp [95% CI] | Holm p | VM-CA-Bayes − Best-Fit，pp [95% CI] | Holm p | 预注册判定 |','|---|---|---|---|---|---|']
for s in ACC[:4]:
    a,b=pick(test,'vm_ca_bayes','lava',s),pick(test,'vm_ca_bayes','best_fit',s)
    verdict='；'.join(f"{'优于' if r['mean']>0 and r['p_holm']<.05 else '未证实优于'} {n}" for r,n in [(a,'LAVA'),(b,'Best-Fit')])
    L.append(f"| {s} | {bold(a,ci(a))} | {a['p_holm']:.2g} | {bold(b,ci(b))} | {b['p_holm']:.2g} | {verdict} |")
L+=['\n### 6.2 全部策略相对 Best-Fit（seeds 1000–1099，n=100）\n','加粗表示 95% CI 下界大于 0。\n']
pols=['lava','nilas','vm_ca','host_ca','nilas_bayes','lava_bayes','vm_ca_bayes','host_ca_bayes']
L+=['| 设置 | '+' | '.join(NAME[p] for p in pols)+' |','|---|'+'---|'*len(pols)]
for s in ACC+['synthetic','oracle']:L.append(f'| {s} | '+' | '.join(bold(r,ci(r)) for r in [pick(test,p,'best_fit',s) for p in pols])+' |')
L+=['\n### 6.3 只换预测器：*-Bayes 相对其原策略（同一调度规则，n=100）\n','| 准确率 | NILAS-Bayes − NILAS | LAVA-Bayes − LAVA | VM-CA-Bayes − VM-CA | Host-CA-Bayes − Host-CA |','|---|---|---|---|---|']
for s in ACC:L.append(f'| {s} | '+' | '.join(bold(r,ci(r)) for r in [pick(test,b,b[:-6],s) for b in ['nilas_bayes','lava_bayes','vm_ca_bayes','host_ca_bayes']])+' |')
g=gate('test')
L+=['\n### 6.4 门控通过率（τ=0.3，走 LAVA 路由的到达占比）\n','| 准确率 | VM-CA（原置信度） | VM-CA-Bayes（融合后验置信度） |','|---|---|---|']
for s in ACC+['synthetic']:L.append(f"| {s} | {g[(s,'vm_ca')]:.1f}% | {g[(s,'vm_ca_bayes')]:.1f}% |")
L+=['\n### 6.5 时间窗口分解（诊断，n=100）\n','`empty_pct_arrivals` 只积分首次到达至最后一次到达；`empty_pct` 是包含排空尾段的主指标。\n','| 比较 | 设置 | 到达窗口 | 全程（主指标） |','|---|---|---|---|']
for p,b,s in [('host_ca','best_fit','synthetic'),('host_ca','vm_ca','synthetic'),('host_ca_bayes','vm_ca_bayes','0.5'),('vm_ca_bayes','lava','0.25'),('vm_ca_bayes','lava','0.5'),('vm_ca_bayes','lava','0.85')]:
    L.append(f"| {NAME[p]} − {NAME[b]} | {s} | {ci(pick(test,p,b,s,'empty_pct_arrivals'))} | {ci(pick(test,p,b,s))} |")
L+=['\n### 6.6 鲁棒性（seeds 2000–2049，n=50，VM-CA-Bayes；仅描述）\n','第一组是同一批种子上未改动的协议（对照），最后一组是到达率加倍（16 VM/h、5,000 个 VM）。\n','| 变体 | 准确率 | − LAVA | − Best-Fit | 门控通过率 |','|---|---|---|---|---|']
rob=[('protocol（同种子对照）',control,'robust_control','protocol')]+[(v,robust,'robust',v) for v in manifest['robust']['variants'] if v!='hosts=90']+[('arrival_x2（负载 ×2）',heavy,'robust_load','arrival_x2')]
for label,rows,suite,v in rob:
    gv=gate(suite,v)
    for s in ACC[:4]:
        a,b=pick(rows,'vm_ca_bayes','lava',s,variant=v),pick(rows,'vm_ca_bayes','best_fit',s,variant=v)
        L.append(f"| {label} | {s} | {bold(a,ci(a))} | {bold(b,ci(b))} | {gv[(s,'vm_ca_bayes')]:.1f}% |")
ratio=[pick(robust,'vm_ca_bayes',b,s,variant='hosts=90')['mean']/pick(control,'vm_ca_bayes',b,s,variant='protocol')['mean'] for b in ('lava','best_fit') for s in ACC[:4]]
L.append(f"\n注册时的 `hosts=90` 变体不是负载测试：忙碌主机从未超过 90 台且平局取最小编号，所以每次放置都与 180 台相同，只有 pp 的分母减半。它相对 LAVA 和 Best-Fit 的 8 个均值正好是同种子协议的 {f'{min(ratio):.3f}' if f'{min(ratio):.3f}'==f'{max(ratio):.3f}' else f'{min(ratio):.3f}–{max(ratio):.3f}'} 倍，因此不列入上表，改用到达率加倍作为负载实验。")
L+=['\n### 6.7 阈值敏感性（验证 seeds 200–219，n=20；仅描述，不用于选择）\n','| τ | '+' | '.join(f'acc {s}' for s in ACC[:4])+' |','|---|'+'---|'*4]
for t in manifest['tau']['thresholds']:L.append(f'| {t} | '+' | '.join(bold(r,ci(r)) for r in [pick(tau,'vm_ca_bayes','lava',s,threshold=t) for s in ACC[:4]])+' |')
L+=['\n### 6.8 延续性：报告的 held-out seeds 20–39（n=20，全部重跑）\n','| 设置 | LAVA − BF | VM-CA − BF | Host-CA − BF | VM-CA-Bayes − BF | VM-CA-Bayes − LAVA |','|---|---|---|---|---|---|']
for s in ACC+['synthetic','oracle']:
    L.append(f'| {s} | '+' | '.join(bold(r,ci(r)) for r in [pick(legacy,p,b,s) for p,b in [('lava','best_fit'),('vm_ca','best_fit'),('host_ca','best_fit'),('vm_ca_bayes','best_fit'),('vm_ca_bayes','lava')]])+' |')
L.append('\n原 6 个策略在 seeds 20–39 上的重跑与 `results/heldout` 存档在全部整数决策计数上完全相同，浮点值只差 libm 末位（相对 ≤ 3.3e-16），因此上表前三列与 `REPRODUCTION_DIFFERENCES.md` 的 Table 1 一致。\n')
raw=[dict(r,seed=int(r['seed']),empty_pct=float(r['empty_pct']),accepted=int(r['accepted']),failures=int(r['failures'])) for r in csv.DictReader((res/'test'/'raw.csv').open())]
idx={(r['seed'],r['setting'],r['policy']):r['empty_pct'] for r in raw};seeds=sorted({r['seed'] for r in raw})
L+=['\n### 6.9 事后分解（未预注册，仅作解释，n=100）\n','“仅先验”= 同一批种子在合成预测器（只用 profile 先验）下的 LAVA，“仅噪声值”= 同一准确率下的原 LAVA。\n',
    '| 准确率 | LAVA-Bayes − 仅噪声值 | LAVA-Bayes − 仅先验 | VM-CA-Bayes − LAVA-Bayes（门控的额外贡献） | NILAS-Bayes − VM-CA-Bayes | NILAS-Bayes − LAVA-Bayes |','|---|---|---|---|---|---|']
for s in ACC:
    cells=[]
    for p,b in [('lava_bayes','lava'),('prior',None),('vm_ca_bayes','lava_bayes'),('nilas_bayes','vm_ca_bayes'),('nilas_bayes','lava_bayes')]:
        d=[idx[(k,s,'lava_bayes')]-idx[(k,'synthetic','lava')] for k in seeds] if p=='prior' else paired_diffs(raw,p,b,s)
        m,lo,hi,pv=t_test(d);cells.append(f'{m:+.3f} [{lo:+.3f}, {hi:+.3f}]，p={pv:.2g}')
    L.append(f'| {s} | '+' | '.join(cells)+' |')
gb=json.loads((res/'gate_by_bucket.json').read_text());G={(r['setting'],r['confidence']):r for r in gb['rows']}
L+=['\n### 6.10 门控按误差桶的通过率（事后，seeds 1000–1099，τ=0.3）\n','`scripts/analyze_gate_by_bucket.py` 用评测框架自己的随机流恢复每个 VM 的误差桶（调度器看不到），统计到达时置信度 ≥ τ（走 LAVA）的比例。\n',
    '| 准确率 | 原置信度：正确桶 | 原置信度：错误桶 | 融合置信度：正确桶 | 融合置信度：错误桶 |','|---|---|---|---|---|']
for s in ACC[:4]:L.append(f"| {s} | {100*G[(s,'original')]['correct_pass']:.1f}% | {100*G[(s,'original')]['incorrect_pass']:.1f}% | {100*G[(s,'fused')]['correct_pass']:.1f}% | {100*G[(s,'fused')]['incorrect_pass']:.1f}% |")
L.append('\n融合后的门控只有弱选择性：错误预测大多仍然走 LAVA，但它们的寿命估计已经被先验拉回，所以门控在估计之上几乎没有额外价值（第 6.9 节）。')
doc=root/'IMPROVEMENT.md';marker='\n## 6. 实测结果';text=doc.read_text();head,_,rest=text.partition(marker)
tail=rest[rest.index('\n## 7.'):] if '\n## 7.' in rest else ''
doc.write_text(head.rstrip('\n')+'\n'+'\n'.join(L).rstrip('\n')+'\n'+tail)
print('\n'.join(L))
