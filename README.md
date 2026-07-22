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
- `liga_pro/history_index.json`
- `liga_pro/history/`
- `liga_pro/dimensions/`
- `liga_pro/manifests/`

The Liga Pro dataset is cleaned official match, schedule, and result history collected from `api.league-pro.com`. Daily UTF-8 CSV files under `liga_pro/history/` are canonical. Current slate, recent results, and player metrics are convenience outputs.

The VPS performs transient collection, validation, normalization, and publication. GitHub is the permanent clean-data store. Raw source payloads are not published and are retained on the VPS only under the bounded operational policy.

The two datasets remain separate: bookmaker pricing is not merged into the official Liga Pro history schema.

This repository contains no betting log, private recommendations, wager history, bankroll, staking information, credentials, tokens, or server configuration. See `liga_pro/README.md` and `liga_pro/schema.json` for the archive contract.
