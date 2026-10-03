# FinanceBench V1 — corpus financier et ground truth annotée

**État : BLOQUÉ à l'étape « téléchargement du corpus ». Aucun PDF, aucune question, aucune annotation n'existe encore.**
Rien n'a été inventé : un benchmark dont la vérité terrain n'a pas été lue dans les documents sources n'a pas de valeur.

| Étape | État |
|---|---|
| Découverte de documents publics (recherche type dork) | fait en partie — `corpus/candidates.json` (16 candidats, **non téléchargés, non vérifiés**) |
| Téléchargement + manifest (provenance, SHA-256, pages) | outil prêt (`tools/fetch_corpus.py`), **bloqué** : la politique réseau de l'environnement refuse les domaines (403 au CONNECT) |
| Gel du corpus | outil prêt (`--freeze`) |
| Analyse, génération de questions, annotation, validation | **non commencé** (dépend des PDF) ; outils de contrôle prêts |

## Pour débloquer

Dans les réglages de l'environnement cloud (menu de l'environnement → Edit → **Network access**), passer en « Custom » et ajouter
sous *Allowed domains* (en gardant la liste des gestionnaires de paquets par défaut) :

```
ecb.europa.eu  belfius.be  asnbank.nl  mandg.com  tcmb.gov.tr  centralbankbahamas.com  lukb.ch
commbank.com.au  investments.metlife.com  guggenheiminvestments.com  report.fresenius.com
reports.emdgroup.com  reporting-hub.group.dhl.com  nbg.gr  fticonsulting.com
sec.gov  amf-france.org  bis.org   (ces trois derniers pour combler les manques ci-dessous)
```

Puis : ouvrir `corpus/candidates.json`, passer `selected: true` sur 10–15 documents (résoudre d'abord les `direct_pdf: false`
vers leur lien PDF), et lancer les commandes de la section « Workflow ».

## Candidats et lacunes

`candidates.json` provient uniquement de résultats de recherche (titres/URL ; les descriptions du moteur sont des résumés non fiables).
Types couverts : banque (Pillar 3 : Belfius, ASN Bank, CBA Europe, LUKB), assureur (SFCR : Belfius Insurance, M&G/Prudential Intl),
banques centrales (BCE, Türkiye, Bahamas), fonds UCITS (MetLife IM, Guggenheim), groupes industriels (Fresenius, Merck KGaA, DHL).
**Lacunes** : prospectus ; rapport d'un régulateur (SEC/AMF/EBA/FCA) ; document d'enregistrement universel français (HSBC Continental
Europe, CIC, CNP n'apparaissent que comme communiqués) ; communiqué de résultats en PDF (définitions d'EBITDA ajusté).
Les nombres de pages sont inconnus jusqu'au téléchargement (seuls Fresenius 440 et Merck 565 sont cités par le moteur, non vérifiés).
Seuls des documents publiés par leurs émetteurs/régulateurs sont retenus ; aucune recherche de contenu privé ou mal publié.

## Passer à ~1 000 questions : ce que ça implique

Le cahier des charges initial visait ~50 questions vérifiées une à une. À 1 000, la lecture manuelle exhaustive n'est plus réaliste.
Plan proposé (à valider) — **deux niveaux étiquetés dans `metadata.tier`**, pour ne jamais présenter des questions auto-validées comme humaines :

- **gold (~100–150)** : rédigées et vérifiées manuellement dans le PDF (`method: manual`) ; toutes les classes difficiles
  (multi-documents, notes de bas de page, pièges d'unités, négatives).
- **silver (~850–900)** : brouillons générés à partir des tables/pages extraites (gabarits + LLM), puis contrôlés automatiquement
  (`validate_dataset.py` : evidence verbatim sur la page, recalcul des opérations, `raw × scale = valeur`) et par une seconde passe
  indépendante ; un échantillon d'au moins 10 % est relu à la main (`method: manual_sample`) et le taux d'erreur est publié.
- Garde-fous : plafond de questions par document, ≤ 30 % de simples lectures de chiffre, part minimale de calculs/multi-evidence/négatives ;
  1 000 questions sur 10–15 PDF donne ~70–100 par document : prévoir plus de documents (20–30) si la diversité prime.
- La vérité terrain ne doit **pas** être produite ni validée avec la RAG cible (règle conservée).

## Workflow (une fois le réseau ouvert)

```bash
python finance_benchmark/tools/fetch_corpus.py              # corpus/documents/fin_doc_NNN.pdf + manifest.json + fetch_report.json
python finance_benchmark/tools/fetch_corpus.py --freeze     # SHA-256 vérifiés, FROZEN.json, fichiers en lecture seule
python finance_benchmark/tools/extract_pages.py --grep "operating income"   # texte par page pour repérer les evidences
# annoter → datasets/finance_benchmark_v1_draft.jsonl ; revue → datasets/finance_benchmark_v1_review.json
python finance_benchmark/tools/validate_dataset.py          # contrôles + distribution
python finance_benchmark/tools/validate_dataset.py --export # finance_benchmark_v1.jsonl = exemples `verified` uniquement
```

## Format d'un exemple (draft)

```json
{"id": "fin_q_001", "question": "…", "reference_answer": "Operating income was €1.284 billion (€1,284 million) in 2025.",
 "evidence": [{"document_id": "fin_doc_001", "page": 87, "text": "Operating income  1,284  1,198   (€ million)"}],
 "metadata": {"type": "table", "difficulty": "medium", "requires_calculation": false, "requires_multiple_documents": false,
              "answerable": true, "tier": "gold", "failure_modes": ["header_dependency", "unit_mismatch"]},
 "calculation": null}
```

- `type` : direct, table, temporal, calculation, multi_evidence, multi_document, definition, risk, negative.
  Cible pour 50 : 10 direct, 10 table, 8 temporal, 7 calculation, 5 multi_evidence, 4 multi_document, 3 definition, 3 negative
  (le rapport de distribution la met à l'échelle) ; `risk` compte en plus.
- `evidence` référence **le document original** (`document_id` + page + citation verbatim, « … » pour sauter du texte), jamais un chunk RAG.
  Une question négative a `evidence: []`, `answerable: false` et une réponse « cannot be established from the available documents ».
- `failure_modes` (optionnel) : same_metric_multiple_years, similar_table_labels, multiple_entities, footnote, terminology_mismatch,
  unit_mismatch, split_across_pages, header_dependency, deep_in_report, multi_evidence_combination.
- **Calculs** : en plus de `inputs`/`operation`/`result` (valeurs en unité de base), chaque entrée a un `input_sources` :
  `{"evidence_index": 0, "raw": "1,284", "unit": "€ million", "scale": 1e6}` — le chiffre tel qu'imprimé, son unité et le multiplicateur.
  Le validateur vérifie que `raw` figure dans l'evidence et que `raw × scale = valeur` : une unité oubliée est une erreur, pas un silence.
  Pourcentages : `scale: 0.01` ; points de base : `0.0001`. Les noms d'entrée peuvent commencer par un chiffre (`2025_revenue`).

## Revue indépendante (`finance_benchmark_v1_review.json`)

```json
{"reviews": {"fin_q_001": {"status": "verified", "method": "manual", "reviewer": "…", "notes": "",
   "checks": {"answer_correctness": true, "numerical_correctness": true, "currency": true, "units": true,
              "reporting_period": true, "entity": true, "evidence_location": true, "calculation": "n/a",
              "ambiguity": true, "completeness": true},
   "independent_recompute": {"result": 0.1673, "matches": true}}}}
```

Chaque question doit avoir ses 10 contrôles ; `verified` exige qu'ils soient tous vrais (ou `n/a`), un recalcul indépendant concordant
pour les calculs, et la revue **manuelle** pour le tier gold. Le doute se signale (`flagged` + `notes`), il ne se devine pas :
les exemples `flagged` restent dans le fichier de revue et sont exclus de `finance_benchmark_v1.jsonl`.
Les contrôles automatiques ne remplacent pas la lecture du document source (ils ne détectent ni un mauvais exercice, ni une mauvaise entité,
ni une ambiguïté).

## Phase suivante (hors périmètre ici)

Ingérer `corpus_v1` dans la RAG, puis convertir `evidence` (document, page, texte) en `relevant_chunks` pour le runner `ragbench`
(correspondance par recouvrement de texte avec les chunks produits). Ne pas lancer le benchmark avant.
