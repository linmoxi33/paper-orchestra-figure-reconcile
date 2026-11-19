#!/usr/bin/env python3
"""Behavioural tests for bin/figreconcile. Stdlib only: python3 -m unittest discover -s tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "bin", "figreconcile")
EXAMPLES = os.path.join(ROOT, "examples", "in")


def run(*args, cwd=None):
    proc = subprocess.run(
        [sys.executable, CLI, *args],
        capture_output=True,
        text=True,
        cwd=cwd or ROOT,
    )
    return proc


def copy_example(name):
    tmp = tempfile.mkdtemp(prefix="figreconcile-")
    dst = os.path.join(tmp, "run")
    shutil.copytree(os.path.join(EXAMPLES, name), dst)
    return tmp, dst


class CheckTests(unittest.TestCase):
    def test_clean_run_exits_zero(self):
        proc = run("check", os.path.join(EXAMPLES, "clean_run"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("OK", proc.stdout)

    def test_clean_json_is_parseable(self):
        proc = run("check", os.path.join(EXAMPLES, "clean_run"), "--json")
        data = json.loads(proc.stdout)
        self.assertTrue(data["ok"])
        self.assertEqual(data["counts"]["dangling"], 0)
        self.assertEqual(data["info_entries"], 1)

    def test_issue55_exits_one(self):
        proc = run("check", os.path.join(EXAMPLES, "issue55_run"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("FAILED", proc.stdout)

    def test_issue55_dangling_include_line(self):
        proc = run("check", os.path.join(EXAMPLES, "issue55_run"), "--json")
        data = json.loads(proc.stdout)
        dangling = [f for f in data["findings"] if f["code"] == "dangling-include"]
        self.assertEqual(len(dangling), 1)
        self.assertEqual(dangling[0]["line"], 13)
        self.assertIn("fig_evaluation_panel_map.pdf", dangling[0]["detail"])

    def test_issue55_reports_unreferenced_figure(self):
        proc = run("check", os.path.join(EXAMPLES, "issue55_run"), "--json")
        data = json.loads(proc.stdout)
        missing = [f for f in data["findings"] if f["code"] == "provided-unreferenced"]
        self.assertEqual([os.path.basename(f["file"]) for f in missing], ["fig2_brechas.pdf"])

    def test_issue55_reports_missing_info_json(self):
        proc = run("check", os.path.join(EXAMPLES, "issue55_run"), "--json")
        data = json.loads(proc.stdout)
        codes = [f["code"] for f in data["findings"]]
        self.assertIn("info-json-missing", codes)
        self.assertEqual(data["info_entries"], 0)

    def test_extensionless_include_resolves(self):
        proc = run("check", os.path.join(EXAMPLES, "clean_run"), "--json")
        data = json.loads(proc.stdout)
        self.assertEqual(data["includes"][0]["target"], "figures/fig1_panel")
        self.assertTrue(data["includes"][0]["resolved"].endswith("fig1_panel.pdf"))

    def test_strict_promotes_warnings(self):
        tmp, run_dir = copy_example("clean_run")
        try:
            info = os.path.join(run_dir, "latex_writeup", "figures", "info.json")
            with open(info, "w", encoding="utf-8") as fh:
                json.dump([{"name": "ghost.png", "caption": ""}], fh)
            soft = run("check", run_dir, "--json")
            hard = run("check", run_dir, "--json", "--strict")
            self.assertEqual(soft.returncode, 0)
            self.assertGreater(json.loads(soft.stdout)["counts"]["warnings"], 0)
            self.assertEqual(hard.returncode, 1)
        finally:
            shutil.rmtree(tmp)

    def test_missing_run_dir_is_usage_error(self):
        proc = run("check", "/nonexistent/paper-orchestra-run")
        self.assertEqual(proc.returncode, 2)

    def test_directory_without_tex_is_usage_error(self):
        tmp = tempfile.mkdtemp(prefix="figreconcile-")
        try:
            proc = run("check", tmp)
            self.assertEqual(proc.returncode, 2)
            self.assertIn("no LaTeX file", proc.stderr)
        finally:
            shutil.rmtree(tmp)


class EmitInfoTests(unittest.TestCase):
    def test_emit_info_writes_name_and_caption(self):
        tmp, run_dir = copy_example("issue55_run")
        try:
            out = os.path.join(run_dir, "latex_writeup", "figures", "info.json")
            proc = run("emit-info", run_dir, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertTrue(data["ok"])
            with open(out, encoding="utf-8") as fh:
                entries = json.load(fh)
            self.assertEqual([e["name"] for e in entries], ["fig1_panel.pdf", "fig2_brechas.pdf"])
            self.assertEqual(
                entries[0]["caption"], "Paired RMSE gaps for the panel estimator."
            )
            self.assertEqual(set(entries[0]), {"name", "caption"})
        finally:
            shutil.rmtree(tmp)

    def test_emit_info_counts_missing_captions(self):
        tmp, run_dir = copy_example("clean_run")
        try:
            os.remove(os.path.join(run_dir, "latex_writeup", "figures", "info.json"))
            proc = run("emit-info", run_dir, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["captions_missing"], 1)
            self.assertEqual(data["entries"][0]["caption"], "(caption not provided)")
        finally:
            shutil.rmtree(tmp)

    def test_emit_info_refuses_overwrite_without_force(self):
        tmp, run_dir = copy_example("clean_run")
        try:
            proc = run("emit-info", run_dir, "--json")
            self.assertEqual(proc.returncode, 1)
            data = json.loads(proc.stdout)
            self.assertFalse(data["ok"])
            self.assertIn("--force", data["reason"])
        finally:
            shutil.rmtree(tmp)

    def test_emit_info_force_overwrites(self):
        tmp, run_dir = copy_example("clean_run")
        try:
            proc = run("emit-info", run_dir, "--force", "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue(json.loads(proc.stdout)["ok"])
        finally:
            shutil.rmtree(tmp)

    def test_emit_info_with_captions_file(self):
        tmp, run_dir = copy_example("clean_run")
        try:
            os.remove(os.path.join(run_dir, "latex_writeup", "figures", "info.json"))
            caps = os.path.join(tmp, "caps.json")
            with open(caps, "w", encoding="utf-8") as fh:
                json.dump({"fig1_panel.pdf": "Custom caption."}, fh)
            proc = run("emit-info", run_dir, "--captions", caps, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["captions_missing"], 0)
            self.assertEqual(data["entries"][0]["caption"], "Custom caption.")
        finally:
            shutil.rmtree(tmp)

    def test_emit_info_without_figures_exits_one(self):
        tmp = tempfile.mkdtemp(prefix="figreconcile-")
        try:
            run_dir = os.path.join(tmp, "run")
            os.makedirs(os.path.join(run_dir, "latex_writeup"))
            with open(os.path.join(run_dir, "latex_writeup", "paper.tex"), "w") as fh:
                fh.write("\\documentclass{article}\\begin{document}x\\end{document}")
            proc = run("emit-info", run_dir, "--json")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["reason"], "no-provided-figures")
        finally:
            shutil.rmtree(tmp)


class RelinkTests(unittest.TestCase):
    def _map(self, tmp, payload):
        path = os.path.join(tmp, "map.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return path

    def test_relink_dry_run_does_not_modify(self):
        tmp, run_dir = copy_example("issue55_run")
        try:
            tex = os.path.join(run_dir, "latex_writeup", "paper.tex")
            before = open(tex, encoding="utf-8").read()
            mapping = self._map(tmp, {"fig_evaluation_panel_map.pdf": "figures/fig2_brechas.pdf"})
            proc = run("relink", run_dir, "--map", mapping, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["applied"], 0)
            self.assertEqual(open(tex, encoding="utf-8").read(), before)
        finally:
            shutil.rmtree(tmp)

    def test_relink_write_rewrites_target(self):
        tmp, run_dir = copy_example("issue55_run")
        try:
            mapping = self._map(tmp, {"figures/fig_evaluation_panel_map.pdf": "figures/fig2_brechas.pdf"})
            proc = run("relink", run_dir, "--map", mapping, "--write", "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data["applied"], 1)
            tex = open(os.path.join(run_dir, "latex_writeup", "paper.tex"), encoding="utf-8").read()
            self.assertNotIn("fig_evaluation_panel_map.pdf", tex)
            self.assertIn("figures/fig2_brechas.pdf", tex)
        finally:
            shutil.rmtree(tmp)

    def test_relink_unmapped_target_fails(self):
        tmp, run_dir = copy_example("issue55_run")
        try:
            mapping = self._map(tmp, {"something_else.pdf": "figures/fig2_brechas.pdf"})
            proc = run("relink", run_dir, "--map", mapping, "--json")
            self.assertEqual(proc.returncode, 1)
            data = json.loads(proc.stdout)
            self.assertEqual(data["unresolved"], 1)
            self.assertEqual(data["changes"][0]["reason"], "no mapping entry")
        finally:
            shutil.rmtree(tmp)

    def test_relink_replacement_must_exist(self):
        tmp, run_dir = copy_example("issue55_run")
        try:
            mapping = self._map(tmp, {"fig_evaluation_panel_map.pdf": "figures/nope.pdf"})
            proc = run("relink", run_dir, "--map", mapping, "--write", "--json")
            self.assertEqual(proc.returncode, 1)
            self.assertEqual(json.loads(proc.stdout)["changes"][0]["reason"], "replacement does not resolve to a file")
        finally:
            shutil.rmtree(tmp)

    def test_relink_bad_mapping_is_usage_error(self):
        tmp, run_dir = copy_example("issue55_run")
        try:
            mapping = self._map(tmp, ["not", "an", "object"])
            proc = run("relink", run_dir, "--map", mapping)
            self.assertEqual(proc.returncode, 2)
        finally:
            shutil.rmtree(tmp)


class CliSurfaceTests(unittest.TestCase):
    def test_version(self):
        proc = run("--version")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("figreconcile", proc.stdout)

    def test_no_subcommand_is_usage_error(self):
        proc = run()
        self.assertEqual(proc.returncode, 2)

    def test_bad_captions_json_is_usage_error(self):
        tmp, run_dir = copy_example("clean_run")
        try:
            os.remove(os.path.join(run_dir, "latex_writeup", "figures", "info.json"))
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as fh:
                fh.write("{not json")
            proc = run("emit-info", run_dir, "--captions", bad, "--json")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not valid JSON", proc.stderr)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()