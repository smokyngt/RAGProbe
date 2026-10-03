# rag-bench — benchmark QA + retrieval (V0)

Le benchmark **n'est pas** la pipeline : c'est un runner qui boucle sur un dataset, appelle la pipeline testée,
puis compare chunks récupérés et réponse au ground truth.

```
dataset (question, réponse de réf., chunks pertinents)
   → runner → pipeline (HTTP ou Python) → {answer, retrieved_chunks}
   → retrieval eval (Recall@K, Hit@K, MRR, nDCG@10) + QA eval (EM, F1, LLM judge optionnel)
   → results.json (agrégats + détail par question + diagnostic d'échec)
```

## Utilisation

```bash
python -m rag_bench run                                   # baseline BM25 extractive (sans LLM)
python -m rag_bench run --pipeline http --url http://localhost:8000/ask --out results/prosperify_v1.json
python -m rag_bench run --judge --out results/bm25_judge.json   # pip install anthropic + ANTHROPIC_API_KEY
python -m rag_bench compare results/bm25.json results/prosperify_v1.json
python -m pytest
```

Contrat HTTP : `POST {"question": "..."}` → `{"answer": "...", "retrieved_chunks": ["id1", "id2", ...]}`
(l'ordre des ids = classement du retriever ; les autres clés sont conservées dans `meta`).
Pour une pipeline Python : implémenter `Pipeline.run(question) -> PipelineResult` (`rag_bench/pipelines/base.py`).

## Formats

`data/questions.jsonl` : `{"id","question","reference_answer","relevant_chunks":[chunk_id],"tags":[]}`
`data/corpus.jsonl` : `{"chunk_id","text"}` (utilisé par le judge et la baseline BM25).

Les ids de `relevant_chunks` doivent être ceux que **ta pipeline** expose.
Le jeu fourni (11 questions, 3 contrats fictifs) n'est qu'un exemple : remplace-le par 20–30 questions annotées à la main.

## Diagnostic par question

| `diagnosis`          | Signification                                         | Suspect                      |
|----------------------|-------------------------------------------------------|------------------------------|
| `ok`                 | réponse correcte (F1 ≥ 0.5, ou judge correctness ≥ 0.5) | —                          |
| `retrieval_miss`     | aucun chunk pertinent dans le top-10                  | parsing, chunking, retriever |
| `ranking_or_context` | pertinent présent mais pas en rang 1                  | reranking, contexte          |
| `generation_error`   | pertinent en rang 1 mais réponse fausse               | prompt / LLM                 |
| `pipeline_error`     | exception ou timeout de la pipeline                   | infra                        |

Les paires (traces, diagnostic) de `results.json` pourront servir de données pour l'orchestrateur.

## Roadmap

V1 : 100 questions · V2 : reranking · V3 : multi-hop · V4 : citations / faithfulness · V5 : documents longs + tableaux.
