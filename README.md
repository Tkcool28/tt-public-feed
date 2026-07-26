# TT Public Feed

Public, read-only table-tennis data used by the automated research workflow.

## Bookmaker/reference feed

- `health.json`
- `latest.json`
- `recent.json`

This feed is reference pricing from the available bookmaker source. It is **not consensus market pricing**. Consumers must validate that `health.json` reports a current successful snapshot before using the pricing files.

## Official Liga Pro archive

- `liga_pro/health.json`
- `liga_pro/current_slate.json`
- `liga_pro/recent_results.json`
- `liga_pro/player_metrics.json`
- `liga_pro/h2h_index.json`
- `liga_pro/matchup_metrics.json`
- `liga_pro/history_index.json`
- `liga_pro/history/`
- `liga_pro/dimensions/`
- `liga_pro/manifests/`

The Liga Pro dataset is cleaned official match, schedule, and result history collected from `api.league-pro.com`. Daily UTF-8 CSV files under `liga_pro/history/` are canonical. Current slate, recent results, player metrics, H2H index, and matchup metrics are convenience outputs.

### H2H derived outputs

**liga_pro/h2h_index.json** — per-pair historical head-to-head records. Keys are `low_id:high_id` (sorted numeric player IDs with colon separator). Each pair contains total_matches, win counts, set totals, first/last meeting dates, and a list of individual meetings ordered oldest to newest.

**liga_pro/matchup_metrics.json** — H2H context attached to each current slate matchup. Keys are `low_id:high_id`. Each item contains h2h_available (false when no prior history), all H2H counts zero in that case, recent_h2h limited to 5 most recent meetings newest first, and player orientation aligned to the current slate.

**source_snapshot_id** — sourced from `current_slate.json` top-level `snapshot_id`. The derivation requires this field to be present and non-blank. It does not fall back to `rows[0].source_snapshot_id`. A deterministic `RuntimeError` is raised if `snapshot_id` is missing or blank. Item-level `source_snapshot_id` values must match the top-level `snapshot_id`; conflicting values raise `RuntimeError`.

**generated_at_utc** — sourced from `current_slate.fetched_at_utc`. No wall-clock call is made during derivation; both outputs share the same deterministic timestamp.

**no-H2H behavior** — when a matchup pair has no prior history rows, `h2h_available` is `false`, all H2H numeric fields are zero, and `recent_h2h` is an empty list.

Missing, blank, or conflicting `snapshot_id` values cause derivation failure with a clear deterministic error.
