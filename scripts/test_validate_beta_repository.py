"""Regression checks for accidental beta feed promotion and identity drift."""

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import validate_beta_repository as beta


class BetaFeedTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        source = Path(__file__).resolve().parents[1]
        shutil.copytree(source / "releases", self.root / "releases")
        shutil.copy(source / "repository-beta.json", self.root / "repository-beta.json")
        shutil.copytree(source / "source-master/definitions", self.root / "source-master/definitions")
        for relative in ("source-master/definitions/asurascans.json", "sources/asurascans.json"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(source / relative, target)
        index = json.loads((self.root / "repository-beta.json").read_text())
        self.release = self.root / "releases" / index["sourcePacks"][0]["version"]
        self.baselines = {
            pack_id: beta.git_json(beta.BASE_REVISION, Path("packs") / pack_id / "source-pack.json", source)
            for pack_id in [beta.BASE_PACK_ID, beta.CURATED_PACK_ID]
        }
        for patcher in (
            patch.object(beta, "validate", return_value=[]),
            patch.object(beta, "git_json", side_effect=lambda ref, path, root: self.baselines[path.parts[1]]),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def edit_index(self, change):
        path = self.root / "repository-beta.json"
        value = json.loads(path.read_text())
        change(value)
        path.write_text(json.dumps(value))

    def test_valid_feed(self):
        self.assertEqual(beta.validate_beta(self.root), [])

    def test_followup_batch_cannot_claim_curated_sources_as_new(self):
        path = self.release / "followup-batch.json"
        batch = json.loads(path.read_text())
        for entry in batch["entries"]:
            entry["outsideCurated"] = False
        path.write_text(json.dumps(batch))
        self.assertTrue(any("outside curated" in error for error in beta.validate_beta(self.root)))

    def test_followup_batch_rejects_duplicate_source_slots(self):
        path = self.release / "followup-batch.json"
        batch = json.loads(path.read_text())
        batch["entries"][-1] = batch["entries"][0]
        path.write_text(json.dumps(batch))
        self.assertTrue(any("twenty distinct" in error for error in beta.validate_beta(self.root)))

    def test_held_followup_cannot_be_marked_published(self):
        path = self.release / "followup-batch.json"
        batch = json.loads(path.read_text())
        next(entry for entry in batch["entries"] if entry["status"] == "held")["status"] = "verified"
        path.write_text(json.dumps(batch))
        self.assertTrue(any("verified follow-up identities" in error for error in beta.validate_beta(self.root)))

    def test_stale_manifest_url_is_rejected(self):
        self.edit_index(lambda index: index["sourcePacks"][0].update(manifestUrl="https://example.com/stale"))
        self.assertTrue(any("URL" in error for error in beta.validate_beta(self.root)))

    def test_bad_checksum_is_rejected(self):
        self.edit_index(lambda index: index["sourcePacks"][0].update(checksum="sha256:" + "0" * 64))
        self.assertTrue(any("checksum mismatch" in error for error in beta.validate_beta(self.root)))

    def test_stable_promotion_is_rejected_even_with_matching_checksum(self):
        self.edit_pack(lambda pack: pack.update(releaseChannel="stable", contractStatus="passed"))
        self.assertTrue(any("canary/passed" in error for error in beta.validate_beta(self.root)))

    def test_repository_identity_drift_is_rejected(self):
        self.edit_index(lambda index: index.update(repositoryId="yomira.sources"))
        self.assertTrue(any("identity" in error for error in beta.validate_beta(self.root)))

    def test_definition_identity_drift_is_rejected_even_with_matching_checksum(self):
        self.edit_pack(lambda pack: pack["definitions"][0].update(sourceId="changed.identity"))
        self.assertTrue(any("preserve" in error for error in beta.validate_beta(self.root)))

    def test_policy_drift_is_rejected_even_with_matching_checksum(self):
        self.edit_pack(lambda pack: pack["definitions"][0].update(downloadPolicy={"maximumAttempts": 99}))
        errors = beta.validate_beta(self.root)
        self.assertTrue(any("preserve" in error for error in errors))
        self.assertTrue(any("maximumAttempts" in error for error in errors))

    def test_missing_image_acceptance_is_rejected_with_valid_report_checksum(self):
        self.edit_report(lambda report: report["results"][0]["sectionHealth"].pop("image"))
        self.assertTrue(any("incomplete live flow" in error for error in beta.validate_beta(self.root)))

    def test_asura_first_image_only_is_rejected(self):
        self.edit_report(lambda report: next(item for item in report["results"] if item["sourceId"] == "asurascans").update(pageCount=1))
        self.assertTrue(any("multiple chapter pages" in error for error in beta.validate_beta(self.root)))

    def test_new_asura_definition_drift_is_rejected(self):
        self.edit_pack(lambda pack: next(item for item in pack["definitions"] if item["id"] == "asurascans")["selectors"]["page_list"].update(container="div[data-page]"))
        self.assertTrue(any("preserve" in error for error in beta.validate_beta(self.root)))

    def test_duplicate_result_cannot_replace_missing_source(self):
        self.edit_report(lambda report: report["results"].__setitem__(-1, report["results"][0]))
        self.assertTrue(any("identities" in error for error in beta.validate_beta(self.root)))

    def test_missing_pagination_acceptance_is_rejected(self):
        self.edit_report(lambda report: next(item for item in report["results"] if item["sourceId"] == "asurascans")["sectionHealth"].pop("pagination"))
        self.assertTrue(any("incomplete live flow" in error for error in beta.validate_beta(self.root)))

    def edit_report(self, change):
        release = self.release
        report_path = release / "live-contracts.json"
        report = json.loads(report_path.read_text())
        change(report)
        raw = json.dumps(report).encode()
        report_path.write_bytes(raw)
        proof_path = release / "verification.json"
        proof = json.loads(proof_path.read_text())
        proof["checks"]["priorityLiveContracts"]["reportSha256"] = hashlib.sha256(raw).hexdigest()
        proof_path.write_text(json.dumps(proof))

    def test_unpublishable_gate_is_rejected(self):
        path = self.release / "canary-release-gate.json"
        gate = json.loads(path.read_text())
        gate["canPublish"] = False
        path.write_text(json.dumps(gate))
        self.assertTrue(any("publishable canary gate" in error for error in beta.validate_beta(self.root)))

    def edit_pack(self, change):
        index_path = self.root / "repository-beta.json"
        index = json.loads(index_path.read_text())
        entry = index["sourcePacks"][0]
        path = self.root / entry["manifestUrl"].removeprefix(beta.RAW_PREFIX)
        pack = json.loads(path.read_text())
        change(pack)
        raw = (json.dumps(pack) + "\n").encode()
        path.write_bytes(raw)
        entry.update(releaseChannel=pack["releaseChannel"], contractStatus=pack["contractStatus"], checksum="sha256:" + hashlib.sha256(raw).hexdigest())
        index_path.write_text(json.dumps(index))


if __name__ == "__main__":
    unittest.main()
