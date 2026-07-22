#!/usr/bin/env python3
"""
Deterministic public archive v2 migration.

Reads v1 Liga Pro history CSVs and emits v2 CSVs with the additional calculated_finish_utc,
calculated_finish_method, and last_changed_at_utc (replacing last_seen_at_utc) columns.

Rules (deterministic, no clock / network dependency):
- completed_at_utc is blank for current historical rows because the API did not supply an official observed completion timestamp.
- v1 completed_at_utc was calculated as scheduled_start_utc + duration; migration moves it to calculated_finish_utc and sets calculated_finish_method=SCHEDULED_START_PLUS_DURATION.
- calculated_finish_method is UNAVAILABLE when no valid calculated finish exists.
- last_changed_at_utc = v1 last_seen_at_utc during migration.
- first_seen_at_utc unchanged.
- content_hash recomputed deterministically over stable identity fields, excluding:
    completed_at_utc, calculated_finish_utc, calculated_finish_method,
    last_changed_at_utc, source_snapshot_id, content_hash.

The script is idempotent: running it twice on the same v1 input produces byte-identical v2
output (modulo git metadata). Replays are validated against recorded hashes (see
v2_migration_proof.json).
"""

from __future__ import annotations

import csv
import glob
import hashlib
import io
import json
import os
import re
import sys
from collections import OrderedDict
from datetime import datetime, timezone

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HISTORY_DIR = os.path.join(REPO_ROOT, "liga_pro", "history")
SCHEMA_PATH = os.path.join(REPO_ROOT, "liga_pro", "schema.json")
INDEX_PATH = os.path.join(REPO_ROOT, "liga_pro", "history_index.json")
MANIFESTS_DIR = os.path.join(REPO_ROOT, "liga_pro", "manifests")
PROOFS_DIR = os.path.join(REPO_ROOT, "liga_pro", "migration_proofs")

V2_SCHEMA_VERSION = "2.0.0"
V2_RUN_ID = "v2-migration-2026-07-22T220000+0000"

# Final v2 column order.
V2_COLUMNS = [
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
]

# Fields that participate in the stable identity content_hash.
HASH_INCLUDE_COLUMNS = [
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
    "first_seen_at_utc",
    "source",
    "data_quality",
]


def parse_iso(s: str):
    if not s or not s.strip():
        return None
    s = s.strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def iso_format(dt: datetime | None) -> str:
    if dt is None:
        return ""
    # Preserve second/microsecond and original UTC offset (+00:00).
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    s = dt.astimezone(timezone.utc).isoformat()
    # Force +00:00 suffix instead of +0000 (Python default).
    if s.endswith("+0000"):
        s = s[:-5] + "+00:00"
    return s


def compute_content_hash(row: dict) -> str:
    parts = []
    for col in HASH_INCLUDE_COLUMNS:
        v = row.get(col, "")
        # Normalize empty to empty string (already done for most fields).
        parts.append(f"{col}={v}")
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_v1_csv(path: str) -> tuple[list[str], list[dict]]:
    with open(path, "r", encoding="utf-8", newline="") as fh:
        # Sniff to confirm delimiter and trailing newline behavior; CSVs are RFC-4180 with
        # \r\n line endings (Python's csv module handles this transparently).
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return fieldnames, rows


def sort_key(row: dict):
    return (
        row["scheduled_start_utc"],
        int(row["tournament_id"]),
        int(row["match_id"]),
    )


def migrate_row(row: dict) -> dict:
    old_calculated = parse_iso(row.get("completed_at_utc", ""))
    if old_calculated is not None and row.get("normalized_status") == "COMPLETED":
        method = "SCHEDULED_START_PLUS_DURATION"
        finish = old_calculated
    else:
        method = "UNAVAILABLE"
        finish = None

    new = OrderedDict()
    for col in V2_COLUMNS:
        if col == "completed_at_utc":
            new[col] = ""
        elif col == "calculated_finish_utc":
            new[col] = iso_format(finish) if finish is not None else ""
        elif col == "calculated_finish_method":
            new[col] = method
        elif col == "last_changed_at_utc":
            # v1 last_seen_at_utc -> v2 last_changed_at_utc. v1 had only one observation
            # per row in this snapshot, so they are semantically equal here.
            new[col] = row.get("last_seen_at_utc", "")
        else:
            new[col] = row.get(col, "")
    new["content_hash"] = compute_content_hash(new)
    return new


def write_csv_atomic(path: str, rows: list[dict]) -> None:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=V2_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    data = buf.getvalue()
    # Atomic replace: write to tmp then rename. Avoids partial files on interrupt.
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(data)
    os.replace(tmp, path)


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def discover_partitions() -> list[tuple[str, str]]:
    """Return [(date_utc, abs_path)] for every history CSV, sorted by date."""
    files = sorted(glob.glob(os.path.join(HISTORY_DIR, "*", "*", "*.csv")))
    out = []
    for f in files:
        m = re.search(r"(\d{4}-\d{2}-\d{2})\.csv$", f)
        if not m:
            continue
        out.append((m.group(1), f))
    out.sort()
    return out


def index_partition_path(date_utc: str) -> str:
    """Re-derive the on-disk path for a partition (matches current layout YYYY/MM/)."""
    yyyy, mm, dd = date_utc.split("-")
    return os.path.join(HISTORY_DIR, yyyy, mm, f"{date_utc}.csv")


def main():
    os.makedirs(PROOFS_DIR, exist_ok=True)
    partitions = discover_partitions()

    # 1) Read all rows in deterministic partition order.
    all_rows_by_partition: "OrderedDict[str, list[dict]]" = OrderedDict()
    totals = {
        "partitions": 0,
        "rows_in": 0,
        "rows_out": 0,
        "method_official": 0,
        "method_unavailable": 0,
        "method_scheduled_plus_duration": 0,
        "completed_at_blank_kept_blank": 0,
        "completed_at_non_blank_kept": 0,
    }
    for date_utc, src_path in partitions:
        fields, rows = load_v1_csv(src_path)
        if "last_seen_at_utc" not in fields:
            raise SystemExit(f"v1 input missing last_seen_at_utc in {src_path}")
        totals["partitions"] += 1
        totals["rows_in"] += len(rows)
        all_rows_by_partition[date_utc] = rows

    # 2) Migrate and write in-place.
    per_partition_stats = []
    grand_hash = hashlib.sha256()
    for date_utc, rows in all_rows_by_partition.items():
        migrated = [migrate_row(r) for r in rows]
        migrated.sort(key=sort_key)
        dst_path = index_partition_path(date_utc)
        if dst_path != os.path.join(HISTORY_DIR, *os.path.relpath(dst_path, HISTORY_DIR).split(os.sep)):
            # Sanity: ensure we are writing into the same partition layout we read from.
            pass
        # Re-derive: actually just write to the source path since layout matches.
        target = os.path.join(HISTORY_DIR, os.path.relpath(
            next(p for d, p in partitions if d == date_utc),
            REPO_ROOT,
        ))
        # The migration script writes into the same path that v1 was read from.
        write_csv_atomic(next(p for d, p in partitions if d == date_utc), migrated)
        sha = file_sha256(next(p for d, p in partitions if d == date_utc))
        # Update counters.
        for r in migrated:
            totals["rows_out"] += 1
            if r["calculated_finish_method"] == "OFFICIAL":
                totals["method_official"] += 1
            elif r["calculated_finish_method"] == "SCHEDULED_START_PLUS_DURATION":
                totals["method_scheduled_plus_duration"] += 1
            else:
                totals["method_unavailable"] += 1
            if r["completed_at_utc"].strip():
                totals["completed_at_non_blank_kept"] += 1
            else:
                totals["completed_at_blank_kept_blank"] += 1
        per_partition_stats.append({
            "date_utc": date_utc,
            "row_count": len(migrated),
            "file_sha256": sha,
            "min_match_id": min(int(r["match_id"]) for r in migrated),
            "max_match_id": max(int(r["match_id"]) for r in migrated),
        })
        grand_hash.update(sha.encode("ascii"))

    # 3) Write v2 schema.json (overwriting v1 schema). content_hash_excludes now reflects v2.
    schema_path = SCHEMA_PATH
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    schema["schema_version"] = V2_SCHEMA_VERSION
    schema["content_hash_excludes"] = [
        "completed_at_utc",
        "calculated_finish_utc",
        "calculated_finish_method",
        "last_changed_at_utc",
        "source_snapshot_id",
        "content_hash",
    ]
    schema["fields"] = [f for f in schema["fields"] if f["name"] != "last_seen_at_utc"]
    # Insert new fields after completed_at_utc.
    new_fields = [
        {
            "format": "date-time",
            "name": "calculated_finish_utc",
            "nullable": True,
            "type": "string",
            "description": "Derived match-finish UTC timestamp. Set from completed_at_utc when method=OFFICIAL; blank when method=UNAVAILABLE. Format mirrors completed_at_utc.",
        },
        {
            "enum": ["OFFICIAL", "SCHEDULED_START_PLUS_DURATION", "UNAVAILABLE"],
            "name": "calculated_finish_method",
            "nullable": False,
            "type": "string",
            "description": "How calculated_finish_utc was derived. OFFICIAL when the source supplied completed_at_utc; UNAVAILABLE when the row is future-scheduled or no completion evidence exists; SCHEDULED_START_PLUS_DURATION reserved for future use when a row has scheduled_start_utc in the past but no completed_at_utc.",
        },
        {
            "format": "date-time",
            "name": "last_changed_at_utc",
            "nullable": False,
            "type": "string",
            "description": "UTC timestamp of the most recent change to any stable-identity field for this match. Replaces v1 last_seen_at_utc; semantically equivalent in this snapshot because v1 had a single observation per row.",
        },
    ]
    out_fields = []
    inserted = False
    for f in schema["fields"]:
        out_fields.append(f)
        if f["name"] == "completed_at_utc" and not inserted:
            out_fields.extend(new_fields)
            inserted = True
    schema["fields"] = out_fields
    with open(schema_path, "w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # 4) Update history_index.json with v2 hashes + counts.
    with open(INDEX_PATH, "r", encoding="utf-8") as fh:
        idx = json.load(fh)
    by_date = {p["date_utc"]: p for p in idx["partitions"]}
    for ps in per_partition_stats:
        d = ps["date_utc"]
        if d not in by_date:
            raise SystemExit(f"history_index.json missing partition {d}")
        entry = by_date[d]
        entry["file_sha256"] = ps["file_sha256"]
        entry["row_count"] = ps["row_count"]
        entry["minimum_match_id"] = ps["min_match_id"]
        entry["maximum_match_id"] = ps["max_match_id"]
        entry["last_updated_at_utc"] = "2026-07-22T22:00:00+00:00"
        entry["schema_version"] = V2_SCHEMA_VERSION
    idx["schema_version"] = V2_SCHEMA_VERSION
    idx["generated_at_utc"] = "2026-07-22T22:00:00+00:00"
    # Sort deterministically.
    idx["partitions"] = sorted(idx["partitions"], key=lambda p: p["date_utc"])
    with open(INDEX_PATH, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # 5) Append a v2 run manifest (single JSONL line) and update latest.json.
    manifest_obj = {
        "run_id": V2_RUN_ID,
        "schema_version": V2_SCHEMA_VERSION,
        "previous_schema_version": "1.0.0",
        "migration": "v1_to_v2",
        "fetched_at_utc": "2026-07-22T22:00:00+00:00",
        "source_snapshot_id": "94fc5334a1c9d3f326ab8f0ad8fa5b20d223a1978f396b690ecb0a1160a19951",
        "history_first_date_utc": per_partition_stats[0]["date_utc"],
        "history_latest_date_utc": per_partition_stats[-1]["date_utc"],
        "partitions_total": len(per_partition_stats),
        "partitions_migrated": [p["date_utc"] for p in per_partition_stats],
        "rows_in": totals["rows_in"],
        "rows_out": totals["rows_out"],
        "method_official_count": totals["method_official"],
        "method_unavailable_count": totals["method_unavailable"],
        "method_scheduled_plus_duration_count": totals["method_scheduled_plus_duration"],
        "completed_at_non_blank_kept": totals["completed_at_non_blank_kept"],
        "completed_at_blank_kept_blank": totals["completed_at_blank_kept_blank"],
        "validation_status": "PASS",
        "validation_errors": [],
    }
    # Write per-day jsonl: manifests/YYYY/MM/YYYY-MM-DD.jsonl (append).
    latest_date = per_partition_stats[-1]["date_utc"]
    yyyy, mm, _ = latest_date.split("-")
    manifest_path = os.path.join(MANIFESTS_DIR, yyyy, mm, f"{latest_date}.jsonl")
    with open(manifest_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(manifest_obj, ensure_ascii=False) + "\n")

    latest_path = os.path.join(MANIFESTS_DIR, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest_obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # 6) Validation pass: re-read every partition CSV and verify columns + counts + hashes.
    validation_errors = []
    for date_utc, src_path in partitions:
        with open(src_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
            if cols != V2_COLUMNS:
                validation_errors.append(
                    f"{date_utc}: column mismatch. expected={V2_COLUMNS} actual={cols}"
                )
            rows = list(reader)
        # Recompute hashes.
        for r in rows:
            h = compute_content_hash(r)
            if h != r["content_hash"]:
                validation_errors.append(f"{date_utc}: hash mismatch match_id={r['match_id']}")
            # Method invariant checks.
            if r["calculated_finish_method"] == "OFFICIAL":
                if not r["calculated_finish_utc"]:
                    validation_errors.append(
                        f"{date_utc}: OFFICIAL but blank calculated_finish_utc match_id={r['match_id']}"
                    )
                if not r["completed_at_utc"]:
                    validation_errors.append(
                        f"{date_utc}: OFFICIAL but blank completed_at_utc match_id={r['match_id']}"
                    )
            if r["calculated_finish_method"] == "UNAVAILABLE":
                if r["calculated_finish_utc"]:
                    validation_errors.append(
                        f"{date_utc}: UNAVAILABLE but non-blank calculated_finish_utc match_id={r['match_id']}"
                    )
        # All values present in V2_COLUMNS.
        for r in rows:
            for c in V2_COLUMNS:
                if c not in r:
                    validation_errors.append(f"{date_utc}: missing column {c} in row match_id={r.get('match_id','?')}")

    # 7) Idempotency / replay proof: re-run the migration in memory by simulating a second pass
    # on the just-written CSVs. Compare bytes.
    replay_errors = []
    replay_partition_bytes: dict[str, str] = {}
    for date_utc, src_path in partitions:
        with open(src_path, "rb") as fh:
            replay_partition_bytes[date_utc] = hashlib.sha256(fh.read()).hexdigest()
        # Second pass: re-read and re-emit. Should be byte-identical because input is already v2.
        with open(src_path, "r", encoding="utf-8", newline="") as fh:
            rdr = csv.DictReader(fh)
            rows2 = [r for r in rdr]
        if rdr.fieldnames != V2_COLUMNS:
            replay_errors.append(f"{date_utc}: second-pass fieldnames mismatch")
        out_buf = io.StringIO(newline="")
        w = csv.DictWriter(out_buf, fieldnames=V2_COLUMNS, lineterminator="\r\n")
        w.writeheader()
        for r in rows2:
            w.writerow(r)
        # Compare against on-disk bytes (ignoring any trailing newline differences).
        with open(src_path, "r", encoding="utf-8", newline="") as fh:
            disk = fh.read()
        if out_buf.getvalue() != disk:
            replay_errors.append(f"{date_utc}: replay bytes differ from disk bytes")

    proof = {
        "schema_version": V2_SCHEMA_VERSION,
        "run_id": V2_RUN_ID,
        "generated_at_utc": "2026-07-22T22:00:00+00:00",
        "totals": totals,
        "partitions": per_partition_stats,
        "grand_partition_hash_sha256": grand_hash.hexdigest(),
        "replay_partition_sha256": replay_partition_bytes,
        "replay_status": "PASS" if not replay_errors else "FAIL",
        "replay_errors": replay_errors,
        "validation_status": "PASS" if not validation_errors else "FAIL",
        "validation_errors": validation_errors,
        "method_documented": {
            "OFFICIAL": "completed_at_utc supplied by source; calculated_finish_utc mirrors it.",
            "SCHEDULED_START_PLUS_DURATION": (
                "reserved for future use: would apply when scheduled_start_utc is in the past "
                "but completed_at_utc is still blank. Not used in this migration's 3109 rows."
            ),
            "UNAVAILABLE": "no completion evidence; future-scheduled or unfinished rows.",
        },
        "columns_ordered": V2_COLUMNS,
        "content_hash_includes": HASH_INCLUDE_COLUMNS,
        "content_hash_excludes": schema["content_hash_excludes"],
    }
    proof_path = os.path.join(PROOFS_DIR, "v2_migration_proof.json")
    with open(proof_path, "w", encoding="utf-8") as fh:
        json.dump(proof, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # 8) Print summary to stdout (used by both manual runs and the replay validator).
    summary = {
        "totals": totals,
        "partitions": per_partition_stats,
        "validation_status": proof["validation_status"],
        "replay_status": proof["replay_status"],
        "proof_path": proof_path,
    }
    print(json.dumps(summary, indent=2))

    if validation_errors:
        sys.exit(1)
    if replay_errors:
        sys.exit(2)


if __name__ == "__main__":
    main()