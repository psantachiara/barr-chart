"""Compute the five planes of comparison on the core charts.

    python3 scripts/build_tool_data.py     # first: tool/barr-charts.json, by SPARQL over the linked data
    python3 scripts/planes.py              # → out/planes/planes.json + out/planes/report.md
    python3 scripts/planes.py --all        # include the secondary set

The algorithms are the same as the ones index.html runs in the browser (PageRank, label
propagation, longest path, edit grammar), so the figures in the report and on the page agree.
Order is never taken from the charts: Planes I-III and V are order-free, and Plane IV reads
each sequence in data/sequences.csv as a separate, labelled reading.
"""
import itertools, json, pathlib, re, sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "out" / "planes"
D = json.loads((ROOT / "tool" / "barr-charts.json").read_text(encoding="utf-8"))
C = D["concepts"]
INCLUDE_ALL = "--all" in sys.argv
V = [v for v in D["versions"] if INCLUDE_ALL or v["set"] == "core"]
N = {v["id"]: v["name"] for v in D["versions"]}
KINDS = ["movement", "person", "place"]
QUALIFIER = re.compile(r"[()\[\]]")          # Barr's own brackets, e.g. "(Abstract) Dadaism"
ILLEGIBLE = "[?]"                               # the transcriber's mark for a word that cannot be read


# ---------------------------------------------------------------- shared definitions
def ents(v): return set(v["nodes"])
def label(v, x): return v["labels"].get(x) or C[x]["l"]
def ekey(e): return f"{e[0]}|{e[2]}|{e[1]}"          # source|relation|target
def rels(v, kind=None): return {ekey(e) for e in v["edges"] if kind is None or e[2] == kind}
def style(v):
    out = {}
    for e in v["edges"]:
        out.setdefault(ekey(e), (e[3], e[5]))          # (line, scope)
    return out


def jaccard(a, b):
    u = len(a | b)
    return round(len(a & b) / u, 3) if u else 0.0


def words(s): return re.findall(r"[^\W_]+", s.lower())


def variant_kind(a, b):
    """case < punctuation < bracketing < word order < wording: the first test that explains the difference."""
    if a.lower() == b.lower():
        return "case"
    if "".join(words(a)) == "".join(words(b)) and bool(QUALIFIER.search(a)) == bool(QUALIFIER.search(b)):
        return "punctuation"
    if words(a) == words(b):
        return "bracketing"
    if sorted(words(a)) == sorted(words(b)):
        return "word order"
    return "wording"


def bracketed(s): return bool(QUALIFIER.search(s.replace(ILLEGIBLE, "")))


# ---------------------------------------------------------------- graph algorithms (mirrors index.html)
def graph(v, mode="influence"):
    es = [(e[0], e[1]) for e in v["edges"] if mode == "all" or e[2] == "influence"]
    es = list(dict.fromkeys(es))
    nodes = [x for x in v["nodes"] if any(x in p for p in es)]
    return nodes, es


def pagerank(nodes, kids, d=0.85, iters=80):
    n = len(nodes)
    if not n:
        return {}
    r = {x: 1 / n for x in nodes}
    for _ in range(iters):
        nx = {x: (1 - d) / n for x in nodes}
        dangling = sum(r[x] for x in nodes if not kids[x])
        for x in nodes:
            if kids[x]:
                share = d * r[x] / len(kids[x])
                for y in kids[x]:
                    nx[y] += share
        spread = d * dangling / n
        r = {x: nx[x] + spread for x in nodes}
    return r


def longest_path(nodes, kids):
    memo = {}
    def go(x, seen=()):
        if x in memo:
            return memo[x]
        if x in seen:
            return 0
        memo[x] = max([1 + go(y, seen + (x,)) for y in kids[x]] or [0])
        return memo[x]
    return max([go(x) for x in nodes] or [0])


def communities(nodes, edges):
    nb = {x: [] for x in nodes}
    for s, t in edges:
        nb[s].append(t); nb[t].append(s)
    lab = {x: i for i, x in enumerate(nodes)}
    order = list(nodes)
    for it in range(24):
        moved = False
        for i in range(len(order) - 1, 0, -1):
            j = (i * 7 + it * 13) % (i + 1)
            order[i], order[j] = order[j], order[i]
        for x in order:
            c = Counter(lab[y] for y in nb[x])
            if not c:
                continue
            best_v = max(c.values())
            best = min(k for k, val in c.items() if val == best_v)
            if best != lab[x]:
                lab[x] = best; moved = True
        if not moved:
            break
    groups = defaultdict(list)
    for x in nodes:
        groups[lab[x]].append(x)
    return sorted((g for g in groups.values() if len(g) > 1), key=lambda g: -len(g))


def cycles_cut(nodes, edges):
    kids = defaultdict(list)
    for s, t in edges:
        kids[s].append(t)
    state, cut = {}, []
    keep = set(edges)
    def visit(x):
        state[x] = 1
        for y in kids[x]:
            if (x, y) not in keep:
                continue
            if state.get(y) == 1:
                keep.discard((x, y)); cut.append((x, y)); continue
            if not state.get(y):
                visit(y)
        state[x] = 2
    for x in list(kids):
        if not state.get(x):
            visit(x)
    return cut


def metrics(v, mode="influence"):
    nodes, es = graph(v, mode)
    kids = {x: [] for x in nodes}; ind = Counter(); outd = Counter()
    for s, t in es:
        kids[s].append(t); ind[t] += 1; outd[s] += 1
    n, m = len(nodes), len(es)
    pr = pagerank(nodes, kids)
    rank = sorted(pr, key=lambda x: (-pr[x], x))
    return {"order": n, "size": m, "isolated": len(v["nodes"]) - n,
            "density": round(m / (n * (n - 1)), 4) if n > 1 else 0,
            "depth": longest_path(nodes, kids),
            "roots": sorted(x for x in nodes if not ind[x]), "sinks": sorted(x for x in nodes if not outd[x]),
            "pagerank": {x: round(pr[x], 4) for x in rank}, "rank": {x: i + 1 for i, x in enumerate(rank)},
            "clusters": communities(nodes, es), "back_edges": cycles_cut(nodes, es)}


def chronology(v):
    """Arrows against the chart's own year scale. Where a concept is written more than once,
    the arrow's own end (the written occurrence it leaves from or reaches) gives the position."""
    y = v["years"]
    ys = lambda e: e[7] if len(e) > 7 and e[7] else y.get(e[0])
    yt = lambda e: e[8] if len(e) > 8 and e[8] else y.get(e[1])
    infl = [e for e in v["edges"] if e[2] == "influence"]
    dated = [e for e in infl if ys(e) and yt(e)]
    return {"influence_arrows": len(infl), "both_ends_on_scale": len(dated),
            "backward": [[e[0], e[1], ys(e), yt(e)] for e in dated if ys(e) > yt(e)],
            "same_year": sum(1 for e in dated if ys(e) == yt(e)),
            "entities_on_scale": len(y), "span": [min(y.values()), max(y.values())] if y else None}


# ---------------------------------------------------------------- pair grammar (order-free) and step grammar (a reading)
def pair(a, b):
    A, B = ents(a), ents(b)
    shared = A & B
    ra, rb = rels(a), rels(b)
    sa, sb = style(a), style(b)
    relab = [{"id": x, "a": label(a, x), "b": label(b, x), "kind": variant_kind(label(a, x), label(b, x))}
             for x in sorted(shared) if label(a, x) != label(b, x)]
    both_ends = lambda k: k.split("|")[0] in shared and k.split("|")[2] in shared
    restyled = [k for k in sorted(ra & rb) if sa[k][0] != sb[k][0] or (sa[k][1] and sb[k][1] and sa[k][1] != sb[k][1])]
    return {"a": a["id"], "b": b["id"], "entity_j": jaccard(A, B), "relation_j": jaccard(ra, rb),
            "influence_j": jaccard(rels(a, "influence"), rels(b, "influence")),
            "shared": len(shared), "only_a": sorted(A - B), "only_b": sorted(B - A),
            "relabelled": relab, "rel_only_a": len(ra - rb), "rel_only_b": len(rb - ra),
            "rewired": sorted(k for k in ra ^ rb if both_ends(k)), "restyled": restyled}


def step(a, b, ma, mb):
    p = pair(a, b)
    A, B = ents(a), ents(b)
    kept = sorted(A & B)
    parent = defaultdict(set)
    for e in a["edges"]:
        if e[2] == "membership":
            parent[e[0]].add(e[1])
    collapsed = [x for x in p["only_a"] if C[x]["t"] == "person" and parent[x] & B]
    ra, rb = ma["rank"], mb["rank"]
    common = [x for x in kept if x in ra and x in rb]
    th = max(4, round(len(common) * 0.12))
    shifts = sorted(({"id": x, "from": ra[x], "to": rb[x], "d": ra[x] - rb[x]} for x in common if abs(ra[x] - rb[x]) >= th),
                    key=lambda s: -abs(s["d"]))
    ka, kb = rels(a), rels(b)
    return {"from": a["id"], "to": b["id"], "inserted": p["only_b"], "deleted": p["only_a"], "relabelled": p["relabelled"],
            "wired": sorted(k for k in kb - ka if k in p["rewired"]), "cut": sorted(k for k in ka - kb if k in p["rewired"]),
            "restyled": p["restyled"], "collapsed": collapsed,
            "restored": [x for x in p["only_b"] if C[x]["t"] == "person"],
            "hedged": [r for r in p["relabelled"] if bracketed(r["b"]) and not bracketed(r["a"])],
            "dehedged": [r for r in p["relabelled"] if bracketed(r["a"]) and not bracketed(r["b"])],
            "promoted": [s for s in shifts if s["d"] > 0], "demoted": [s for s in shifts if s["d"] < 0],
            "entity_j": p["entity_j"]}


# ---------------------------------------------------------------- the five planes
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ids = [v["id"] for v in V]
    byid = {v["id"]: v for v in V}
    M = {v["id"]: metrics(v) for v in V}
    MA = {v["id"]: metrics(v, "all") for v in V}

    # I Terminological
    every = sorted(set().union(*(ents(v) for v in V)), key=lambda x: C[x]["l"])
    variants = []
    for x in every:
        on = [v for v in V if x in ents(v)]
        forms = {v["id"]: label(v, x) for v in on}
        if len(set(forms.values())) > 1:
            kinds = sorted({variant_kind(p, q) for p, q in itertools.combinations(set(forms.values()), 2)})
            variants.append({"id": x, "pref": C[x]["l"], "labels": forms, "kinds": kinds})
    term = {"per_chart": {v["id"]: {"labels": len(v["nodes"]),
                                    "bracketed": sorted(x for x in v["nodes"] if bracketed(label(v, x))),
                                    "illegible": sorted(x for x in v["nodes"] if ILLEGIBLE in label(v, x)),
                                    "uncertain": sorted(x for x in v["nodes"] if v["certainty"].get(x)),
                                    "differs_from_pref": sum(1 for x in v["nodes"] if label(v, x) != C[x]["l"])} for v in V},
            "variants": variants,
            "variant_kinds": dict(Counter(k for r in variants for k in r["kinds"]))}

    # II Conceptual
    where = {x: [v["id"] for v in V if x in ents(v)] for x in every}
    conc = {"per_chart": {v["id"]: {"entities": len(v["nodes"]), **{k: sum(1 for x in v["nodes"] if C[x]["t"] == k) for k in KINDS},
                                    "external": len(v["external"])} for v in V},
            "core": sorted(x for x, w in where.items() if len(w) == len(V)),
            "hapax": {i: sorted(x for x, w in where.items() if w == [i]) for i in ids},
            "by_kind_presence": {k: dict(Counter(len(w) for x, w in where.items() if C[x]["t"] == k)) for k in KINDS},
            "union": len(every)}

    # III Structural
    struct = {}
    for v in V:
        m, ma = M[v["id"]], MA[v["id"]]
        struct[v["id"]] = {"influence": {k: m[k] for k in ("order", "size", "isolated", "density", "depth")} |
                           {"roots": len(m["roots"]), "sinks": len(m["sinks"]), "clusters": [len(g) for g in m["clusters"]],
                            "top_pagerank": list(m["pagerank"].items())[:10], "back_edges": m["back_edges"]},
                           "all_relations": {k: ma[k] for k in ("order", "size", "isolated", "density", "depth")} |
                           {"roots": len(ma["roots"]), "sinks": len(ma["sinks"]), "clusters": [len(g) for g in ma["clusters"]],
                            "top_pagerank": list(ma["pagerank"].items())[:10], "back_edges": ma["back_edges"]},
                           "arcs": dict(Counter(e[2] for e in v["edges"])),
                           "influence_by_scope": dict(Counter(e[5] or "ink carries no meaning" for e in v["edges"] if e[2] == "influence")),
                           "influence_by_line": dict(Counter(e[3] or "unrecorded" for e in v["edges"] if e[2] == "influence")),
                           "chronology": chronology(v),
                           "conventions": {"ink_key": v["inkKey"], "legend": v["legend"], "rules": v["conventions"]}}

    # IV Genetic: every sequence in data/sequences.csv, restricted to the charts in scope
    gen = {}
    for s in D["sequences"]:
        order = [c for c in s["charts"] if c in byid]
        gen[s["id"]] = {"label": s["label"], "basis": s["basis"], "proposed_by": s["proposedBy"], "order": order,
                        "dropped": [c for c in s["charts"] if c not in byid],
                        "steps": [step(byid[a], byid[b], M[a], M[b]) for a, b in zip(order, order[1:])],
                        "to_endpoint": {c: jaccard(ents(byid[c]), ents(byid[order[-1]])) for c in order} if order else {}}

    # V Synchronic: all pairs, consensus, nearest neighbours
    pairs = [pair(a, b) for a, b in itertools.combinations(V, 2)]
    ecount, rcount = Counter(), Counter()
    for v in V:
        ecount.update(ents(v)); rcount.update(rels(v))
    nearest = {}
    for i in ids:
        cands = [(p["entity_j"], p["b"] if p["a"] == i else p["a"]) for p in pairs if i in (p["a"], p["b"])]
        nearest[i] = max(cands)[1] if cands else None
    syn = {"pairs": [{k: (len(v) if isinstance(v, list) else v) for k, v in p.items()} for p in pairs],
           "entity_consensus": dict(sorted(Counter(ecount.values()).items())),
           "relation_consensus": dict(sorted(Counter(rcount.values()).items())),
           "relations_on_all": sorted(k for k, n in rcount.items() if n == len(V)),
           "nearest": nearest, "mutual_nearest": sorted({tuple(sorted((a, b))) for a, b in nearest.items() if b and nearest.get(b) == a})}

    planes = {"scope": "all charts" if INCLUDE_ALL else "core", "charts": ids,
              "terminological": term, "conceptual": conc, "structural": struct, "genetic": gen,
              "synchronic": syn}
    (OUT / "planes.json").write_text(json.dumps(planes, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "report.md").write_text(report(planes), encoding="utf-8")
    print(f"out/planes/: {len(ids)} charts ({', '.join(N[i] for i in ids)}), {len(every)} entities, {len(variants)} wording variants")


# ---------------------------------------------------------------- report
def report(P):
    ids = P["charts"]; T = lambda i: N[i]; L = lambda x: C[x]["l"]
    k = lambda key: f"{L(key.split('|')[0])} —{key.split('|')[1]}→ {L(key.split('|')[2])}"
    row = lambda cells: "| " + " | ".join(str(c) for c in cells) + " |"
    hdr = lambda cols: [row(cols), row(["---"] * len(cols))]
    md = ["# Five planes of comparison", "",
          f"Scope: {P['scope']} set ({', '.join(T(i) for i in ids)}). Generated by `scripts/planes.py` from `tool/barr-charts.json`; "
          "the comparison tool (`index.html`) computes the same figures in the browser.", "",
          "Each chart is treated as a complete ontology in its own right. No plane except IV uses an order, "
          "and Plane IV reports each ordering as a reading with its stated basis.", ""]

    t = P["terminological"]
    md += ["## I · Terminological", "", "Wording as written on each chart, against the reconciled label.", ""]
    md += hdr(["chart", "labels", "Barr's brackets", "illegible ([?])", "uncertain reading", "differs from reconciled label"])
    md += [row([T(i), r["labels"], len(r["bracketed"]), len(r["illegible"]), len(r["uncertain"]), r["differs_from_pref"]])
           for i, r in t["per_chart"].items()]
    md += ["", f"{len(t['variants'])} entities are worded differently on at least two charts. "
           f"Kinds of difference (an entity can show more than one): {t['variant_kinds']}.", ""]
    md += hdr(["entity", *[T(i) for i in ids], "kind"])
    md += [row([r["pref"], *[r["labels"].get(i, "—") for i in ids], ", ".join(r["kinds"])]) for r in t["variants"]]

    c = P["conceptual"]
    md += ["", "## II · Conceptual", ""]
    md += hdr(["chart", "entities", "movements", "persons", "places", "external (by ink key)"])
    md += [row([T(i), r["entities"], r["movement"], r["person"], r["place"], r["external"]]) for i, r in c["per_chart"].items()]
    md += ["", f"Union: {c['union']} entities. On every chart: {len(c['core'])}. "
           + "On one chart only: " + ", ".join(f"{T(i)} {len(x)}" for i, x in c["hapax"].items()) + ".", "",
           "Presence by kind (number of charts → number of entities): "
           + "; ".join(f"{kk}: {dict(sorted(v.items()))}" for kk, v in c["by_kind_presence"].items()) + ".", "",
           "On every chart: " + ", ".join(L(x) for x in c["core"]) + "."]

    s = P["structural"]
    for mode, title in (("influence", "influence arrows only"), ("all_relations", "all relations (influence, siting, membership)")):
        md += ["", f"## III · Structural — {title}", ""]
        md += hdr(["chart", "order", "size", "not in this graph", "density", "depth", "roots", "sinks", "clusters ≥2", "highest PageRank"])
        for i in ids:
            r = s[i][mode]
            md.append(row([T(i), r["order"], r["size"], r["isolated"], r["density"], r["depth"], r["roots"], r["sinks"],
                           len(r["clusters"]), ", ".join(f"{L(x)} {p:.3f}" for x, p in r["top_pagerank"][:3])]))
    md += ["", "Influence arrows by meaning (per chart ink key) and line:", ""]
    md += hdr(["chart", "by meaning (ink key)", "by line", "back-edges (cycles)"])
    md += [row([T(i), s[i]["influence_by_scope"], s[i]["influence_by_line"], len(s[i]["influence"]["back_edges"])]) for i in ids]
    md += ["", "Conventions: how each chart's marks are given meaning. Stated on the sheet (the Insert's legend) or inferred by the analyst.", ""]
    md += hdr(["chart", "ink key", "legend (stated on the sheet)", "other conventions (inferred)"])
    for i in ids:
        cv = s[i]["conventions"]
        rules = [f"{r['value']}={r['meaning']}" for r in cv["rules"] if r["value"] and not r["code"] and r["value"] not in cv["ink_key"]]
        md.append(row([T(i), " ".join(f"{a}={b}" for a, b in cv["ink_key"].items()) or "none",
                       ", ".join(f"{t['code']}={t['meaning']}" for t in cv["legend"]) or "—", ", ".join(rules) or "—"]))
    md += ["", "Chronology against each chart's own year scale. An arrow is *backward* when its tail sits later on the scale than its head.", ""]
    md += hdr(["chart", "entities on scale", "span", "arrows", "both ends on scale", "same year", "backward"])
    for i in ids:
        ch = s[i]["chronology"]
        md.append(row([T(i), ch["entities_on_scale"], "–".join(map(str, ch["span"] or [])), ch["influence_arrows"],
                       ch["both_ends_on_scale"], ch["same_year"], len(ch["backward"])]))
    back = [(i, b) for i in ids for b in s[i]["chronology"]["backward"]]
    if back:
        md += ["", "Backward arrows: " + "; ".join(f"{T(i)}: {L(b[0])} ({b[2]}) → {L(b[1])} ({b[3]})" for i, b in back) + "."]

    md += ["", "## IV · Genetic", "", "Each reading is an ordering with a stated source and basis. Charts outside the scope are dropped from it.", ""]
    for sid, g in P["genetic"].items():
        md += [f"### {g['label']} (`{sid}`)", "", f"Basis: {g['basis']}. Source: {g['proposed_by']}. "
               f"Order in scope: {' → '.join(T(i) for i in g['order'])}"
               + (f" (dropped: {', '.join(T(i) for i in g['dropped'])})" if g["dropped"] else "") + ".", ""]
        md += hdr(["step", "inserted", "deleted", "relabelled", "wired", "cut", "restyled", "persons collapsed", "promoted", "demoted", "brackets gained/lost", "J"])
        md += [row([f"{T(st['from'])} → {T(st['to'])}", len(st["inserted"]), len(st["deleted"]), len(st["relabelled"]), len(st["wired"]),
                    len(st["cut"]), len(st["restyled"]), len(st["collapsed"]), len(st["promoted"]), len(st["demoted"]),
                    len(st["hedged"]) + len(st["dehedged"]), st["entity_j"]]) for st in g["steps"]]
        md += ["", "Similarity to the reading's endpoint: " + ", ".join(f"{T(i)} {j}" for i, j in g["to_endpoint"].items()) + "."]

    y = P["synchronic"]
    md += ["", "## V · Synchronic", "", "All pairs, no order.", ""]
    md += hdr(["pair", "entity J", "relation J", "influence J", "shared", "only A", "only B", "relabelled", "relations only A", "relations only B", "rewired", "restyled"])
    md += [row([f"{T(p['a'])} – {T(p['b'])}", p["entity_j"], p["relation_j"], p["influence_j"], p["shared"], p["only_a"], p["only_b"],
                p["relabelled"], p["rel_only_a"], p["rel_only_b"], p["rewired"], p["restyled"]]) for p in y["pairs"]]
    md += ["", f"Entities by number of charts: {y['entity_consensus']}. Relations by number of charts: {y['relation_consensus']}.", "",
           "Nearest neighbour (entity Jaccard): " + ", ".join(f"{T(a)} → {T(b)}" for a, b in y["nearest"].items()) + ". "
           "Mutual pairs: " + (", ".join(f"{T(a)} – {T(b)}" for a, b in y["mutual_nearest"]) or "none") + ".", "",
           f"Relations on every chart ({len(y['relations_on_all'])}):", ""]
    md += [f"- {k(x)}" for x in y["relations_on_all"]]

    return "\n".join(md) + "\n"


main()
