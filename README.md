# <img src="custom_components/star_jar/brand/icon.png" alt="" height="42" valign="top"> Star Jar

A Home Assistant custom integration that keeps one child's star jar. Stars accumulate toward a full jar. A full jar is one reward. Three services are the only way to change the count. It is deliberately small and tailored to one household. Automations decide *when* a star is earned (chore completions, bedtime, morning routine, a parent's decision) and call the services.

## Install

1. Add `https://github.com/tcarney/ha-star-jar` as a custom repository in HACS (category: integration).
2. Download it.
3. Restart Home Assistant.
4. Add **Star Jar** from Settings → Devices & services, one entry per child.

The entry name prefixes every entity.

## What you get

One device per child, named for the child, carrying five read-only sensors:

| Entity | State | Attributes |
|---|---|---|
| `sensor.<child>_star_jar` | Stars in the active jar, `0` to `jar_size - 1` | `jar_size`, `stars_to_fill`, `last_event`, `recent` (last 10 ledger entries, newest first). `last_event` and `recent` are excluded from recorder history. |
| `sensor.<child>_stars_today` | Stars since midnight in Home Assistant's configured time zone | |
| `sensor.<child>_rewards_available` | Rewards earned and not yet redeemed | |
| `sensor.<child>_rewards_redeemed` | Lifetime rewards taken | |
| `sensor.<child>_star_message` | A short plain line about the latest award or redemption, with the current counts. Adjustments refresh the numbers but never get a line of their own. | `message` (the narration when there is one, else the plain line), `action`, `stars`, `reason`, `source`, `reward`, `at` |

## Card

The integration ships its own Lovelace card and registers it as a resource at startup, so there is nothing to add under Settings → Dashboards → Resources. It draws the jar filling from the bottom, with the count, today's stars, the stars still to go, and the message beside it.

```yaml
type: custom:star-jar-card
entity: sensor.<child>_star_jar
height: 176   # optional, minimum card height in px
```

The jar sensor is the only entity named. The card finds the stars-today and message sensors through the entity registry, as the entities on the same device, so renaming an entity id does not break it. The card is one plain custom element in `custom_components/star_jar/www/star-jar-card.js`, with no build step and no visual editor: the configuration is small enough to write by hand, and the file is meant to be read as an example. Colours come from the theme (`--yellow-color` for the stars, `--divider-color` for the glass). An unavailable jar shows empty with zeros.

## Services

All three target the **device** (the jar itself). Any of its sensors works as a target too, since Home Assistant resolves either back to the same jar.

```yaml
action: star_jar.award
target:
  device_id: 0123456789abcdef0123456789abcdef
data:
  stars: 1          # 1-10, default 1
  reason: making the bed
  source: chore     # free text: whatever detector or person is awarding
```

```yaml
action: star_jar.adjust
target:
  device_id: 0123456789abcdef0123456789abcdef
data:
  stars: -2         # signed, not zero, -100 to 100
  reason: physical jar recount
  source: adjust    # optional, defaults to "adjust"
```

```yaml
action: star_jar.redeem
target:
  device_id: 0123456789abcdef0123456789abcdef
data:
  reward: movie night
```

`redeem` raises a validation error when no reward is available, so a script that calls it stops before delivering the reward. `reason`, `source` and `reward` are trimmed and must be 1 to 200 characters; whitespace-only text is rejected.

## The rules

These are enforced in code and covered by tests; nothing in YAML can bypass them. That is why the score is an integration at all: a YAML counter can be written by any automation or dashboard tap, and script fields are not validated on a call. Here every service call is validated against a schema.

- **The active jar is never drained.** Stars only accumulate. At `jar_size` (default 24) the jar empties into one reward in `rewards_available`, carrying any overflow: a 3-star award at 22 leaves 1 in the jar and one reward available.
- **One full jar is one reward.** `redeem` spends one and refuses at zero. Rewards are sized so one jar buys one; there is no saving up two rewards for something bigger, so there is no arithmetic to argue about.
- **Adjust reconciles, never drains.** A positive adjust behaves like an award. A negative adjust floors the jar and today's count at zero and never touches rewards.
- **Sensors are read-only.** The three services are the only writers, and each one is a single atomic store write.
- **The model never awards a star.** Narration is asked for one text field and can only change the `message` attribute.

## Event

Every mutation fires `star_jar_updated`:

| Key | Meaning |
|---|---|
| `entity_id` | The jar sensor |
| `action` | `award`, `adjust` or `redeem` |
| `stars` | Signed delta (`0` for a redeem) |
| `reason`, `source` | As given to the service |
| `reward` | The reward name on a redeem, else `null` |
| `jar_before`, `jar` | Active jar before and after |
| `jar_filled` | `true` when this mutation filled the jar and earned a reward |
| `rewards_available`, `stars_today` | Totals after the mutation |

Notifications, celebrations and displays listen to this from automations; the integration sends nothing itself.

## Narration

Optional. Set an **AI Task entity** in the integration's options and every award and redemption asks it for a short sentence. The sentence is written from the exact facts of the transition, in the voice given by the **instructions** option. Adjustments are not narrated. The call runs in the background after the state is committed. It times out after 30 seconds. If a newer event arrives first, the older answer is discarded. When there is no entity, or the call fails, the `message` attribute carries the plain line.

## Options

| Option | Default | Notes |
|---|---|---|
| Stars to fill the jar | 24 | Applies at the next award. After lowering it, the jar can exceed the new size until the next award rolls it over |
| AI Task entity | none | Leave empty for plain messages only |
| Narration instructions | a short warm persona | Words only, never numbers |

## Storage

State lives in `.storage/star_jar.<entry_id>`: the four counts, the date the daily count belongs to, the latest narration, and a ledger of the last 1000 events with timestamp, action, stars, reason, source, jar before and after, and whether the jar filled. The ledger is what makes a physical jar reconcilable: every `adjust` with its reason is in it.

## Development

Cloned from the [chore_calendar](https://github.com/tcarney/ha-chore-calendar) tooling. Develop in the devcontainer (`.devcontainer/`). Always use the project scripts:

```bash
script/setup/bootstrap   # once: venv + Home Assistant + test deps
script/test              # all tests; script/test -k name for one
script/check             # type-check, lint, spell, translations, hassfest
script/lint              # auto-format and fix
script/develop           # local Home Assistant on :8123
```

The minimum Home Assistant version in `hacs.json` is the version the household host runs. `pytest-homeassistant-custom-component` in `requirements_test.txt` is pinned to the release that pins exactly that version. When the host upgrades, bump both or the bootstrap fails to resolve:

1. Raise the minimum version in `hacs.json`.
2. Pin `pytest-homeassistant-custom-component` to the matching release in `requirements_test.txt`.

