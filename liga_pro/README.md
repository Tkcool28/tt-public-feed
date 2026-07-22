# Liga Pro Official Archive

Schema version: `1.0.0`

This directory contains cleaned official Liga Pro schedules and results collected from `api.league-pro.com`. GitHub is the permanent clean-data store; the VPS is a transient collector and publisher.

## Canonical history

`history/YYYY/MM/YYYY-MM-DD.csv` is canonical. Each UTF-8 CSV contains one row per official `match_id`, partitioned by the UTC date of `scheduled_start_utc`, and sorted by `scheduled_start_utc`, `tournament_id`, then `match_id`.

The official API orientation is preserved: `player_1` is `side_one` and `player_2` is `side_two`. Scores are never reversed to put the winner first. The upstream API currently supplies aggregate sets won, not point-by-point set scores; therefore `set_scores` contains the official aggregate orientation such as `3-1`, not fabricated individual games.

## Status mapping

| Official value | Normalized value |
|---|---|
| `1` | `SCHEDULED` |
| `2` | `LIVE` |
| `3` | `COMPLETED` |
| Unrecognized | `UNKNOWN` |

`POSTPONED`, `CANCELLED`, and `ABANDONED` remain reserved normalized values. No undocumented API value is guessed into those categories.

## Updates and corrections

Rows are upserted globally by `match_id`. `first_seen_at_utc` is immutable. A changed schedule, status, player, or result updates the existing row; `last_seen_at_utc` and `source_snapshot_id` identify the latest changed observation. Disappearance from the rolling API window never deletes history. A UTC-date reschedule removes the row from its former partition and inserts it into the new partition, with the relocation recorded in the run manifest.

`content_hash` is deterministic over canonical fields excluding `last_seen_at_utc`, `source_snapshot_id`, and `content_hash` itself.

## Other files

- `current_slate.json`, `recent_results.json`, and `player_metrics.json`: current convenience outputs, not canonical history.
- `health.json`: collection health.
- `history_index.json`: partition navigation, counts, and hashes.
- `dimensions/players.csv`: official player-ID dimension. Similar names are never merged.
- `dimensions/tournaments.csv`: official tournament-ID dimension.
- `manifests/YYYY/MM/YYYY-MM-DD.jsonl`: append-only import audit.
- `manifests/latest.json`: latest successful import object.
- `schema.json`: machine-readable field definitions.

No credentials, private recommendations, wager history, bankroll, or staking information belongs here.
