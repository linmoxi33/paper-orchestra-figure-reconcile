#!/usr/bin/env python3
"""Probe upstream PaperOrchestra's real figure-context function, offline.

Usage:
  python3 tools/probe_upstream.py /path/to/paper-orchestra [--json]

It imports methods/agents/section_writing_agent.py from a local checkout,
stubbing the two LLM utility modules that need API keys, then calls the exact
_read_json/_format_figures_context methods the section writer uses on the
official CVPR example figure. No LLM call, no network.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLI = os.path.join(ROOT, "bin", "figreconcile")


def import_agent(upstream):
    for name in ("methods.prompts.section_writing_agent",):
        mod = types.ModuleType(name)
        mod.section_writing_agent_prompt = "probe"
        sys.modules[name] = mod
    for name, attrs in (
        ("utils.gemini_utils", {"parse_gemini_latex_results": lambda *a, **k: None}),
        ("utils.llm_backend_utils", {"call_llm_with_images": lambda *a, **k: None}),
    ):
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        sys.modules[name] = mod
    sys.path.insert(0, upstream)
    from methods.agents.section_writing_agent import SectionWritingAgent

    return SectionWritingAgent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    upstream = os.path.abspath(args.upstream)
    head = subprocess.run(
        ["git", "-C", upstream, "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    example = os.path.join(upstream, "frontend", "examples", "cvpr_example.json")
    with open(example, encoding="utf-8") as fh:
        demo = json.load(fh)

    SectionWritingAgent = import_agent(upstream)
    tmp = tempfile.mkdtemp(prefix="probe-upstream-")
    latex = os.path.join(tmp, "latex_writeup")
    figs = os.path.join(tmp, "latex_writeup", "figures")
    raw_figs = os.path.join(tmp, "raw_materials", "figures")
    os.makedirs(figs)
    os.makedirs(raw_figs)
    with open(os.path.join(latex, "paper.tex"), "w", encoding="utf-8") as fh:
        fh.write("\\documentclass{article}\\begin{document}x\\end{document}\n")
    name = demo["figure_path"]
    source = os.path.join(upstream, "frontend", "examples", name)
    for target in (raw_figs, figs):
        with open(os.path.join(target, name), "wb") as fh:
            fh.write(open(source, "rb").read())

    agent = SectionWritingAgent(
        "o", "t", "i", "e", "c", os.path.join(figs, "info.json"), "g"
    )
    fallback_available = hasattr(agent, "_load_figures_info")
    if fallback_available:
        before_entries = agent._load_figures_info()
    else:
        before_entries = agent._read_json(agent.figures_info_path)
    before_text = agent._format_figures_context(before_entries)

    proc = subprocess.run(
        [sys.executable, CLI, "emit-info", tmp, "--json"], capture_output=True, text=True
    )
    emitted = json.loads(proc.stdout)
    after_entries = agent._read_json(agent.figures_info_path)
    after_text = agent._format_figures_context(after_entries)

    result = {
        "upstream_commit": head,
        "example": "frontend/examples/cvpr_example.json",
        "figure": name,
        "before_entries": len(before_entries or []),
        "before_text": before_text,
        "before_chars": len(before_text),
        "after_entries": len(after_entries or []),
        "after_chars": len(after_text),
        "after_mentions_real_filename": name in after_text,
        "emit_exit": proc.returncode,
        "emit_captions_missing": emitted.get("captions_missing"),
        "fallback_available": fallback_available,
    }
    if fallback_available:
        result["verdict"] = "already-fixed" if name in before_text else "not-confirmed"
    else:
        result["verdict"] = (
            "confirmed"
            if before_text == "No figures provided." and name in after_text
            else "not-confirmed"
        )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("upstream %s @ %s" % (os.path.basename(upstream), head[:12]))
        print("before: %r (%d chars)" % (result["before_text"], result["before_chars"]))
        print("after : %d chars, real filename present: %s" % (
            result["after_chars"], result["after_mentions_real_filename"]))
        print("verdict:", result["verdict"])
    return 0 if result["verdict"] in ("confirmed", "already-fixed") else 1


if __name__ == "__main__":
    sys.exit(main())