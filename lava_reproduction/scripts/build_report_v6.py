#!/usr/bin/env python3
"""Expand the report's literature grounding with verified primary references.

Reference numbers are assigned in first-citation order. Every bibliography
entry must be cited in the body; project materials are described separately.
"""
import argparse
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
import build_report_v5 as previous
import build_report_mlsys as layout

CATALOG_PATH = layout.HERE.parent / 'configs' / 'literature_v6.json'
CATALOG = json.loads(CATALOG_PATH.read_text())
BY_KEY = {r['id']: r for r in CATALOG}
OLD_KEYS = {1: 'lava', 2: 'borg', 3: 'resource_central', 4: 'lifetime_vm',
            5: 'protean', 6: 'kaplan_meier', 8: 'holm'}
OLD_CITATION = re.compile(r'\[(?P<numbers>[1-9](?:\s*,\s*[1-9])*)(?:,\s*(?P<suffix>Appendix\s+G\.1))?\]')
MARKER = re.compile(r'\[@(?P<keys>[\w,@\s-]+)(?:\|(?P<suffix>[^\]]+))?\]')
LAST_CITATION_ORDER = []


class ReferenceParagraph(layout.PaperParagraph):
    """Keep each bibliographic entry intact at its natural type size."""
    _paper_atomic = True
    def split(self, available_width, available_height):
        return []


def legacy_markers(text):
    text = text.replace('the surviving report and presentation&nbsp;[7]',
                        'the archived course report and presentation in <i>reference/</i>')
    text = text.replace('&nbsp;[9]', '')
    def replace(match):
        numbers = [int(x.strip()) for x in match['numbers'].split(',')]
        if any(n not in OLD_KEYS for n in numbers):
            raise ValueError(f'Unresolved project-material citation: {match.group()}')
        keys = ',@'.join(OLD_KEYS[n] for n in numbers)
        suffix = '|' + match['suffix'] if match['suffix'] else ''
        return f'[@{keys}{suffix}]'
    return OLD_CITATION.sub(replace, text)


def reference_text(record, number):
    title = escape(record['title'])
    venue = escape(record['venue'])
    authors = escape(record['authors']).rstrip('.')
    text = (f'[{number}] {authors}. {title}. '
            f'<i>{venue}</i>, {escape(record["detail"])}, {record["year"]}.')
    if record.get('doi'):
        href = 'https://doi.org/' + record['doi']
        text += f' <link href="{escape(href)}" color="#153F70">doi:{escape(record["doi"])}</link>.'
    else:
        text += f' <link href="{escape(record["url"])}" color="#153F70">Paper</link>.'
    if record.get('additional_url'):
        text += (f' <link href="{escape(record["additional_url"])}" color="#153F70">'
                 f'{escape(record["additional_label"])}</link>.')
    return text


def cited_capture():
    global LAST_CITATION_ORDER
    source, old = previous.editorial_capture()
    P = source.P
    flows = []
    for flow in old:
        if isinstance(flow, layout.PaperParagraph):
            if flow.role == 'ref':
                continue
            if flow.role == 'h2' and flow.original == 'References':
                break
            text = legacy_markers(flow.original)
            if flow.role == 'code':
                text = text.replace('build_report_v5.py', 'build_report_v6.py')
            flows.append(P(text, flow.role))
        else:
            flows.append(flow)

    def find(predicate):
        return next(i for i, f in enumerate(flows)
                    if isinstance(f, layout.PaperParagraph) and predicate(f))
    def insert_after(predicate, text):
        i = find(predicate)
        flows.insert(i + 1, P(text))

    related = find(lambda f: f.role == 'body' and f.original.startswith('Resource Central'))
    flows[related] = P(
        'Resource Central showed that historical VM behavior can support resource prediction [@resource_central]. '
        'Online VM allocation with lifetime and load predictions [@online_vm] and lifetime-alignment placement '
        '[@lifetime_vm] are direct precursors; our LA-Binary baseline follows the comparison in LAVA [@lava]. '
        'Protean illustrates the architecture and operational constraints of a large-scale VM allocation service '
        '[@protean]. LAVA adds distributions, re-prediction and host lifecycle states [@lava]. Our prior-fused '
        'predictor combines Bayesian updating [@bayes] with right-censored survival information [@kaplan_meier] '
        'to refine the noisy predictions consumed by the scheduler.')

    insert_after(lambda f: f.role == 'cap' and f.original.startswith('Table 2.1.'),
        'Prediction-driven resource management also includes Quasar, which infers resource and interference '
        'characteristics for QoS-aware allocation [@quasar]. TetriSched uses estimated runtimes in adaptive '
        'plan-ahead scheduling [@tetrisched], while 3Sigma explicitly represents runtime uncertainty with distributions '
        '[@three_sigma]. LAVA also draws on lifetime re-estimation in learning-based memory allocation for C++ '
        'servers [@memory_allocation]. These systems provide context for using predictions in scheduling; '
        'the experiments here isolate VM lifetimes and two-resource host packing.')

    insert_after(lambda f: f.role == 'h1' and f.original.startswith('4  '),
        'Conditioning on observed uptime uses survival information to update the remaining-lifetime distribution '
        '[@kaplan_meier,@cox]. The two-exponential mixture and its parameters are explicit synthetic assumptions '
        '(Table 3.2), rather than a fit to a production trace.')

    inference = find(lambda f: f.role == 'body' and 'n−1 degrees of freedom.' in f.original)
    flows[inference] = P(flows[inference].original.replace(
        'n−1 degrees of freedom.', 'n−1 degrees of freedom, applied to the per-seed differences [@student].'))

    registration = find(lambda f: f.role == 'body' and f.original.startswith('Development of the new method'))
    flows[registration] = P(
        'The protocol distinguishes planned tests from later exploratory analyses, following the preregistration '
        'principle [@preregistration]. ' + flows[registration].original)

    insert_after(lambda f: f.role == 'body' and f.original.startswith('Fixing the inversion alone'),
        'Calibration concerns agreement between predicted confidence and empirical correctness [@calibration]. '
        'The class probability here follows the specified mixture; the observed failure concerns the mean-selected '
        'class as a decision summary. A valid probability for that event need not rank VM predictability well or '
        'provide a useful routing order for packing.')

    posterior = find(lambda f: f.role == 'body' and f.original.startswith('Let <i>T</i> denote'))
    flows[posterior] = P(
        "The update combines a prior and an observation likelihood by Bayes' rule [@bayes]. " + flows[posterior].original)

    # Add the theoretical evaluation lens at the close of RQ1, before RQ2.
    routing = find(lambda f: f.role == 'h1' and f.original.startswith('7  '))
    flows.insert(routing, P(
        'Learning-augmented online algorithms distinguish gains from accurate advice from protection against bad '
        'predictions [@online_ml]. Error-dependent bounds for dynamic bin packing with predictions formalize that '
        'distinction [@dynamic_binpacking]. The present study reports paired empirical comparisons in a two-resource '
        'simulator, without claiming competitive-ratio guarantees.'))

    internal = find(lambda f: f.role == 'body' and f.original.startswith('Within these limits'))
    flows.insert(internal, P(
        'Future evaluation of learned lifetime distributions should combine proper scoring rules [@proper_scores] '
        'with downstream allocation metrics. Uncertainty benchmarks on classification tasks demonstrate deterioration '
        'under dataset shift [@dataset_shift], motivating temporal workload splits and drift tests of both VM priors '
        'and error models. The current misspecification experiments probe selected assumptions rather than that '
        'broader deployment setting.'))

    flows.append(P(
        '<b>Artifact and provenance.</b> Historical course materials are archived under <i>reference/</i>; '
        'the reconstructed code, frozen results and report sources are available in the '
        '<link href="https://github.com/xxxmian/CE7490-P2_Revisiting_LAVA" color="#153F70">project repository</link>. '
        'These project materials are described separately from the academic bibliography.'))

    order = []
    def number(match):
        keys = [x.strip().lstrip('@') for x in match['keys'].split(',')]
        nums = []
        for key in keys:
            if key not in BY_KEY:
                raise ValueError(f'Unknown reference key: {key}')
            if key not in order:
                order.append(key)
            nums.append(str(order.index(key) + 1))
        suffix = ', ' + match['suffix'] if match['suffix'] else ''
        return '[' + ', '.join(nums) + suffix + ']'

    numbered = []
    for flow in flows:
        if isinstance(flow, layout.PaperParagraph):
            text = MARKER.sub(number, flow.original)
            if '[@' in text:
                raise ValueError(f'Unresolved citation marker: {text}')
            numbered.append(P(text, flow.role))
        else:
            numbered.append(flow)
    assert set(order) == set(BY_KEY), f'Uncited references: {set(BY_KEY)-set(order)}'
    LAST_CITATION_ORDER = order
    source.S['ref'] = ParagraphStyle('paper-reference-v6', parent=source.S['ref'],
                                   leftIndent=20, firstLineIndent=-20,
                                   fontSize=9, leading=11, spaceAfter=4)
    numbered.append(P('References', 'h2'))
    for i, key in enumerate(order, 1):
        text = reference_text(BY_KEY[key], i)
        numbered.append(ReferenceParagraph(text, source.S['ref'], role='ref', original=text))
    print('Academic references:', len(order), '(all cited in body; project materials separate)')
    return source, numbered


def build(output, audit=None):
    layout.COMPACT_ACCURACY_TABLE = True
    layout.TABLE_PADDING = 2.2
    layout.capture_content = cited_capture
    layout.build(output, audit)
    if audit:
        (audit.parent / 'citation-map.json').write_text(json.dumps(
            [{'number': i, **BY_KEY[key]} for i, key in enumerate(LAST_CITATION_ORDER, 1)],
            ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=layout.PROJECT / 'Revisiting_Lifetime_Aware_VM_Allocation_Report_v6.pdf')
    parser.add_argument('--audit', type=Path)
    args = parser.parse_args()
    build(args.output, args.audit)
