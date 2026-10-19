"""Write index.html: tool/template.html with tool/barr-charts.json embedded.

    python3 scripts/build_tool_data.py   # data/*.csv  -> tool/barr-charts.json
    python3 scripts/build_tool.py        # template + json -> index.html

Embedding the dataset lets the page work opened straight from disk (file://) as well as on
GitHub Pages. If the placeholder is left in, the page fetches tool/barr-charts.json instead.
"""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
tpl = (ROOT / "tool" / "template.html").read_text(encoding="utf-8")
data = json.loads((ROOT / "tool" / "barr-charts.json").read_text(encoding="utf-8"))
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
assert tpl.count("/*DATASET*/") == 1, "template must contain the /*DATASET*/ placeholder once"
(ROOT / "index.html").write_text(tpl.replace("/*DATASET*/", blob), encoding="utf-8")
core = sum(1 for v in data["versions"] if v["set"] == "core")
print(f"index.html: {len(data['versions'])} charts ({core} core), {len(blob) // 1024} KB of data embedded")
