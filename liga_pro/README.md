# Liga Pro Archive v2

The Liga Pro Archive is the canonical, sanitized public mirror of the
official Liga Pro (`api.league-pro.com`) match data. Every record in this
directory has been cleaned, validated, and deduplicated before
publication. No credentials, tokens, private endpoints, wager history,
recommendations, bankroll information, or staking detail are ever
written here.

## Completion-time semantics

The v2 schema records three distinct states for a finished match. Any
research process that derives workload or rest figures from this
archive **must** apply the matching label.

| Method                       | Meaning |
| ---------------------------- | ------- |
| `OFFICIAL`                   | The Liga Pro API returned an explicit official completion timestamp. `completed_at_utc` is populated and `calculated_finish_utc` equals it. Use this for official figures. |
| `SCHEDULED_START_PLUS_DURATION` | No official completion was observed. The archive derives an **estimated** finish as `scheduled_start_utc + average_set_duration` and stores it in `calculated_finish_utc`. This is **estimated, not official**. Do not present it as an observed completion. |
| `UNAVAILABLE`                | The match is scheduled or live but no estimate exists yet. `calculated_finish_utc` and `completed_at_utc` are both blank. |

`completed_at_utc` is **only** populated when the Liga Pro source
returned an official timestamp; the archive never fabricates one.

`calculated_finish_method` participates in the row content hash so any
change to the official observation is detected by the validator.

## `last_changed_at_utc`

`last_changed_at_utc` is updated whenever the canonical row contents
change (score correction, reschedule, status update). It is nonblank
and parseable for every committed row.

## Layout

```
liga_pro/
├── README.md                          this file
├── schema.json                        machine-readable schema (version 2.0.0)
├── canonical_v2_contract.py           byte-identical copy of the canonical contract
├── health.json                        Liga Pro collector health
├── current_slate.json                 upcoming matches
├── recent_results.json                recently completed matches
├── player_metrics.json                current player aggregates
├── history_index.json                 navigation and totals across all partitions
├── journal.jsonl                      append-only audit log of committed plans
├── dimensions/
│   ├── players.csv                    canonical player dimension
│   └── tournaments.csv                canonical tournament dimension
├── history/
│   └── YYYY/MM/YYYY-MM-DD.csv         daily canonical match partitions
├── manifests/
│   ├── latest.json                    latest committed manifest object
│   └── YYYY/MM/YYYY-MM-DD.jsonl       daily manifest append log
├── snapshots/
│   ├── <sha>.json                     content-addressed snapshot files
│   └── latest                         symlink to the current snapshot
└── migration_proofs/
    └── v2_migration_proof.json        schema v2 regeneration audit
```

## Canonical contract

The canonical contract is the single source of truth for the schema,
method enum, hash algorithm, and exclusion list:

* `MATCH_FIELDS`: 27 columns in exact order
* `METHODS`: `OFFICIAL`, `SCHEDULED_START_PLUS_DURATION`, `UNAVAILABLE`
* `HASH_EXCLUDE`: `content_hash`, `last_changed_at_utc`, `source_snapshot_id`
* Hash: SHA-256 over canonical JSON of all MATCH_FIELDS except HASH_EXCLUDE

The byte-identical copy of the canonical contract is committed at
`liga_pro/canonical_v2_contract.py` for verification by external
processes. The authoritative version lives in `tt-data-pipeline`.

## Content-addressed snapshots

Each snapshot's filename equals the SHA-256 of its exact bytes. The
`latest` symlink points at the current snapshot and is replaced
atomically.

## Daily partitions

`liga_pro/history/YYYY/MM/YYYY-MM-DD.csv` — one canonical CSV per
UTC date, sorted deterministically by `(scheduled_start_utc,
tournament_id, match_id)`. Each row's content hash is deterministic.

## Researcher contract

Any downstream consumer must:

1. Verify `schema.json` schema_version equals `"2.0.0"`.
2. Verify `canonical_v2_contract.py` is byte-identical to the canonical source.
3. Read `history_index.json` to enumerate the partitions.
4. Read `manifests/latest.json` for the latest totals.
5. Read `journal.jsonl` for the audit log.
6. For each row, label `calculated_finish_utc` as `OFFICIAL`,
   `ESTIMATED (SCHEDULED_START_PLUS_DURATION)`, or `UNAVAILABLE`.
