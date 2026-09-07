# Internal reader beta Source Repository — 2026.09.07.1

**Pre-publication acceptance: verified, canary publishable.** This release contains
only the six priority Source Definitions. The existing 421-definition expanded
and 27-definition curated packs remain pending and are excluded from this feed.
Neither existing pack has been relabeled stable or passed.

## Candidate identity

- Branch: `release/internal-reader-beta`.
- Feed: `https://raw.githubusercontent.com/Seanghost117/yomira-sources/release/internal-reader-beta/repository-beta.json`.
- Repository ID: `yomira.sources.internal-beta`.
- Pack ID: `yomira-reader-beta`; version: `2026.09.07.1`; channel: `canary`; contract status: `passed`.
- Input Source Repository revision: `b4ec392f28f03d88a67f8fb2f8f35504354e9102`.
- Checker revision: `d855e6d9cb44ae578b1a39c42b74bb0d37923933`.
- Exact artifact checksum, core tree, toolchain and dependency identities: [verification.json](verification.json).

The feed references the versioned six-source pack snapshot. Do not overwrite an
accepted version: create a new version and update its index/checksum together.
A branch is mutable; the checksum binds the manifest's exact bytes. Verify the
public feed and manifest against the intended source commit/digest after push.
Remote delivery and authorized iOS device acceptance are separate from this
pre-publication evidence.

## Fresh bounded live acceptance

The final six-source artifact was tested directly through the candidate's built-in
connector engines. All six passed browse/search, details, chapters, pages and an
actual first-image byte check; applicable pagination checks also passed. There
were no warnings, failures, skipped sources, Browser Verification recoveries or
fixture repairs. No source sessions, cookies or credentials were imported.

| Source | Preserved source ID | Search results | Chapters | Pages in checked chapter | Actual image |
| --- | --- | ---: | ---: | ---: | --- |
| Atsumaru | `keiyoushi.en.atsumaru` | 7 | 802 | 49 | Passed |
| MangaPill | `keiyoushi.en.mangapill` | 6 | 281 | 16 | Passed |
| Manhua Plus | `keiyoushi.en.manhuaplus` | 3 | 3364 | 12 | Passed |
| S2Read | `keiyoushi.en.s2manga` | 1 | 385 | 8 | Passed |
| MangaK | `keiyoushi.en.mangabuddy` | 24 | 50 | 14 | Passed |
| Manhwatop | `keiyoushi.en.manhwatop` | 12 | 47 | 83 | Passed |

These are dated fixture results, not a guarantee for every title or future host
availability. The checker validates actual downloaded image bytes; it does not
replace reader display, download recovery or device acceptance. The pass used
at most two independent source hosts concurrently and a 180-second process limit
per source. See [live contracts](live-contracts.json), [execution bounds and durations](probe-execution.json),
and [the publishable canary gate](canary-release-gate.json).

The six-source pack also passed app-core import validation with six installable
definitions and zero rejected definitions, warnings or errors. The unchanged
broad input packs were structurally checked (421 and 27 installable definitions)
but that does not grant them full live acceptance or inclusion in this feed.
The older VyManga HTTP 522 blocker remains historical evidence; it was not probed
again in this six-source pass.

## Identity and personal-data preservation

All six definition objects are identical to the pinned expanded input: source ID,
definition version, connector configuration, mapping provenance and download
policy remain intact. S2Read remains `keiyoushi.en.s2manga`; MangaK remains
`keiyoushi.en.mangabuddy`. Each priority source retains automatic download
transport, one concurrent page and at most four attempts.

The distinct beta pack adds a provider membership for these existing source IDs;
it does not rename the source IDs, replace the broad packs, or remove their other
definitions. Explicit repository trust and source selection still apply. Import
must not automatically fill My Sources, and beta setup must not delete old packs
or personal reading data. Existing core tests cover duplicate-provider imports,
saved-source preservation through a remaining provider, last-provider removal
without library-data deletion, and saved/disabled state during updates. The parent
release verification owns execution of those tests and authorized device checks.
Device acceptance must still verify Library, History, progress, downloads,
bookmarks and selective My Sources state across provider changes/update/removal.

## Previous delivery pointers

The existing `repository.json`, `repository-canary.json` and `packs/` are unchanged.
Remote source main was freshly observed at
`8b8821ef0b0494e9d5fabdf45345c8455f7af50e`; its pack versions are `2026.07.13.1`
with their prior stable/passed labels. Those labels are historical, not fresh live
evidence. The broader candidate artifacts `2026.08.20.1` remain available at
`b4ec392f28f03d88a67f8fb2f8f35504354e9102`. The dedicated beta pack is a first
release and has no previous beta-pack version. Select an existing provider or
an exact prior artifact deliberately when rolling back; do not erase personal
data as part of rollback.

## Reproduction

From the Source Repository:

```sh
python3 scripts/validate_repository.py --base-ref b4ec392f28f03d88a67f8fb2f8f35504354e9102
python3 scripts/validate_beta_repository.py
python3 -m unittest discover -s scripts -p 'test_*.py'
```

The checker is excluded from the parent's Cargo workspace and has no committed
lockfile. For the observed build, its temporary lock was seeded from the parent's
checked-in Cargo.lock; every external package/version matched that root lock.
Only the local checker package was added. The temporary lock was removed from the
Source Tools checkout after building. Use an isolated temporary build directory,
two jobs, and retain sanitized evidence without committing local build products.

From the exact parent/tool checkout, after preparing that temporary checker lock:

```sh
cargo build --manifest-path tools/source-converter/Cargo.toml --target-dir /tmp/yomira-beta-source-target --locked -j 2
/tmp/yomira-beta-source-target/debug/yomira-source-converter validate-source-pack --pack extensions/releases/2026.09.07.1/yomira-reader-beta/source-pack.json --out /tmp/beta-pack-validation --pretty
/tmp/yomira-beta-source-target/debug/yomira-source-converter contract-test --pack extensions/releases/2026.09.07.1/yomira-reader-beta/source-pack.json --contracts extensions/contracts/internal-reader-beta.json --live --max-sources 6 --out /tmp/beta-live.json --pretty
/tmp/yomira-beta-source-target/debug/yomira-source-converter release-gate --repository extensions/repository-beta.json --report /tmp/beta-live.json --channel canary --out /tmp/beta-canary.json --pretty
```

For the recorded run each source used `--source <existing source ID>` and
`--max-sources 1` under the bounds above; the six unmodified results were combined
into the included report. No source failures were discarded. GitHub CI validates
feed identity, bytes, unchanged definitions, complete image-stage evidence and the
matching canary decision. It does not rerun external live contracts on every push.
No staging/production deployment, signing/upload, simulator or device action was
performed by this source pass.
