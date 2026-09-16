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
CURATED_PACK_ID = "yomira-curated"
PRIORITY_SOURCE_IDS = {
    "keiyoushi.en.atsumaru", "keiyoushi.en.mangapill", "keiyoushi.en.manhuaplus",
    "keiyoushi.en.s2manga", "keiyoushi.en.mangabuddy", "keiyoushi.en.manhwatop",
    "yomira.en.mangadex", "keiyoushi.en.mangakatana", "asurascans",
}
FOLLOWUP_SOURCE_IDS = {
    "keiyoushi.en.kuramanga", "keiyoushi.en.manhwaden", "keiyoushi.en.mangareadorg",
    "keiyoushi.en.kingofshojo", "keiyoushi.en.lhtranslation", "keiyoushi.en.mangasushi",
    "keiyoushi.en.galaxydegenscans",
}
PRIORITY_SOURCE_IDS |= FOLLOWUP_SOURCE_IDS


def validate_followup_scope(root: Path, release: Path, errors: list[str]) -> None:
    try:
        batch = json.loads((release / "followup-batch.json").read_text())
        curated = git_json("04aafaf", Path("packs") / CURATED_PACK_ID / "source-pack.json", root)
        if not curated:
            raise ValueError("missing pinned curated baseline")
        curated_ids = {item.get("sourceId", item.get("id")) for item in curated["definitions"]}
        entries = batch["entries"]
        ids = {entry["sourceId"] for entry in entries}
        if len(entries) != 20 or len(ids) != 20 or batch.get("selectedCount") != 20:
            errors.append("follow-up batch must contain twenty distinct source identities")
        if ids & (PRIORITY_SOURCE_IDS - FOLLOWUP_SOURCE_IDS):
            errors.append("follow-up batch must not recount previously delivered sources")
        if batch.get("curatedBaselineRevision") != "04aafaf" or batch.get("curatedBaselinePack") != "packs/yomira-curated/source-pack.json":
            errors.append("follow-up batch must use the pinned curated baseline")
        outside = ids - curated_ids
        if len(outside) < 5 or batch.get("outsideCuratedCount") != len(outside) or any(entry.get("outsideCurated") != (entry["sourceId"] in outside) for entry in entries):
            errors.append("follow-up batch outside curated accounting is invalid")
        verified = {entry["sourceId"] for entry in entries if entry.get("status") == "verified"}
        if verified != FOLLOWUP_SOURCE_IDS or batch.get("verifiedAdditionsCount") != len(verified) or any(entry.get("status") not in {"verified", "held"} for entry in entries):
            errors.append("verified follow-up identities must match the delivered additions")
        if len(verified - curated_ids) < 5 or batch.get("verifiedOutsideCuratedCount") != len(verified - curated_ids):
            errors.append("verified follow-up additions must include at least five outside curated")
    except (OSError, ValueError, KeyError, TypeError):
        errors.append("follow-up batch evidence is missing or invalid")


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
        errors.append("beta: expected only the verified reader beta pack")
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
        curated = git_json(BASE_REVISION, Path("packs") / CURATED_PACK_ID / "source-pack.json", root)
        for value in (curated or {}).get("definitions", []):
            identity = value.get("sourceId", value.get("id"))
            if identity in {"yomira.en.mangadex", "keiyoushi.en.mangakatana"}:
                expected_definitions[identity] = value
        try:
            asura = json.loads((root / "source-master/definitions/asurascans.json").read_text())
            legacy_asura = json.loads((root / "sources/asurascans.json").read_text())
            if asura != legacy_asura or asura.get("id") != "asurascans" or asura.get("sourceId") != "asurascans":
                errors.append(f"{pack_id}: preserve Asura standalone and curated identity/configuration")
            expected_definitions["asurascans"] = asura
        except (OSError, ValueError):
            errors.append(f"{pack_id}: missing or invalid Asura source definition")
        for source_id in FOLLOWUP_SOURCE_IDS:
            try:
                definition = json.loads((root / "source-master/definitions" / f"{source_id}.json").read_text())
                if definition.get("id") != source_id or definition.get("sourceId") != source_id:
                    errors.append(f"{pack_id}: preserve follow-up source identity: {source_id}")
                expected_definitions[source_id] = definition
            except (OSError, ValueError):
                errors.append(f"{pack_id}: missing follow-up definition: {source_id}")
        if current_definitions != expected_definitions or len(pack.get("definitions", [])) != len(PRIORITY_SOURCE_IDS):
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
        validate_followup_scope(root, release_root, errors)
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
        if report.get("packId") != pack_id or report.get("live") is not True or report.get("testedCount") != len(PRIORITY_SOURCE_IDS) or report.get("passedCount") != len(PRIORITY_SOURCE_IDS) or any(report.get(field) != 0 for field in ("failedCount", "warningCount", "skippedCount")):
            errors.append(f"{pack_id}: complete live acceptance required")
        results = report.get("results", [])
        if len(results) != len(PRIORITY_SOURCE_IDS) or {result.get("sourceId") for result in results} != PRIORITY_SOURCE_IDS:
            errors.append(f"{pack_id}: live result identities must match the priority sources")
        for result in results:
            required = ["capabilities", "search", "details", "chapters", "pages", "image"]
            if result.get("capabilities", {}).get("pagination"):
                required.append("pagination")
            required.extend(stage for stage in result.get("checkedStages", []) if stage.startswith("browse:"))
            if result.get("status") != "passed" or result.get("live") is not True or any(result.get("sectionHealth", {}).get(stage, {}).get("status") != "passed" for stage in required):
                errors.append(f"{pack_id}: incomplete live flow: {result.get('sourceId')}")
            if result.get("sourceId") == "asurascans" and (result.get("pageCount") or 0) < 5:
                errors.append(f"{pack_id}: Asura must return multiple chapter pages")
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
