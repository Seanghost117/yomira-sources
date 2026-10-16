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
        # Historical tests remain about the published sixteen-source release,
        # even after the active feed advances to a new candidate.
        legacy_index = beta.git_json(beta.FOLLOWUP_REVISION, Path("repository-beta.json"), source)
        (self.root / "repository-beta.json").write_text(json.dumps(legacy_index))
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
        published = json.loads((source / "releases/2026.09.16.2/yomira-reader-beta/source-pack.json").read_text())
        self.followup_definitions = {d["id"]: d for d in published["definitions"]}
        self.candidate_definitions = {
            identity: json.loads((source / "source-master/definitions" / f"{identity}.json").read_text())
            for identity in beta.REQUESTED_SOURCE_IDS | {"keiyoushi.en.kuramanga"}
        }
        for patcher in (
            patch.object(beta, "validate", return_value=[]),
            patch.object(beta, "git_json", side_effect=lambda ref, path, root:
                         self.baselines[path.parts[1]] if path.parts[0] == "packs"
                         else (self.candidate_definitions if ref == beta.CANDIDATE_DEFINITIONS_REVISION
                               else self.followup_definitions).get(path.stem)),
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

    def test_new_master_revision_does_not_rewrite_immutable_beta_expectations(self):
        path = self.root / "source-master/definitions/keiyoushi.en.kuramanga.json"
        definition = json.loads(path.read_text())
        definition["version"] = "99.0.0"
        definition["pagination"] = {"param": "offset", "start": 0, "step": 10}
        path.write_text(json.dumps(definition))
        for relative in ("source-master/definitions/asurascans.json", "sources/asurascans.json"):
            path = self.root / relative
            definition = json.loads(path.read_text())
            definition["version"] = "99.0.0"
            path.write_text(json.dumps(definition))
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


class ExpandedBetaFeedTests(BetaFeedTests):
    """The new candidate has its own pinned inputs and complete acceptance."""

    def setUp(self):
        super().setUp()
        index_path = self.root / "repository-beta.json"
        index = json.loads(index_path.read_text())
        entry = index["sourcePacks"][0]
        previous = self.release
        self.release = self.root / "releases" / beta.CANDIDATE_VERSION
        self.release.mkdir(parents=True, exist_ok=True)
        pack = json.loads((previous / "yomira-reader-beta/source-pack.json").read_text())
        definitions = dict(self.followup_definitions)
        definitions.update(self.candidate_definitions)
        pack.update(version=beta.CANDIDATE_VERSION, sourceCount=23,
                    definitions=list(definitions.values()))
        relative = f"releases/{beta.CANDIDATE_VERSION}/yomira-reader-beta/source-pack.json"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(pack) + "\n").encode()
        path.write_bytes(raw)
        entry.update(version=pack["version"], sourceCount=23,
                     manifestUrl=beta.RAW_PREFIX + relative,
                     checksum="sha256:" + hashlib.sha256(raw).hexdigest())
        index_path.write_text(json.dumps(index))

        report = json.loads((previous / "live-contracts.json").read_text())
        existing = {result["sourceId"]: result for result in report["results"]}
        for identity in beta.REQUESTED_SOURCE_IDS:
            stages = ["capabilities", "search", "details", "chapters", "pages", "image", "pagination", "browse:latest"]
            existing[identity] = {
                "sourceId": identity, "status": "passed", "live": True,
                "capabilities": {"pagination": True, "browse": True},
                "checkedStages": stages,
                "sectionHealth": {stage: {"status": "passed"} for stage in stages},
                "chapterCount": 10, "pageCount": 3,
            }
        kura = existing["keiyoushi.en.kuramanga"]
        kura["capabilities"]["pagination"] = True
        if "pagination" not in kura["checkedStages"]:
            kura["checkedStages"].append("pagination")
        kura["sectionHealth"]["pagination"] = {"status": "passed"}
        report.update(testedCount=23, passedCount=23, results=list(existing.values()))
        report_raw = json.dumps(report).encode()
        (self.release / "live-contracts.json").write_bytes(report_raw)
        proof = json.loads((previous / "verification.json").read_text())
        proof.update(candidateVersion=beta.CANDIDATE_VERSION,
                     sourceDefinitionsRevision=beta.CANDIDATE_DEFINITIONS_REVISION,
                     liveInputPackChecksum=entry["checksum"])
        proof["checks"]["priorityLiveContracts"].update(
            tested=23, passed=23, failed=0, warnings=0, skipped=0,
            maximumConcurrentSources=2, perSourceTimeoutSeconds=300,
            reportSha256=hashlib.sha256(report_raw).hexdigest())
        (self.release / "verification.json").write_text(json.dumps(proof))
        gate = json.loads((previous / "canary-release-gate.json").read_text())
        gate["packVersions"] = {"yomira-reader-beta": beta.CANDIDATE_VERSION}
        gate["packs"][0].update(version=beta.CANDIDATE_VERSION, testedSourceCount=23)
        (self.release / "canary-release-gate.json").write_text(json.dumps(gate))

    # These inherited tests mutate historical audit evidence. It deliberately
    # remains under the old release rather than being copied into the new one.
    def audit_path(self):
        return self.root / "releases" / beta.LEGACY_VERSION / "followup-batch.json"

    def test_followup_batch_cannot_claim_curated_sources_as_new(self):
        path = self.audit_path()
        batch = json.loads(path.read_text())
        for entry in batch["entries"]:
            entry["outsideCurated"] = False
        path.write_text(json.dumps(batch))
        self.assertTrue(any("outside curated" in error for error in beta.validate_beta(self.root)))

    def test_followup_batch_rejects_duplicate_source_slots(self):
        path = self.audit_path()
        batch = json.loads(path.read_text())
        batch["entries"][-1] = batch["entries"][0]
        path.write_text(json.dumps(batch))
        self.assertTrue(any("twenty distinct" in error for error in beta.validate_beta(self.root)))

    def test_held_followup_cannot_be_marked_published(self):
        path = self.audit_path()
        batch = json.loads(path.read_text())
        next(entry for entry in batch["entries"] if entry["status"] == "held")["status"] = "verified"
        path.write_text(json.dumps(batch))
        self.assertTrue(any("verified follow-up identities" in error for error in beta.validate_beta(self.root)))

    def test_only_the_requested_seven_additions_are_accepted(self):
        self.edit_pack(lambda pack: next(item for item in pack["definitions"] if item["id"] == "kagane").update(id="held.toonkotsu", sourceId="held.toonkotsu"))
        self.assertTrue(any("preserve" in error for error in beta.validate_beta(self.root)))

    def test_original_source_policy_cannot_drift(self):
        self.edit_pack(lambda pack: next(item for item in pack["definitions"] if item["id"] == "keiyoushi.en.atsumaru").update(rate_limit_ms=1))
        self.assertTrue(any("preserve" in error for error in beta.validate_beta(self.root)))

    def test_kura_must_match_the_pinned_stride_fix(self):
        self.edit_pack(lambda pack: next(item for item in pack["definitions"] if item["id"] == "keiyoushi.en.kuramanga")["pagination"].update(step=1))
        self.assertTrue(any("preserve" in error for error in beta.validate_beta(self.root)))

    def test_any_source_with_only_one_page_is_rejected(self):
        self.edit_report(lambda report: next(item for item in report["results"] if item["sourceId"] == "kagane").update(pageCount=1))
        self.assertTrue(any("every source" in error for error in beta.validate_beta(self.root)))

    def test_result_cannot_hide_required_pagination_by_changing_capabilities(self):
        def remove(report):
            result = next(item for item in report["results"] if item["sourceId"] == "kagane")
            result["capabilities"]["pagination"] = False
            result["sectionHealth"].pop("pagination")
        self.edit_report(remove)
        self.assertTrue(any("incomplete live flow" in error for error in beta.validate_beta(self.root)))

    def test_missing_browse_is_rejected(self):
        self.edit_report(lambda report: next(item for item in report["results"] if item["sourceId"] == "kagane").update(checkedStages=["capabilities", "search", "details", "chapters", "pages", "image", "pagination"]))
        self.assertTrue(any("browse acceptance" in error for error in beta.validate_beta(self.root)))

    def test_pinned_revision_is_required(self):
        path = self.release / "verification.json"
        proof = json.loads(path.read_text())
        proof["sourceDefinitionsRevision"] = "uncommitted-master"
        path.write_text(json.dumps(proof))
        self.assertTrue(any("pinned source revision" in error for error in beta.validate_beta(self.root)))

    def test_source_verification_must_remain_bounded(self):
        path = self.release / "verification.json"
        proof = json.loads(path.read_text())
        proof["checks"]["priorityLiveContracts"].update(maximumConcurrentSources=23, perSourceTimeoutSeconds=0)
        path.write_text(json.dumps(proof))
        self.assertTrue(any("bounded live verification" in error for error in beta.validate_beta(self.root)))

    def test_missing_live_result_is_rejected(self):
        self.edit_report(lambda report: report["results"].pop())
        self.assertTrue(any("identities" in error for error in beta.validate_beta(self.root)))

    def test_gate_cannot_publish_with_sixteen_source_acceptance(self):
        path = self.release / "canary-release-gate.json"
        gate = json.loads(path.read_text())
        gate["packs"][0]["testedSourceCount"] = 16
        path.write_text(json.dumps(gate))
        self.assertTrue(any("twenty-three-source" in error for error in beta.validate_beta(self.root)))

    def test_live_proof_checksum_cannot_be_stale(self):
        path = self.release / "verification.json"
        proof = json.loads(path.read_text())
        proof["checks"]["priorityLiveContracts"]["reportSha256"] = "0" * 64
        path.write_text(json.dumps(proof))
        self.assertTrue(any("report checksum" in error for error in beta.validate_beta(self.root)))


if __name__ == "__main__":
    unittest.main()
