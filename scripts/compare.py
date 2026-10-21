"""Compare the charts, reading only the linked-data edition (out/barr-charts.trig).

    python3 scripts/compare.py

Writes to out/comparison/:
  charts.csv           per-chart counts (entities by type, relations by type, density, DAG check)
  pairs.csv            all pairs: entity and relation overlap (Jaccard), edit-grammar counts
  edit_grammar.json    all pairs in full: added/removed entities and relations, relabelings, restylings
  consensus_entities.csv / consensus_relations.csv
                       for each entity/relation, on how many charts (and which) it appears
  sequences.json       for each sequence in the catalogue: the edit grammar along that path
  report.md            readable summary of all the above

Order-free by design: every pair is compared both ways round, and sequences are
read from the data only where a reading proposes one.
"""
import csv, json, pathlib, itertools, sys
from collections import defaultdict
from rdflib import Dataset, URIRef
from rdflib.collection import Collection

ROOT = pathlib.Path(__file__).resolve().parent.parent
Q, OUT = ROOT / "queries", ROOT / "out" / "comparison"
BASE = "https://psantachiara.github.io/barr-chart/"
BARR = BASE + "ns#"
DINO = "https://psantachiara.github.io/dino/ns#"
CRM = "http://www.cidoc-crm.org/cidoc-crm/"
SKOS = "http://www.w3.org/2004/02/skos/core#"
RDF_TYPE = URIRef("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
RDFS_LABEL = URIRef("http://www.w3.org/2000/01/rdf-schema#label")
INTERP, READINGS = URIRef(BASE + "graph/interpretation"), URIRef(BASE + "graph/readings")
KIND = {CRM + "E55_Type": "Movement", CRM + "E21_Person": "Person", CRM + "E53_Place": "Place"}
REL = {SKOS + "related": "relatedTo"}


def short(u):
    s = str(u)
    if s in KIND:
        return KIND[s]
    if s in REL:
        return REL[s]
    for p in (BASE + "chart/", BASE + "id/", BASE + "reading/", BARR, DINO):
        if s.startswith(p):
            return s[len(p):]
    return s


def jaccard(a, b):
    return round(len(a & b) / len(a | b), 3) if a | b else 1.0


def acyclic(pairs):
    adj = defaultdict(set)
    for s, t in pairs:
        adj[s].add(t)
    state = {}

    def dfs(u):
        state[u] = 1
        for v in adj[u]:
            if state.get(v) == 1 or (v not in state and not dfs(v)):
                return False
        state[u] = 2
        return True

    return all(dfs(n) for n in list(adj) if n not in state)


def main(include_all=False):
    ds = Dataset()
    ds.parse(ROOT / "out" / "barr-charts.trig", format="trig")
    run = lambda name: ds.query((Q / name).read_text())

    ent, label, etype, ext = defaultdict(set), defaultdict(dict), {}, defaultdict(set)
    for r in run("entities_per_chart.rq"):
        c, e = short(r.chart), short(r.entity)
        ent[c].add(e); etype[e] = short(r.type)
        if r.label is not None:
            label[c][e] = str(r.label)
        if r.external is not None and r.external.toPython() is True:
            ext[c].add(e)

    rel, style, scope = defaultdict(set), defaultdict(dict), defaultdict(dict)
    for r in run("relations_per_chart.rq"):
        c, t = short(r.chart), (short(r["from"]), short(r.relation), short(r.to))
        rel[c].add(t)
        # style compares what a mark means (line, and scope by the chart's ink key), not raw ink colour,
        # so graphite on one chart and black on another are not counted as a restyling
        style[c][t] = (short(r.line) if r.line else "", short(r.scope) if r.scope else "")
        if r.scope is not None:
            scope[c][t] = short(r.scope)

    # charts are the sheets (crm:E22) in the chart graphs; the core / secondary grouping is the modeller's
    sheets = {s: ctx for s, _, _, ctx in ds.quads((None, RDF_TYPE, URIRef(CRM + "E22_Human-Made_Object"), None))}
    TITLE = {short(s): str(ds.graph(g).value(s, RDFS_LABEL) or short(s)) for s, g in sheets.items()}
    ig = ds.graph(INTERP)
    in_set = lambda s: ig.value(s, URIRef("http://purl.org/dc/terms/type")) == URIRef(BARR + "coreSet")
    charts = sorted((short(s) for s in sheets if include_all or in_set(s)), key=lambda c: TITLE[c])
    T = lambda c: TITLE.get(c, c)
    if not charts:
        print("No charts in the edition yet."); return
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- per chart ----------------------------------------------------------
    rows = []
    for c in charts:
        by_t = defaultdict(int)
        for e in ent[c]:
            by_t[etype[e]] += 1
        by_r = defaultdict(int)
        for _, p, _ in rel[c]:
            by_r[p] += 1
        infl = [(s, o) for s, p, o in rel[c] if p == "influenced"]
        n = len(ent[c])
        rows.append({"chart": c, "title": T(c), "entities": n, **{f"n_{t}": by_t[t] for t in ("Movement", "Person", "Place")}, "n_external": len(ext[c]),
                     **{f"r_{p}": by_r[p] for p in ("influenced", "associatedWithPlace", "memberOf", "relatedTo")},
                     "infl_internal": sum(1 for t_ in rel[c] if t_[1] == "influenced" and scope[c].get(t_) == "internal"),
                     "infl_external": sum(1 for t_ in rel[c] if t_[1] == "influenced" and scope[c].get(t_) == "external"),
                     "infl_secondary": sum(1 for s_, p_, o_ in rel[c] if p_ == "influenced" and style[c][(s_, p_, o_)][0] == "dotted"),
                     "influence_density": round(len(infl) / (n * (n - 1)), 4) if n > 1 else 0,
                     "influence_acyclic": acyclic(infl)})
    with open(OUT / "charts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

    # ---- all pairs ----------------------------------------------------------
    def diff(a, b):
        shared = ent[a] & ent[b]
        return {
            "entities_only_in_" + a: sorted(ent[a] - ent[b]),
            "entities_only_in_" + b: sorted(ent[b] - ent[a]),
            "relabelled": sorted([e, label[a].get(e, ""), label[b].get(e, "")] for e in shared
                                 if label[a].get(e) != label[b].get(e)),
            "relations_only_in_" + a: sorted(list(t) for t in rel[a] - rel[b]),
            "relations_only_in_" + b: sorted(list(t) for t in rel[b] - rel[a]),
            # a restyling is a change of line, or of meaning where both charts give the mark one
            "restyled": sorted([*t, *style[a][t], *style[b][t]] for t in rel[a] & rel[b]
                               if style[a][t][0] != style[b][t][0]
                               or (style[a][t][1] and style[b][t][1] and style[a][t][1] != style[b][t][1])),
            # relations that could have been drawn on both (both ends present on both charts) but appear on one only
            "relations_dropped_with_ends_kept": sorted(list(t) for t in rel[a] ^ rel[b]
                                                       if t[0] in shared and t[2] in shared),
        }

    pairs, grammar = [], {}
    for a, b in itertools.combinations(charts, 2):
        d = diff(a, b)
        grammar[f"{a}|{b}"] = d
        pairs.append({"a": a, "b": b,
                      "entity_jaccard": jaccard(ent[a], ent[b]),
                      "relation_jaccard": jaccard(rel[a], rel[b]),
                      "influence_jaccard": jaccard({t for t in rel[a] if t[1] == "influenced"},
                                                   {t for t in rel[b] if t[1] == "influenced"}),
                      "shared_entities": len(ent[a] & ent[b]),
                      "entities_only_a": len(ent[a] - ent[b]), "entities_only_b": len(ent[b] - ent[a]),
                      "relabelled": len(d["relabelled"]),
                      "relations_only_a": len(rel[a] - rel[b]), "relations_only_b": len(rel[b] - rel[a]),
                      "restyled": len(d["restyled"]),
                      "rewired": len(d["relations_dropped_with_ends_kept"])})
    with open(OUT / "pairs.csv", "w", newline="") as f:
        if pairs:
            w = csv.DictWriter(f, fieldnames=pairs[0].keys()); w.writeheader(); w.writerows(pairs)
    (OUT / "edit_grammar.json").write_text(json.dumps(grammar, indent=1, ensure_ascii=False))

    # ---- consensus ----------------------------------------------------------
    def consensus(sets, fname, keyname):
        where = defaultdict(list)
        for c in charts:
            for x in sets[c]:
                where[x].append(c)
        with open(OUT / fname, "w", newline="") as f:
            w = csv.writer(f); w.writerow([keyname, "n_charts", "charts"])
            for x, cs in sorted(where.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))):
                w.writerow([" ".join(x) if isinstance(x, tuple) else x, len(cs), " ".join(cs)])
        hist = defaultdict(int)
        for cs in where.values():
            hist[len(cs)] += 1
        return dict(sorted(hist.items()))

    h_ent = consensus(ent, "consensus_entities.csv", "entity")
    h_rel = consensus(rel, "consensus_relations.csv", "relation")

    # ---- sequences (genetic readings) --------------------------------------
    seqs = {}
    g = ds.graph(READINGS)
    for s in g.subjects(RDF_TYPE, URIRef(DINO + "Reading")):
        order = [short(c) for c in Collection(g, g.value(s, URIRef(DINO + "orders"))) if short(c) in charts]
        steps = []
        for a, b in zip(order, order[1:]):
            d = diff(a, b)
            steps.append({"from": a, "to": b, "entities_added": len(ent[b] - ent[a]), "entities_removed": len(ent[a] - ent[b]),
                          "relabelled": len(d["relabelled"]), "relations_added": len(rel[b] - rel[a]),
                          "relations_removed": len(rel[a] - rel[b]), "restyled": len(d["restyled"]),
                          "entity_jaccard": jaccard(ent[a], ent[b])})
        seqs[short(s)] = {"basis": short(g.value(s, URIRef(DINO + "basis"))),
                                                          "proposed_by": str(g.value(s, URIRef("http://purl.org/dc/terms/creator"))),
                                                          "order": order, "steps": steps}
    (OUT / "sequences.json").write_text(json.dumps(seqs, indent=1, ensure_ascii=False))

    # ---- report -------------------------------------------------------------
    md = ["# Chart comparison", "", "Generated from `out/barr-charts.trig`. Order-free unless a sequence is named. "
          + ("All charts." if include_all else "Core set only (run with --all to include secondary charts)."), "",
          "## Charts", "", "Influence arrows are split by each chart's ink key (internal / external) and by line (dotted = secondary).", "",
          "| chart | entities | movements | persons | places | external entities | influence | internal | external | secondary | place association | member | acyclic |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['title']} | {r['entities']} | {r['n_Movement']} | {r['n_Person']} | {r['n_Place']} | {r['n_external']} | "
                  f"{r['r_influenced']} | {r['infl_internal']} | {r['infl_external']} | {r['infl_secondary']} | {r['r_associatedWithPlace']} | {r['r_memberOf']} | {'yes' if r['influence_acyclic'] else 'NO'} |")
    md += ["", "## Entity overlap (Jaccard)", "", "| | " + " | ".join(T(c) for c in charts) + " |", "|---" * (len(charts) + 1) + "|"]
    J = {(p["a"], p["b"]): p["entity_jaccard"] for p in pairs}
    for a in charts:
        md.append(f"| **{T(a)}** | " + " | ".join("1" if a == b else str(J.get((a, b), J.get((b, a)))) for b in charts) + " |")
    md += ["", "## Edit grammar, all pairs", "", "| pair | shared | only A | only B | relabelled | rel. only A | rel. only B | restyled | rewired |",
           "|---|---|---|---|---|---|---|---|---|"]
    for p in pairs:
        md.append(f"| {T(p['a'])} – {T(p['b'])} | {p['shared_entities']} | {p['entities_only_a']} | {p['entities_only_b']} | {p['relabelled']} | "
                  f"{p['relations_only_a']} | {p['relations_only_b']} | {p['restyled']} | {p['rewired']} |")
    md += ["", "## Consensus", "", f"Entities by number of charts they appear on: {h_ent}",
           "", f"Relations by number of charts they appear on: {h_rel}", ""]
    # wording variants: entities treated as one referent but written differently across charts.
    # The merge into one entity is conceptual; the formal difference stays visible here.
    variants = []
    for e in sorted({e for c in charts for e in ent[c]}):
        written = {c: label[c].get(e, "") for c in charts if e in ent[c]}
        if len(written) > 1 and len(set(written.values())) > 1:
            variants.append((e, written))
    shared = sum(1 for e in {e for c in charts for e in ent[c]} if sum(e in ent[c] for c in charts) > 1)
    with open(OUT / "wording_variants.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["entity"] + [T(c) for c in charts])
        for e, written in variants:
            w.writerow([e] + [written.get(c, "") for c in charts])
    md += ["## Wording variants", "",
           f"{len(variants)} of the {shared} entities that appear on more than one chart are written differently on different charts.", "",
           "| entity | " + " | ".join(T(c) for c in charts) + " |", "|---" * (len(charts) + 1) + "|"]
    md += [f"| {e} | " + " | ".join(written.get(c, "").replace("|", "/") for c in charts) + " |" for e, written in variants]
    md.append("")
    tags = list(run("tags_per_chart.rq"))
    if tags:
        md += ["## Legend tags", "", "| chart | code | meaning | entities |", "|---|---|---|---|"]
        md += [f"| {T(short(r.chart))} | {r.code} | {r.meaning} | {r.entities} |" for r in tags]
        md.append("")
    for k, s in seqs.items():
        md += [f"## Sequence `{k}` ({s['basis']}; {s['proposed_by']})", "", " → ".join(T(c) for c in s["order"]), "",
               "| step | +entities | −entities | relabelled | +relations | −relations | restyled | Jaccard |", "|---|---|---|---|---|---|---|---|"]
        for st in s["steps"]:
            md.append(f"| {T(st['from'])} → {T(st['to'])} | {st['entities_added']} | {st['entities_removed']} | {st['relabelled']} | "
                      f"{st['relations_added']} | {st['relations_removed']} | {st['restyled']} | {st['entity_jaccard']} |")
        md.append("")
    (OUT / "report.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main(include_all="--all" in sys.argv)
