# Ontology audit: what to reuse, what to mint

Status: draft for review. Nothing in the pipeline changes until the open decisions at the end are settled.

## Principle

The model has three layers, and keeps them apart:

1. **Mark** — what is on the sheet: an arrow, a label, a box, a semicircle, an underline, a position against the year scale, each with graphical properties (ink, line, shape). No meaning attached.
2. **Convention** — a rule, specific to one chart, that gives a graphical value a meaning: on 458 graphite signifies external influence; on 457 graphite signifies nothing. A convention is either stated on the sheet (the Insert's legend) or inferred by the analyst (every ink key).
3. **Proposition** — what the chart asserts once its conventions are applied: "Cubism influenced Futurism, internally, as a primary influence". Derived by a query from marks and conventions, never entered by hand.

Entities (artists, movements, places) are not modelled here: they come from existing vocabularies.

Reuse comes first. A term is minted only where no established vocabulary has it, or where the established term would assert something the charts do not.

## Vocabularies considered

| prefix | vocabulary | use here |
|---|---|---|
| `skos:` | SKOS (W3C) | each chart as a concept scheme; mappings between charts and to external vocabularies |
| `skosxl:` | SKOS-XL (W3C) | wording as written, as label resources that can belong to one chart and carry certainty |
| `crm:` | CIDOC CRM | the sheet as a physical object, the diagram as a visual item it shows |
| `dcterms:` | Dublin Core terms | identifiers, dates, creators, audience, medium |
| `foaf:` | FOAF | facsimile images |
| Getty AAT, ULAN, TGN; Wikidata | external authorities | targets of `skos:exactMatch` / `skos:closeMatch` for movements, persons, places |
| VISO (`http://purl.org/viso/`) | Visualization Ontology (Polowinski & Voigt) | related work only. Its GRAPHIC module models graphic attributes (colour, shape, texture) and graphic relations (linking, containment) for producing visualizations; its companion RVL maps data to graphics. Our conventions run the other way, from graphics to meaning. Version 0.6, maintenance uncertain: aligned with, not depended on. |
| DOLCE+DnS (Gangemi) | Descriptions and Situations pattern | related work for the later formalization: a convention behaves like a Description that a chart's marks satisfy. Not imported. |

## 1. The chart as a record

| need | current term | reuse | note |
|---|---|---|---|
| the physical sheet | `bc:Chart` | `crm:E22_Human-Made_Object` | the archival object |
| the diagram drawn on it | (none) | `crm:E36_Visual_Item`, linked by `crm:P65_shows_visual_item` | P65 makes no claim about what the visual item represents, which is the point: meaning comes from conventions |
| the knowledge system the diagram expresses | (named graph) | `skos:ConceptScheme` | one per chart; link from diagram to scheme is minted (see gaps) |
| archival reference | `bc:archivalReference` | `dcterms:identifier` | |
| date | (CSV only) | `dcterms:created` | with the basis in a note |
| facsimile | (CSV only) | `foaf:depiction` | |
| core / secondary set | `bc:set` | `dcterms:type` with two project concepts | an analytical grouping, not a property of the sheet |

## 2. Concepts and wording

| need | current term | reuse | note |
|---|---|---|---|
| a concept as it appears on one chart | `bc:Concept` + one id shared by all charts | `skos:Concept` with its own IRI per chart, `skos:inScheme` the chart's scheme | the Cover's "(Abstract) Dadaism" and 458's "Dadaism (Abstract)" become two concepts |
| wording as written | `bc:labelAsWritten` | `skosxl:Label` with `skosxl:literalForm`, attached by `skosxl:prefLabel` | a label resource can carry certainty and belong to one chart |
| illegible word | label "[?]" | `skosxl:Label` with literal form "[?]" and uncertain certainty | kept distinct per position, as now |
| identity across charts (a merge) | shared id; note in concepts.csv | `skos:exactMatch` from each chart concept to a reconciled concept | stated by the analyst, in the interpretation graph (below) |
| analogue but not identical (biomorphic ~ non-geometric) | (nothing) | `skos:closeMatch` | makes "kept distinct" an explicit judgment |
| the reconciled index | `skos:prefLabel` in the catalogue | a separate `skos:ConceptScheme` authored by the analyst | the index used to join charts, not a correction of them |
| link to authorities | (none) | `skos:exactMatch` / `skos:closeMatch` to AAT, ULAN, TGN, Wikidata | from the reconciled concepts |
| kind: person, place | `bc:Person`, `bc:Place` | `crm:E21_Person`, `crm:E53_Place` on reconciled concepts' referents | |
| kind: movement | `bc:Movement` | **open decision** | CIDOC CRM has no class for an art movement; candidates are `crm:E55_Type` (style), `crm:E4_Period`, or AAT style terms. Each asserts something different. |

## 3. Propositions

| need | current term | reuse | note |
|---|---|---|---|
| influence | `bc:influenced` | **mint** | `crm:P15_was_influenced_by` has an activity as its domain; Wikidata P737 "influenced by" applies to persons and ideas. Both noted as alignments, neither adopted. |
| place written with a movement | `bc:sitedIn` | **mint** | `crm:P7_took_place_at` is for events; `dcterms:spatial` is about a resource's coverage |
| person listed with a movement | `bc:memberOf` | **mint**, rename open | "member of" claims membership; the chart only lists a name under a current. See decisions. |
| unassignable connection | `bc:relatedTo` | `skos:related` | between concepts of the same scheme |
| internal / external, primary / secondary | `bc:scope`, `bc:weight` (strings) | **mint** as concepts in a small scheme of notational meanings | so that "external" is one resource on every chart |

## 4. Marks and conventions (the gap)

| need | current term | reuse | note |
|---|---|---|---|
| a mark | `bc:Mark` | **mint** `Mark`, `rdfs:subClassOf crm:E36_Visual_Item` | not `crm:E37_Mark`, which covers signatures and similar identifying marks |
| kinds of mark: arrow, label, enclosure, underline | `bc:form` (strings) | **mint** as SKOS concepts | aligned to VISO GRAPHIC where a counterpart exists |
| graphic values: inks, line styles, shapes | `bc:ink`, line, `bc:form` (strings) | **mint** as SKOS concepts | as above |
| position on the chart's year scale | `bc:yearOnScale` | **mint** | a reading of position, governed by the chart's scale convention |
| what a mark notates | (implicit) | **mint** `notates` | `crm:P138_represents` is for depiction; a label does not depict Cubism |
| convention | `bc:inkMeaning "graphite=external"` (string) | **mint** `Convention` with `onChart`, `graphicValue`, `appliesTo` (kind of mark), `signifies`, `basis` | the core contribution |
| basis of a convention | (none) | **mint** values `StatedOnSheet`, `InferredByAnalyst` | the Insert's legend is stated; every ink key is inferred |
| legend codes on the Insert | `bc:Tag`, `bc:code` | the same `Convention` class, with `basis StatedOnSheet` | unifies legend and ink key |
| derivation of propositions | Python lookup | SPARQL `CONSTRUCT` | no OWL reasoning |
| anchoring a mark to a region of the facsimile | (none) | Web Annotation with IIIF image selectors | later: needs coordinates not yet recorded |

## 5. Readings and transcription quality

| need | current term | reuse | note |
|---|---|---|---|
| an ordering proposed by a reading | `bc:Sequence`, `bc:charts` | **mint** `Reading`, with an `rdf:List` of charts | order is a reading, not a property of the charts |
| who proposed it | `bc:proposedBy` (string) | `dcterms:creator` | |
| its basis | `bc:basis` | **mint** values `Documented`, `Analytical` | |
| certainty of a reading of a mark | `bc:certainty` | **mint** | the CRM route (attribute assignments) is far heavier than needed |
| date checked against the facsimile | `bc:verified` | **mint** `checkedOn` | no Dublin Core term means this |

## Graph layout

- **One graph per chart**: the sheet, its diagram, its marks, its concept scheme, its wording, and the conventions stated on the sheet. What the chart itself shows.
- **One interpretation graph**, with `dcterms:creator` the analyst: inferred conventions, the reconciled index, all `exactMatch` / `closeMatch` mappings, links to authorities.
- **One readings graph**: sequences and their bases.

Attribution is carried by the graph, so no provenance vocabulary is needed. The boundary between what the charts say and what the analyst says is visible in the data's structure.

## What gets minted

- **Classes (4):** Mark, Convention, Reading, NotationalMeaning.
- **Properties (about 12):** notates, onChart, graphicValue, appliesTo, signifies, basis, positionOnScale, certainty, checkedOn, influenced, sitedIn, listedUnder.
- **Controlled values, as SKOS concepts:**
  - mark kinds;
  - graphic values;
  - notational meanings (internal, external, primary, secondary, membership, no meaning);
  - bases (stated on sheet, inferred by analyst; documented, analytical).

Everything else is reused.

## Decisions

Settled (2026-10-18):

- **Movements** are typed `crm:E55_Type`.
- **Box** signifies a source outside modern art (convention, inferred by the analyst).
- **Semicircle** signifies membership: the names inside it are members of the current. So the proposition keeps the name "member of" (minted: CIDOC CRM's group membership property takes a group, not a type, as its subject).
- **Underline** signifies a title: the label is the conceptual anchor of what is written with it.
- **Per-chart concept identifiers**: yes, with identity across charts as `skos:exactMatch` / `skos:closeMatch` in the interpretation graph.
- **Facsimile anchoring**: later.

- **Name**: DINO, the Diagram Notation Ontology, prefix `dino:`, namespace `https://psantachiara.github.io/dino/ns#`. Terms specific to the Barr charts (their relations, the meanings of their conventions) are in a separate project vocabulary, `barr:`, so DINO stays reusable for other diagrams.
- **Influence** is minted (`barr:influenced`), not `crm:P15i_influenced`. P15i has `crm:E7_Activity` as its range; asserting that one movement influenced another would make the second an activity, and in CIDOC CRM an activity (a temporal entity) cannot also be a type (a conceptual object). The clash is documented on the property.
- **No per-sheet dossier.** The Pragmatic plane was dropped (2026-10-19), and with it the dossier fields (support, audience, permanence, constraint, function) and the three DINO properties minted for them.
- **Not open data.** The linked data reuses open ontologies and points to open vocabularies, but is not published for dereferencing or reuse. No persistent identifiers are minted for now.

Implemented in `vocab/dino.ttl`, `vocab/barr.ttl`, `data/conventions.csv`, `data/alignments.csv` and `scripts/build_rdf.py`. The comparison computed by SPARQL over the new model is identical to the one before it.

To revisit:

- The box convention makes Modern Architecture, boxed on 458 and the Cover, a source outside modern art.
- Backward arrows on the year scale (checked against the facsimiles, 2026-10-19). The Cover's Japanese Prints → Synthetism and Cézanne → Synthetism were transcription errors (Synthetism 1891, Cézanne 1889, Japanese Prints 1890), now corrected. Eight remain. Seven start from Machine Esthetic, on every chart (456: 2, to Cubism and Brancusi; 457: 2; 458: 2; Cover: 1): Barr places Machine Esthetic later on the scale than what he draws it influencing, confirmed as drawn. The seventh, Negro Sculpture (1905) → Fauvism (1904) on 457, is still to check. On 456 Machine Esthetic is written twice (1910 and 1917). Each occurrence is now its own label mark, and each arrow leaves from the occurrence it is drawn from (`dino:fromMark`): Futurism, Cubism and Constructivism from 1910; Abstract Dadaism, Purism, Brancusi and De Stijl from 1917. Read that way, 456 has a second backward arrow, Machine Esthetic (1917) → Brancusi (1912).
