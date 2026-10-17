"""Regress delivery through existing pack identities, not a separate beta-only pack."""
import hashlib
import json
from pathlib import Path
import unittest
from validate_repository import git_json, source_id

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '21fbda1e5079a0c51e669269c4fbc637dfa1d23a'
REQUESTED_READERS = {
    'keiyoushi.en.likemangain', 'keiyoushi.en.manhwatoon',
    'keiyoushi.en.xcomic', 'yomira.en.chikari', 'yomira.en.swarm',
    'yomira.en.toonverse', 'kagane',
}


class ReaderCatalogDeliveryTests(unittest.TestCase):
    def published_pack(self, pack_id):
        repository = json.loads((ROOT / 'repository.json').read_text())
        entry = next(p for p in repository['sourcePacks'] if p['packId'] == pack_id)
        prefix = 'https://raw.githubusercontent.com/Seanghost117/yomira-sources/main/'
        self.assertTrue(entry['manifestUrl'].startswith(prefix))
        raw = (ROOT / entry['manifestUrl'].removeprefix(prefix)).read_bytes()
        self.assertEqual('sha256:' + hashlib.sha256(raw).hexdigest(), entry['checksum'])
        pack = json.loads(raw)
        self.assertEqual(pack_id, pack['packId'])
        self.assertEqual(entry['sourceCount'], len(pack['definitions']))
        return entry, pack

    def test_existing_curated_update_delivers_requested_readers(self):
        _, pack = self.published_pack('yomira-curated')
        ids = {source_id(d) for d in pack['definitions']}
        self.assertFalse(REQUESTED_READERS - ids, 'New readers must reach an existing Curated installation')

    def test_existing_expanded_update_delivers_requested_readers(self):
        _, pack = self.published_pack('keiyoushi-core-expanded')
        ids = {source_id(d) for d in pack['definitions']}
        self.assertFalse(REQUESTED_READERS - ids, 'New readers must reach an existing Expanded installation')

    def test_updates_keep_all_prior_library_source_roots(self):
        for pack_id in ('yomira-curated', 'keiyoushi-core-expanded'):
            with self.subTest(pack_id=pack_id):
                entry, pack = self.published_pack(pack_id)
                baseline = git_json(BASELINE, Path('packs') / pack_id / 'source-pack.json', ROOT)
                previous = {source_id(d) for d in baseline['definitions']}
                current = {source_id(d) for d in pack['definitions']}
                self.assertFalse(previous - current, 'Publication must not orphan old source identities')
                self.assertGreater(tuple(map(int, entry['version'].split('.'))), tuple(map(int, baseline['version'].split('.'))))

    def test_fixed_reader_profiles_reach_existing_pack_updates(self):
        beta = json.loads((ROOT / 'releases/2026.10.15.1/yomira-reader-beta/source-pack.json').read_text())
        for pack_id in ('yomira-curated', 'keiyoushi-core-expanded'):
            _, pack = self.published_pack(pack_id)
            definitions = {source_id(d): d for d in pack['definitions']}
            for fixed in beta['definitions']:
                identity = source_id(fixed)
                with self.subTest(pack=pack_id, source=identity):
                    self.assertTrue(identity in definitions, identity)
                    if identity not in definitions:
                        continue
                    for field in ('sourceType', 'connectorEngine', 'connectorProfile', 'endpoints', 'flags', 'downloadPolicy', 'api'):
                        self.assertEqual(definitions[identity].get(field), fixed.get(field), field)


if __name__ == '__main__':
    unittest.main()
