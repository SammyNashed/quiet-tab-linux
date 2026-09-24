#!/usr/bin/env bash
# Quiet Tab for Linux: registers the helper that lets the New Tab page read your
# wallpaper and matugen's colours. Safe to run again (e.g. after moving the folder).
#
#   ./install.sh              register the helper + add the matugen template
#   ./install.sh --uninstall  undo both
set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd -P)
HOST=com.quiettab.helper
HELPER="$DIR/helper/quiet-tab-helper.py"
MG_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/matugen/config.toml"
MG_TEMPLATE="${XDG_CONFIG_HOME:-$HOME/.config}/matugen/templates/quiet-tab-colors.json"
COLORS="${XDG_CACHE_HOME:-$HOME/.cache}/quiet-tab/colors.json"
BEGIN='# >>> Quiet Tab (added by quiet-tab install.sh) >>>'
END='# <<< Quiet Tab <<<'

# Every Chromium browser reads native hosts from <its config dir>/NativeMessagingHosts.
BROWSERS=(
    net.imput.helium google-chrome google-chrome-beta google-chrome-unstable chromium
    BraveSoftware/Brave-Browser vivaldi microsoft-edge thorium
)

# An unpacked extension's ID comes from its folder path: sha256, first 32 hex
# digits, each mapped 0-f -> a-p. Moving the folder changes it, so re-run this.
EXT_ID=$(python3 -c 'import hashlib,sys; print("".join(chr(97+int(c,16)) for c in hashlib.sha256(sys.argv[1].encode()).hexdigest()[:32]))' "$DIR")

if [[ ${1:-} == --uninstall ]]; then
    for b in "${BROWSERS[@]}"; do rm -f "$HOME/.config/$b/NativeMessagingHosts/$HOST.json"; done
    [[ -f $MG_CONFIG ]] && sed -i "/^$BEGIN\$/,/^$END\$/d" "$MG_CONFIG"
    rm -f "$MG_TEMPLATE"
    echo "Helper unregistered and matugen template removed."
    echo "Remove the extension from your browser's extensions page to finish."
    exit 0
fi

chmod +x "$HELPER"
registered=()
for b in "${BROWSERS[@]}"; do
    [[ -d "$HOME/.config/$b" ]] || continue
    mkdir -p "$HOME/.config/$b/NativeMessagingHosts"
    cat > "$HOME/.config/$b/NativeMessagingHosts/$HOST.json" <<EOF
{
  "name": "$HOST",
  "description": "Quiet Tab: reads the wallpaper and matugen colours",
  "path": "$HELPER",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://$EXT_ID/"]
}
EOF
    registered+=("${b##*/}")
done
if ((${#registered[@]})); then
    echo "Helper registered for: ${registered[*]}"
else
    echo "No Chromium browser config found under ~/.config; start your browser once, then re-run this."
fi

if command -v matugen >/dev/null; then
    mkdir -p "$(dirname "$MG_TEMPLATE")" "$(dirname "$COLORS")"
    cp "$DIR/matugen-integration/quiet-tab-colors.json" "$MG_TEMPLATE"
    if [[ -f $MG_CONFIG ]] && ! grep -qF "$BEGIN" "$MG_CONFIG"; then
        [[ -z $(tail -c1 "$MG_CONFIG") ]] || echo >> "$MG_CONFIG"
        printf '%s\n[templates.quiet_tab_linux]\ninput_path  = %s\noutput_path = %s\n%s\n' \
            "$BEGIN" "'$MG_TEMPLATE'" "'$COLORS'" "$END" >> "$MG_CONFIG"
        echo "Added the Quiet Tab template to $MG_CONFIG"
    elif [[ ! -f $MG_CONFIG ]]; then
        echo "No $MG_CONFIG yet; add this to it when you set matugen up:"
        printf '  [templates.quiet_tab_linux]\n  input_path  = %s\n  output_path = %s\n' "'$MG_TEMPLATE'" "'$COLORS'"
    fi
    # First colours now, from the current wallpaper, touching nothing else of
    # matugen's (a throwaway config with only this template). The next time you
    # change wallpaper your own matugen run replaces them with your own style.
    wp=$("$HELPER" --check | sed -n 's/^wallpaper: //p')
    if [[ -f $wp && ! -s $COLORS ]]; then
        tmp=$(mktemp)
        printf "[config]\n[templates.qt]\ninput_path = '%s'\noutput_path = '%s'\n" "$MG_TEMPLATE" "$COLORS" > "$tmp"
        matugen -c "$tmp" image "$wp" --source-color-index 0 >/dev/null 2>&1 && echo "Generated first colours from $(basename "$wp")"
        rm -f "$tmp"
    fi
else
    echo "matugen isn't installed: the Matugen source stays empty and the tab follows the wallpaper instead."
fi

cat <<EOF

One step left, in your browser:
  1. Open its extensions page (chrome://extensions, brave://extensions, ...) and turn on Developer mode.
  2. Click 'Load unpacked' and choose:  $DIR
     (already loaded? press its reload arrow instead)
  3. Open a new tab and click the palette button (top right).
Extension ID for this folder: $EXT_ID
EOF
