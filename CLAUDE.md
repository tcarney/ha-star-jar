## Project Overview

Home Assistant custom integration **Star Jar** (domain: `star_jar`): one device per child holding a star count, three services as the only writers, one event, a persisted ledger, and optional LLM narration. It is built for one household. It knows nothing about chores, calendars or lights, and anything the household does not need stays out. `README.md` is the design reference. The rules under "The rules" are invariants enforced in `jar.py` and covered by `tests/test_jar.py`.

## Development Commands

Always use project scripts, never run `hass`, `pip`, `pytest` directly.

```bash
script/check                          # Full validation (type-check + lint + spell + translations + hassfest)
script/lint                           # Auto-format and fix linting issues
script/type-check                     # Pyright
script/test                           # Run all tests
script/test -k test_name              # Run one test
script/test --cov                     # With coverage
script/develop                        # Local HA on port 8123
script/hassfest                       # Validate manifest, translations, services against HA standards
```

Restart HA after modifying Python, `manifest.json`, `services.yaml`, translations, or the config flow.

Development happens in the devcontainer. Pre-commit hooks are installed with `prek install` (HA's test requirements ship `prek`, not `pre-commit`).

## Code Style

- Python 3.14+, 4 spaces, 120 char lines, double quotes, full type hints, async for all I/O
- Ruff for linting (matches HA core config), Pyright basic mode
- Google-style docstrings; comments as complete sentences
- Import aliases: `voluptuous` as `vol`, `homeassistant.helpers.config_validation` as `cv`, `homeassistant.util.dt` as `dt_util`
- Import order: `from __future__ import annotations` → stdlib → third-party → HA core → local
- Commit messages: Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`)
- Tests: `pytest` with `asyncio_mode = auto`, `pytest-homeassistant-custom-component` fixtures; `enable_custom_integrations` is autouse in `tests/conftest.py`. Warnings are errors; the one `filterwarnings` ignore in `pyproject.toml` (aiohttp `NotAppKeyWarning` from HA's http component) is deliberate and required for every test that sets up http.
- File size: target 200-400 lines
- `strings.json` and `translations/en.json` must stay byte-identical; `script/check` fails when they differ

**Never suppress checks with blanket ignores.** Use specific codes with reasons: `# noqa: F401 - reason`.

## Architecture

- `jar.py` is a pure state machine over frozen dataclasses. Every rule lives there. Change a rule there first, with a test in `tests/test_jar.py`.
- `coordinator.py` is the only place state changes: one `asyncio.Lock`, one store write per mutation, then the event, then narration in a background task.
- All times are local: `dt_util.now()` and `async_track_time_change`, never UTC and never a hardcoded zone. Tests that touch midnight pin `America/New_York` with `hass.config.async_set_time_zone`.
- `services.py` resolves targets with `async_extract_config_entry_ids`, so the device or any entity on it works.
- `narration.py`: `plain_message` is always the message sensor's state; the LLM only ever fills the `message` attribute, and only when an `ai_task` entity is configured.
- Entities: `(CoordinatorEntity[StarJarCoordinator], SensorEntity)`, `has_entity_name`, unique id `<entry_id>_<key>`, `translation_key` = key with the name in `strings.json`. The card finds a jar's sibling sensors by device and translation key, so the keys are part of its contract.
- Services are registered once in `async_setup`. They live at integration level, so they exist regardless of which entries are loaded.
- The card is `www/star-jar-card.js`, a plain custom element with no build step. `async_setup` serves it as a static path and registers it as a Lovelace resource (falling back to `add_extra_js_url` when resources are YAML-managed), with the file's mtime as the cache-busting query, so a change to the file needs a restart before browsers fetch it.

## Workflow Rules

- Write tests for new features and bug fixes; follow the patterns in `tests/`.
- Do NOT create markdown files without explicit permission. Extend `README.md`.
- Implement features completely (new sensor = description + attributes + tests + README row).
- Don't guess HA patterns; look them up at developers.home-assistant.io.

## AI Contribution Policy

This project follows the [Open Home Foundation AI policy](https://developers.home-assistant.io/docs/ai_policy/).

- **Human in the loop.** Every change is reviewed and understood by the maintainer before it ships. Keep diffs small; call out non-obvious decisions in the summary.
- **No autonomous GitHub activity.** Never open or update issues, PRs, comments, or reviews without explicit approval for that specific action. Draft the text; the maintainer posts it.
- **Treat AI review comments as fallible.** Verify against the code before acting.

Commits keep the `Co-Authored-By` trailer. The trailer discloses AI involvement. The maintainer still reviews every line.
