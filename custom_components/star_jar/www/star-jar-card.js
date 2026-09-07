/**
 * Star Jar card.
 *
 * A jar that fills from the bottom as stars go in, with the count beside it.
 * It is the integration's own view of its sensors, so it ships with the
 * integration and is registered as a Lovelace resource by it; there is
 * nothing to add under Settings → Dashboards → Resources.
 *
 *   type: custom:star-jar-card
 *   entity: sensor.robin_star_jar
 *   height: 176      # optional, px
 *
 * The jar sensor is the only entity named: the stars-today and message
 * sensors are found through the entity registry, as the entities on the
 * same device with the matching translation keys, so a renamed entity id
 * still resolves. It is a plain custom element on purpose: no Lit, no
 * build step, no reach into Home Assistant's own elements beyond `ha-card`,
 * so the one file here is the whole card and survives frontend releases.
 * Every value defaults, so an unavailable integration shows an empty jar
 * and zeros.
 */

const DEFAULT_JAR_SIZE = 24;
const DEFAULT_HEIGHT = 176;

const STYLE = `
  ha-card {
    position: relative;
    min-height: var(--star-jar-height);
    box-sizing: border-box;
    padding: 16px 16px 16px 120px;
  }
  .jar {
    position: absolute;
    left: 24px;
    top: 16px;
    bottom: 16px;
    width: 72px;
    box-sizing: border-box;
    border: 3px solid var(--divider-color);
    border-top-width: 6px;
    border-radius: 8px 8px 22px 22px;
    background: color-mix(in srgb, var(--divider-color) 15%, transparent);
    overflow: hidden;
  }
  .fill {
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 0%;
    background: var(--yellow-color, #f4c430);
    transition: height 0.6s ease;
  }
  .count {
    font-size: 36px;
    font-weight: 680;
    line-height: 1;
    margin: 0;
  }
  .today {
    font-size: 16px;
    font-weight: 400;
    color: var(--secondary-text-color);
    margin: 6px 0 12px;
  }
  .message {
    font-size: 16px;
    margin: 0;
  }
  .message:empty {
    display: none;
  }
`;

class StarJarCard extends HTMLElement {
  static getStubConfig() {
    return { entity: "sensor.robin_star_jar" };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("star-jar-card: `entity` (the star jar sensor) is required");
    }
    this._config = config;
    this._build();
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 3;
  }

  _build() {
    const root = this.shadowRoot ?? this.attachShadow({ mode: "open" });
    const height = this._config.height ?? DEFAULT_HEIGHT;
    root.innerHTML = `
      <style>${STYLE}</style>
      <ha-card style="--star-jar-height: ${typeof height === "number" ? `${height}px` : height}">
        <div class="jar"><div class="fill"></div></div>
        <div class="count"></div>
        <div class="today"></div>
        <p class="message"></p>
      </ha-card>
    `;
    this._drawn = false;
    this._els = {
      fill: root.querySelector(".fill"),
      count: root.querySelector(".count"),
      today: root.querySelector(".today"),
      message: root.querySelector(".message"),
    };
  }

  _siblings() {
    // hass.entities is replaced as a whole when the registry changes, so its
    // identity is a cheap cache key for the lookup.
    if (this._hass.entities !== this._entities) {
      this._entities = this._hass.entities;
      const jar = this._entities?.[this._config.entity];
      const found = {};
      if (jar?.device_id) {
        for (const entry of Object.values(this._entities)) {
          if (entry.device_id === jar.device_id && entry.platform === "star_jar") {
            found[entry.translation_key] = entry.entity_id;
          }
        }
      }
      this._todayEntity = found.stars_today;
      this._messageEntity = found.star_message;
    }
  }

  _update() {
    if (!this._hass || !this._els) {
      return;
    }
    this._siblings();
    const jarState = this._hass.states[this._config.entity];
    const todayState = this._todayEntity ? this._hass.states[this._todayEntity] : undefined;
    const messageState = this._messageEntity ? this._hass.states[this._messageEntity] : undefined;
    // Every hass assignment lands here; only redraw when one of ours changed.
    if (this._drawn && jarState === this._jarState && todayState === this._todayState && messageState === this._messageState) {
      return;
    }
    this._drawn = true;
    this._jarState = jarState;
    this._todayState = todayState;
    this._messageState = messageState;

    const jar = toInt(jarState?.state, 0);
    const size = toInt(jarState?.attributes?.jar_size, DEFAULT_JAR_SIZE);
    const toGo = toInt(jarState?.attributes?.stars_to_fill, Math.max(0, size - jar));
    const today = toInt(todayState?.state, 0);
    const fraction = Math.min(1, Math.max(0, jar / size));

    this._els.fill.style.height = `${(fraction * 100).toFixed(1)}%`;
    this._els.count.textContent = `${jar} stars`;
    this._els.today.textContent = `${today} today · ${toGo} to go`;
    this._els.message.textContent = messageState?.attributes?.message ?? "";
  }
}

function toInt(value, fallback) {
  const number = parseInt(value, 10);
  return Number.isNaN(number) ? fallback : number;
}

customElements.define("star-jar-card", StarJarCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "star-jar-card",
  name: "Star Jar",
  description: "A jar that fills as stars go in.",
  preview: false,
});
