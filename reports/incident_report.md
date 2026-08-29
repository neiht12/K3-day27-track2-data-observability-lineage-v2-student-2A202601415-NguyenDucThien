# Incident Report — Stale Support Knowledge Base

## Severity

**P2 / High.** Commerce checkout remains available, but the Support Agent can return obsolete refund policy and create direct customer harm.

## Summary

The KB ingestion batch remained structurally valid and the pipeline could report `SUCCESS`, but `published_at` was roughly three hours older than the healthy publication window. The contract freshness rule detected the stale batch and selected `quarantine`, preventing it from replacing the active KB.

## Detection

- Signal: `kb_contract.yaml` freshness check on `published_at` (`max_delay_minutes: 60`).
- First observed: baseline run on 2026-08-29 after the stale KB scenario was introduced.
- Evidence: healthy run produced 0 failed KB checks; incident run produced 1 failed check and action `quarantine`.

## Root Cause

The incoming KB publication timestamps lagged the observation clock by about three additional hours. Content length did not change, so a text-length-only detector remained healthy. This demonstrates why freshness must be an explicit contract SLI rather than inferred from schema or pipeline status.

## Evidence

1. Orders contract: 0 failed checks; row count: 600; row-count anomaly: false. Commerce ingestion was not the initiating failure.
2. KB schema/content-length signals remained valid, while the freshness check alone failed. This isolates the issue to publication recency rather than truncation.
3. Dataset lineage shows the transitive path from the stale source to the user-facing agent.

## Blast Radius

```text
kb_documents
-> kb_active_docs
-> rag_index
-> support_agent
```

Potential impact: obsolete documents can enter retrieval, causing Support Agent answers to cite an old refund policy. The CEO revenue dashboard is outside this lineage branch.

## Mitigation

1. Block promotion of the failed KB batch and copy it to quarantine for investigation.
2. Keep serving the last known-good `kb_active_docs` snapshot.
3. Restore/republish documents with current, authoritative `published_at` values.
4. Rebuild the RAG index only after contract validation passes.

## Recovery

The healthy baseline was restored. A subsequent baseline run returned 0 KB contract failures and action `accept`; orders remained healthy and the Support Agent lineage was rechecked before promotion.

## Verification

- [x] Contract healthy after reset
- [x] dbt build healthy: 20/20 resources passed
- [x] anomaly returned to expected range: row-count anomaly false
- [x] SLO/error-budget behavior covered by tests
- [x] downstream path verified through transitive lineage
- [x] GX checkpoint passed on the restored orders batch

## Prevention / Action Items

| Action | Owner | Deadline | Why |
|---|---|---|---|
| Enforce KB freshness before active snapshot promotion | Support AI | Immediate | Prevent stale policy from entering retrieval |
| Persist freshness SLI and multi-window burn alerts | Reliability | 1 week | Page only on sustained user-impacting burn |
| Alert on embedding-norm and text-length drift | ML Platform | 2 weeks | Cover semantic/index failures beyond freshness |
| Add producer publish-lag telemetry | KB Platform | 2 weeks | Shorten time to root cause |
| Exercise quarantine recovery in game days | Reliability | Monthly | Verify rollback remains operational |
