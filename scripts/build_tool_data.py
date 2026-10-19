"""Build the comparison tool's dataset (tool/barr-charts.json) from the linked data.

    python3 scripts/build_rdf.py          # first: out/barr-charts.trig from data/*.csv
    python3 scripts/build_tool_data.py    # then:  tool/barr-charts.json, by SPARQL over the TriG

Everything the tool and planes.py show comes from the linked data, through the queries in
queries/tool/: wording, years and forms from each chart's graph; identity across charts from
the analyst's skos:exactMatch; every meaning (internal, external, ...) from the derived graph,
which follows from each chart's conventions; conventions and readings as stated in the data.
Nothing is read from the CSV tables.

Linked data has no order, so the dataset is put in a canonical one: charts by title, entities
and relations by identifier, readings in the order their rdf:List gives.
"""
import json, pathlib, re
from collections import defaultdict
from rdflib import Dataset, URIRef
from rdflib.collection import Collection

ROOT = pathlib.Path(__file__).resolve().parent.parent
Q = ROOT / "queries" / "tool"
BASE = "https://psantachiara.github.io/barr-chart/"
DINO = "https://psantachiara.github.io/dino/ns#"
BARR = BASE + "ns#"
CRM = "http://www.cidoc-crm.org/cidoc-crm/"
SKOS = "http://www.w3.org/2004/02/skos/core#"
KIND = {CRM + "E55_Type": "movement", CRM + "E21_Person": "person", CRM + "E53_Place": "place"}
REL = {BARR + "influenced": "influence", BARR + "sitedIn": "siting", BARR + "memberOf": "membership", SKOS + "related": "related"}
INKS = {"black", "red", "blue", "graphite", "otherInk"}
LINES = {"solid", "dotted", "dashed", "otherLine"}
FORM = {"box": "boxed", "underline": "underlined", "semicircle": "semicircle", "oval": "oval", "otherShape": "other", "plain": "plain"}


def year(s):
    m = re.search(r"\d{4}", s or "")
    return int(m.group()) if m else None


def local(u):
    s = str(u)
    for p in (BASE + "chart/", BASE + "id/", BASE + "reading/", BARR, DINO):
        if s.startswith(p):
            return s[len(p):]
    return s


ds = Dataset()
ds.parse(ROOT / "out" / "barr-charts.trig", format="trig")
vocab = ds.graph(URIRef(BASE + "graph/vocabularies"))      # in memory only, for the labels of meanings
vocab.parse(ROOT / "vocab" / "dino.ttl"); vocab.parse(ROOT / "vocab" / "barr.ttl")
run = lambda name: ds.query((Q / name).read_text())

# ---- the reconciled index
concepts = {}
for r in run("index.rq"):
    concepts[local(r.entity)] = {"l": str(r.label), "t": KIND[str(r.kind)], "note": str(r.note) if r.note else ""}
concepts = dict(sorted(concepts.items()))

# ---- sheets
sheets = {}
for r in run("sheets.rq"):
    notes = [n for n in str(r.notes or "").split("\n") if n]
    basis = [n[len("Date basis: "):] for n in notes if n.startswith("Date basis: ")]
    sheets[local(r.sheet)] = {
        "name": str(r.title), "set": "core" if str(r.set) == BARR + "coreSet" else "secondary",
        "date": str(r.date or ""), "dateBasis": basis[0] if basis else "",
        "archival": str(r.archival or ""), "note": "\n".join(n for n in notes if not n.startswith("Date basis: ")),
        "facsimile": str(r.facsimile).replace(BASE, "") if r.facsimile else "",
        "pragmatic": {"support": str(r.support or ""), "audience": str(r.audience or ""), "permanence": str(r.permanence or ""),
                      "constraint": str(r.constraint or ""), "fn": str(r["function"] or "")}}

# ---- labels: one entity per label mark, with all its values
lab = defaultdict(lambda: defaultdict(lambda: {"values": set(), "codes": set(), "meanings": set()}))
for r in run("labels.rq"):
    e = lab[local(r.sheet)][local(r.entity)]
    e["wording"] = str(r.wording)
    if r.value is not None: e["values"].add(local(r.value))
    if r.code is not None: e["codes"].add(str(r.code))
    if r.meaning is not None: e["meanings"].add(local(r.meaning))
    if r.year is not None: e.setdefault("positions", set()).add(str(r.year))
    if r.certainty is not None: e["certainty"] = str(r.certainty)

# ---- relation marks
rel = defaultdict(dict)
for r in run("relations.rq"):
    m = rel[local(r.sheet)].setdefault(str(r.mark), {"from": local(r["from"]), "to": local(r.to), "rel": REL[str(r.relation)],
                                                      "values": set(), "meanings": set(), "certainty": "",
                                                      "fromPos": None, "toPos": None})
    if r.value is not None: m["values"].add(local(r.value))
    if r.meaning is not None: m["meanings"].add(local(r.meaning))
    if r.certainty is not None: m["certainty"] = str(r.certainty)
    if r.fromPos is not None: m["fromPos"] = year(str(r.fromPos))
    if r.toPos is not None: m["toPos"] = year(str(r.toPos))

# ---- conventions
conv = defaultdict(list)
for r in run("conventions.rq"):
    conv[local(r.sheet)].append({"value": local(r.value) if r.value is not None else "", "code": str(r.code or ""),
                                 "meaning": str(r.meaningLabel) if r.meaningLabel else local(r.meaning),
                                 "meaningId": local(r.meaning), "basis": local(r.basis),
                                 "appliesTo": local(r.applies) if r.applies is not None else ""})


def one(values, allowed):
    hit = sorted(v for v in values if v in allowed)
    return hit[0] if hit else ""


versions = []
for pos, sid in enumerate(sorted(sheets, key=lambda s: sheets[s]["name"]), start=1):
    sh, labels, marks, cs = sheets[sid], lab[sid], rel[sid], conv[sid]
    ids = sorted(labels)
    ink_name = lambda v: "other" if v == "otherInk" else v
    edges = []
    for m in sorted(marks.values(), key=lambda m: (m["from"], m["rel"], m["to"])):
        line = one(m["values"], LINES).replace("otherLine", "other")
        colour = ink_name(one(m["values"], INKS))
        scope = one(m["meanings"], {"internal", "external"}) if m["rel"] == "influence" else ""
        # [7], [8]: positions of the written occurrences the mark leaves from / arrives at, where a
        # concept is written more than once on the chart (otherwise null: the concept's one position)
        edges.append([m["from"], m["to"], m["rel"], line, colour, scope, m["certainty"] if m["certainty"] != "certain" else "",
                      m["fromPos"], m["toPos"]])
    ink_key = {ink_name(c["value"]): c["meaningId"] for c in cs
               if c["value"] in INKS and c["meaningId"] in ("internal", "external")}
    versions.append({
        "id": sid, "name": sh["name"], "set": sh["set"], "pos": pos,
        "date": sh["date"], "dateBasis": sh["dateBasis"], "archival": sh["archival"], "note": sh["note"],
        "facsimile": sh["facsimile"] or f"img/{sid}.jpg",
        "inkKey": dict(sorted(ink_key.items())),
        "legend": sorted(({"code": c["code"], "meaning": c["meaning"]} for c in cs if c["code"]), key=lambda t: t["code"]),
        "conventions": sorted(({k: c[k] for k in ("value", "code", "meaning", "basis", "appliesTo")} for c in cs),
                              key=lambda c: (c["basis"], c["value"], c["code"])),
        "pragmatic": sh["pragmatic"],
        "nodes": ids,
        "labels": {k: labels[k]["wording"] for k in ids},
        # a concept written more than once is placed at its first position; all positions are kept
        "years": {k: min(year(p) for p in labels[k]["positions"]) for k in ids if labels[k].get("positions")},
        "positions": {k: sorted(year(p) for p in labels[k]["positions"]) for k in ids if len(labels[k].get("positions", ())) > 1},
        "ink": {k: ink_name(one(labels[k]["values"], INKS)) for k in ids if one(labels[k]["values"], INKS)},
        "form": {k: sorted(FORM[v] for v in labels[k]["values"] if v in FORM) for k in ids
                 if any(v in FORM for v in labels[k]["values"])},
        "tags": {k: sorted(labels[k]["codes"]) for k in ids if labels[k]["codes"]},
        "external": [k for k in ids if "external" in labels[k]["meanings"]],
        "certainty": {k: labels[k]["certainty"] for k in ids if labels[k].get("certainty", "certain") != "certain"},
        "edges": edges,
    })

# ---- readings
rg = ds.graph(URIRef(BASE + "graph/readings"))
sequences = []
for r in run("readings.rq"):
    order = [local(c) for c in Collection(rg, rg.value(r.reading, URIRef(DINO + "orders")))]
    sequences.append({"id": local(r.reading), "label": str(r.label), "basis": local(r.basis), "proposedBy": str(r.creator),
                      "charts": order, "note": str(r.note or "")})
sequences.sort(key=lambda s: s["id"])

out = {"generated_from": "out/barr-charts.trig (by SPARQL, queries/tool/)", "concepts": concepts,
       "versions": versions, "sequences": sequences}
(ROOT / "tool").mkdir(exist_ok=True)
(ROOT / "tool" / "barr-charts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
core = [v["name"] for v in versions if v["set"] == "core"]
print(f"tool/barr-charts.json from the linked data: {len(versions)} charts ({', '.join(core)} core), {len(concepts)} entities")
