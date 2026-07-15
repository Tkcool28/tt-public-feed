# TT Public Feed

Public, read-only mirror of the sanitized table-tennis odds feed used by the automated TT research brief.

Published files:

- `health.json`
- `latest.json`
- `recent.json`

The VPS feed remains the source of truth. This repository contains no betting log, private wager history, credentials, server configuration, or secret endpoint paths.

Consumers must validate that `health.json` reports a current successful snapshot before using `latest.json` or `recent.json`.
