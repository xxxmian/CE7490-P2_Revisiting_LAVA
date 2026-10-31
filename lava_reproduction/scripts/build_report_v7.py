#!/usr/bin/env python3
"""Concise report with continuous columns and source-derived result tables.

The archived v6 report retains the complete matrices. This edition keeps the
confirmatory family, decomposition and all robustness-to-LAVA cells at natural
type sizes, removing duplicate tables and repeated explanations.
"""
import argparse
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, PageTemplate,
                               KeepTogether, Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.flowables import _listWrapOn
from reportlab.pdfgen.canvas import Canvas
from reportlab.graphics.shapes import Drawing, Line, Rect

import build_report_mlsys as layout
import build_report_v6 as previous
import report_figures as figures


def compact_fusion(source):
    """The same three series as v6, with a single-column legend."""
    d = figures.make_fusion_figure(source, width=layout.COL_W, height=188)
    # The original function appends its three legend groups last, followed by
    # the baseline label. Remove only those nine legend primitives.
    del d.contents[-10:-1]
    for pos, (label, color, shape) in zip([0, 72, 135], [
            ('VM-CA-Bayes', figures.NAVY, 'circle'),
            ('LAVA-Bayes', figures.ORANGE, 'square'),
            ('LAVA', figures.SLATE, 'diamond')]):
        x, y = 44 + pos, d.height - 10
        d.add(Line(x, y, x+12, y, strokeColor=color, strokeWidth=1.6))
        figures._marker(d, shape, x+6, y, color, 2.1)
        figures._text(d, x+16, y-2.4, label, 7.2, bold=True)
    return d


def compact_confidence(source):
    d = figures.make_confidence_figure(source, width=layout.COL_W, height=176)
    # Reposition the two legend labels and threshold annotation at full type
    # size. The bars and all profile probabilities remain unchanged.
    del d.contents[-6:]
    for offset, label, color in [(0, 'Most likely class', figures.NAVY),
                                  (94, 'Gate confidence', figures.ORANGE)]:
        x, y = 39 + offset, d.height - 12
        d.add(Rect(x, y-2, 7, 7, fillColor=color, strokeColor=None))
        figures._text(d, x+11, y-1, label, 7.1, bold=True)
    labels=[item for item in d.contents if getattr(item,'text',None)=='0.364']
    if len(labels)==2:
        labels[0].x-=1.5
        labels[1].x+=1.5
    threshold_y=27+(d.height-27-29)*.3
    for item in d.contents:
        if (re.fullmatch(r'0\.\d{3}',getattr(item,'text',''))
                and abs(item.y-threshold_y)<8):
            item.y=threshold_y+4
    # Restore the original y-axis label, which was the final removed Group.
    from reportlab.graphics.shapes import Group, String
    g = Group(); g.add(String(0, 0, 'Probability', fontName=figures.FONT,
                             fontSize=8, fillColor=figures.INK, textAnchor='middle'))
    g.transform = (0, 1, -1, 0, 10, 27+(d.height-27-29)/2)
    d.add(g)
    return d


def concise_capture():
    source, old = previous.cited_capture()
    P = source.P
    content = list(old[:3])
    def p(text, role='body'):
        content.append(P(text, role))
    def h(text): p(text, 'h1')
    def sub(text): p(text, 'h2')
    def old_body(prefix):
        return next(f.original for f in old if isinstance(f, layout.PaperParagraph)
                    and f.role == 'body' and f.original.startswith(prefix))
    def old_rows(label):
        index = next(i for i,f in enumerate(old) if isinstance(f, layout.PaperParagraph)
                     and f.role == 'cap' and f.original.startswith(label+'.'))
        return [[getattr(c, 'original', str(c)) for c in row]
                for row in old[index-1]._cellvalues]
    table_data = []
    def table(label, caption, rows, widths, shade=None):
        p(label+'. '+caption, 'cap')
        cell = ParagraphStyle('v7-cell', parent=source.S['cell'], fontSize=8.4, leading=10.2)
        bold = ParagraphStyle('v7-cell-head', parent=cell, fontName='PaperTimes-Bold')
        vals = [[Paragraph(str(v), bold if i==0 else cell) for v in row]
                for i,row in enumerate(rows)]
        t = Table(vals, colWidths=widths, hAlign='LEFT', repeatRows=1, splitByRow=1)
        commands = [('VALIGN',(0,0),(-1,-1),'TOP'),
                    ('LEFTPADDING',(0,0),(-1,-1),3),
                    ('RIGHTPADDING',(0,0),(-1,-1),3),
                    ('TOPPADDING',(0,0),(-1,-1),3),
                    ('BOTTOMPADDING',(0,0),(-1,-1),3),
                    ('LINEABOVE',(0,0),(-1,0),.8,colors.black),
                    ('LINEBELOW',(0,0),(-1,0),.5,colors.black),
                    ('LINEBELOW',(0,-1),(-1,-1),.8,colors.black)]
        commands += [('BACKGROUND',(c,r),(c,r),col) for (c,r),col in (shade or {}).items()]
        t.setStyle(TableStyle(commands)); content.extend([t,Spacer(1,7)])
        table_data.append({'label':label,'rows':rows})
    def figure(d, caption):
        d._paper_final_style=True
        content.extend([d,P(caption,'cap'),Spacer(1,3)])

    p('Abstract', 'h2')
    p('We reconstruct LAVA and confidence-aware virtual-machine allocation in a synthetic simulator with '
      '180 hosts and 2,500 VMs per trace. On 100 fresh seeds, LAVA underperforms Best-Fit by 0.187 percentage '
      'points at 25% prediction accuracy. Confidence routing fails to correct this: its signal ranks profiles '
      'poorly, controlled-noise gates are nearly unselective, and host isolation impairs packing. We fuse noisy '
      'predictions with profile priors, treating capped observations as censored and conditioning on uptime. '
      'With unchanged scheduling rules, the registered variant outperforms LAVA at three of four accuracy levels '
      'after Holm correction; the 75% test remains unconfirmed. Post-hoc analysis attributes most gains to improved '
      'estimates rather than gating. Underestimated prior lifetimes produce the principal observed failure. '
      'Results depend on synthetic assumptions and do not establish production gains.')

    h('1  Introduction')
    p('A virtual-machine (VM) scheduler places requests that consume CPU and memory. A feasible placement can '
      'still strand capacity, while different departure times keep hosts occupied for different periods. '
      'LAVA [1] uses learned lifetime distributions, re-prediction and host lifecycle adaptation in Borg [2]. '
      'We reconstruct its public scheduling ideas and compare policies on identical synthetic traces, rather '
      'than reproduce private production workloads.')
    p('Resource Central predicts VM resource use from history [3]. Online allocation with lifetime and load '
      'predictions [4] and lifetime-alignment placement [5] directly motivate lifetime-aware packing. Protean '
      'describes the operational constraints of a large VM allocation service [6]. Related systems infer resource '
      'needs (Quasar [9]), plan with runtime estimates (TetriSched [10]), or represent runtime uncertainty '
      '(3Sigma [11]); learning-based memory allocation also motivates lifetime re-estimation [12]. These '
      'systems establish context, not evidence for the gains in our simulator.')
    p('The original course code and traces are unavailable. Parameters inferred from archived course materials '
      'are declared explicitly and never fitted to historical outcomes. We ask whether prediction quality '
      'determines LAVA’s benefit (RQ1), whether confidence-based routing protects it from poor estimates (RQ2), '
      'and whether improving the estimate itself is more effective (RQ3).')
    p('<b>Contributions and findings.</b> We provide an auditable reconstruction, diagnose a negative routing '
      'result, and evaluate a prior-fused predictor. Unreliable predictions can make LAVA worse than Best-Fit; '
      'routing alone does not resolve this. With the same placement code, prior fusion improves on LAVA in '
      'three of four registered tests. The main observed failure is underestimating long lifetimes.')

    h('2  Reconstruction and experimental design')
    sub('Policies and workload')
    table('Table 2.1','Placement rules; CA means confidence-aware. Bayes variants change only the predictor.',[
        ['Policy','Placement signal'],
        ['Best-Fit','Minimize the sum of squared CPU and memory residuals.'],
        ['LA-Binary','Prefer non-empty hosts with matching initial short/long label (2-hour boundary).'],
        ['NILAS','Quantized extension of predicted latest host exit, then Best-Fit.'],
        ['LAVA','Lifecycle and lifetime class, then NILAS and Best-Fit.'],
        ['VM-CA','Choose LAVA or Best-Fit per arrival using confidence ≥ τ.'],
        ['Host-CA','Same gate; keep LAVA and Best-Fit host modes separate.'],
        ['*-Bayes','Same placement rules, prior-fused lifetime estimate.']], [52,182])
    p('LAVA uses remaining-lifetime boundaries of 1, 10 and 100 hours [1]. A host starts open, becomes recycling '
      'when either resource reaches 90%, and tracks its resident cohort. Placement prefers higher-class recycling '
      'hosts, same-class open hosts, other occupied hosts, then empty hosts. Cohort departure or deadline expiry '
      'updates the host class. Host-CA fixes a host’s mode until it empties, allowing cross-mode placement only '
      'if no same-mode or empty host can admit a request; no such fallback occurred.')
    p('Each trace has 180 unit-capacity hosts and 2,500 requests. Independent exponential interarrivals have '
      'mean rate 8 VMs/hour; the rate is recovered, but the Poisson process is an assumption. Lifetimes follow '
      'a two-exponential profile mixture (Table 2.2). Profile names and the mixture family are recovered; all '
      'numeric mixture values, profile shares and resource shapes are inferred synthetic defaults.')
    profiles=[['Profile','Share','p','a (h)','b (h)']]
    for (name,(prob,a,b)),share in zip(source.C['profiles'].items(),source.C['profile_weights']):
        profiles.append([name.capitalize(),f'{share:.0%}',f'{prob:g}',f'{a:g}',f'{b:g}'])
    table('Table 2.2','Synthetic profiles: p is the short-component probability; a and b are component means.',
          profiles,[69,40,31,46,48])
    p('CPU/memory shapes (0.125, 0.125), (0.25, 0.125), (0.125, 0.25), (0.5, 0.25) and (0.25, 0.5) '
      'have probabilities 0.35, 0.20, 0.20, 0.125 and 0.125. Shape, profile and component are sampled independently. '
      'Lifetimes are untruncated; only predictions are capped at 336 hours. The generating mixture is not varied '
      'in the robustness analysis.')
    sub('Lifetime predictions')
    p('For total lifetime T and observed uptime u, the default predictor uses conditional survival information '
      '[8, 13]. With mixture parameters p, a, b, the short-component weight and mean remaining lifetime are:')
    p('w(u) = p·e<super>−u/a</super> / [p·e<super>−u/a</super> + (1−p)·e<super>−u/b</super>],','eq')
    p('E[T−u | T&gt;u] = w(u)·a + (1−w(u))·b.','eq')
    p('The estimate is capped at 336 hours. Confidence is the conditional probability of the LAVA class containing '
      'that mean. In a bimodal mixture, the mean may lie in an unlikely class.')
    p('The controlled protocol [1, Appendix G.1] assigns a hidden correct bucket with probability equal to the '
      'requested accuracy. Noise in log10 lifetime has σ = 0.001 in that bucket and σ = 3 otherwise. All policies '
      'see identical capped observations; the scheduler never sees the bucket label. The original predictor '
      'subtracts uptime from this frozen observation, then switches to min(336, max(0.1, uptime)) when overdue. '
      'Its confidence uses a log-uniform prior and the known global error model. The Oracle instead supplies '
      'true remaining lifetimes with confidence one; it is a reference, not a bound for every policy.')
    sub('Protocol, inference and scale')
    p('The primary metric is the percentage of host-time empty from first arrival to final exit. We report paired '
      'differences in percentage points (pp); arrival-window values are a secondary packing diagnostic. '
      'Best-Fit leaves 89.6% empty host-time, offered steady-state CPU load is about 20%, and about 68% of the '
      'horizon is the drain tail. A +0.224 pp gain corresponds to about 0.40 additional empty hosts on average '
      '(about 398 empty host-hours), rather than a measured production or energy saving.')
    p('Per-seed differences receive two-sided Student-t 95% intervals [14]. Only the eight registered tests '
      'receive Holm-adjusted p-values [15]; all other comparisons are descriptive and intervals are unadjusted. '
      'Development uses seeds 0–19; held-out comparisons use 20–39. Before evaluation, hypotheses, τ = 0.3, '
      'test seeds and source hashes were frozen in a locally timestamped protocol [16], not an external registry. '
      'Confirmatory evaluation uses unused seeds 1000–1099 (n = 100); robustness uses 2000–2049 (n = 50), and '
      'threshold sensitivity 200–219 (n = 20). Control/load additions are post-review analyses.')
    p('All 24,884 recorded runs admit every request without oversubscription; 29 unit tests pass. Re-simulation '
      'matches integer decisions exactly, with floating-point differences no larger than 5.2×10<super>−16</super> '
      'across macOS and Linux. Frozen manifests, complete suite definitions and verification logs are archived '
      'with the results. Comparisons reject missing pairs, failed admissions or unequal accepted counts.')

    h('3  Prediction accuracy matters')
    p('The initial accuracy sweep shows a transition from negative to positive LAVA gains (Figure 3.1). '
      'The first tested level with an entirely positive interval is 75%; this descriptive grid does not '
      'establish a universal accuracy threshold.')
    p('Fresh-seed results confirm the pattern: LAVA minus Best-Fit is −0.187 [−0.240, −0.135] pp at 25%, '
      '−0.025 [−0.077, +0.027] at 50%, +0.218 [+0.162, +0.274] at 75%, +0.309 [+0.250, +0.369] at 85% '
      'and +0.507 [+0.445, +0.569] at 100%. The Oracle reaches +0.552 [+0.491, +0.613]. Thus trusting poor '
      'predictions can harm packing. Under the default predictor, the initial small gain does not replicate '
      'on fresh seeds (−0.043 [−0.098, +0.012] pp).')
    figure(figures.make_accuracy_figure(source),
           'Figure 3.1. Initial-split LAVA minus Best-Fit, seeds 0–19; paired means and 95% intervals, n = 20. '
           'Accuracy uses a true numeric axis.')
    p('Learning-augmented online algorithms distinguish gains from accurate advice from protection against '
      'prediction errors [17]. Dynamic-bin-packing bounds formalize error dependence [18]. Our two-resource '
      'simulator provides paired empirical evidence, without competitive-ratio guarantees.')

    h('4  Why confidence routing fails')
    p('With the default predictor, Host-CA is worse than Best-Fit on fresh seeds: −0.090 [−0.147, −0.034] pp. '
      'VM-CA’s held-out benefit also fails to replicate (−0.015 [−0.070, +0.041] pp). Host isolation removes '
      'all cross-mode placements without capacity fallback, so the negative outcome persists despite satisfying '
      'its intended invariant. Three observations explain the failure.')
    p('<b>Inverted confidence.</b> The gate scores the class containing the mixture mean rather than the most '
      'likely class. Interactive VMs are most predictable but receive the lowest score; service VMs receive '
      'the highest (Figure 4.1). At τ = 0.3, only service VMs pass, effectively isolating them.')
    figure(compact_confidence(source),
           'Figure 4.1. The most likely class versus gate confidence at arrival. A low-probability mean class '
           'reverses the ranking of profile predictability. Dashed line: gate threshold 0.3.')
    p('Using the most likely class instead did not beat LAVA on development seeds (−0.129 to −0.043 pp at '
      'tested thresholds), so inversion is not a sufficient explanation. Calibration measures agreement with '
      'empirical correctness [19]; here the specified class probability can be valid while remaining an '
      'unhelpful decision summary for scheduling.')
    p('<b>Unselective gating.</b> Under controlled noise the original gate passes 99.96% of arrivals at 25% '
      'accuracy and 100% at 50% and above. At the latter levels both CA variants reproduce LAVA exactly, '
      'because confidence does not separate damaging errors.')
    p('<b>Packing cost.</b> Mode restrictions open hosts that could otherwise be shared. With the default '
      'predictor, Host-CA loses '
      '0.992 pp versus Best-Fit during arrivals but 0.090 pp over the full horizon; the tail recovers about '
      '72% of lost empty host-hours. Validation selects a threshold that reduces Host-CA to Best-Fit, '
      'with every candidate score negative. Changing the routing threshold does not rescue this design.')

    h('5  Prior-fused lifetime prediction')
    p('The alternative repairs the estimate while keeping placement rules unchanged. Bayes’ rule [7] combines '
      'the profile prior with the noisy observation: log10 o = log10 T + ε, using the same narrow/broad noise '
      'mixture as the controlled protocol. The predictor knows global accuracy, error spreads, cap and profile, '
      'but never the hidden bucket or true lifetime. The prior is the generating distribution, a strong '
      'assumption tested through misspecification below.')
    p('A capped observation contributes P(log10 T + ε ≥ log10 336), not a point likelihood [8]. The implementation '
      'uses 425 weighted log-grid atoms over 10<super>−4</super>–10<super>4.5</super> hours plus nine atoms for '
      'the narrow component. Conditioning on survival removes atoms below the current age; suffix sums support '
      'O(log n) re-prediction. The interface returns the capped posterior mean remaining lifetime and its '
      'LAVA-class probability. If no atom survives, it falls back to the profile prediction.')
    p('For an interactive VM at 25% accuracy, an implausible 300-hour observation becomes a 1.52-hour estimate. '
      'For a service VM at 50%, a plausible 2-hour observation moves the estimate from the 85.2-hour prior mean '
      'to 27.0 hours. At 100% accuracy and uptime 300 hours, a capped service observation gives '
      '151 hours remaining rather than '
      'the original predictor’s 36 hours: censoring does not imply an exact departure. A no-truth-access test '
      'changes true lifetimes fiftyfold while preserving observations and verifies identical predictions.')
    p('Development used only seeds 0–19. An expected host-exit score and most-likely-class routing were rejected '
      'before registration. VM-CA-Bayes was selected because adding its gate appeared beneficial on development '
      'seeds; the additional gate benefit did not replicate on fresh seeds. Under the default predictor or '
      'Oracle, there is no noisy observation to fuse and Bayes variants equal their base policies bit for bit.')

    h('6  Confirmatory evaluation')
    p('The registered family compares VM-CA-Bayes with LAVA and Best-Fit at 25%, 50%, 75% and 85% accuracy '
      'on 100 unused seeds. An improvement requires a positive mean and Holm-adjusted p &lt; 0.05. All eight '
      'tests are shown in Table 6.1; 100% accuracy is a secondary comparison because the predictors then differ '
      'only in overdue handling.')
    family=[['Acc.','Versus LAVA','Versus Best-Fit']]
    shades={}
    for i,acc in enumerate(source.REG,1):
        row=[source.lab(acc)]
        for j,baseline in enumerate(['lava','best_fit'],1):
            r=source.FAMILY[(acc,baseline)]
            pvalue=source.pf(r['p_holm'])
            pvalue=(' '+pvalue if pvalue.startswith('&lt;') else ' = '+pvalue)
            row.append(source.ci2(r)+'<br/>p<sub>H</sub>'+pvalue+
                       ('; holds' if source.ok(r) else '; unconfirmed'))
            if source.ok(r):shades[(j,i)]=colors.HexColor('#E6F0E9')
        family.append(row)
    table('Table 6.1','Registered VM-CA-Bayes gains (pp): mean [95% CI], Holm p (pH) and decision. '
          'Intervals are unadjusted. Three of four tests hold against each baseline.',family,[36,99,99],shades)
    p('Against LAVA, the 75% test remains unconfirmed (+0.054 [−0.001, +0.109] pp; Holm p = 0.11). '
      'Against Best-Fit, the 25% test also fails (+0.037 [−0.012, +0.086]; Holm p = 0.14). At 75% and 85%, '
      'unmodified LAVA already beats Best-Fit, so fusion-specific evidence comes from the three LAVA tests '
      'and the Best-Fit test at 50%. Figure 6.1 displays the full accuracy trend.')
    figure(compact_fusion(source),
           'Figure 6.1. Fresh-seed gain over Best-Fit (n = 100), paired means and unadjusted 95% intervals. '
           'VM-CA-Bayes is registered; LAVA-Bayes is secondary. Small horizontal offsets separate markers.')
    p('Fusion improves NILAS, LAVA and VM-CA at most accuracies but worsens Host-CA at every tested level '
      'from 25% to 85% (−0.091 to −0.189 pp), consistent with further host partitioning. LA-Binary remains '
      'slightly below Best-Fit (−0.056 to −0.114 pp). Complete policy matrices remain in the archived full '
      'report and per-seed results.')
    sub('Where the gain comes from (post hoc)')
    decomp=old_rows('Table 9.5')
    decomp[0]=['Acc.','Fused − noisy','Fused − prior','Gate on top']
    for row in decomp[1:]:
        for j in range(1,len(row)):
            row[j]=row[j].replace(' [','<br/>[')
    table('Table 6.2','Post-hoc decomposition (pp). LAVA-Bayes minus LAVA under controlled noise or the '
          'default predictor; final column is VM-CA-Bayes minus LAVA-Bayes. Unadjusted intervals.',
          decomp,[32,67,67,68])
    p('Fusion improves on the prior alone at every registered accuracy and on noisy predictions alone except '
      '75%, where the interval includes zero. Adding the gate changes the mean by −0.018 to +0.011 pp, with '
      'intervals about ±0.05 pp wide. A small gate effect cannot be excluded, but the development advantage '
      'did not replicate. Post hoc, the fused gate accepts 82–87% of correct-bucket and 73–75% of incorrect-bucket '
      'predictions; hidden labels are used only by the analysis. The estimate appears to absorb most of '
      'the damage, a descriptive interpretation rather than a registered mediation test.')

    h('7  Robustness and failure modes')
    p('Each robustness setting uses 50 fresh seeds and changes one predictor assumption or the load. '
      'Table 7.1 keeps all 32 comparisons against LAVA. These intervals and p-values are descriptive, '
      'without multiplicity correction.')
    robust=old_rows('Table 10.1')
    robust[0]=['Variant','25%','50%','75%','85%']
    shades={}
    # Original shading comes from unadjusted paired intervals in the same rows.
    original_robust_index=next(i for i,f in enumerate(old) if isinstance(f,layout.PaperParagraph)
                               and f.role=='cap' and f.original.startswith('Table 10.1.'))
    for cmd in old[original_robust_index-1]._bkgrndcmds:
        if cmd[0]=='BACKGROUND': shades[cmd[1]]=cmd[3]
    table('Table 7.1','VM-CA-Bayes minus LAVA, mean [95% CI] in pp, n = 50. Green/red mark '
          'unadjusted intervals wholly above/below zero.',robust,[66,42,42,42,42],shades)
    p('Milder incorrect predictions reduce gains; misspecified error spreads retain positive means but not '
      'uniformly positive intervals. Doubling prior means preserves all four positive intervals. Halving them '
      'makes correct long lifetimes look implausible: at 85% accuracy VM-CA-Bayes minus LAVA is '
      '−0.116 [−0.197, −0.034] pp (unadjusted p = 0.006), while its gain over Best-Fit remains '
      '+0.191 [+0.111, +0.272] pp. This is the only '
      'entirely negative interval among the 32 cells, and motivates testing learned priors and underestimation risk.')
    p('Doubling arrivals and requests (16 VMs/hour, 5,000 VMs) increases gains over LAVA at 25–75%; the 85% '
      'interval includes zero. A 90-host variant was only a denominator rescaling and is not a load test. '
      'Thresholds 0.1–0.5 give positive means throughout, with positive intervals in 12 of 16 cells; thresholds '
      '0.7–0.9 produce negative intervals in three of nine cells at 50–85%. These analyses did not select '
      'the frozen threshold. Legacy reruns reproduce original-policy decisions and show a similar fusion pattern.')

    h('8  Discussion and limitations')
    p('The prior is the generating profile model; in practice it must be learned from history. Global accuracy '
      'and error spreads are assumed known, as in the original controlled confidence. Broad σ = 3 errors are '
      'easy to flag as implausible, while milder errors yield smaller gains. Both directions of error-spread '
      'misspecification were tested, but the workload mixture and resource shapes remain inferred assumptions.')
    p('Low load and the long drain tail limit external validity. The arrival-window metric supports fusion '
      '(+0.312, +0.207 and +0.076 pp over LAVA at 25%, 50% and 85%), but absolute values cannot be compared '
      'with production [1]. NILAS often exceeds LAVA here, unlike in [1]; class, deadline and tie-breaking '
      'rules are reconstructed. The Oracle is not an upper bound across variants: NILAS-Bayes at 100% '
      '(+0.599 pp) exceeds NILAS Oracle (+0.581 pp). Disagreement with historical outcomes does not falsify '
      'the lost implementation, whose critical parameters and random streams are unknown.')
    p('Only the eight primary tests are multiplicity-adjusted. Decomposition, other policy comparisons and '
      'robustness are descriptive; the registration has a self-reported local timestamp. Internal comparisons '
      'remain paired on identical traces and observations, with equal admission and unused confirmatory seeds. '
      'Future learned distributions should be evaluated with proper scoring rules [20] and allocation metrics; '
      'uncertainty degradation under dataset shift [21] also motivates temporal splits and drift tests.')

    h('9  Conclusion and artifact')
    p('Prediction quality determines whether LAVA helps or harms packing in this reconstruction. Routing '
      'uncertain arrivals does not resolve the failure; improving the lifetime estimate does, in three of '
      'four registered comparisons with LAVA. The 75% test remains unconfirmed. Post-hoc evidence points to '
      'the estimate rather than the gate, while underestimated priors reveal a concrete failure mode. '
      'Production traces and learned priors are needed to assess transfer.')
    p('The <link href="https://github.com/xxxmian/CE7490-P2_Revisiting_LAVA" color="#153F70">project repository</link> '
      'contains raw results, frozen protocols, source hashes, verification logs and reproduction commands. '
      'The archived v6 report retains the full result matrices omitted here. Historical course materials are '
      'under <i>reference/</i>; the reconstructed source is not the lost original commit 377cbb1. Experiments '
      'need Python 3.9+ and the standard library; the PDF builder also needs ReportLab.')

    # Renumber the preserved academic references in order of first use. This
    # also checks that shortening prose has not left uncited bibliography items.
    old_refs={int(re.match(r'\[(\d+)\]',f.original)[1]):f for f in old
              if isinstance(f,layout.PaperParagraph) and f.role=='ref'}
    citation=re.compile(r'\[(\d+(?:,\s*\d+)*)(, Appendix G\.1)?\]')
    order=[]
    def renumber(match):
        ns=[int(x.strip()) for x in match[1].split(',')]
        for n in ns:
            if n not in old_refs: raise ValueError(f'Unknown citation {n}')
            if n not in order: order.append(n)
        return '['+', '.join(str(order.index(n)+1) for n in ns)+(match[2] or '')+']'
    numbered=[]
    for f in content:
        if isinstance(f,layout.PaperParagraph):
            numbered.append(P(citation.sub(renumber,f.original),f.role))
        else: numbered.append(f)
    assert set(order)==set(old_refs),f'Uncited: {set(old_refs)-set(order)}'
    numbered.append(P('References','h2'))
    for n,old_n in enumerate(order,1):
        text=re.sub(r'^\[\d+\]',f'[{n}]',old_refs[old_n].original)
        numbered.append(previous.ReferenceParagraph(text,source.S['ref'],role='ref',original=text))
    source._v7_tables=table_data
    return source,numbered


def build(output,audit=None):
    layout.register_fonts()
    source,content=concise_capture()
    # Reuse exactly the title/author/abstract composition; measure it before
    # defining first-page columns. The body uses ordinary continuous Frames.
    first_h1=next(i for i,f in enumerate(content) if isinstance(f,layout.PaperParagraph) and f.role=='h1')
    header=layout.assemble(source,content[:first_h1]+[source.P('1  Introduction','h1')])[:-1]
    _,header_height=_listWrapOn(header,layout.TEXT_W,Canvas('/dev/null'))
    header_top=layout.PAGE_H-72
    body_top=header_top-header_height-7
    assert body_top-layout.BOTTOM>180,'First-page columns too short'
    first_frames=[
        Frame(layout.LEFT,body_top+7,layout.TEXT_W,header_height,id='title',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0),
        *[Frame(layout.LEFT+k*(layout.COL_W+layout.GUTTER),layout.BOTTOM,layout.COL_W,
                body_top-layout.BOTTOM,id=f'first-{k}',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
          for k in range(2)]]
    later=[Frame(layout.LEFT+k*(layout.COL_W+layout.GUTTER),layout.BOTTOM,layout.COL_W,
                 layout.PAGE_H-layout.TOP-layout.BOTTOM,id=f'column-{k}',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)
           for k in range(2)]
    team=layout.team_metadata()
    doc=BaseDocTemplate(str(output),pagesize=(layout.PAGE_W,layout.PAGE_H),
        title='Revisiting Lifetime-Aware VM Allocation: Reconstruction, Diagnosis and Prior-Fused Lifetime Prediction',
        author='; '.join(m['name'] for m in team['members']),subject='Concise course report in MLSys-style continuous columns')
    def decorate(canvas,document):
        layout.decoration(canvas,document)
        canvas.saveState()
        canvas.setFont('PaperTimes',9)
        canvas.setFillColor(colors.HexColor('#48515D'))
        canvas.drawCentredString(layout.LEFT+layout.TEXT_W/2,46,str(document.page))
        canvas.restoreState()
    doc.addPageTemplates([PageTemplate('first',frames=first_frames,onPage=decorate,autoNextPageTemplate='later'),
                          PageTemplate('later',frames=later,onPage=decorate)])
    body=[];raw=content[first_h1:];i=0
    while i<len(raw):
        f=raw[i]
        if isinstance(f,Drawing):
            assert i+1<len(raw) and getattr(raw[i+1],'role',None)=='cap'
            body.append(KeepTogether([f,raw[i+1]]));i+=2
        else:
            if getattr(f,'role',None)=='cap':f.keepWithNext=True
            body.append(f);i+=1
    output.parent.mkdir(parents=True,exist_ok=True)
    doc.build([*header,FrameBreak(),*body])
    if audit:
        records=[]
        for f in content:
            if isinstance(f,layout.PaperParagraph):records.append({'type':f.role,'text':f.original})
            elif isinstance(f,Drawing):records.append({'type':'figure','points':f._data_points,
                                                       'oracle':getattr(f,'_oracle_mean',None)})
        audit.parent.mkdir(parents=True,exist_ok=True)
        audit.write_text(json.dumps({'content':records,'tables':source._v7_tables,
              'header_height':header_height,'first_body_top':body_top},indent=2,ensure_ascii=False))
    print(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=layout.PROJECT/'Revisiting_Lifetime_Aware_VM_Allocation_Report_v7.pdf')
    parser.add_argument('--audit',type=Path)
    args=parser.parse_args();build(args.output,args.audit)
