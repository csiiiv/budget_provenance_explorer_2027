# data_formalization

Formal provenance and line-item tracking layer for the FY2027 Philippine
budget workbenches (DPWH, DA FMR, DOH HFEP, NIA). Design spec:
[docs/DATA_MODEL.md](docs/DATA_MODEL.md) — read §1 (problem) and §5 (two-layer
DAG) first.

## Layout

- `docs/DATA_MODEL.md` — the model: derivation DAG + identity graph + the
  per-line-item append ledger (§6), revision path grammar (§7), connection
  inventory (§14)
- `scripts/` — deterministic, boring tooling:
  - `ledger.py` — append-only JSONL ledger per domain
    (`append` / `fold` / `timeline` / `open-reviews` / `verify`)
  - `lineage.py` — content-addressed node registry
    (`register` / `list` / `verify` / `stale` / `graph`)
  - `backfill_fmr.py`, `backfill_other_domains.py`, `wire_new_sources.py`,
    `transitions_fmr.py`, `extract_nia_recon.py` — one-time backfills/wiring
    (idempotent; guarded against duplicate appends)
  - `replay_fmr.py` — equivalence proof: ledger + snapshots regenerate
    `fmr_workbench.json`'s comparison layer
  - `integrity.py` — cross-ledger validation (monotonic seq, schema,
    dangling edges, duplicates, registered snapshots); appends
    `validation.run` records under subject `integrity/run`
  - `coverage.py` — per-domain connection coverage + bridge probes (§14)
- `data/` — generated, committed:
  - `ledger/{fmr,hfep,nia,dpwh}.jsonl` — the append-only ledgers
  - `nodes/**.manifest.json` + `registry.json` — lineage manifests
  - `transitions/fmr/*.json` — materialized transition/view nodes

## Rules

1. Never edit a ledger line; append only (`ledger.py append` or a backfill
   script). Repairs happen as new records (`defect.repair`), not edits.
2. Register every artifact consumed or produced (`lineage.py register`);
   `lineage.py verify` must stay clean before any commit.
3. Run `integrity.py` after any bulk write; commit only on ALL CLEAN.
4. Rebuild from source PDFs only for new documents or proven defects —
   existing trusted extractions are registered as snapshots (§11).
