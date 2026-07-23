#!/usr/bin/env python3
"""Canonical Liga Pro archive v2 contract — single source of truth.

This module is imported by every repository participating in the v2 archive
delivery:

* tt-data-pipeline    — collector, archiver, publisher
* tt-public-feed      — canonical archive repository
* tt-edge-log         — research validator

Each repository's copy of the contract must be byte-identical.  The
self-tests under ``tests/test_canonical_v2_contract.py`` prove this with
the same shared fixture on both sides.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SCHEMA_VERSION = "2.0.0"
SOURCE = "api.league-pro.com"

# Exact, ordered match-row column list.  Order matters: it is the on-disk
# header order, the schema.json declaration, and the order in which the
# content_hash payload is serialized.
MATCH_FIELDS = (
    "match_id",
    "tournament_id",
    "tournament_name",
    "league_band",
    "scheduled_start_utc",
    "scheduled_start_mountain",
    "scheduled_start_prague",
    "official_status",
    "normalized_status",
    "player_1_id",
    "player_1_name",
    "player_2_id",
    "player_2_name",
    "player_1_sets",
    "player_2_sets",
    "winner_player_id",
    "winner_player_name",
    "set_scores",
    "completed_at_utc",
    "calculated_finish_utc",
    "calculated_finish_method",
    "first_seen_at_utc",
    "last_changed_at_utc",
    "source_snapshot_id",
    "source",
    "data_quality",
    "content_hash",
)

# Fields that do NOT participate in the content_hash.  These are either
# derived (content_hash itself), per-cycle pointers (source_snapshot_id),
# or transient observation timestamps (last_changed_at_utc).
HASH_EXCLUDE = frozenset({"last_changed_at_utc", "source_snapshot_id",
                          "content_hash"})

# Player dimension schema.
PLAYER_FIELDS = (
    "player_id",
    "canonical_name",
    "normalized_name",
    "first_seen_at_utc",
    "last_seen_at_utc",
    "first_match_id",
    "latest_match_id",
    "source",
)

# Tournament dimension schema.
TOURNAMENT_FIELDS = (
    "tournament_id",
    "tournament_name",
    "league_band",
    "first_seen_at_utc",
    "last_seen_at_utc",
    "first_scheduled_start_utc",
    "latest_scheduled_start_utc",
    "source",
)

# Top-level convenience file names used by the publisher.
CONVENIENCE_FILES = (
    "health.json",
    "latest.json",
    "recent.json",
)
LIGA_CONVENIENCE_FILES = (
    "liga_pro/health.json",
    "liga_pro/current_slate.json",
    "liga_pro/recent_results.json",
    "liga_pro/player_metrics.json",
)

# Exact, ordered method enum for calculated_finish_method.  Three values:
#   OFFICIAL                          — completed_at_utc is set
#   SCHEDULED_START_PLUS_DURATION     — completed_at_utc blank,
#                                       calculated_finish_utc = scheduled_start_utc + duration
#   UNAVAILABLE                       — both completed_at_utc and calculated_finish_utc blank
METHOD_OFFICIAL = "OFFICIAL"
METHOD_SCHEDULED_PLUS_DURATION = "SCHEDULED_START_PLUS_DURATION"
METHOD_UNAVAILABLE = "UNAVAILABLE"
METHODS = (METHOD_OFFICIAL, METHOD_SCHEDULED_PLUS_DURATION, METHOD_UNAVAILABLE)


# ---------------------------------------------------------------------------
# Canonical content hash
# ---------------------------------------------------------------------------


def content_hash(row):
    """Compute the canonical SHA-256 of one match row.

    Algorithm
    ---------
    1. Build a dict containing every column in ``MATCH_FIELDS`` *except*
       those listed in ``HASH_EXCLUDE``.
    2. ``json.dumps`` with ``sort_keys=True``, ``ensure_ascii=False``,
       and compact ``separators=(",", ":")``.
    3. UTF-8 encode and SHA-256 the bytes.

    The same row (regardless of how it was loaded from CSV) always
    produces the same hash; the inverse is also true — any change in
    the contributing fields produces a different hash.  Completion
    provenance fields (``completed_at_utc``, ``calculated_finish_utc``,
    ``calculated_finish_method``) participate in the hash, so a real
    correction changes the hash while an unchanged re-observation does
    not.
    """
    body = {k: row.get(k, "") for k in MATCH_FIELDS if k not in HASH_EXCLUDE}
    encoded = json.dumps(body, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def canonical_payload_hash(payload):
    """Canonical SHA-256 of a snapshot payload (sorted, compact JSON)."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Shared fixture — proves the three repositories agree on the hash.
# ---------------------------------------------------------------------------


# A single canonical row that all three repositories must hash identically.
# If any repository changes its MATCH_FIELDS or hash algorithm, this hash
# will change and the cross-repository test will fail.
FIXTURE_ROW = {
    "match_id": "fixture-001",
    "tournament_id": "9001",
    "tournament_name": "Tournament A1. League 700-800",
    "league_band": "700-800",
    "scheduled_start_utc": "2026-07-22T12:00:00+00:00",
    "scheduled_start_mountain": "2026-07-22T06:00:00-06:00",
    "scheduled_start_prague": "2026-07-22T14:00:00+02:00",
    "official_status": "3",
    "normalized_status": "COMPLETED",
    "player_1_id": "10",
    "player_1_name": "Alice One",
    "player_2_id": "20",
    "player_2_name": "Bob Two",
    "player_1_sets": "3",
    "player_2_sets": "1",
    "winner_player_id": "10",
    "winner_player_name": "Alice One",
    "set_scores": "11-8;9-11;11-6;11-7",
    "completed_at_utc": "",
    "calculated_finish_utc": "2026-07-22T13:30:00+00:00",
    "calculated_finish_method": "SCHEDULED_START_PLUS_DURATION",
    "first_seen_at_utc": "2026-07-22T05:40:48+00:00",
    "last_changed_at_utc": "2026-07-22T05:40:48+00:00",
    "source_snapshot_id": "snap-fixture-001",
    "source": SOURCE,
    "data_quality": "OK",
    "content_hash": "",
}

# Canonical SHA-256 of FIXTURE_ROW (computed at module load).  Any change
# to MATCH_FIELDS, HASH_EXCLUDE, or the algorithm changes this hash, and
# the cross-repository fixture test fails immediately.
FIXTURE_ROW_SHA256 = content_hash(FIXTURE_ROW)

# A canonical snapshot payload used by tests that need to exercise
# content-addressed snapshot filename = SHA-256(payload bytes).
FIXTURE_SNAPSHOT_PAYLOAD = {
    "schema_version": SCHEMA_VERSION,
    "snapshot_id": "snap-fixture-001",
    "fetched_at_utc": "2026-07-22T05:40:48+00:00",
    "source": SOURCE,
    "raw_match_count": 1,
    "items": [FIXTURE_ROW],
}
FIXTURE_SNAPSHOT_SHA256 = canonical_payload_hash(FIXTURE_SNAPSHOT_PAYLOAD)


# ---------------------------------------------------------------------------
# Convenience file declarations (kept here so all three repos agree)
# ---------------------------------------------------------------------------


def convenience_file_snapshot_id(path):
    """Pull the source snapshot id from a convenience JSON file, if present."""
    if not Path(path).exists():
        return ""
    import json as _json
    with open(path, encoding="utf-8") as handle:
        data = _json.load(handle)
    return str(data.get("snapshot_id") or data.get("source_snapshot_id") or "")
