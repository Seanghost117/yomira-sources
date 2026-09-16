# Priority source refresh — 2026.09.16.1

The existing internal beta feed advances from six to nine verified definitions:
Atsumaru, MangaPill, ManhuaPlus, S2Read, MangaK, ManhwaTop, MangaDex,
MangaKatana and Asura Scans. The original source IDs and eight existing
definition objects are preserved. Asura advances from 1.0.0 to 1.0.1.

Feed: <https://raw.githubusercontent.com/Seanghost117/yomira-sources/release/internal-reader-beta/repository-beta.json>

Refresh the Source Repository, then update the installed reader-beta Source Pack.
New definitions do not automatically enter My Sources. No app binary, website
service, database, physical device or simulator is changed by this publication.

## Selection and held candidates

[`priority-refresh-2026-09-16.json`](../../source-master/priority-refresh-2026-09-16.json)
records twelve candidates, dated traffic evidence, missing estimates and live
status. This is an English-reader priority shortlist, not a definitive global
traffic ranking. The estimates cover different months; legacy-domain traffic
is not reassigned to a new host.

Comix, MangaFire and WeebCentral remain in the source inventory but are excluded
from verified beta delivery. WeebCentral requires Browser Verification. Comix
and MangaFire also returned empty/invalid discovery using their existing
definitions; public-origin challenges were observed separately. Completing
verification alone is not proven to repair their connectors. Their failed
contracts are retained in `held-source-contracts.json`.

Non-explicit GL/BL coverage through MangaDex is included. Dedicated additions
are not claimed complete: Dynasty needs root-level reader JSON support;
WEBTOON needs bounded chapter-list pagination to avoid hiding older episodes.
The genre candidates are not asserted to be traffic-ranked top-two specialists.

## Asura repair and acceptance

The new definition follows the site's current server-rendered browse/comics
routes. Search and pagination use the current query parameters. Listing scope
selects the hydrated grid once, avoiding its duplicate fallback markup. Reader
image extraction scopes the whole document and then selects page-indexed images;
scoping a single page container incorrectly returned only one image.

The retained failing and passing contracts demonstrate both the obsolete-site
failure and the first-image-only regression. The final contract requires at
least five reader images and checks actual first-image bytes; the tested chapter
returned fifteen. Only publicly accessible chapters are supported.

Known existing core limitation: a numeric chapter zero is assigned a sequential
number by the installed selector engine. Asura's chapter URL and title remain
intact, but the numeric field can show 201 for the prologue. Correct this in the
app core before stable promotion; this source-only release does not change it.

All nine definitions passed exact-artifact live contracts, static contracts,
app-core import validation and the canary release gate. Live checks are bounded
to two concurrent sources and 180 seconds per source. `verification.json`
binds the tested manifest and report checksums. Device acceptance remains separate.

## Publication and rollback

Publish only after repository validation, beta integrity validation and Python
regression tests pass. Verify the remote feed and its immutable manifest digest
after pushing `release/internal-reader-beta`.

The previous `releases/2026.09.07.1/` artifacts remain unchanged. To roll back,
restore `repository-beta.json` from source revision
`8a63a5f2c18386f6fc2b09a1610467a6d0e57772` and publish that feed change without
rewriting the retained artifacts. Stable and broad canary feeds are unchanged.
