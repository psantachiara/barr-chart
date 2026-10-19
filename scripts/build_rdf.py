"""Build the linked-data edition of the Barr charts from the transcription tables.

    python3 scripts/build_rdf.py              # build, warn about unverified rows
    python3 scripts/build_rdf.py --strict     # refuse to build if any row is unverified

Reads   data/charts.csv, concepts.csv, nodes.csv, edges.csv, legend.csv, sequences.csv,
        conventions.csv, alignments.csv
Writes  out/barr-charts.trig      the dataset (graphs below)
        out/validation.txt        everything the checks found

Vocabularies: DINO (vocab/dino.ttl) for marks, conventions and readings; the project
vocabulary (vocab/barr.ttl) for the relations the charts assert and the meanings their
conventions point to; SKOS, SKOS-XL, CIDOC CRM and Dublin Core for the rest.

Graph layout
  <…/graph/{chart}>        what one chart shows: the sheet, its diagram, its concept scheme,
                           its labels as written, its relation marks, conventions stated on it
  <…/graph/interpretation> what the analyst says: the reconciled index, identity across charts
                           (skos:exactMatch / closeMatch), conventions inferred from the drawing
  <…/graph/readings>       orderings proposed by readings
  <…/graph/derived>        what follows from marks and conventions (computed by query)
"""
import csv, sys, pathlib, re
from urllib.parse import quote
from collections import defaultdict
from rdflib import Dataset, Literal, Namespace, URIRef, BNode
from rdflib.namespace import RDF, RDFS, SKOS, DCTERMS, XSD, FOAF
from rdflib.collection import Collection

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA, OUT = ROOT / "data", ROOT / "out"
BASE = "https://psantachiara.github.io/barr-chart/"
DINO = Namespace("https://psantachiara.github.io/dino/ns#")
BARR = Namespace(BASE + "ns#")
CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
SKOSXL = Namespace("http://www.w3.org/2008/05/skos-xl#")
ID = Namespace(BASE + "id/")
CH = Namespace(BASE + "chart/")
READING = Namespace(BASE + "reading/")
GRAPH = Namespace(BASE + "graph/")
INTERP, READINGS, DERIVED = GRAPH.interpretation, GRAPH.readings, GRAPH.derived
ANALYST = "Pietro Santachiara"

TYPES = {"Movement": CRM.E55_Type, "Person": CRM.E21_Person, "Place": CRM.E53_Place}
RELATIONS = {"influenced": (BARR.influenced, DINO.Arrow), "sitedIn": (BARR.sitedIn, DINO.Juxtaposition),
             "memberOf": (BARR.memberOf, DINO.Enclosure), "relatedTo": (SKOS.related, DINO.Connector)}
LINES = {"solid": DINO.solid, "dotted": DINO.dotted, "dashed": DINO.dashed, "other": DINO.otherLine}
INK = {"black": DINO.black, "red": DINO.red, "blue": DINO.blue, "graphite": DINO.graphite, "other": DINO.otherInk}
SHAPES = {"boxed": DINO.box, "semicircle": DINO.semicircle, "underlined": DINO.underline, "oval": DINO.oval,
          "other": DINO.otherShape, "plain": DINO.plain}
GRAPHIC = {"box": DINO.box, "semicircle": DINO.semicircle, "underline": DINO.underline, "oval": DINO.oval,
           "solid": DINO.solid, "dotted": DINO.dotted, "dashed": DINO.dashed, "verticalPosition": DINO.verticalPosition,
           **{k: v for k, v in INK.items()}}
APPLIES = {"label": DINO.LabelMark, "relation": DINO.RelationMark, "any": None}
MEANINGS = {"internal", "external", "primary", "secondary", "sourceOutsideModernArt", "membership", "title", "date"}
CERTAINTY = {"certain", "probable", "uncertain", ""}
INKS = set(INK) | {""}
BASIS = {"documented", "analytical"}
DEFAULT_KEY = {"black": "internal", "red": "external"}   # the Cover's key; applies where a chart sets none
SLUG = re.compile(r"^[a-z0-9_]+$")


def positions_of(raw):
    """The positions a label is written at on the scale: '1910, 1917' -> ['1910', '1917']."""
    return [p.strip() for p in (raw or "").split(",") if p.strip()]


def label_u(cid, concept, position=None):
    """A written label. A concept written once has one label mark; written more than once, one per position."""
    base = f"{BASE}chart/{cid}/label/{concept}"
    return URIRef(f"{base}/{position}" if position else base)


def ink_key(chart_row):
    """Parse charts.csv ink_key, e.g. 'blue=internal graphite=external'. Empty -> the Cover's key; 'none' -> {}."""
    raw = chart_row.get("ink_key", "").split()
    if raw == ["none"]:
        return {}
    if not raw:
        return dict(DEFAULT_KEY)
    return {k: v for k, v in (x.split("=", 1) for x in raw if "=" in x)}


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
    C_LABEL = {k: v["pref_label"] for k, v in concept.items()}

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
        for f in n["form"].split():
            if f not in SHAPES:
                errors.append(f"nodes.csv line {i}: form '{f}' (expected {sorted(SHAPES)})")
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
        if e["line"] not in set(LINES) | {""}:
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

    conventions = read("conventions.csv") if (DATA / "conventions.csv").exists() else []
    for i, c in enumerate(conventions, start=2):
        if c["chart_id"] != "*" and c["chart_id"] not in chart_ids:
            errors.append(f"conventions.csv line {i}: unknown chart '{c['chart_id']}'")
        if c["applies_to"] not in APPLIES:
            errors.append(f"conventions.csv line {i}: applies_to '{c['applies_to']}' (label | relation | any)")
        if c["graphic_value"] not in GRAPHIC:
            errors.append(f"conventions.csv line {i}: graphic_value '{c['graphic_value']}' (expected {sorted(GRAPHIC)})")
        if c["signifies"] not in MEANINGS | {"noMeaning"}:
            errors.append(f"conventions.csv line {i}: signifies '{c['signifies']}' (expected {sorted(MEANINGS)} or noMeaning)")
        if c["basis"] not in ("statedOnSheet", "inferredByAnalyst"):
            errors.append(f"conventions.csv line {i}: basis '{c['basis']}' (statedOnSheet | inferredByAnalyst)")
    alignments = read("alignments.csv") if (DATA / "alignments.csv").exists() else []
    for i, a in enumerate(alignments, start=2):
        for end in ("source", "target"):
            if a[end] not in concept:
                errors.append(f"alignments.csv line {i}: unknown concept '{a[end]}'")
        if a["relation"] not in ("exactMatch", "closeMatch", "broadMatch", "narrowMatch", "relatedMatch"):
            errors.append(f"alignments.csv line {i}: relation '{a['relation']}' (a SKOS mapping property)")

    occurrences = read("occurrences.csv") if (DATA / "occurrences.csv").exists() else []
    edge_keys = {(e["chart_id"], e["source"], e["relation"], e["target"]) for e in edges}
    node_pos = {(n["chart_id"], n["concept_id"]): positions_of(n["year_on_scale"]) for n in nodes}
    occurrence = {}
    for i, o in enumerate(occurrences, start=2):
        key = (o["chart_id"], o["source"], o["relation"], o["target"])
        if key not in edge_keys:
            errors.append(f"occurrences.csv line {i}: no such relation {key} in edges.csv")
        for end, col in (("source", "from_position"), ("target", "to_position")):
            pos = node_pos.get((o["chart_id"], o[end]), [])
            if o[col] and (len(pos) < 2 or o[col] not in pos):
                errors.append(f"occurrences.csv line {i}: {o[end]} is not written at {o[col]} on {o['chart_id']} "
                              f"(positions in nodes.csv: {', '.join(pos) or 'none'})")
        occurrence[key] = o

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
    for k, v in (("dino", DINO), ("barr", BARR), ("crm", CRM), ("skosxl", SKOSXL), ("id", ID), ("chart", CH),
                 ("reading", READING), ("skos", SKOS), ("dcterms", DCTERMS), ("foaf", FOAF)):
        ds.bind(k, v)
    ig, rg = ds.graph(INTERP), ds.graph(READINGS)
    ig.add((INTERP, DCTERMS.creator, Literal(ANALYST)))
    ig.add((INTERP, DCTERMS.description, Literal("The analyst's statements: the reconciled index, identity across charts, conventions inferred from the drawing.")))

    # the reconciled index: one entry per referent, typed with CIDOC CRM
    index = ID["index"]
    ig.add((index, RDF.type, SKOS.ConceptScheme)); ig.add((index, RDFS.label, Literal("Reconciled index")))
    for c in concepts:
        u = ID[c["concept_id"]]
        ig.add((u, RDF.type, SKOS.Concept)); ig.add((u, RDF.type, TYPES[c["type"]]))
        ig.add((u, SKOS.inScheme, index))
        ig.add((u, SKOS.prefLabel, Literal(c["pref_label"], lang="en")))
        if c["note"]:
            ig.add((u, SKOS.note, Literal(c["note"])))
    for a in alignments:
        ig.add((ID[a["source"]], SKOS[a["relation"]], ID[a["target"]]))
        if a["note"]:
            ig.add((ID[a["source"]], SKOS.editorialNote, Literal(f"{a['relation']} {a['target']}: {a['note']}")))

    def gv_slug(v):
        return str(v).split("#")[-1]

    for c in charts:
        cid = c["chart_id"]
        g = ds.graph(GRAPH[cid])
        sheet, diagram, scheme = CH[cid], URIRef(f"{CH[cid]}/diagram"), URIRef(f"{CH[cid]}/scheme")
        concept_u = lambda k: URIRef(f"{CH[cid]}/concept/{k}")

        # the sheet, the diagram it shows, the concept scheme the diagram expresses
        g.add((sheet, RDF.type, CRM["E22_Human-Made_Object"])); g.add((sheet, RDFS.label, Literal(c["title"])))
        if c["archival_reference"]:
            g.add((sheet, DCTERMS.identifier, Literal(c["archival_reference"])))
        if c["date"]:
            g.add((sheet, DCTERMS.created, Literal(c["date"])))
        if c["date_basis"]:
            g.add((sheet, SKOS.note, Literal("Date basis: " + c["date_basis"])))
        if c.get("facsimile"):
            g.add((sheet, FOAF.depiction, URIRef(BASE + c["facsimile"])))
        if c["note"]:
            g.add((sheet, SKOS.note, Literal(c["note"])))
        g.add((sheet, CRM.P65_shows_visual_item, diagram))
        g.add((diagram, RDF.type, CRM.E36_Visual_Item)); g.add((diagram, DINO.expresses, scheme))
        g.add((scheme, RDF.type, SKOS.ConceptScheme)); g.add((scheme, RDFS.label, Literal(f"{c['title']}: concepts")))
        ig.add((sheet, DCTERMS.type, BARR.coreSet if (c.get("set") or "core") == "core" else BARR.secondarySet))

        # concepts and their labels as written (each label is a SKOS-XL label and a mark)
        used_inks = set()
        for n in (n for n in nodes if n["chart_id"] == cid):
            k = n["concept_id"]; cu = concept_u(k)
            g.add((cu, RDF.type, SKOS.Concept)); g.add((cu, SKOS.inScheme, scheme))
            # one label mark per written occurrence: "1910, 1917" means the label is written twice
            positions = positions_of(n["year_on_scale"])
            for y in positions or [None]:
                lab = label_u(cid, k, y if len(positions) > 1 else None)
                g.add((lab, RDF.type, DINO.LabelMark)); g.add((lab, SKOSXL.literalForm, Literal(n["label_as_written"] or C_LABEL[k])))
                g.add((cu, SKOSXL.prefLabel, lab)); g.add((lab, DINO.notates, cu)); g.add((diagram, CRM.P106_is_composed_of, lab))
                if n["ink"]:
                    g.add((lab, DINO.graphicValue, INK[n["ink"]])); used_inks.add(n["ink"])
                for f in n["form"].split():
                    if SHAPES[f] is not None:
                        g.add((lab, DINO.graphicValue, SHAPES[f]))
                if y:
                    g.add((lab, DINO.positionOnScale, Literal(y, datatype=XSD.gYear) if re.fullmatch(r"\d{4}", y) else Literal(y)))
                    g.add((lab, DINO.graphicValue, DINO.verticalPosition))
                for code in n.get("tags", "").split():
                    g.add((lab, DINO.carriesCode, Literal(code)))
                if n["certainty"]:
                    g.add((lab, DINO.certainty, Literal(n["certainty"])))
                if n["verified"]:
                    g.add((lab, DINO.checkedOn, Literal(n["verified"], datatype=XSD.date)))
                if n["note"]:
                    g.add((lab, SKOS.note, Literal(n["note"])))
            ig.add((cu, SKOS.exactMatch, ID[k]))        # identity across charts is the analyst's statement

        # relation marks, and the plain triple each records
        for e in (e for e in edges if e["chart_id"] == cid):
            rel, kind = RELATIONS[e["relation"]]
            m = URIRef(f"{CH[cid]}/mark/{e['source']}--{e['relation']}--{e['target']}")
            s_, o_ = concept_u(e["source"]), concept_u(e["target"])
            g.add((s_, rel, o_))
            g.add((m, RDF.type, kind)); g.add((diagram, CRM.P106_is_composed_of, m))
            g.add((m, DINO["from"], s_)); g.add((m, DINO.to, o_)); g.add((m, DINO.records, rel))
            occ = occurrence.get((cid, e["source"], e["relation"], e["target"]))
            if occ and occ["from_position"]:
                g.add((m, DINO.fromMark, label_u(cid, e["source"], occ["from_position"])))
            if occ and occ["to_position"]:
                g.add((m, DINO.toMark, label_u(cid, e["target"], occ["to_position"])))
            if e["line"]:
                g.add((m, DINO.graphicValue, LINES[e["line"]]))
            if e["colour"]:
                g.add((m, DINO.graphicValue, INK[e["colour"]])); used_inks.add(e["colour"])
            if e["certainty"]:
                g.add((m, DINO.certainty, Literal(e["certainty"])))
            if e["verified"]:
                g.add((m, DINO.checkedOn, Literal(e["verified"], datatype=XSD.date)))
            if e["note"]:
                g.add((m, SKOS.note, Literal(e["note"])))

        # conventions stated on the sheet: the chart's own legend
        for code, meaning in codes[cid].items():
            cv = URIRef(f"{CH[cid]}/convention/legend-{quote(code, safe='')}")
            lc = URIRef(f"{CH[cid]}/legend/{quote(code, safe='')}")
            g.add((lc, RDF.type, SKOS.Concept)); g.add((lc, SKOS.inScheme, scheme)); g.add((lc, SKOS.prefLabel, Literal(meaning)))
            g.add((cv, RDF.type, DINO.Convention)); g.add((cv, DINO.holdsFor, diagram)); g.add((cv, DINO.code, Literal(code)))
            g.add((cv, DINO.signifies, lc)); g.add((cv, DINO.basis, DINO.statedOnSheet))

        # conventions inferred by the analyst: the ink key (and inks that mean nothing), then conventions.csv
        def convention(slug, value, meaning, applies=None, note=""):
            cv = URIRef(f"{CH[cid]}/convention/{slug}")
            ig.add((cv, RDF.type, DINO.Convention)); ig.add((cv, DINO.holdsFor, diagram))
            ig.add((cv, DINO.graphicValue, value)); ig.add((cv, DINO.signifies, meaning))
            ig.add((cv, DINO.basis, DINO.inferredByAnalyst))
            if applies is not None:
                ig.add((cv, DINO.appliesTo, applies))
            if note:
                ig.add((cv, SKOS.note, Literal(note)))
        key = ink_key(c)
        for ink in sorted(used_inks):                 # only inks the chart uses: a key never invents marks
            meaning = key.get(ink)
            convention(f"ink-{ink}", INK[ink], BARR[meaning] if meaning else DINO.noMeaning)
        present = {o for _, _, o in g.triples((None, DINO.graphicValue, None))}
        for r in conventions:
            if r["chart_id"] in ("*", cid) and GRAPHIC[r["graphic_value"]] in present:
                convention(r["graphic_value"], GRAPHIC[r["graphic_value"]],
                           DINO.noMeaning if r["signifies"] == "noMeaning" else BARR[r["signifies"]],
                           APPLIES[r["applies_to"]], r["note"])

    for s in seqs:
        u = READING[s["sequence_id"]]
        rg.add((u, RDF.type, DINO.Reading)); rg.add((u, RDFS.label, Literal(s["label"])))
        rg.add((u, DINO.basis, DINO[s["basis"]])); rg.add((u, DCTERMS.creator, Literal(s["proposed_by"])))
        if s["note"]:
            rg.add((u, SKOS.note, Literal(s["note"])))
        head = BNode()
        Collection(rg, head, [CH[c] for c in s["charts"].split()])
        rg.add((u, DINO.orders, head))

    # derived: what each mark signifies, by the conventions of its diagram
    dg = ds.graph(DERIVED)
    for t in ds.query((ROOT / "queries" / "derive_meanings.rq").read_text()):
        dg.add(t)

    ds.serialize(destination=OUT / "barr-charts.trig", format="trig")
    print("\n".join(report))
    print(f"\nBuilt {OUT/'barr-charts.trig'} ({sum(1 for _ in ds.quads())} quads; {len(charts)} chart graphs, "
          f"interpretation, readings, derived: {len(dg)} derived statements)")


if __name__ == "__main__":
    main(strict="--strict" in sys.argv)
