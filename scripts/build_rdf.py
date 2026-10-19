"""Build the linked-data edition of the Barr charts from the transcription tables.

    python3 scripts/build_rdf.py              # build, warn about unverified rows
    python3 scripts/build_rdf.py --strict     # refuse to build if any row is unverified

Reads   data/charts.csv, concepts.csv, nodes.csv, edges.csv, sequences.csv
Writes  out/barr-charts.trig      one named graph per chart + a catalogue graph
        out/validation.txt        everything the checks found

Graph layout
  <…/graph/catalogue>   chart records, reconciled concepts, sequences
  <…/chart/{id}>        what that chart asserts: entities as written, relations, marks
"""
import csv, sys, pathlib, re
from urllib.parse import quote
from collections import defaultdict
from rdflib import Dataset, Graph, Literal, Namespace, URIRef, BNode
from rdflib.namespace import RDF, RDFS, SKOS, DCTERMS, XSD
from rdflib.collection import Collection

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", ROOT / "out"
BASE = "https://psantachiara.github.io/barr-chart/"
BC = Namespace(BASE + "ns#")
ID = Namespace(BASE + "id/")
CH = Namespace(BASE + "chart/")
SEQ = Namespace(BASE + "sequence/")
CATALOGUE = URIRef(BASE + "graph/catalogue")

TYPES = {"Movement", "Person", "Place"}
RELATIONS = {"influenced", "sitedIn", "memberOf", "relatedTo"}
LINES = {"solid", "dotted", "dashed", "other", ""}
CERTAINTY = {"certain", "probable", "uncertain", ""}
INKS = {"black", "red", "blue", "graphite", "other", ""}
# Barr's key, applied only where the sheet distinguishes colours.
DEFAULT_KEY = {"black": "internal", "red": "external"}   # the Cover's key; applies where a chart sets none


def ink_key(chart_row):
    """Parse charts.csv ink_key, e.g. 'blue=internal graphite=external'. Empty -> the Cover's key."""
    raw = chart_row.get("ink_key", "").split()
    if raw == ["none"]:
        return {}
    if not raw:
        return dict(DEFAULT_KEY)
    return {k: v for k, v in (x.split("=", 1) for x in raw if "=" in x)}
WEIGHT = {"solid": "primary", "dotted": "secondary"}
BASIS = {"documented", "analytical"}
SLUG = re.compile(r"^[a-z0-9_]+$")


def read(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def find_cycles(edges):
    """Return influence cycles (each as a list of node ids) via DFS back-edges."""
    adj = defaultdict(list)
    for s, t in edges:
        adj[s].append(t)
    colour, stack, cycles = {}, [], []

    def visit(u):
        colour[u] = 1; stack.append(u)
        for v in adj[u]:
            if colour.get(v) == 1:
                cycles.append(stack[stack.index(v):] + [v])
            elif v not in colour:
                visit(v)
        stack.pop(); colour[u] = 2

    for n in list(adj):
        if n not in colour:
            visit(n)
    return cycles


def main(strict=False):
    errors, warnings, info = [], [], []
    charts, concepts = read("charts.csv"), read("concepts.csv")
    nodes, edges, seqs = read("nodes.csv"), read("edges.csv"), read("sequences.csv")
    chart_ids = {c["chart_id"] for c in charts}
    legend = read("legend.csv") if (DATA / "legend.csv").exists() else []
    codes = defaultdict(dict)
    for i, t in enumerate(legend, start=2):
        if t["chart_id"] not in chart_ids:
            errors.append(f"legend.csv line {i}: unknown chart '{t['chart_id']}'")
        if not t["code"]:
            errors.append(f"legend.csv line {i}: empty code")
        elif t["code"] in codes[t["chart_id"]]:
            errors.append(f"legend.csv line {i}: code '{t['code']}' defined twice for {t['chart_id']}")
        codes[t["chart_id"]][t["code"]] = t["meaning"]

    concept = {c["concept_id"]: c for c in concepts}

    # ---- checks -------------------------------------------------------------
    for c in concepts:
        if not SLUG.match(c["concept_id"]):
            errors.append(f"concepts: bad id '{c['concept_id']}' (use a-z, 0-9, _)")
        if c["type"] not in TYPES:
            errors.append(f"concepts: {c['concept_id']} has type '{c['type']}' (expected {sorted(TYPES)})")

    on_chart = defaultdict(set)
    seen = set()
    for i, n in enumerate(nodes, start=2):
        key = (n["chart_id"], n["concept_id"])
        if n["chart_id"] not in chart_ids:
            errors.append(f"nodes.csv line {i}: unknown chart '{n['chart_id']}'")
        if n["concept_id"] not in concept:
            errors.append(f"nodes.csv line {i}: unknown concept '{n['concept_id']}' (add it to concepts.csv)")
        if key in seen:
            errors.append(f"nodes.csv line {i}: duplicate {key}")
        if n["certainty"] not in CERTAINTY:
            errors.append(f"nodes.csv line {i}: certainty '{n['certainty']}'")
        for code in n.get("tags", "").split():
            if code not in codes[n["chart_id"]]:
                errors.append(f"nodes.csv line {i}: tag '{code}' is not in the legend of {n['chart_id']} (legend.csv)")
        if n.get("ink", "") not in INKS:
            errors.append(f"nodes.csv line {i}: ink '{n['ink']}' (expected {sorted(INKS - {''})})")
        if not n["label_as_written"]:
            warnings.append(f"nodes.csv line {i}: {key} has no label_as_written")
        seen.add(key); on_chart[n["chart_id"]].add(n["concept_id"])

    seen = set()
    for i, e in enumerate(edges, start=2):
        key = (e["chart_id"], e["source"], e["relation"], e["target"])
        if e["chart_id"] not in chart_ids:
            errors.append(f"edges.csv line {i}: unknown chart '{e['chart_id']}'")
        for end in ("source", "target"):
            if e[end] not in on_chart[e["chart_id"]]:
                errors.append(f"edges.csv line {i}: {e[end]} is not listed in nodes.csv for chart {e['chart_id']}")
        if e["relation"] not in RELATIONS:
            errors.append(f"edges.csv line {i}: relation '{e['relation']}' (expected {sorted(RELATIONS)})")
        if e["line"] not in LINES:
            errors.append(f"edges.csv line {i}: line '{e['line']}'")
        if e["certainty"] not in CERTAINTY:
            errors.append(f"edges.csv line {i}: certainty '{e['certainty']}'")
        if e["colour"] not in INKS:
            errors.append(f"edges.csv line {i}: colour '{e['colour']}' (expected {sorted(INKS - {''})})")
        if e["relation"] == "sitedIn" and concept.get(e["target"], {}).get("type") != "Place":
            warnings.append(f"edges.csv line {i}: sitedIn target {e['target']} is not a Place")
        if e["relation"] == "memberOf" and concept.get(e["source"], {}).get("type") != "Person":
            warnings.append(f"edges.csv line {i}: memberOf source {e['source']} is not a Person")
        if key in seen:
            errors.append(f"edges.csv line {i}: duplicate {key}")
        seen.add(key)

    for s in seqs:
        if s["basis"] not in BASIS:
            errors.append(f"sequences: {s['sequence_id']} basis '{s['basis']}' (documented | analytical)")
        for c in s["charts"].split():
            if c not in chart_ids:
                errors.append(f"sequences: {s['sequence_id']} names unknown chart '{c}'")

    for c in charts:
        if c.get("set", "core") not in ("core", "secondary", ""):
            errors.append(f"charts: {c['chart_id']} set '{c['set']}' (core | secondary)")
        for x in [y for y in c.get("ink_key", "").split() if y != "none"]:
            ink, _, meaning = x.partition("=")
            if ink not in INKS or meaning not in ("internal", "external"):
                errors.append(f"charts: {c['chart_id']} ink_key entry '{x}' (expected ink=internal|external)")
        if not c["archival_reference"]:
            warnings.append(f"charts: {c['chart_id']} has no archival_reference")

    unverified_n = sum(1 for n in nodes if not n["verified"])
    unverified_e = sum(1 for e in edges if not e["verified"])
    legacy = sum(1 for r in nodes + edges if r["origin"] == "legacy" and not r["verified"])
    info.append(f"unverified rows: {unverified_n} nodes, {unverified_e} edges ({legacy} of them seeded from the legacy file)")
    if strict and (unverified_n or unverified_e):
        errors.append("--strict: unverified rows remain")

    for cid in sorted(chart_ids):
        infl = [(e["source"], e["target"]) for e in edges
                if e["chart_id"] == cid and e["relation"] == "influenced"]
        cyc = find_cycles(infl)
        info.append(f"{cid}: {len(on_chart[cid])} entities, {len(infl)} influence arrows, "
                    + ("acyclic (well-formed DAG)" if not cyc else f"CYCLES: {cyc}"))

    report = ["ERRORS"] + (errors or ["none"]) + ["", "WARNINGS"] + (warnings or ["none"]) + ["", "SUMMARY"] + info
    OUT.mkdir(exist_ok=True)
    (OUT / "validation.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    if errors:
        print("\n".join(report)); print("\nNot built: fix the errors above."); sys.exit(1)

    # ---- build --------------------------------------------------------------
    ds = Dataset()
    ds.bind("bc", BC); ds.bind("id", ID); ds.bind("chart", CH); ds.bind("seq", SEQ)
    ds.bind("skos", SKOS); ds.bind("dcterms", DCTERMS)
    cat = ds.graph(CATALOGUE)

    for c in concepts:
        u = ID[c["concept_id"]]
        cat.add((u, RDF.type, BC[c["type"]]))
        cat.add((u, SKOS.prefLabel, Literal(c["pref_label"], lang="en")))
        if c["note"]:
            cat.add((u, SKOS.note, Literal(c["note"])))

    for c in charts:
        u = CH[c["chart_id"]]
        cat.add((u, RDF.type, BC.Chart))
        cat.add((u, BC.set, Literal(c.get("set") or "core")))
        cat.add((u, RDFS.label, Literal(c["title"])))
        if c["archival_reference"]:
            cat.add((u, BC.archivalReference, Literal(c["archival_reference"])))
        if c["date"]:
            cat.add((u, DCTERMS.date, Literal(c["date"])))
        if c["date_basis"]:
            cat.add((u, DCTERMS.description, Literal("Date basis: " + c["date_basis"])))
        if c["note"]:
            cat.add((u, SKOS.note, Literal(c["note"])))

    for s in seqs:
        u = SEQ[s["sequence_id"]]
        cat.add((u, RDF.type, BC.Sequence))
        cat.add((u, RDFS.label, Literal(s["label"])))
        cat.add((u, BC.basis, Literal(s["basis"])))
        cat.add((u, BC.proposedBy, Literal(s["proposed_by"])))
        if s["note"]:
            cat.add((u, SKOS.note, Literal(s["note"])))
        head = BNode()
        Collection(cat, head, [CH[c] for c in s["charts"].split()])
        cat.add((u, BC.charts, head))

    for c in charts:
        g = ds.graph(CH[c["chart_id"]])
        key = ink_key(c)
        for ink, meaning in key.items():
            cat.add((CH[c["chart_id"]], BC.inkMeaning, Literal(f"{ink}={meaning}")))
        for code, meaning in codes[c["chart_id"]].items():
            tg = URIRef(f"{CH[c['chart_id']]}/tag/{quote(code, safe='')}")
            g.add((tg, RDF.type, BC.Tag)); g.add((tg, BC.code, Literal(code)))
            g.add((tg, RDFS.label, Literal(meaning))); g.add((tg, BC.inLegendOf, CH[c["chart_id"]]))
        for n in (n for n in nodes if n["chart_id"] == c["chart_id"]):
            u = ID[n["concept_id"]]
            g.add((u, BC.appearsOn, CH[c["chart_id"]]))
            if n["label_as_written"]:
                g.add((u, BC.labelAsWritten, Literal(n["label_as_written"])))
            if n["year_on_scale"]:
                g.add((u, BC.yearOnScale, Literal(n["year_on_scale"])))
            for f in n["form"].split():          # several marks may combine, e.g. "underlined semicircle"
                g.add((u, BC.form, Literal(f)))
            if n.get("ink"):
                g.add((u, BC.ink, Literal(n["ink"])))
            for code in n.get("tags", "").split():
                g.add((u, BC.taggedWith, URIRef(f"{CH[c['chart_id']]}/tag/{quote(code, safe='')}")))
            if key.get(n.get("ink", "")) == "external":   # by this chart's ink key
                g.add((u, BC.external, Literal(True)))
        for e in (e for e in edges if e["chart_id"] == c["chart_id"]):
            s, o, p = ID[e["source"]], ID[e["target"]], BC[e["relation"]]
            g.add((s, p, o))
            m = URIRef(f"{CH[c['chart_id']]}/mark/{e['source']}--{e['relation']}--{e['target']}")
            g.add((m, RDF.type, BC.Mark))
            g.add((m, BC.onChart, CH[c["chart_id"]]))
            g.add((m, BC["from"], s)); g.add((m, BC.to, o)); g.add((m, BC.relation, p))
            for col, prop in (("line", BC.line), ("colour", BC.colour), ("certainty", BC.certainty)):
                if e[col]:
                    g.add((m, prop, Literal(e[col])))
            if e["relation"] == "influenced":
                if key.get(e["colour"]):
                    g.add((m, BC.scope, Literal(key[e["colour"]])))
                if e["line"] in WEIGHT:
                    g.add((m, BC.weight, Literal(WEIGHT[e["line"]])))
            if e["verified"]:
                g.add((m, BC.verified, Literal(e["verified"])))
            if e["note"]:
                g.add((m, SKOS.note, Literal(e["note"])))

    ds.serialize(destination=OUT / "barr-charts.trig", format="trig")
    print("\n".join(report))
    print(f"\nBuilt {OUT/'barr-charts.trig'} ({sum(1 for _ in ds.quads())} quads, {len(charts)} chart graphs)")


if __name__ == "__main__":
    main(strict="--strict" in sys.argv)
