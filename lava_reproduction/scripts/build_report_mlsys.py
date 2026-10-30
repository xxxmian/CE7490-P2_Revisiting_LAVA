#!/usr/bin/env python3
"""Lay out the v3 report content in the style of the LAVA MLSys 2025 paper.

The original report builder remains the source of prose, tables and computed
values. This module changes presentation only: Letter paper, embedded Times,
small caps, a full-width abstract, two-column text and full-width data tables.
Requires reportlab; see build_report.py for the data sources.
"""
import argparse
import importlib.util
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BalancedColumns, BaseDocTemplate, CondPageBreak, Frame, HRFlowable,
    Indenter, KeepInFrame, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer,
    Table, TableStyle,
)
from reportlab.graphics.shapes import Drawing, String

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
PAGE_W, PAGE_H = 612.0, 792.0
LEFT, TEXT_W, GUTTER = 55.44, 486.0, 18.0
COL_W = (TEXT_W - GUTTER) / 2
TABLE_PADDING = 1.6
COMPACT_ACCURACY_TABLE = False
BOTTOM, TOP = 74.0, 67.8
BLACK = colors.black
TEAM_FILE = HERE.parent / 'configs' / 'team_members.json'


def team_metadata():
    return json.loads(TEAM_FILE.read_text()) if TEAM_FILE.exists() else None


def register_fonts():
    """Use a serif face with coverage for Greek and mathematical symbols."""
    roots = [Path('/System/Library/Fonts/Supplemental')]
    roots += list((Path.home() / '.cache/codex-runtimes').glob(
        '**/fonts/truetype'))
    choices = [
        ('Times New Roman.ttf', 'Times New Roman Bold.ttf',
         'Times New Roman Italic.ttf', 'Times New Roman Bold Italic.ttf'),
        ('LiberationSerif-Regular.ttf', 'LiberationSerif-Bold.ttf',
         'LiberationSerif-Italic.ttf', 'LiberationSerif-BoldItalic.ttf'),
    ]
    for folder in roots:
        for names in choices:
            paths = [folder / name for name in names]
            if all(p.exists() for p in paths):
                for suffix, path in zip(('', '-Bold', '-Italic', '-BoldItalic'), paths):
                    pdfmetrics.registerFont(TTFont('PaperTimes' + suffix, str(path)))
                pdfmetrics.registerFontFamily(
                    'PaperTimes', normal='PaperTimes', bold='PaperTimes-Bold',
                    italic='PaperTimes-Italic', boldItalic='PaperTimes-BoldItalic')
                return
    raise FileNotFoundError('Install Times New Roman or Liberation Serif fonts.')


def small_caps(text, size):
    """Match the small-cap headings of the original conference paper."""
    parts = []
    for token in re.findall(r'[a-z]+|[^a-z]+', text):
        if token.islower():
            parts.append(f'<font size="{size * .8:g}">{escape(token.upper())}</font>')
        else:
            parts.append(escape(token))
    return ''.join(parts)


class PaperParagraph(Paragraph):
    def __init__(self, text, style, role=None, original=None, **kwargs):
        self.role = role
        self.original = original if original is not None else text
        super().__init__(text, style, **kwargs)

    def draw(self):
        if self.role in ('h1', 'h2') and self.getPlainText() != 'Abstract':
            canvas = self.canv
            seen = getattr(canvas, '_paper_bookmarks', set())
            key = f'paper-heading-{id(self)}'
            if key not in seen:
                level = 0 if self.role == 'h1' else 1
                if self.role == 'h1':
                    canvas._paper_seen_main_heading = True
                if not getattr(canvas, '_paper_seen_main_heading', False):
                    level = 0
                canvas.bookmarkHorizontalAbsolute(key, canvas.absolutePosition(0, self.height)[1])
                canvas.addOutlineEntry(re.sub(r'\s+', ' ', self.original), key, level, closed=True)
                seen.add(key)
                canvas._paper_bookmarks = seen
        super().draw()


def styles():
    common = dict(fontName='PaperTimes', textColor=BLACK, splitLongWords=True,
                  allowWidows=0, allowOrphans=0, embeddedHyphenation=0)
    def s(name, **kw):
        return ParagraphStyle(name, **dict(common, **kw))
    return {
        'title': s('paper-title', fontName='PaperTimes-Bold', fontSize=14.35,
                   leading=17.93, alignment=TA_CENTER),
        'subtitle': s('paper-subtitle', fontName='PaperTimes-Bold', fontSize=14.35,
                      leading=17.93, alignment=TA_CENTER),
        'meta': s('paper-meta', fontSize=9, leading=11, alignment=TA_CENTER),
        'h1': s('h1', fontName='PaperTimes-Bold', fontSize=12, leading=14,
                spaceBefore=10, spaceAfter=5, keepWithNext=True),
        'h2': s('h2', fontName='PaperTimes-Bold', fontSize=10, leading=12,
                spaceBefore=7, spaceAfter=4, keepWithNext=True),
        'body': s('paper-body', fontSize=10, leading=12, spaceAfter=5,
                  alignment=TA_JUSTIFY),
        'eq': s('paper-equation', fontSize=9, leading=12, spaceBefore=2,
                spaceAfter=5, alignment=TA_CENTER),
        'bullet': s('paper-bullet', fontSize=10, leading=12, spaceAfter=4,
                    leftIndent=10, bulletIndent=0, alignment=TA_JUSTIFY),
        'cell': s('paper-cell', fontSize=8.6, leading=10.3, alignment=TA_LEFT),
        'cellb': s('paper-cell-bold', fontName='PaperTimes-Bold', fontSize=8.6,
                   leading=10.3, alignment=TA_LEFT),
        'cap': s('paper-caption', fontSize=9, leading=11, spaceBefore=4,
                 spaceAfter=7, alignment=TA_JUSTIFY),
        'small': s('paper-small', fontSize=9, leading=11, spaceAfter=5,
                   alignment=TA_JUSTIFY),
        'ref': s('paper-reference', fontSize=9, leading=11, leftIndent=12,
                 firstLineIndent=-12, spaceAfter=5, alignment=TA_LEFT),
        'code': s('paper-code', fontName='Courier', fontSize=8, leading=10.5,
                  spaceAfter=2, alignment=TA_LEFT),
    }


def capture_content():
    """Run the unchanged data/prose builder, intercepting only its renderer."""
    spec = importlib.util.spec_from_file_location('lava_report_v3', HERE / 'build_report.py')
    source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    source.S = styles()
    recorded = []
    original_line_figure = source.line_figure
    original_bar_figure = source.bar_figure
    # Reflow the same vector data into the shallower aspect ratios common in
    # conference papers, rather than shrinking text along with an old drawing.
    source.line_figure = lambda series, xs, width=TEXT_W, height=175, refs=(): original_line_figure(
        series, xs, width=width, height=height, refs=refs)
    source.bar_figure = lambda groups, series, width=TEXT_W, height=160, ref=None: original_bar_figure(
        groups, series, width=width, height=height, ref=ref)

    def p(text, role='body'):
        rendered = text
        if role == 'h1':
            rendered = small_caps(text, 12)
        elif role == 'cap':
            rendered = re.sub(r'^(Figure|Table) ([0-9.]+\.)', r'<i>\1 \2</i>', text)
        return PaperParagraph(rendered, source.S[role], role=role, original=text)

    def make_table(rows, widths, shade=None, header=True):
        compact_accuracy = (COMPACT_ACCURACY_TABLE and len(rows[0]) == 2
                            and rows[0][0] == 'Accuracy / predictor')
        display_rows = [list(row) for row in rows]
        if compact_accuracy:
            display_rows[0][1] = 'Gain [95% CI] (pp)'
        vals = [[p(str(value), 'cellb' if header and row_i == 0 else 'cell')
                 if isinstance(value, str) else value for value in row]
                for row_i, row in enumerate(display_rows)]
        total = sum(widths)
        # Small numeric tables fit one column at the same readable type size.
        # Dense result matrices and prose-heavy algorithm tables stay full width.
        narrow = (rows[0][:2] == ['Profile', 'p (short component)']
                  or (len(rows[0]) == 3 and rows[0][0] == 'Accuracy')
                  or compact_accuracy)
        if narrow and len(rows[0]) == 3:
            widths = [3.5, 6.25, 6.25]
            total = sum(widths)
        width = COL_W if narrow else TEXT_W
        t = Table(vals, colWidths=[width * w / total for w in widths],
                  repeatRows=1 if header else 0, hAlign='LEFT')
        commands = [
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), TABLE_PADDING),
            ('BOTTOMPADDING', (0, 0), (-1, -1), TABLE_PADDING),
            ('LINEABOVE', (0, 0), (-1, 0), .8, BLACK),
            ('LINEBELOW', (0, -1), (-1, -1), .8, BLACK),
        ]
        if header:
            commands.append(('LINEBELOW', (0, 0), (-1, 0), .5, BLACK))
        for (col, row), color in (shade or {}).items():
            commands.append(('BACKGROUND', (col, row), (col, row), color))
        t.setStyle(TableStyle(commands))
        t._paper_table = True
        t._paper_narrow = narrow
        return t

    class CaptureDoc:
        def __init__(self, *args, **kwargs):
            pass
        def build(self, content, **kwargs):
            recorded.extend(content)

    source.P = p
    source.B = lambda items: [PaperParagraph(t, source.S['bullet'], role='bullet',
                                            original=t, bulletText='•') for t in items]
    source.table = make_table
    source.boxed = lambda flow, **kw: KeepTogether(flow)
    source.section = lambda title: [p(title, 'h1')]
    source.OutlinedDoc = CaptureDoc
    source.build(Path('/dev/null'))
    return source, flatten(recorded)


def flatten(items):
    out = []
    for item in items:
        if isinstance(item, KeepTogether):
            out.extend(flatten(item._content))
        elif isinstance(item, (PageBreak, CondPageBreak, Spacer)):
            continue
        elif isinstance(item, (list, tuple)):
            out.extend(flatten(item))
        else:
            out.append(item)
    return out


def restyle_drawing(drawing, width=TEXT_W):
    if getattr(drawing, '_paper_final_style', False):
        return
    def visit(obj):
        if isinstance(obj, String):
            obj.fontName = 'PaperTimes-Bold' if 'Bold' in obj.fontName else 'PaperTimes'
            obj.fontSize *= 1.1
        for child in getattr(obj, 'contents', []):
            visit(child)
    visit(drawing)
    scale = width / drawing.width
    drawing.scale(scale, scale)
    drawing.width *= scale
    drawing.height *= scale
    drawing.hAlign = 'CENTER'


class SafeBalancedColumns(BalancedColumns):
    """Balance at natural type size, failing visibly rather than shrinking text."""

    def _generated_content(self, avail_width, avail_height):
        height, generated = super()._generated_content(avail_width, avail_height)
        for i, flow in enumerate(generated):
            if isinstance(flow, KeepInFrame):
                flow.mode = 'error'
                flow.__dict__.pop('_scale', None)
            elif isinstance(flow, BalancedColumns):
                # ReportLab creates base-class continuations internally. Copy
                # their complete state so subsequent pages retain this guard.
                safe = self.__class__.__new__(self.__class__)
                safe.__dict__.update(flow.__dict__)
                safe._needed = max(flow._needed, self._needed)
                generated[i] = safe
        return height, generated


def two_columns(items, name):
    # BalancedColumns does not honor Paragraph.keepWithNext by itself. Bind
    # each heading to the first three lines of its next paragraph so a heading
    # cannot be stranded at the bottom of a page or column.
    attached = []
    i = 0
    while i < len(items):
        flow = items[i]
        if (isinstance(flow, PaperParagraph) and flow.role in ('h1', 'h2')
                and i + 1 < len(items) and isinstance(items[i + 1], PaperParagraph)
                and items[i + 1].role in ('body', 'ref', 'small')):
            following = items[i + 1]
            following.wrap(COL_W, 1e7)
            parts = following.split(COL_W, max(36, following.style.leading * 3)) or [following]
            if len(parts) > 1:
                # The starter is still part of the same paragraph; do not add
                # paragraph spacing between its first lines and continuation.
                parts[0].spaceAfter = 0
            holder = Table([[[flow, parts[0]]]], colWidths=[COL_W], hAlign='LEFT', splitByRow=0)
            holder.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            attached.extend([holder, *parts[1:]])
            i += 2
        else:
            attached.append(flow)
            i += 1
    items = attached
    # Balanced bands let wide tables span both columns at their point of use.
    # An atomic table/figure must fit at its natural height. The inherited wrap
    # method starts a new page when the remaining band is below this minimum.
    needed = 30
    for flow in items:
        if (getattr(flow, '_paper_atomic', False) or isinstance(flow, Drawing)
                or (isinstance(flow, Table) and not flow.splitByRow)):
            _, height = flow.wrapOn(None, COL_W, 1e7)
            needed = max(needed, height + flow.getSpaceBefore() + flow.getSpaceAfter())
    return SafeBalancedColumns(items, nCols=2, needed=needed, leftPadding=0,
                           rightPadding=0, innerPadding=GUTTER, topPadding=0,
                           bottomPadding=0, spaceAfter=5, endSlack=0,
                           name=name)


def assemble(source, content):
    abstract_idx = next(i for i, f in enumerate(content)
                        if isinstance(f, PaperParagraph) and f.original == 'Abstract')
    finding_idx = next((i for i, f in enumerate(content)
                        if isinstance(f, PaperParagraph) and 'Principal findings' in f.original), None)
    if finding_idx is None:
        finding_idx = next(i for i, f in enumerate(content)
                           if isinstance(f, PaperParagraph) and f.role == 'h1')
    abstract = content[abstract_idx + 1:finding_idx]
    title = content[0].original + ':<br/>' + content[1].original
    meta = content[2].original
    team = team_metadata()
    author_style = ParagraphStyle(
        'author', fontName='PaperTimes', fontSize=10, leading=12, alignment=TA_CENTER)
    if team:
        member_style = ParagraphStyle(
            'member', fontName='PaperTimes', fontSize=9, leading=10.5, alignment=TA_CENTER)
        cells = [Paragraph(
            f'<font size="10"><b>{escape(m["name"])}</b></font> '
            f'({escape(m["student_id"])})<br/>'
            f'<font size="8.5">{escape(m["email"])}</font>', member_style)
            for m in team['members']]
        members = Table([cells], colWidths=[TEXT_W / len(cells)] * len(cells), hAlign='CENTER')
        members.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        author_block = [
            Paragraph(f'<b>{escape(team["course"])} · {escape(team["group"])}</b>', author_style),
            Spacer(1, 4), members,
        ]
    else:
        author_block = [Paragraph('<b>CE7490 Course Project</b>', author_style),
                        Paragraph(escape(meta), source.S['meta'])]
    story = [
        HRFlowable(width=TEXT_W, thickness=2, color=BLACK, spaceAfter=10),
        Paragraph(small_caps(title.split(':<br/>')[0] + ':', 14.35) + '<br/>' +
                  small_caps(title.split(':<br/>')[1], 14.35), source.S['title']),
        Spacer(1, 12),
        HRFlowable(width=TEXT_W, thickness=1, color=BLACK, spaceAfter=10 if team else 14),
        *author_block, Spacer(1, 10 if team else 14),
        Paragraph(small_caps('Abstract', 12), ParagraphStyle(
            'abstract-heading', fontName='PaperTimes-Bold', fontSize=12, leading=14,
            alignment=TA_CENTER, spaceAfter=5)),
        Indenter(20, 20), *abstract, Indenter(-20, -20), Spacer(1, 9),
    ]
    body = content[finding_idx:]
    run = []
    band = 0
    i = 0
    def flush():
        nonlocal run, band
        if run:
            band += 1
            story.append(two_columns(run, f'text-band-{band}'))
            run = []
    while i < len(body):
        flow = body[i]
        if isinstance(flow, (Table, Drawing)) and getattr(flow, '_paper_narrow', False):
            group = []
            if isinstance(flow, Drawing):
                restyle_drawing(flow, width=COL_W)
                group.append(flow)
            if i + 1 < len(body) and isinstance(body[i + 1], PaperParagraph) and body[i + 1].role == 'cap':
                group.append(body[i + 1])
                i += 1
            if isinstance(flow, Table):
                group.append(flow)
            # BalancedColumns may unpack KeepTogether while balancing. A
            # single unsplittable cell keeps the caption and table indivisible.
            holder = Table([[group]], colWidths=[COL_W], hAlign='LEFT', splitByRow=0)
            holder.setStyle(TableStyle([
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            run.extend([holder, Spacer(1, 6)])
        elif isinstance(flow, PaperParagraph) and flow.role == 'code':
            flush()
            commands = [flow]
            while i + 1 < len(body) and isinstance(body[i + 1], PaperParagraph) and body[i + 1].role == 'code':
                i += 1
                commands.append(body[i])
            story.extend([KeepTogether(commands), Spacer(1, 8)])
        elif isinstance(flow, (Table, Drawing)):
            heading = None
            if run and isinstance(run[-1], PaperParagraph) and run[-1].role in ('h1', 'h2'):
                heading = run.pop()
            flush()
            caption = None
            if i + 1 < len(body) and isinstance(body[i + 1], PaperParagraph) and body[i + 1].role == 'cap':
                caption = body[i + 1]
                i += 1
            group = [heading] if heading else []
            if isinstance(flow, Table):
                if caption:
                    group.append(caption)
                group.append(flow)
            else:
                restyle_drawing(flow)
                group.append(flow)
                if caption:
                    group.append(caption)
            story.extend([KeepTogether(group), Spacer(1, 8)])
        else:
            run.append(flow)
        i += 1
    flush()
    return story


def decoration(canvas, doc):
    if doc.page > 1:
        canvas.saveState()
        canvas.setFillColor(BLACK)
        canvas.setFont('PaperTimes-Bold', 9)
        canvas.drawCentredString(LEFT + TEXT_W / 2, PAGE_H - 54.11,
                                'Revisiting Lifetime-Aware VM Allocation')
        canvas.setStrokeColor(BLACK)
        canvas.setLineWidth(1)
        canvas.line(LEFT, PAGE_H - 57.60, LEFT + TEXT_W, PAGE_H - 57.60)
        canvas.restoreState()


def build(output, audit=None):
    register_fonts()
    source, content = capture_content()
    if audit:
        records = []
        for f in content:
            if isinstance(f, PaperParagraph):
                records.append({'type': f.role, 'text': f.original})
            elif isinstance(f, Table):
                records.append({'type': 'table', 'rows': [
                    [getattr(c, 'original', str(c)) for c in row] for row in f._cellvalues]})
            elif isinstance(f, Drawing):
                records.append({'type': 'figure'})
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    output.parent.mkdir(parents=True, exist_ok=True)
    team = team_metadata()
    doc = BaseDocTemplate(
        str(output), pagesize=(PAGE_W, PAGE_H), leftMargin=LEFT,
        rightMargin=PAGE_W-LEFT-TEXT_W, topMargin=TOP, bottomMargin=BOTTOM,
        title='Revisiting Lifetime-Aware VM Allocation: Reconstruction, Diagnosis and Prior-Fused Lifetime Prediction',
        author='; '.join(m['name'] for m in team['members']) if team else 'CE7490 Course Project',
        subject='Course report in the layout style of the LAVA MLSys 2025 paper',
    )
    first = Frame(LEFT, BOTTOM, TEXT_W, PAGE_H-72-BOTTOM, id='first',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    later = Frame(LEFT, BOTTOM, TEXT_W, PAGE_H-TOP-BOTTOM, id='later',
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([
        PageTemplate(id='first', frames=[first], onPage=decoration, autoNextPageTemplate='later'),
        PageTemplate(id='later', frames=[later], onPage=decoration),
    ])
    doc.build(assemble(source, content))
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=PROJECT / 'Revisiting_Lifetime_Aware_VM_Allocation_Report_v4_MLSys.pdf')
    parser.add_argument('--audit', type=Path, help='Optional content inventory for validation')
    args = parser.parse_args()
    build(args.output, args.audit)
