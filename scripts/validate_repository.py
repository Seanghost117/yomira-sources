#!/usr/bin/env python3
"""Validate Yomira Source Repository structure and update invariants."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
RELEASE_CHANNELS = {"canary", "stable"}
CONTRACT_STATUSES = {"passed", "passed_with_warnings", "failed", "pending"}
CONTRACT_TIERS = {"live", "repository_only"}
CAPABILITY_KEYS = {
    "search",
    "browse",
    "details",
    "chapters",
    "pages",
    "filters",
    "pagination",
    "imagePages",
    "textPages",
    "browserVerification",
    "listings",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def normalized_checksum(value: str) -> str:
    return value.removeprefix("sha256:").lower()


def source_id(definition: dict[str, Any]) -> str:
    return str(definition.get("sourceId") or definition.get("id") or "").strip()


def validate_capabilities(definition: dict[str, Any], label: str, errors: list[str]) -> None:
    capabilities = definition.get("capabilities")
    if capabilities is None:
        return
    if not isinstance(capabilities, dict):
        errors.append(f"{label}: capabilities must be an object")
        return
    unknown = sorted(set(capabilities) - CAPABILITY_KEYS)
    if unknown:
        errors.append(f"{label}: unknown capabilities: {', '.join(unknown)}")
    for key, value in capabilities.items():
        if key == "listings":
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                errors.append(f"{label}: capabilities.listings must contain names")
        elif not isinstance(value, bool):
            errors.append(f"{label}: capabilities.{key} must be true or false")
    if capabilities.get("browse") is True and not capabilities.get("listings"):
        errors.append(f"{label}: browse capability requires listings")
    if capabilities.get("pages") is True and not (
        capabilities.get("imagePages") is True
        or capabilities.get("textPages") is True
    ):
        errors.append(f"{label}: pages capability requires imagePages or textPages")


def definition_without_version(definition: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(definition)
    value.pop("version", None)
    return value


def git_json(base_ref: str, path: Path, root: Path) -> dict[str, Any] | None:
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{path.as_posix()}"],
        check=False,
        capture_output=True,
        text=True,
        cwd=root,
    )
    if result.returncode != 0:
        return None
    value = json.loads(result.stdout)
    return value if isinstance(value, dict) else None


def validate(root: Path, base_ref: str | None) -> list[str]:
    errors: list[str] = []
    repository_path = root / "repository.json"
    repository = load_json(repository_path)
    if repository.get("schemaVersion") != "1.0":
        errors.append("repository.json: unsupported schemaVersion")
    if repository.get("repositoryId") != "yomira.sources":
        errors.append("repository.json: unexpected repositoryId")
    release_policy = repository.get("releasePolicy")
    if not isinstance(release_policy, dict):
        errors.append("repository.json: releasePolicy is required")
    else:
        channels = release_policy.get("channels")
        if not isinstance(channels, list) or set(channels) != RELEASE_CHANNELS:
            errors.append("repository.json: releasePolicy.channels must contain canary and stable")
        if release_policy.get("defaultChannel") != "stable":
            errors.append("repository.json: releasePolicy.defaultChannel must be stable")
        retention = release_policy.get("retainedRollbackVersions")
        if not isinstance(retention, int) or not 1 <= retention <= 10:
            errors.append(
                "repository.json: retainedRollbackVersions must be between 1 and 10"
            )
    entries = repository.get("sourcePacks")
    if not isinstance(entries, list) or not entries:
        return errors + ["repository.json: sourcePacks must not be empty"]

    old_repository = (
        git_json(base_ref, Path("repository.json"), root) if base_ref else None
    )
    old_entries = {
        entry.get("packId"): entry
        for entry in (old_repository or {}).get("sourcePacks", [])
        if isinstance(entry, dict)
    }

    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("repository.json: each Source Pack entry must be an object")
            continue
        pack_id = str(entry.get("packId") or "")
        release_channel = str(entry.get("releaseChannel") or "")
        contract_status = str(entry.get("contractStatus") or "")
        contract_tier = str(entry.get("contractTier") or "")
        release_notes = entry.get("releaseNotes")
        if release_channel not in RELEASE_CHANNELS:
            errors.append(f"{pack_id}: releaseChannel must be canary or stable")
        if contract_status not in CONTRACT_STATUSES:
            errors.append(f"{pack_id}: contractStatus is invalid")
        if contract_tier not in CONTRACT_TIERS:
            errors.append(f"{pack_id}: contractTier must be live or repository_only")
        if not isinstance(entry.get("publishedAt"), str) or not entry.get("publishedAt"):
            errors.append(f"{pack_id}: publishedAt is required")
        if not isinstance(release_notes, list) or not release_notes or not all(
            isinstance(note, str) and note.strip() for note in release_notes
        ):
            errors.append(f"{pack_id}: releaseNotes must contain at least one note")
        if release_channel == "stable" and contract_status != "passed":
            errors.append(f"{pack_id}: stable releases require passed contracts")
        if entry.get("checksumAlgorithm") != "sha256":
            errors.append(f"{pack_id}: stable release checksumAlgorithm must be sha256")
        checksum = str(entry.get("checksum") or "")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", checksum):
            errors.append(f"{pack_id}: checksum must be a lowercase sha256 digest")
        pack_path = Path("packs") / pack_id / "source-pack.json"
        absolute_pack_path = root / pack_path
        if not absolute_pack_path.exists():
            errors.append(f"{pack_id}: missing {pack_path}")
            continue
        raw = absolute_pack_path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        expected = normalized_checksum(str(entry.get("checksum") or ""))
        if digest != expected:
            errors.append(f"{pack_id}: repository checksum does not match Source Pack")
        pack = load_json(absolute_pack_path)
        definitions = pack.get("definitions")
        if pack.get("schemaVersion") != "1.0":
            errors.append(f"{pack_id}: unsupported Source Pack schemaVersion")
        if pack.get("packId") != pack_id:
            errors.append(f"{pack_id}: packId mismatch")
        for field in (
            "version",
            "releaseChannel",
            "contractStatus",
            "publishedAt",
            "releaseNotes",
        ):
            if pack.get(field) != entry.get(field):
                errors.append(
                    f"{pack_id}: repository {field} does not match Source Pack manifest"
                )
        if not isinstance(definitions, list) or not definitions:
            errors.append(f"{pack_id}: definitions must not be empty")
            continue
        if pack.get("sourceCount") != len(definitions):
            errors.append(f"{pack_id}: sourceCount does not match definitions")
        if entry.get("sourceCount") != len(definitions):
            errors.append(f"{pack_id}: repository sourceCount does not match definitions")

        seen: set[str] = set()
        current_definitions: dict[str, dict[str, Any]] = {}
        for index, value in enumerate(definitions):
            if not isinstance(value, dict):
                errors.append(f"{pack_id}[{index}]: definition must be an object")
                continue
            identifier = source_id(value)
            label = f"{pack_id}:{identifier or index}"
            if not identifier:
                errors.append(f"{label}: sourceId is required")
            elif identifier in seen:
                errors.append(f"{label}: duplicate sourceId")
            seen.add(identifier)
            current_definitions[identifier] = value
            if not (value.get("displayName") or value.get("name")):
                errors.append(f"{label}: displayName is required")
            if not (value.get("baseUrl") or value.get("base_url")):
                errors.append(f"{label}: baseUrl is required")
            version = str(value.get("version") or "")
            if not SEMVER.fullmatch(version):
                errors.append(f"{label}: version must be semantic")
            if value.get("appStoreSafe", True) is not True:
                errors.append(f"{label}: appStoreSafe must be true")
            if value.get("containsExecutableCode", False) is not False:
                errors.append(f"{label}: containsExecutableCode must be false")
            if value.get("requiresExternalBridge", False) is not False:
                errors.append(f"{label}: requiresExternalBridge must be false")
            validate_capabilities(value, label, errors)

        if not base_ref:
            continue
        old_pack = git_json(base_ref, pack_path, root)
        old_entry = old_entries.get(pack_id)
        if old_pack is None or not isinstance(old_entry, dict):
            continue
        if old_pack != pack:
            if old_entry.get("version") == entry.get("version"):
                errors.append(f"{pack_id}: changed Source Pack must bump repository version")
            if old_entry.get("updatedAt") == entry.get("updatedAt"):
                errors.append(f"{pack_id}: changed Source Pack must update updatedAt")
        old_definitions = {
            source_id(value): value
            for value in old_pack.get("definitions", [])
            if isinstance(value, dict)
        }
        for identifier, definition in current_definitions.items():
            previous = old_definitions.get(identifier)
            if previous is None:
                continue
            if definition_without_version(previous) != definition_without_version(definition):
                if previous.get("version") == definition.get("version"):
                    errors.append(
                        f"{pack_id}:{identifier}: changed definition must bump version"
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--base-ref")
    args = parser.parse_args()
    errors = validate(args.root.resolve(), args.base_ref)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Source Repository structure and update invariants passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
