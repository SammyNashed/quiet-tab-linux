# Quiet Tab

A minimal New Tab page for Helium (or any Chromium-based browser) that follows your [matugen](https://github.com/InioX/matugen) wallpaper palette everywhere: the page itself, the browser's toolbar/tabs/omnibox accent, and even GTK's native text-selection color.

Curated shortcuts only — no auto-tracked "most visited," no third-party favicon service. You add what you want, and each tile fetches a high-res icon straight from the site itself (or from a hand-picked local override for a couple of sites where that didn't look right).

![screenshot placeholder](#)

## What's in here

- **The extension** (`manifest.json`, `newtab.html/css/js`, `icons/`) — load it unpacked via `chrome://extensions` (or `helium://extensions`) with Developer Mode on, "Load unpacked," point it at this folder.
- **`matugen-integration/`** — the pieces that make the *live theming* part work. This extension will run fine standalone with the default colors baked into `newtab.css`, but to get the full effect you need matugen generating `colors.json` and driving the browser's native accent for you:
  - `newtab-colors.json.template` — matugen template that generates the extension's `colors.json`
  - `set_helium_accent.py` — called from matugen's post_hook; seeds Helium's native "Colors" accent (`Preferences: browser.theme.user_color2`) from the same palette. If Helium is running when your wallpaper changes, it gracefully quits it, writes the color while it's safely closed, and relaunches with `--restore-last-session` so your tabs come back. If Helium is closed, it just writes directly.
  - `gtk-selection-colors.css` — a few extra GTK3 symbolic color names (`theme_selected_bg_color` etc.) that Helium's native text-field/omnibox selection highlight reads directly; without them it falls back to a default blue even with everything else themed.
  - `config.toml.snippet` — the matugen config entries that wire the above together

## Setup

1. Clone this repo (or just copy the extension files) somewhere permanent, e.g. `~/newtab`.
2. Load it unpacked in your browser's extensions page.
3. If you use matugen: add the entries from `matugen-integration/config.toml.snippet` to your own `~/.config/matugen/config.toml`, adjusting paths if you didn't clone to `~/newtab`. Add the color definitions from `gtk-selection-colors.css` to your existing GTK color template if you want that fixed too.
4. Run matugen once to generate `colors.json` for the first time.

Without matugen wired up, the page still works fine — it just stays on the default color scheme baked into `newtab.css`, and the browser accent/GTK pieces do nothing (they only run from matugen's post_hook).

## Notes on the icons

Shortcuts fetch `apple-touch-icon.png` (then `-precomposed`, then `favicon.ico`) directly from each site's own domain, no third party involved. A couple of sites (WhatsApp, YouTube) have hand-picked local overrides in `icons/apps/` instead, because the live fetch didn't produce a good result for them. Those override images are sourced from third-party icon packs / official brand assets and are included here as-is for personal convenience — if you fork this, you may want to swap them for your own or remove them, since I can't vouch for their redistribution terms.

## Caveats

This started as, and still mostly is, a personal setup tuned to one specific machine (Arch Linux, Hyprland, Helium, matugen). `set_helium_accent.py` assumes Helium's profile lives at `~/.config/net.imput.helium/Default/Preferences` — adjust that path for other Chromium forks. It's shared here as reference/inspiration, not a polished drop-in install.

## License

MIT — see [LICENSE](LICENSE).
