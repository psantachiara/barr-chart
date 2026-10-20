# Chart comparison

Generated from `out/barr-charts.trig`. Order-free unless a sequence is named. Core set only (run with --all to include secondary charts).

## Charts

Influence arrows are split by each chart's ink key (internal / external) and by line (dotted = secondary).

| chart | entities | movements | persons | places | external entities | influence | internal | external | secondary | sited | member | acyclic |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 456 | 84 | 20 | 50 | 14 | 0 | 41 | 0 | 0 | 10 | 24 | 52 | yes |
| 457 | 34 | 20 | 3 | 11 | 0 | 43 | 0 | 0 | 4 | 21 | 0 | yes |
| 458 | 94 | 21 | 62 | 11 | 6 | 53 | 34 | 19 | 8 | 19 | 66 | yes |
| Cover | 40 | 21 | 7 | 12 | 4 | 51 | 34 | 17 | 6 | 25 | 2 | yes |

## Entity overlap (Jaccard)

| | 456 | 457 | 458 | Cover |
|---|---|---|---|---|
| **456** | 1 | 0.311 | 0.633 | 0.305 |
| **457** | 0.311 | 1 | 0.333 | 0.762 |
| **458** | 0.633 | 0.333 | 1 | 0.396 |
| **Cover** | 0.305 | 0.762 | 0.396 | 1 |

## Edit grammar, all pairs

| pair | shared | only A | only B | relabelled | rel. only A | rel. only B | restyled | rewired |
|---|---|---|---|---|---|---|---|---|
| 456 – 457 | 28 | 56 | 6 | 6 | 75 | 22 | 6 | 23 |
| 456 – 458 | 69 | 15 | 25 | 6 | 33 | 54 | 9 | 34 |
| 456 – Cover | 29 | 55 | 11 | 8 | 74 | 35 | 6 | 25 |
| 457 – 458 | 32 | 2 | 62 | 8 | 10 | 84 | 5 | 13 |
| 457 – Cover | 32 | 2 | 8 | 7 | 9 | 23 | 1 | 15 |
| 458 – Cover | 38 | 56 | 2 | 6 | 74 | 14 | 4 | 18 |

## Consensus

Entities by number of charts they appear on: {1: 31, 2: 45, 3: 9, 4: 26}

Relations by number of charts they appear on: {1: 74, 2: 51, 3: 27, 4: 35}

## Wording variants

11 of the 80 entities that appear on more than one chart are written differently on different charts.

| entity | 456 | 457 | 458 | Cover |
|---|---|---|---|---|
| abstract_dadaism | Abstract Dadaism | (Abstract) Dadaism | Dadaism (Abstract) | (Abstract) Dadaism |
| abstract_expressionism | Abstract Expressionism | Abstract Expressionism | Abstract Expressionism | (Abstract) Expressionism |
| abstract_surrealism | Abstract Surrealism | (Abstract) Surrealism | Surrealism (Abstract) | (Abstract) Surrealism |
| geometric_abstract_art | Geometric Abstract Art | Contemporary Geometric Abstract Art | Geometric Abstract Art | Geometrical Abstract Art |
| japanese_prints | Japanese prints | Japanese Prints | Japanese Prints | Japanese Prints |
| le_corbusier | Corbusier |  | Le Corbusier |  |
| near_eastern_art | Near Eastern Art | Near Eastern Art | Near-Eastern Art | Near-Eastern Art |
| neoimpressionism | Neoimpressionism | Seurat and Neo-Impressionism | Neoimpressionism | Neo-Impressionism |
| non_geometric_abstract_art |  | Contemporary Non-Geometric Abstract Art | Non-Geometric Abstract Art | Non-Geometrical Abstract Art |
| synthetism | Synthetism | Gauguin and Synthetism | Synthetism | Synthetism |
| van_gogh | van Gogh | van Gogh | Van Gogh | Van Gogh |

## Legend tags

| chart | code | meaning | entities |
|---|---|---|---|
| 456 | a | architect | 6 |
| 456 | c | constructivism [?] | 4 |
| 456 | p | painter | 27 |
| 456 | ph | photographer | 2 |
| 456 | s | sculptor | 8 |
| 456 | t | theatre | 1 |

## Sequence `lowry2012` (published; Lowry (2012))

456 → 457 → 458 → Cover

| step | +entities | −entities | relabelled | +relations | −relations | restyled | Jaccard |
|---|---|---|---|---|---|---|---|
| 456 → 457 | 6 | 56 | 6 | 22 | 75 | 6 | 0.311 |
| 457 → 458 | 62 | 2 | 8 | 84 | 10 | 5 | 0.333 |
| 458 → Cover | 2 | 56 | 6 | 14 | 74 | 4 | 0.396 |
