# AI Agent Decision Log

The agent implemented proposals only after establishing a baseline and added evidence for each reliability behavior.

## Decision 1 — Contract semantics

- Hypothesis: schema-only checks miss parse failures and stale batches, while every failed check needs an operational disposition.
- Prompt / request to agent: implement logical type validation, freshness, severity and action without changing `student_api.py`.
- Agent proposal: validate serialized logical types, support both `columns` and `fields`, emit `action`, and aggregate the strongest action.
- Evidence/test: malformed integer/number and two-hour stale timestamp tests pass; public healthy fixture remains valid through an event-time freshness reference.
- Accept / reject / revise: **Accept after revision**.
- Why: freshness uses wall-clock UTC by default but permits a declared reference column for deterministic replay fixtures.

## Decision 2 — Robust anomaly and distribution drift

- Hypothesis: mean/std can be widened by outliers and mean-ratio cannot detect equal-mean shape drift.
- Prompt / request to agent: retain z-score, implement robust `auto`, and add a non-mean distribution signal.
- Agent proposal: finite-value filtering, median/MAD with zero-MAD handling, optional same-segment history, and empirical KS plus robust median shift.
- Evidence/test: stable value with a 10x history outlier is healthy; an 80% drop is anomalous; equal-mean shape drift is detected.
- Accept / reject / revise: **Accept**.
- Why: deterministic statistics solve the lab failure modes without model downloads.

## Decision 3 — SCD revenue protection in dbt

- Hypothesis: two active customer rows multiply joined order rows and inflate revenue even when key output columns are non-null.
- Prompt / request to agent: add the smallest native unit test, a business test, and protect the model.
- Agent proposal: unit fixture with one order/two active customer versions, latest-active deduplication, and a singular upstream uniqueness assertion.
- Evidence/test: dbt reports the native unit test passing and all 20 build resources successful.
- Accept / reject / revise: **Accept**.
- Why: the unit test proves transformation behavior; the singular test independently detects upstream SCD corruption.

## Decision 4 — Alert policy and lineage

- Hypothesis: paging on only a short-window spike causes noise, and direct-only column lineage understates impact.
- Prompt / request to agent: implement paired-window burn policy and transitive cycle-safe column traversal.
- Agent proposal: critical page at short/long 14.4/6, warning page at 6/3, and shared BFS traversal for both graph levels.
- Evidence/test: sustained 20/8 burn pages; transient 20/1 does not; a cyclic three-hop column graph terminates with complete output.
- Accept / reject / revise: **Accept**.
- Why: both behaviors are explicit, explainable and covered by tests.

## Decision 5 — GX operational flow and Windows execution

- Hypothesis: isolated expectations do not provide a reusable validation boundary, and executable discovery is unreliable with Windows Store Python.
- Prompt / request to agent: create Suite/ValidationDefinition/Checkpoint/actions and make commands portable.
- Agent proposal: a named ephemeral GX checkpoint, failed-batch block/quarantine action, `python -m pytest`, and a Python dbt entry-point wrapper.
- Evidence/test: GX healthy checkpoint returns `accept`; dbt wrapper completes 20/20 resources on Windows.
- Accept / reject / revise: **Accept**.
- Why: the submission can be reproduced without relying on `dbt.exe`, `pytest.exe`, or `streamlit.exe` being on `PATH`.
