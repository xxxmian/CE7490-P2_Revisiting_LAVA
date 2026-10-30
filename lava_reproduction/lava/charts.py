"""Portable SVG scientific error-bar chart, no graphics dependency."""
import html
from pathlib import Path

def plot(summary,path,title):
    width=1100; row=28; height=100+row*len(summary)
    low=min([0]+[x['low'] for x in summary]);high=max([0]+[x['high'] for x in summary]);span=max(.01,high-low)
    low-=span*.08;high+=span*.08
    def x(v):return 470+580*(v-low)/(high-low)
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">','<rect width="100%" height="100%" fill="white"/>',f'<text x="20" y="28" font-family="sans-serif" font-size="18">{html.escape(title)}</text>',f'<path d="M{x(0)} 48 V{height-35}" stroke="#777" stroke-dasharray="4 4"/>']
    for i,r in enumerate(summary):
        y=64+i*row
        label=f"{r['setting']} | {r['policy']} vs {r['baseline']}"
        s.extend([f'<text x="15" y="{y+4}" font-family="sans-serif" font-size="13">{html.escape(label)}</text>',f'<path d="M{x(r["low"])} {y} H{x(r["high"])} M{x(r["low"])} {y-5} v10 M{x(r["high"])} {y-5} v10" stroke="#267a89" stroke-width="2"/>',f'<circle cx="{x(r["mean"])}" cy="{y}" r="4" fill="#173c51"/>'])
    for i in range(6):
        v=low+(high-low)*i/5
        s.append(f'<text x="{x(v)}" y="{height-10}" text-anchor="middle" font-family="sans-serif" font-size="12">{v:.3f} pp</text>')
    s.append('</svg>');Path(path).write_text('\n'.join(s))
