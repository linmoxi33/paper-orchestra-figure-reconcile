#!/usr/bin/env python3
"""Generate the tiny offline fixtures used by examples/ and tests/.

Run from the repository root:  python3 tools/make_fixtures.py
No third-party packages; each "PDF" is a minimal one-page document.
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = os.path.join(ROOT, "examples", "in")

PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 72 72]>>endobj
trailer<</Root 1 0 R>>
%%EOF
"""

TEX_HEAD = r"""\documentclass{article}
\usepackage{graphicx}
\begin{document}
"""

TEX_TAIL = r"""
\end{document}
"""


def write(path, data, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if mode == "wb":
        with open(path, "wb") as fh:
            fh.write(data)
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data)


def build_issue55():
    base = os.path.join(IN, "issue55_run")
    fig_src = os.path.join(base, "raw_materials", "figures")
    fig_dst = os.path.join(base, "latex_writeup", "figures")
    for name in ("fig1_panel.pdf", "fig2_brechas.pdf"):
        write(os.path.join(fig_src, name), PDF, "wb")
        write(os.path.join(fig_dst, name), PDF, "wb")
    write(
        os.path.join(fig_src, "captions.json"),
        json.dumps(
            {
                "fig1_panel.pdf": "Paired RMSE gaps for the panel estimator.",
                "fig2_brechas.pdf": "Interval coverage across four benchmarks.",
            },
            indent=2,
        )
        + "\n",
    )
    tex = TEX_HEAD + r"""\section{Evaluation}
As shown in Figure~\ref{fig:panel}, the panel estimator closes most of the gap.
\begin{figure}[t]
\includegraphics[width=0.8\linewidth]{figures/fig1_panel.pdf}
\caption{Paired RMSE gaps.}\label{fig:panel}
\end{figure}
Figure~\ref{fig:intervals} reports coverage; the intervals are provided in the
supplementary material.
\begin{figure}[t]
\includegraphics[width=0.8\linewidth]{figures/fig_evaluation_panel_map.pdf}
\caption{Interval coverage.}\label{fig:intervals}
\end{figure}
""" + TEX_TAIL
    write(os.path.join(base, "latex_writeup", "paper.tex"), tex)


def build_clean():
    base = os.path.join(IN, "clean_run")
    fig_src = os.path.join(base, "raw_materials", "figures")
    fig_dst = os.path.join(base, "latex_writeup", "figures")
    write(os.path.join(fig_src, "fig1_panel.pdf"), PDF, "wb")
    write(os.path.join(fig_dst, "fig1_panel.pdf"), PDF, "wb")
    write(
        os.path.join(fig_dst, "info.json"),
        json.dumps([{"name": "fig1_panel.pdf", "caption": "Paired RMSE gaps."}], indent=2)
        + "\n",
    )
    tex = TEX_HEAD + r"""\begin{figure}[t]
\includegraphics[width=0.8\linewidth]{figures/fig1_panel}
\caption{Paired RMSE gaps.}
\end{figure}
""" + TEX_TAIL
    write(os.path.join(base, "latex_writeup", "paper.tex"), tex)


def main():
    for name in ("issue55_run", "clean_run"):
        target = os.path.join(IN, name)
        if os.path.isdir(target):
            shutil.rmtree(target)
    build_issue55()
    build_clean()
    print("fixtures written under", IN)


if __name__ == "__main__":
    main()