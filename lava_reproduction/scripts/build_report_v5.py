#!/usr/bin/env python3
"""Build the edited, compact course report from the recorded experiment results.

The v3 builder remains the numerical source. This edition removes repeated
front matter, turns lists into an argument, and uses high-contrast vector plots.
"""
import argparse
import re
from pathlib import Path

from reportlab.graphics.shapes import Drawing
from reportlab.platypus import Table

import build_report_mlsys as layout
from report_figures import make_accuracy_figure, make_confidence_figure, make_fusion_figure

ORIGINAL_CAPTURE = layout.capture_content


def plain_label(text):
    return re.sub(r'^<b>[^<]+</b>\s*', '', text).strip()


def editorial_capture():
    source, original = ORIGINAL_CAPTURE()
    P = source.P

    def paragraph(text, role='body'):
        # The diagnoses are now grouped, so point at the whole argument rather
        # than retain references to deleted microheadings.
        text = re.sub(r'\bSection 7\.[1-6]\b', 'Section 7', text)
        return P(text, role)

    sections = {}
    current = None
    for flow in original:
        if isinstance(flow, layout.PaperParagraph) and flow.role == 'h1':
            current = int(re.match(r'\d+', flow.original).group())
            sections[current] = []
        if current is not None:
            sections[current].append(flow)

    original_intro = [f.original for f in sections[1]
                      if isinstance(f, layout.PaperParagraph) and f.role == 'body']
    low_accuracy = source.pick(source.IMP['test'], 'lava', 'best_fit', '0.25')
    abstract = (
        'Lifetime-aware VM allocation can improve consolidation, but inaccurate lifetime estimates may reverse its benefit. '
        f'We reconstruct LAVA and confidence-aware variants in an event-driven simulator with {source.C["hosts"]} hosts '
        f'and {source.C["vms"]:,} VMs per paired synthetic trace. On {source.N_TEST} fresh seeds, LAVA is '
        f'{abs(low_accuracy["mean"]):.3f} percentage points worse than Best-Fit at 25% prediction accuracy. '
        'Confidence routing does not resolve this failure: class confidence can be inverted, the gate passes nearly all '
        'requests under controlled noise, and host isolation incurs a packing cost. We instead fuse each noisy prediction '
        'with a profile-level lifetime prior, handling censoring and conditioning on uptime without changing the scheduling rules. '
        f'In a pre-registered evaluation with Holm correction, the fused confidence-aware variant outperforms LAVA at '
        f'{source.HOLDS_LAVA} of 4 tested accuracy levels. Post-hoc analysis suggests that the gain comes mainly from '
        'the estimate rather than the gate. Robustness experiments identify underestimated prior lifetimes as the main observed failure mode. '
        'The findings apply to the reconstructed synthetic environment and do not establish production gains.'
    )
    title_prefix = original[:3]
    edited = title_prefix + [paragraph('Abstract', 'h2'), paragraph(abstract)]
    edited += [
        paragraph('1  Introduction', 'h1'),
        paragraph(original_intro[0]),
        paragraph(original_intro[1]),
        paragraph(original_intro[2]),
        paragraph('The original course implementation and traces are unavailable. We therefore reconstruct the public '
                  'scheduling mechanisms from the surviving report and presentation&nbsp;[7], declaring inferred parameters '
                  'explicitly rather than fitting them to historical outcomes. This scope supports paired comparisons '
                  'within a synthetic environment; it does not recover the lost commit or reproduce production performance.'),
        paragraph("This reconstruction asks whether LAVA's benefit tracks lifetime-prediction quality (RQ1), whether routing "
                  'uncertain arrivals to Best-Fit protects the scheduler from unreliable predictions (RQ2), and whether '
                  'improving the lifetime estimate itself is more effective than switching placement policies (RQ3). '
                  'We compare policies on identical synthetic traces and prediction realizations, separating the scheduling '
                  'rules from the predictor.'),
        paragraph('<b>Contributions and findings.</b> We provide an auditable reconstruction, diagnose confidence-routing '
                  'failure, and evaluate a predictor-level remedy. Unreliable predictions can make LAVA worse than Best-Fit. '
                  'Inverted confidence, an unselective gate and host isolation help explain why routing does not help here. '
                  f'Prior fusion improves on LAVA in {source.HOLDS_LAVA} of 4 pre-registered tests on '
                  f'{source.N_TEST} unused seeds, with scheduling rules unchanged. Underestimated prior lifetimes are '
                  'the main observed failure mode.'),
    ]

    heading_titles = {
        2: '2  Scheduling algorithms', 3: '3  Workload model and provenance',
        4: '4  Lifetime prediction', 5: '5  Experimental protocol',
        6: '6  Prediction accuracy sensitivity', 7: '7  Confidence-aware routing',
        8: '8  Prior-fused lifetime prediction', 9: '9  Pre-registered evaluation',
        10: '10  Robustness and sensitivity', 11: '11  Discussion and limitations',
        12: '12  Conclusion and reproducibility',
    }
    heading_changes = {
        2: {'Host lifecycle and placement order': None, 'Confidence-aware routing': None, 'Prior-fused variants': None},
        3: {'Two-exponential lifetime mixtures': None, 'CPU and memory shapes': None},
        4: {'Conditional remaining lifetime': 'Conditional lifetime model',
            'Controlled prediction accuracy': 'Controlled-noise protocol',
            'Strict Oracle': None, 'Three properties that matter later': None},
        5: {'Metrics': 'Metrics and statistical inference', 'Inference': None,
            'Pre-registration': 'Registration and verification', 'Verification': None, 'Compute': None},
        7: {'7.1  Held-out and fresh-seed outcome': '7.1  Outcomes and placement behavior',
            '7.2  The mechanism works as designed': None,
            '7.3  Diagnosis 1: confidence is inverted relative to predictability': '7.2  Why routing fails',
            '7.4  Diagnosis 2: the gate is blind under controlled noise': None,
            '7.5  Diagnosis 3: isolation costs packing': None,
            '7.6  Threshold validation': '7.3  Threshold implications', 'Conclusion for RQ2': None},
        8: {'Model': 'Posterior construction', 'Information boundary': 'Information boundary and examples',
            'Worked examples': None, 'Development history': 'Development and frozen choices'},
        9: {'All policies versus Best-Fit': 'Policy comparisons', 'Only the predictor changes': None,
            'Where the gain comes from (post hoc)': 'Post-hoc decomposition'},
        10: {'Interpretation': None, 'Threshold sensitivity': 'Threshold and split sensitivity',
             'Continuity with the report split': None},
        12: {'Running the artifact': 'Reproducibility'},
    }
    plot_index = 0
    data_checks = []

    for section_number in range(2, 13):
        flows = sections[section_number]
        edited.append(paragraph(heading_titles[section_number], 'h1'))
        i = 1
        pending_lead = ''
        if section_number == 12:
            # Replace the repetitive three-paragraph recap with one conclusion.
            edited.append(paragraph(
                'Prediction quality determines whether LAVA helps or harms consolidation in this reconstructed setting. '
                'Confidence-aware routing does not resolve low-quality predictions: the confidence signal is inverted '
                'under the default predictor, the gate is nearly unselective under controlled noise, and host isolation '
                'incurs a packing cost. Prior fusion addresses the error in the lifetime estimate '
                'without changing the scheduler. It improves on LAVA in '
                f'{source.HOLDS_LAVA} of 4 pre-registered tests on {source.N_TEST} fresh seeds; the 75% test remains '
                'unconfirmed. The post-hoc decomposition points to the estimate, rather than the gate, as the main source '
                'of improvement. Underestimating long lifetimes was the main observed failure mode. Learned priors '
                'and production traces are needed to establish how far the result transfers beyond the synthetic workload.'))
            while i < len(flows) and not (isinstance(flows[i], layout.PaperParagraph) and flows[i].role == 'h2'):
                i += 1

        while i < len(flows):
            flow = flows[i]
            if isinstance(flow, layout.PaperParagraph) and flow.role == 'h2':
                text = flow.original
                if section_number == 7:
                    if text.startswith('7.3 '): pending_lead = '<b>Inverted confidence.</b> '
                    elif text.startswith('7.4 '): pending_lead = '<b>Unselective gating.</b> '
                    elif text.startswith('7.5 '): pending_lead = '<b>Packing cost.</b> '
                replacement = heading_changes.get(section_number, {}).get(text, text)
                if replacement:
                    edited.append(paragraph(replacement, 'h2'))
                i += 1
                continue

            if isinstance(flow, layout.PaperParagraph) and flow.role == 'bullet':
                items = []
                while i < len(flows) and isinstance(flows[i], layout.PaperParagraph) and flows[i].role == 'bullet':
                    items.append(plain_label(flows[i].original))
                    i += 1
                if section_number == 4:
                    groups = [items]
                elif section_number == 8 and len(items) == 6:
                    groups = [
                        ["Let <i>T</i> denote the VM's total lifetime and <i>o</i> its noisy lifetime observation. "
                         'The prior is ' + items[0][0].lower() + items[0][1:],
                         'The observation model is ' + items[1].replace('far narrower than any grid', 'much narrower than the numerical grid')],
                        [items[2], 'Numerically, we use ' + items[3]],
                        ['We ' + items[4][0].lower() + items[4][1:],
                         'The interface returns ' + items[5][0].lower() + items[5][1:]],
                    ]
                elif section_number == 8 and len(items) == 3:
                    fused_i, raw_i = source.predict_pair('interactive', '0.25', 300.)
                    fused_s, raw_s = source.predict_pair('service', '0.5', 2.)
                    cap = float(source.C['cap_hours'])
                    fused_300, raw_300 = source.predict_pair('service', '1.0', cap, 300.)
                    fused_400, raw_400 = source.predict_pair('service', '1.0', cap, 400.)
                    groups = [[
                        f'For an interactive VM at 25% accuracy, the 300-hour noisy value is implausible under its prior. '
                        f'The fused estimate is {fused_i[0]:.2f} h, close to the profile mean of '
                        f'{source.profile_probs("interactive")[1]:.2f} h; the original predictor returns {raw_i[0]:.0f} h. '
                        f'For a service VM at 50% accuracy, a plausible 2-hour observation moves the posterior mean to '
                        f'{fused_s[0]:.1f} h, between the raw value of {raw_s[0]:.0f} h and the prior mean of '
                        f'{source.profile_probs("service")[1]:.1f} h.'
                    ], [
                        f'Censoring matters when a service VM has a correct prediction at the {cap:.0f}-hour cap. '
                        f'At uptime 300 h, the original predictor expects {raw_300[0]:.0f} h remaining and the fused '
                        f'predictor {fused_300[0]:.0f} h, because the lifetime is only known to exceed {cap:.0f} h. '
                        f'At uptime 400 h, the original estimate jumps to {raw_400[0]:.0f} h with confidence '
                        f'{raw_400[1]:.1f}, while the fused estimate is {fused_400[0]:.0f} h.'
                    ]]
                elif section_number == 10:
                    groups = [items[:3], items[3:5], items[5:]]
                elif section_number == 11:
                    groups = [items[:3], [items[3], items[4], items[6]], [items[5]]]
                else:
                    groups = [items]
                for group in groups:
                    edited.append(paragraph(' '.join(group)))
                continue

            if isinstance(flow, Drawing):
                factories = [make_accuracy_figure, make_confidence_figure, make_fusion_figure]
                plot = (make_fusion_figure(source, height=164) if plot_index == 2
                        else factories[plot_index](source))
                plot._paper_final_style = True
                plot._paper_narrow = plot_index == 0
                data_checks.append((plot_index, plot._data_points))
                edited.append(plot)
                plot_index += 1
            elif isinstance(flow, layout.PaperParagraph):
                text = flow.original
                if section_number == 3 and text.startswith('For each profile,'):
                    text = 'VM lifetimes follow a two-exponential mixture. ' + text
                if section_number == 6 and flow.role == 'cap' and text.startswith('Table 6.1.'):
                    text = 'Table 6.1. Initial-split LAVA gain over Best-Fit, percentage points (mean and 95% CI).'
                if section_number == 9 and flow.role == 'cap' and text.startswith('Figure 9.1.'):
                    text += ' Markers are offset slightly for visibility.'
                if flow.role == 'code' and 'build_report.py' in text:
                    text = 'python3 scripts/build_report_v5.py'
                edited.append(paragraph(pending_lead + text if flow.role == 'body' else text, flow.role))
                if flow.role == 'body':
                    pending_lead = ''
            else:
                edited.append(flow)
            i += 1

    # Introduce the experimental design in prose before its long suite table.
    # This lets the preceding column fill naturally instead of ending early.
    suite_cap = next(i for i, f in enumerate(edited) if isinstance(f, layout.PaperParagraph)
                     and f.role == 'cap' and f.original.startswith('Table 5.1.'))
    suite_block = edited[suite_cap-1:suite_cap+1]
    del edited[suite_cap-1:suite_cap+1]
    registration = next(i for i, f in enumerate(edited) if isinstance(f, layout.PaperParagraph)
                        and f.original == 'Registration and verification')
    edited[registration:registration] = suite_block

    # Show the confidence comparison first, then its exact profile probabilities.
    # Both pieces remain adjacent and retain their established identifiers.
    profile_cap = next(i for i, f in enumerate(edited) if isinstance(f, layout.PaperParagraph)
                       and f.role == 'cap' and f.original.startswith('Table 7.4.'))
    profile_block = edited[profile_cap-1:profile_cap+1]
    del edited[profile_cap-1:profile_cap+1]
    confidence_cap = next(i for i, f in enumerate(edited) if isinstance(f, layout.PaperParagraph)
                          and f.role == 'cap' and f.original.startswith('Figure 7.1.'))
    edited[confidence_cap+1:confidence_cap+1] = profile_block

    assert plot_index == 3
    source._editorial_metrics = {
        'abstract_words': len(abstract.split()),
        'bullet_count': sum(isinstance(f, layout.PaperParagraph) and f.role == 'bullet' for f in edited),
        'subheadings': sum(isinstance(f, layout.PaperParagraph) and f.role == 'h2' for f in edited),
        'tables': sum(isinstance(f, Table) for f in edited),
    }
    print('Editorial summary:', source._editorial_metrics)
    return source, edited


def build(output, audit=None):
    layout.COMPACT_ACCURACY_TABLE = True
    layout.TABLE_PADDING = 2.2
    layout.capture_content = editorial_capture
    layout.build(output, audit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=layout.PROJECT / 'Revisiting_Lifetime_Aware_VM_Allocation_Report_v5.pdf')
    parser.add_argument('--audit', type=Path)
    args = parser.parse_args()
    build(args.output, args.audit)
