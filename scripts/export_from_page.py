"""Write data/*.csv from a JSON dump of the Barr Chart Transcriber's store.

The page's own "Download the tables" does the same; this script lets the tables be
regenerated from a store dump (charts/<id>.json and vocab/concepts.json) without a browser.

    python3 scripts/export_from_page.py path/to/dump/   # dump has charts/ and vocab/
"""
import csv, json, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DUMP = pathlib.Path(sys.argv[1])
INKS = ["black", "red", "blue", "graphite", "other"]
DEFAULT_KEY = {"black": "internal", "red": "external"}


def body(p):
    d = json.load(open(p, encoding="utf-8"))
    return d["data"] if isinstance(d.get("data"), dict) else d


charts = {p.stem: body(p) for p in (DUMP / "charts").glob("*.json")}
concepts = body(DUMP / "vocab" / "concepts.json")["items"]
order = sorted(charts, key=lambda k: (charts[k].get("pos", 99), k))


def meaning(c, ink):
    key = c.get("inkKey") or DEFAULT_KEY
    return key.get(ink, "")


def write(name, header, rows):
    with open(ROOT / "data" / name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)


used = {k for c in charts.values() for k in c.get("nodes", {})}
write("charts.csv", ["chart_id", "title", "set", "archival_reference", "date", "date_basis", "facsimile", "ink_key", "note"],
      [[k, c.get("title", k), c.get("set") or "core", c.get("archival_reference", ""), c.get("date", ""), c.get("date_basis", ""),
        f"img/{k}.jpg", " ".join(f"{i}={meaning(c, i)}" for i in INKS if meaning(c, i)) or "none", c.get("note", "")]
       for k, c in ((k, charts[k]) for k in order)])
write("concepts.csv", ["concept_id", "type", "pref_label", "note"],
      [[k, v["type"], v["pref_label"], v.get("note", "")] for k, v in concepts.items() if k in used])
write("nodes.csv", ["chart_id", "concept_id", "label_as_written", "year_on_scale", "form", "ink", "tags", "certainty", "verified", "origin", "note"],
      [[k, cid, n.get("label", ""), n.get("date", ""), n.get("form", ""), n.get("ink", ""), " ".join(t for t in n.get("tags", []) if t),
        n.get("certainty", ""), n.get("verified", ""), n.get("origin", ""), n.get("note", "")]
       for k in order for cid, n in charts[k].get("nodes", {}).items()])
write("edges.csv", ["chart_id", "source", "target", "relation", "line", "colour", "certainty", "verified", "origin", "note"],
      [[k, e["source"], e["target"], e["relation"], e.get("line", ""), e.get("colour", ""), e.get("certainty", ""),
        e.get("verified", ""), e.get("origin", ""), e.get("note", "")]
       for k in order for e in charts[k].get("edges", []) if e.get("target")])
write("pragmatic.csv", ["chart_id", "support", "audience", "permanence", "constraint", "function"],
      [[k] + [(charts[k].get("pragmatic") or {}).get(f, "") for f in ("support", "audience", "permanence", "constraint", "fn")] for k in order])
write("legend.csv", ["chart_id", "code", "meaning"],
      [[k, t["code"], t.get("meaning", "")] for k in order for t in charts[k].get("legend", []) if t.get("code")])
print("wrote tables for", ", ".join(charts[k].get("title", k) for k in order))
