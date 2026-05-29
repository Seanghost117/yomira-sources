# Yomira Sources

Community-maintained Source Definitions and Source Packs for the Yomira iOS app.
Sources are **not bundled with the app** — users add them manually or point the app to this repository.

## App Links

Repository index:

```text
https://raw.githubusercontent.com/Seanghost117/yomira-sources/main/repository.json
```

Expanded Source Pack:

```text
https://raw.githubusercontent.com/Seanghost117/yomira-sources/main/packs/keiyoushi-core-expanded/source-pack.json
```

Curated Source Pack:

```text
https://raw.githubusercontent.com/Seanghost117/yomira-sources/main/packs/yomira-curated/source-pack.json
```

## Structure

```
extensions/
  bases/          # Shared base configs (madara_base, listupd_base)
  sources/        # Individual site configs
  source-master/  # Curated pack inputs
  packs/          # App-installable Source Pack artifacts
```

## Current Packs

- `keiyoushi-core-expanded`: 438 generated and curated Source Definitions from currently supported connector families
- `yomira-curated`: 16 hand-curated Source Definitions used for focused source iteration

## Adding a Source

1. Fork this repo.
2. Copy an existing config from `sources/` as a template
3. If the site uses the Madara WordPress theme, use `"extends": "madara"` — you only need to provide `id`, `name`, `base_url`, and any overrides
4. Open a PR with your new file

## Schema Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | ✅ | Unique snake_case identifier |
| `name` | ✅ | Human-readable display name |
| `version` | ✅ | Semver string |
| `base_url` | ✅ | Site root URL |
| `language` | ✅ | ISO 639-1 language code |
| `nsfw` | ✅ | Whether adult content is expected |
| `extends` | — | Base config to inherit (e.g. `"madara"`) |
| `description` | — | Short blurb shown in the UI |
| `tags` | — | Array of category tags |
| `flags.uses_cloudflare` | — | Set `true` if Cloudflare challenge expected |
| `flags.is_madara` | — | Auto-set when using `extends: "madara"` |
| `selectors` | — | CSS selector overrides (only needed if site deviates from base) |
| `headers` | — | Extra HTTP headers (e.g., Referer) |

## License

Source definitions are MIT licensed. Manga content belongs to its respective rights holders.
