#!/usr/bin/env python3
"""Check the internal beta feed without promoting or modifying stable artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from validate_repository import git_json, validate, validate_capabilities, validate_download_policy


BASE_REVISION = "b4ec392f28f03d88a67f8fb2f8f35504354e9102"
RAW_PREFIX = "https://raw.githubusercontent.com/Seanghost117/yomira-sources/release/internal-reader-beta/"
PACK_IDS = {"yomira-reader-beta"}
BASE_PACK_ID = "keiyoushi-core-expanded"
PRIORITY_SOURCE_IDS = {
    "keiyoushi.en.atsumaru", "keiyoushi.en.mangapill", "keiyoushi.en.manhuaplus",
    "keiyoushi.en.s2manga", "keiyoushi.en.mangabuddy", "keiyoushi.en.manhwatop",
}


def validate_beta(root: Path) -> list[str]:
    errors = validate(root, BASE_REVISION)
    repository = json.loads((root / "repository-beta.json").read_text())
    if repository.get("schemaVersion") != "1.0":
        errors.append("beta: unsupported schema version")
    if repository.get("repositoryId") != "yomira.sources.internal-beta":
        errors.append("beta: unexpected repository identity")
    policy = repository.get("releasePolicy", {})
    if policy.get("channels") != ["canary"] or policy.get("defaultChannel") != "canary":
        errors.append("beta: only the canary channel is allowed")
    for key, expected in {
        "stableRequiresContractStatus": "passed",
        "stableRequiresChecksum": True,
        "stableRequiresReleaseNotes": True,
        "retainedRollbackVersions": 1,
    }.items():
        if policy.get(key) != expected:
            errors.append(f"beta: release policy changed: {key}")
    entries = repository.get("sourcePacks", [])
    if {entry.get("packId") for entry in entries} != PACK_IDS or len(entries) != 1:
        errors.append("beta: expected only the six-source reader beta pack")
    for entry in entries:
        pack_id = entry.get("packId")
        if pack_id not in PACK_IDS:
            continue
        version = str(entry.get("version", ""))
        if not version or any(part in version for part in ("/", "\\", "..")):
            errors.append(f"{pack_id}: invalid beta version")
            continue
        relative = f"releases/{version}/{pack_id}/source-pack.json"
        if entry.get("manifestUrl") != RAW_PREFIX + relative:
            errors.append(f"{pack_id}: beta manifest URL must identify its versioned artifact")
        artifact = root / relative
        if not artifact.is_file():
            errors.append(f"{pack_id}: missing beta artifact")
            continue
        raw = artifact.read_bytes()
        pack = json.loads(raw)
        baseline = git_json(BASE_REVISION, Path("packs") / BASE_PACK_ID / "source-pack.json", root)
        if baseline is None:
            errors.append(f"{pack_id}: pinned baseline unavailable")
            continue
        if entry.get("checksumAlgorithm") != "sha256" or entry.get("checksum") != "sha256:" + hashlib.sha256(raw).hexdigest():
            errors.append(f"{pack_id}: beta checksum mismatch")
        for field in ("packId", "version", "releaseChannel", "contractStatus", "publishedAt", "releaseNotes", "sourceCount"):
            if pack.get(field) != entry.get(field):
                errors.append(f"{pack_id}: beta manifest/index mismatch: {field}")
        if pack.get("releaseChannel") != "canary" or pack.get("contractStatus") != "passed":
            errors.append(f"{pack_id}: priority beta must remain canary/passed")
        current_definitions = {value.get("sourceId", value.get("id")): value for value in pack.get("definitions", [])}
        expected_definitions = {value.get("sourceId", value.get("id")): value for value in baseline.get("definitions", []) if value.get("sourceId", value.get("id")) in PRIORITY_SOURCE_IDS}
        if current_definitions != expected_definitions or len(pack.get("definitions", [])) != 6:
            errors.append(f"{pack_id}: candidate must preserve the baseline definitions, identities and policies")
        try:
            if tuple(map(int, version.split("."))) <= tuple(map(int, baseline["version"].split("."))):
                errors.append(f"{pack_id}: beta version must advance the baseline")
        except ValueError:
            errors.append(f"{pack_id}: beta version must contain numeric components")
        if pack.get("sourceCount") != len(pack.get("definitions", [])):
            errors.append(f"{pack_id}: beta definition count mismatch")
        if not pack.get("releaseNotes") or repository.get("updatedAt") != entry.get("updatedAt"):
            errors.append(f"{pack_id}: missing notes or inconsistent update timestamp")
        for definition in pack.get("definitions", []):
            label = f"{pack_id}:{definition.get('sourceId', definition.get('id'))}"
            validate_capabilities(definition, label, errors)
            validate_download_policy(definition, label, errors)
        release_root = root / "releases" / version
        try:
            report_raw = (release_root / "live-contracts.json").read_bytes()
            report = json.loads(report_raw)
            proof = json.loads((release_root / "verification.json").read_text())
            gate = json.loads((release_root / "canary-release-gate.json").read_text())
        except (OSError, ValueError):
            errors.append(f"{pack_id}: missing or invalid live acceptance evidence")
            continue
        if proof.get("liveInputPackChecksum") != entry.get("checksum"):
            errors.append(f"{pack_id}: live evidence input checksum mismatch")
        if proof.get("checks", {}).get("priorityLiveContracts", {}).get("reportSha256") != hashlib.sha256(report_raw).hexdigest():
            errors.append(f"{pack_id}: live evidence report checksum mismatch")
        if report.get("packId") != pack_id or report.get("live") is not True or report.get("testedCount") != 6 or report.get("passedCount") != 6:
            errors.append(f"{pack_id}: complete live acceptance required")
        results = report.get("results", [])
        if len(results) != 6 or {result.get("sourceId") for result in results} != PRIORITY_SOURCE_IDS:
            errors.append(f"{pack_id}: live result identities must match the six priority sources")
        for result in results:
            required = ("capabilities", "search", "details", "chapters", "pages", "image")
            if result.get("status") != "passed" or result.get("live") is not True or any(result.get("sectionHealth", {}).get(stage, {}).get("status") != "passed" for stage in required):
                errors.append(f"{pack_id}: incomplete live flow: {result.get('sourceId')}")
        if gate.get("canPublish") is not True or gate.get("channel") != "canary" or gate.get("repositoryId") != repository.get("repositoryId") or gate.get("repositoryUpdatedAt") != repository.get("updatedAt") or gate.get("packVersions") != {pack_id: version}:
            errors.append(f"{pack_id}: matching publishable canary gate required")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    failures = validate_beta(args.root.resolve())
    for failure in failures:
        print(f"ERROR: {failure}")
    if not failures:
        print("Internal beta feed identity, hashes, unchanged definitions and complete canary evidence passed; remote and device acceptance remain separate.")
    raise SystemExit(bool(failures))
