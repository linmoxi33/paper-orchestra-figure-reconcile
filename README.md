# paper-orchestra-figure-reconcile

PaperOrchestra produces a "submission-ready" PDF while silently dropping every figure you supplied it. This tool finds that before you submit — and rebuilds the missing `figures/info.json` that causes it.

Upstream: https://github.com/google-research/paper-orchestra

## Why this exists now

PaperOrchestra (Google Research, 4.4k stars, pushed 2026-11-15) generates a LaTeX manuscript from raw material and figures. Its non-plotting path copies your figures into `latex_writeup/figures/` but never writes the `info.json` inventory that `SectionWritingAgent` reads. The section writer is therefore told `No figures provided.`, invents plausible filenames, and `pdflatex` only warns about missing graphics — so the run "succeeds" with a figure-free PDF. This is reported by users, not hypothetical:

- [issue #55](https://github.com/google-research/paper-orchestra/issues/55) — open, 2026-11-18, "Provided figures are silently missing from the output PDF when running without --use_plotting"
- [issue #53](https://github.com/google-research/paper-orchestra/issues/53) — same report, closed as duplicate
- [issue #23](https://github.com/google-research/paper-orchestra/issues/23) — open, Streamlit demo never writes `figures/info.json`, so uploaded figures are dropped

`figreconcile` is not a reimplementation of the pipeline. It reads the artifacts a run already produced and answers one question deterministically: **does every figure the run was given appear in the LaTeX, and does every `\includegraphics` point at a file that exists?**

## What it does / does not do

Does:

- parses `\includegraphics` (optional args, extensionless targets, multi-line) from every generated `.tex`;
- resolves each target against the figures directory and lists dangling includes with file and line;
- lists supplied figures that the manuscript never includes (`provided-unreferenced`);
- checks the `figures/info.json` contract (`info-json-missing`, unknown names, empty captions);
- `emit-info` reconstructs a valid `[{name, caption}]` inventory from the supplied figures plus an optional caption map, fixing the root cause for the next run;
- `relink` rewrites dangling `\includegraphics` targets from an **explicit** mapping (dry-run by default, `--write` to apply), so an already-broken manuscript can be repaired without guessing which file belongs where;
- `--strict` turns warnings into failures; `--json` is machine-readable.

Does not:

- call any LLM, compile LaTeX, or inspect PDF pixels;
- prove that a caption matches the image (it checks provenance, not semantics);
- decide which supplied figure belongs at a dangling include — it never rewrites `\includegraphics`, so there is no silent remapping.

## Upstream behaviour we measured

`tools/probe_upstream.py` imports upstream's own `SectionWritingAgent` at commit `d9bae997e793` and calls the exact `_read_json` / `_format_figures_context` methods on the repository's **official** `frontend/examples/cvpr_example.json` figure. No LLM call, no network.

```text
$ python3 tools/probe_upstream.py /path/to/paper-orchestra
upstream po @ d9bae997e793
before: 'No figures provided.' (20 chars)
after : 160 chars, real filename present: True
verdict: confirmed
```

The same fixture with `figreconcile check` reports three errors: 1 dangling include, 1 supplied-but-unreferenced figure, 1 missing inventory — see `examples/out/issue55_expected.json`. This reproduces the issue's mechanism at the function boundary; it is not an end-to-end LLM run.

## Install

Zero dependencies, Python 3.8+:

```bash
git clone git@github.com:linmoxi33/paper-orchestra-figure-reconcile.git
cd paper-orchestra-figure-reconcile
python3 bin/figreconcile --version
```

## Usage

Point it at a PaperOrchestra run directory (`latex_writeup/` + `raw_materials/figures/`):

```bash
python3 bin/figreconcile check path/to/latex_writeup/..
python3 bin/figreconcile check path/to/run --json
python3 bin/figreconcile emit-info path/to/run --captions captions.json
python3 bin/figreconcile relink path/to/run --map mapping.json --write
```

`mapping.json` is a plain object from a dangling target to a real file, e.g.
`{"fig_evaluation_panel_map.pdf": "figures/fig2_brechas.pdf"}`. Without `--write`
`relink` only reports; it never invents a mapping.

`--json` output (abridged from `examples/out/issue55_expected.json`):

```json
{
  "ok": false,
  "counts": {"provided": 2, "includes": 2, "resolved": 1, "dangling": 1, "unreferenced": 1, "errors": 3, "warnings": 0},
  "findings": [
    {"code": "dangling-include", "severity": "error", "line": 13,
     "detail": "\\includegraphics refers to 'figures/fig_evaluation_panel_map.pdf' but no such image exists"}
  ]
}
```

`emit-info` writes upstream's exact `[{name, caption}]` schema (only those two keys) and reports `captions_missing` instead of inventing captions:

```bash
python3 bin/figreconcile emit-info path/to/run --json --force
```

### Exit codes

| code | meaning |
| --- | --- |
| 0 | check clean (or `emit-info` wrote the inventory) |
| 1 | problems detected (`check` / `relink`), or `emit-info` refused/found nothing to write |
| 2 | usage or input error (missing run dir, no `.tex`, malformed captions JSON) |

### Tests

```bash
python3 -m unittest discover -s tests -v   # 24 tests, 1.1 s
```

All fixtures are local and offline: `python3 tools/make_fixtures.py` regenerates `examples/in/` (two minimal PDFs, no network).

## 本轮创新

Reports so far are one-off anecdotes; this is the first check that turns PaperOrchestra's silent figure drop into a deterministic, repair-backed gate: it measures upstream's own figure-context function on the repository's official CVPR example (20 chars `No figures provided.` → 160 chars naming the real file after repair), classifies every include as resolved/dangling and every supplied figure as referenced/unreferenced, and repairs either the next run (inventory) or the current manuscript (explicit relink). The novelty is the closed loop — detect, rebuild the inventory the writer reads, and prove upstream's function now sees the file — not another README lint.

## 与同类项目的差异

`gh search repos "latex figure includegraphics validator"` returns no project doing figure-provenance reconciliation (see `/tmp/similar.md` at build time). LaTeX linters such as `chktex` check syntax, not whether the files a run was given reached the manuscript; PaperOrchestra's own `autoraters/` score prose and citations, not figure presence.

## Limits

- Only figures referenced through `\includegraphics` are checked; TikZ/pgfplots figures are invisible to it.
- Caption quality is not judged; `(caption not provided)` is a deliberate placeholder, never a generated claim.
- The upstream probe is source-level and stubs two LLM utility modules; it does not run the pipeline end to end.
- `relink` requires a human-supplied mapping; it deliberately refuses to infer a figure-to-file binding from names or ordering.

## License

MIT for this tool. Upstream PaperOrchestra is Apache-2.0; no upstream source is vendored here.