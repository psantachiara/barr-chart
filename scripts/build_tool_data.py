"""Build the comparison tool's dataset (tool/barr-charts.json) from the transcription tables.

    python3 scripts/build_tool_data.py

One JSON file, read by index.html and by planes.py, so the tool and the written
report always show the same numbers. Every chart is included with its set
(core | secondary); the tool shows the core set.
"""
import csv, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_KEY = {"black": "internal", "red": "external"}
REL = {"influenced": "influence", "sitedIn": "siting", "memberOf": "membership", "relatedTo": "related"}


def read(name):
    p = DATA / name
    if not p.exists():
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def ink_key(raw):
    raw = raw.split()
    if raw == ["none"]:
        return {}
    if not raw:
        return dict(DEFAULT_KEY)
    return {k: v for k, v in (x.split("=", 1) for x in raw if "=" in x)}


def year(s):
    m = re.search(r"\d{4}", s or "")
    return int(m.group()) if m else None


charts = read("charts.csv")
concepts = {r["concept_id"]: {"l": r["pref_label"], "t": r["type"].lower(), "note": r["note"]} for r in read("concepts.csv")}
nodes, edges = read("nodes.csv"), read("edges.csv")
legend, prag = read("legend.csv"), {r["chart_id"]: r for r in read("pragmatic.csv")}

versions = []
for i, c in enumerate(charts):
    cid = c["chart_id"]
    key = ink_key(c.get("ink_key", ""))
    ns = [n for n in nodes if n["chart_id"] == cid]
    p = prag.get(cid, {})
    versions.append({
        "id": cid, "name": c["title"] or cid, "set": c.get("set") or "core", "pos": i + 1,
        "date": c["date"], "dateBasis": c["date_basis"], "archival": c["archival_reference"], "note": c["note"],
        "facsimile": c["facsimile"] or f"img/{cid}.jpg",
        "inkKey": key,
        "legend": [{"code": t["code"], "meaning": t["meaning"]} for t in legend if t["chart_id"] == cid],
        "pragmatic": {"support": p.get("support", ""), "audience": p.get("audience", ""), "permanence": p.get("permanence", ""),
                      "constraint": p.get("constraint", ""), "fn": p.get("function", "")},
        "nodes": [n["concept_id"] for n in ns],
        "labels": {n["concept_id"]: n["label_as_written"] for n in ns},
        "years": {n["concept_id"]: year(n["year_on_scale"]) for n in ns if year(n["year_on_scale"])},
        "ink": {n["concept_id"]: n["ink"] for n in ns if n["ink"]},
        "form": {n["concept_id"]: n["form"].split() for n in ns if n["form"]},
        "tags": {n["concept_id"]: n["tags"].split() for n in ns if n["tags"]},
        "external": [n["concept_id"] for n in ns if key.get(n["ink"]) == "external"],
        "certainty": {n["concept_id"]: n["certainty"] for n in ns if n["certainty"] and n["certainty"] != "certain"},
        # edge: [source, target, relation, line, colour, scope (from the ink key), certainty if not certain]
        "edges": [[e["source"], e["target"], REL.get(e["relation"], "related"), e["line"] or "", e["colour"] or "",
                   key.get(e["colour"], "") if e["relation"] == "influenced" else "",
                   e["certainty"] if e["certainty"] != "certain" else ""]
                  for e in edges if e["chart_id"] == cid and e["target"]],
    })

sequences = [{"id": s["sequence_id"], "label": s["label"], "basis": s["basis"], "proposedBy": s["proposed_by"],
              "charts": s["charts"].split(), "note": s["note"]} for s in read("sequences.csv")]

out = {"generated_from": "data/*.csv (Barr Chart Transcriber export)", "concepts": concepts,
       "versions": versions, "sequences": sequences}
(ROOT / "tool").mkdir(exist_ok=True)
(ROOT / "tool" / "barr-charts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
core = [v["name"] for v in versions if v["set"] == "core"]
print(f"tool/barr-charts.json: {len(versions)} charts ({', '.join(core)} core), {len(concepts)} entities")
