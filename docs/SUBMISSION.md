# Lab 27 Submission Notes

## 1. System understanding

- Critical commerce assets: `orders`, `stg_orders`, `fct_daily_revenue` and the CEO revenue dashboard.
- Critical support assets: `kb_documents`, `kb_active_docs`, `rag_index` and the Support Agent.
- Reliability signals: deterministic contract failures, dbt transformation tests, row-count/distribution anomaly, freshness, RAG drift, lineage blast radius and SLO burn rate.

## 2. Implemented controls

| Layer | Implementation | Failure caught |
|---|---|---|
| Contract | required, null, unique, accepted values, range, logical type, min length and freshness | malformed/type-drifted/stale input |
| Actions | severity-to-action mapping: critical block, warning warn, configurable quarantine | unsafe batches reaching transformations |
| GX | named Suite, ValidationDefinition and Checkpoint; failed batch is blocked and copied to `data/quarantine/` | duplicate keys, nulls, invalid domain/range/type |
| dbt | generic tests, two singular business assertions and a native unit test | bad staging data and SCD join inflation |
| Anomaly | z-score plus robust median/MAD `auto` mode and optional same-segment baseline | volume collapse despite no fixed row-count rule |
| Distribution | empirical two-sample KS plus robust location shift | shape drift even when means are similar |
| Lineage | cycle-safe transitive BFS for dataset and column graphs | complete downstream blast radius |
| SLO | normalized error budget and paired multi-window burn policy | sustained fast burn without paging on a transient spike |
| RAG | text-length and embedding-norm distribution drift | truncated documents and embedding-space change |

## 3. Required explanations

`not_null` and `unique` are data tests: they inspect rows produced by a model. A dbt unit test supplies controlled mock rows to upstream `ref()` inputs and checks the exact transformation output. The unit test in `models/marts/unit_tests.yml` proves that two active SCD records cannot double one order's revenue; the production model independently selects the latest active customer version before joining.

Z-score works for an approximately stationary, light-tailed baseline, but becomes unreliable with outliers, a trend, near-zero variance or weekday/seasonal regimes. `method="auto"` therefore uses an optional same-segment history and median/MAD. A known event can explicitly suppress a non-actionable alert while preserving its score and reason.

For SLO 99.5% with 2 bad checks out of 100: actual bad rate = 2%, allowed bad rate = 0.5%, burn rate = 4, remaining budget = 0%, and the SLO is breached. Multi-window paging requires both the short and long window to cross paired thresholds.

## 4. Evidence

- `python -m pytest tests_public tests_student -q -p no:cacheprovider`: 18 passed.
- Healthy baseline: 600 rows, no contract failure, row-count anomaly false (MAD score about 0.17), KB contract healthy.
- `volume_drop`: 150/600 rows retained; row-count anomaly true (MAD score about 10.29).
- `duplicate_pk`: unique check fails at critical severity; resulting action is `block`.
- `stale_kb`: freshness check fails after a three-hour timestamp delay; resulting action is `quarantine`.
- dbt build: 20/20 resources pass, including 14 data tests and the native SCD unit test.
- GX healthy checkpoint: success with action `accept`; failed checkpoints use `block_and_quarantine`.

## 5. Reproduce on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\reset_lab.py
python scripts\run_baseline.py
python -m pytest tests_public tests_student -q
python scripts\sync_dbt_seeds.py
python scripts\run_dbt.py build --project-dir dbt_project --profiles-dir dbt_project
python gx\validate_orders.py
```

If GNU Make is installed, `make verify` runs the same verification flow.
