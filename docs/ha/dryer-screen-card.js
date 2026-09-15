// Dryer Screen card: shows an image entity and swaps in each new frame only
// after it has fully downloaded and decoded, so a slow link such as the
// Cloudflare tunnel never shows a blank or half-painted frame. The built-in
// Picture Entity card points its <img> at the new URL straight away, which
// blinks whenever a frame takes a moment to arrive. See docs/screen-in-ha.md.
//
// Published on Home Assistant as an inline dashboard resource (module); keep
// this file identical to what is published.
//
//   type: custom:dryer-screen-card
//   entity: image.dryer_screen

class DryerScreenCard extends HTMLElement {
  setConfig(config) {
    if (!config.entity) throw new Error("entity is required");
    this._config = config;
    if (this._card) return;
    this._card = document.createElement("ha-card");
    this._card.style.cssText = "overflow:hidden;aspect-ratio:1;background:#000;cursor:pointer";
    this._card.addEventListener("click", () =>
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          bubbles: true,
          composed: true,
          detail: { entityId: this._config.entity },
        }),
      ),
    );
    this.appendChild(this._card);
  }

  set hass(hass) {
    const state = hass.states[this._config.entity];
    const token = state && state.attributes.access_token;
    if (!token) return;
    // The same URL the frontend builds for image entities. The state changes
    // on every refresh, so each frame has its own URL.
    this._wanted = hass.hassUrl(
      `/api/image_proxy/${state.entity_id}?token=${token}&state=${encodeURIComponent(state.state)}`,
    );
    // hass is set on every state change anywhere in HA, so only start a load
    // for a URL that is neither shown, loading, nor already failed.
    if (!this._loading && this._wanted !== this._shown && this._wanted !== this._failed) this._load();
  }

  // Loads the newest wanted frame off-screen and replaces the visible one
  // once it has decoded. Frames that fall due meanwhile are skipped for the
  // latest; a failed load leaves the current frame up until the URL changes.
  async _load() {
    this._loading = true;
    while (this._wanted !== this._shown && this._wanted !== this._failed) {
      const url = this._wanted;
      const img = new Image();
      img.alt = this._config.entity;
      img.style.cssText = "display:block;width:100%;height:100%;object-fit:cover";
      img.src = url;
      try {
        await img.decode();
      } catch (err) {
        this._failed = url;
        break;
      }
      this._card.replaceChildren(img);
      this._shown = url;
    }
    this._loading = false;
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: "full", rows: "auto" };
  }
}

if (!customElements.get("dryer-screen-card")) {
  customElements.define("dryer-screen-card", DryerScreenCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "dryer-screen-card",
    name: "Dryer Screen",
    description: "Image entity that swaps frames only once they have fully loaded",
  });
}
