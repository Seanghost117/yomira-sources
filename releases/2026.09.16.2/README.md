# Follow-up source batch — 2026.09.16.2

This pass audited twenty distinct follow-up sources. Ten are outside the pinned
27-source curated pack at revision `04aafaf`. Seven passed live acceptance,
including five outside that pack, and join the previous nine in the verified
internal beta feed. Thirteen are held; this release does not claim twenty
working additions.

Feed: <https://raw.githubusercontent.com/Seanghost117/yomira-sources/release/internal-reader-beta/repository-beta.json>

Refresh the Source Repository and update the reader-beta Source Pack. Existing
source IDs remain stable, and the previous nine definition objects are unchanged.
New definitions do not automatically enter My Sources. No app binary or website
deployment is required.

## Delivered additions

| Source | Outside previous curated pack | Repair / limitation |
| --- | --- | --- |
| KuraManga | No | Explicit first-batch-only search; removed misleading offset pagination capability. |
| ManhwaDen | No | Correct WordPress search page parameter. |
| MangaRead.org | Yes | Correct WordPress search page parameter. |
| King of Shojo | Yes | Correct search route and chapter container; removes incompatible compound selector. |
| LHTranslation | Yes | Correct WordPress search page parameter. |
| Mangasushi | Yes | Correct WordPress search page parameter. |
| GalaxyDegenScans | Yes | Correct WordPress search page parameter. |

All seven definitions advance their patch version and declare their supported
capabilities. Downloads are capped at one concurrent page and four attempts.
Existing adult-content classification is preserved; dedicated pornographic
services are excluded from this batch.

KuraManga returns its first search batch only. Its numeric offset stride cannot
be expressed by the installed declarative pagination schema. Do not advertise
continuous results until the app core supports that behavior and it is tested.

## Held candidates

| Source | Reason |
| --- | --- |
| HariManga | Origin displays Account Suspended. |
| Kun Manga | Browser Verification required. |
| MadaraDex | Browser Verification required. |
| MangaBall | Browser Verification required. |
| MangaCloud | Browser Verification required. |
| MangaGG | Browser Verification required. |
| Mangakakalot | Browser Verification required. |
| Manganato | Invalid browse responses and Browser Verification on search. |
| ManhuaUS | Browser Verification required. |
| ManhuaTop | Empty chapter extraction; diagnostic origin requests also require Browser Verification. |
| ManhwaClan | Browser Verification required. |
| Coffee Manga | Configured host returns HTTP 404; replacement host not established. |
| Reset Scans | Configured host fails DNS resolution. |

The audit inventory and dated popularity evidence are in `followup-batch.json`.
Missing traffic estimates remain absent; this is not a measured global top-twenty
ranking. `audit-input.json` and `baseline-contracts.json` preserve the tested
twenty-source baseline. They are audit evidence, not an installable feed.

## Verification and publication

- Sixteen exact-artifact live contracts passed: browse/search, details, chapters,
  reader pages and actual first-image bytes. Search pagination is checked where
  declared. King of Shojo's fixture returned 129 chapters and 30 reader images.
- One unchanged ManhuaPlus browse request returned an invalid payload. A single
  bounded recheck passed; `transient-manhuaplus-failure.json` preserves the failure.
- Sixteen static contracts and app-core import validation passed.
- Repository integrity, canary release gate and 24 Python regression tests passed.
- Checks use at most two concurrent sources, with a 150-second per-source limit.
- No database access, staging deployment, simulator run or device update occurred.

`verification.json` binds the exact release bytes and accepted live report.
Verify the public feed and immutable manifest checksum after publishing
`release/internal-reader-beta`. Public availability is recorded separately from
the pre-publication evidence.

The previous `2026.09.16.1` and `2026.09.07.1` artifacts remain unchanged. Rollback
uses a revert of this release commit on the source branch, preserving Git history
and restoring the previous feed and validation rules. Stable and broad canary
feeds remain unchanged.

Remaining work: authorized source-session acceptance for protected sites,
ManhuaTop/Manganato connector recovery, unavailable-host recovery, KuraManga
offset paging in the app core, and the previously recorded chapter-zero numbering
limitation. Physical-device acceptance is separate from these source checks.
