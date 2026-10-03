# ragbench — benchmark runner pour pipelines RAG (V1 : retrieval + QA)

Un runner **indépendant** : il envoie les questions d'un dataset à une pipeline existante (HTTP), récupère
`answer` + `retrieved_chunks`, calcule les métriques, et garde une **trace complète par question**.
Il ne contient aucune pipeline RAG. Question centrale de la V1 :

> Quand la réponse est mauvaise, l'information n'a-t-elle **pas été trouvée** (retrieval) ou **pas été utilisée** (génération) ?

```
datasets/*.jsonl ─► Runner ──HTTP──► Pipeline RAG (n'importe laquelle)
                      │                  │
                      │      {answer, retrieved_chunks[]}
                      ▼                  ▼
              evaluation/retrieval   evaluation/qa (+ judge LLM optionnel)
                      └────────┬─────────┘
                               ▼
                    diagnostic (retrieval / génération / grounding)
                               ▼
               results/<run_id>/{summary.json, traces.jsonl}
```

## Installation et essai en 2 minutes

```bash
pip install -r requirements.txt pytest          # + `pip install anthropic` pour le judge Anthropic
python examples/mock_pipeline.py --port 8000 &  # pipeline factice (BM25 + réponse extractive)

python benchmark.py run --dataset datasets/sample.jsonl --config configs/pipeline.yaml --run-id demo
python benchmark.py report  --run demo
python benchmark.py analyze --run demo --metric token_f1 --worst 5
python -m pytest
```

Sortie (extrait, 10 questions d'exemple) :

```
RETRIEVAL                          WHY DO ANSWERS FAIL?
Recall@1        0.77                                 answer correct  answer wrong
Recall@5        1.00               evidence retrieved             7             3
MRR             0.95               evidence missing               0             0
QA                                 Accuracy when evidence retrieved : 70%
Exact Match     0.00               Wrong answers (3): 0% retrieval failure, 100% generation failure
Token F1        0.59
```

Avec `--top-k 2` sur la pipeline factice, les mêmes questions donnent 2 `RETRIEVAL_FAILURE` et 1 `GENERATION_FAILURE`.

## Commandes

| Commande | Rôle |
|---|---|
| `run --dataset D --config C [--run-id ID] [--limit N] [--no-judge]` | exécute le benchmark, écrit `results/<run_id>/` |
| `report --run ID` | affiche le rapport (retrieval, QA, judge, latence, diagnostic) |
| `analyze --run ID [--metric M] [--worst N] [--failure-type T]` | pires traces selon `recall_at_5`, `mrr`, `token_f1`, `correctness`, `groundedness`… |
| `compare A B` | tableau de différences entre deux runs (avertit si les datasets diffèrent) |

`run_id` par défaut : `<date>_<pipeline>_<version>` (suffixe `_2`, `_3` en cas de collision ; un `--run-id` explicite n'écrase jamais).
Option globale : `--results-dir` (défaut `results`).

## Contrat avec la pipeline testée

`POST <endpoint>` avec `{"question": "..."}` → `200` avec :

```json
{"answer": "Le contrat est conclu pour cinq ans.",
 "retrieved_chunks": [{"chunk_id": "contract_12_chunk_084", "text": "…", "score": 12.3}, "contract_12_chunk_021"]}
```

Un chunk est un id (`str`) ou un objet (`chunk_id`|`id`, `text`|`content`, `score`). L'ordre = classement du retriever.
**Fournir `text`** est nécessaire pour que le judge évalue la groundedness. Les noms des champs sont configurables
(`request_field`, `answer_field`, `chunks_field`). Pour une pipeline non HTTP : sous-classer `PipelineAdapter.query()`.

Gestion d'erreurs : timeout, retries limités avec backoff (réseau, 408/425/429/5xx ; **pas** de retry sur 4xx),
payload invalide → l'erreur est isolée **à la question** (`PIPELINE_ERROR`, métriques à 0) et le run continue.

## Dataset

JSONL, une question par ligne (validé par Pydantic, ids uniques, erreurs avec numéro de ligne) :

```json
{"id": "q_001", "question": "…", "reference_answer": "…", "document_id": "alpha_2025",
 "relevant_chunks": ["alpha_2025_chunk_001"], "metadata": {"category": "factual", "difficulty": "easy"}}
```

`relevant_chunks` (≥ 1) doit contenir les ids **que la pipeline expose**. Chaque run enregistre le SHA-256 du
dataset : deux runs sont comparables ssi les hash sont égaux. `datasets/sample.jsonl` : 10 questions financières
fictives (factuel, numérique, multi-hop) ; `sample_corpus.jsonl` ne sert qu'à la pipeline factice.

## Métriques

- **Retrieval** (`evaluation/retrieval.py`) : Recall@K, MRR ; Precision@K et nDCG@K disponibles (`benchmark.retrieval_metrics`).
  Les doublons de chunks ne comptent qu'une fois. Ajouter une métrique = une fonction + une ligne dans `K_METRICS`/`RANK_METRICS`
  (ex. MAP).
- **QA déterministe** (`evaluation/qa.py`) : Exact Match, Token F1 après normalisation (minuscules, accents, ponctuation, articles).
- **LLM judge** (`evaluation/judge.py`) : `correctness`, `completeness`, `groundedness` ∈ [0,1] + `reason`, JSON validé par Pydantic
  (un seul réessai si invalide ; sinon `judge_error` dans la trace et repli sur Token F1). Le provider est dans la config
  (`anthropic` ou `openai_compatible`) ; le benchmark ne dépend que de l'interface `AnswerJudge`. La réponse évaluée est
  traitée comme une donnée (balises + consigne), pas comme des instructions. Plusieurs judges : écrire un `AnswerJudge` composite.

## Diagnostic (point central)

Chaque trace contient `analysis` = {`retrieval_ok`, `answer_correct`, `grounded`} et un `diagnosis` qui en dérive :

| `retrieval_ok` | réponse | `diagnosis` |
|---|---|---|
| non | fausse | `RETRIEVAL_FAILURE` — les preuves manquent dans le top-K max |
| oui | fausse | `GENERATION_FAILURE` — les preuves étaient là, mal exploitées |
| — | juste mais `groundedness` < seuil | `GROUNDING_FAILURE` (nécessite le judge) |
| — | juste | `SUCCESS` |
| — | erreur HTTP / timeout | `PIPELINE_ERROR` |

- `retrieval_ok` = **toutes** les preuves annotées sont dans le top-K max (`max(top_k)`) : strict pour le multi-hop.
- « réponse juste » = `correctness` du judge ≥ 0,5 s'il est activé, sinon Token F1 ≥ 0,5 (seuils dans `benchmark`).
  Sans judge, le F1 est un proxy grossier : l'EM vaut ~0 dès que la formulation diffère.
- Le rapport donne la table 2×2 (preuves × réponse) et la part des mauvaises réponses due au retrieval vs à la génération.

## Configuration (`configs/pipeline.yaml`)

YAML validé (clés inconnues refusées). `${VAR}` est résolu depuis l'environnement (URL, tokens) ; les valeurs des
headers sont masquées dans `summary.json`. Judge Anthropic : `ANTHROPIC_API_KEY` ou `ant auth login` ; `temperature`
n'est pas envoyée (refusée par certains modèles récents).

## Sorties d'un run

- `traces.jsonl` : une ligne par question (écrite au fil de l'eau) — entrée, vérité terrain, sortie pipeline complète,
  métriques, judge, analyse, diagnostic, latence, erreur.
- `summary.json` : `run` (run_id, timestamp, pipeline + version, dataset + version + sha256, configuration), agrégats,
  latence (mean/p50/p95), compteurs de diagnostic, analyse des échecs.
- Les erreurs pipeline sont comptées à 0 dans les moyennes (et signalées), les latences ne portent que sur les succès.

## Structure

```
benchmark.py            point d'entrée CLI (→ ragbench/cli.py)
ragbench/
  models.py             structures Pydantic (Sample, PipelineResult, Trace, Summary…)
  config.py  dataset.py chargement/validation YAML et JSONL
  runner.py             boucle dataset → pipeline → métriques → traces
  storage.py            results/<run_id>/ (écriture incrémentale, relecture)
  pipelines/            base.py (PipelineAdapter), http.py (HTTPPipelineAdapter)
  evaluation/           retrieval.py, qa.py, judge.py, diagnosis.py
  reporting/            aggregator.py, report.py, analyze.py
examples/mock_pipeline.py   pipeline factice (n'importe pas ragbench)
```

## Limites connues de la V1

Exécution séquentielle (pas de parallélisme ni de reprise après interruption — les traces déjà écrites sont conservées) ;
le judge Anthropic/OpenAI-compatible n'est testé qu'avec un faux client dans les tests ; pas de comparaison statistique
(intervalles de confiance) entre runs ; sur de petits datasets, les écarts entre runs ne sont pas significatifs.
