# TT Public Feed

Public, read-only table-tennis data produced by the VPS collector and Python v2 publisher and consumed by ChatGPT research.

## Bookmaker/reference feed

- `health.json`
- `latest.json`
- `recent.json`

This feed is reference pricing from the available bookmaker source. It is **not consensus market pricing**. Consumers must validate `health.json` and treat YELLOW coverage as degraded but potentially non-blocking for Liga Pro publication under the publisher contract.

## Official Liga Pro archive

- `liga_pro/health.json`
- `liga_pro/current_slate.json`
- `liga_pro/recent_results.json`
- `liga_pro/player_metrics.json`
- `liga_pro/history_index.json`
- `liga_pro/history/`
- `liga_pro/dimensions/`
- `liga_pro/manifests/`
- `liga_pro/snapshots/`
- `liga_pro/schema.json`

The Liga Pro dataset is cleaned official match, schedule, and result history collected from `api.league-pro.com`. Daily UTF-8 CSV files under `liga_pro/history/` are canonical. Current slate, recent results, and player metrics are convenience outputs.

## Publication ownership

The VPS runs repository-owned systemd collectors and the Python v2 publisher from `Tkcool28/tt-data-pipeline`:

```text
collect raw → normalize → validate → deduplicate → merge archive
→ stage in disposable worktree → commit → push → verify remote SHA
→ promote local archive → bounded raw cleanup
```

GitHub is the permanent clean-data store. Raw source payloads are never published and are retained on the VPS only under the bounded operational policy.

Hermes does not collect, clean, publish, validate, or modify this repository.

## Consumer contract

Consumers must:

1. Resolve and pin one exact `main` commit SHA.
2. Validate the health, manifest, history index, content-addressed snapshots, partition hashes, and relevant convenience files.
3. Confirm the commit belongs to the expected collection cycle rather than assuming that equality with `origin/main` proves freshness.
4. Fail or downgrade honestly when evidence is stale, incomplete, inconsistent, or unavailable.

The bookmaker and official Liga Pro datasets remain separate. Bookmaker pricing is not merged into the canonical Liga Pro history schema.

This repository contains no betting log, private recommendations, wager history, bankroll, staking information, credentials, tokens, raw payloads, or server configuration. See `liga_pro/README.md` and `liga_pro/schema.json` for the archive contract.