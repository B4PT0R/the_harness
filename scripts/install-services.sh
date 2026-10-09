#!/bin/sh
set -eu
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
unit_root="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
application_root="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
start_services=true
if [ "${1:-}" = "--no-start" ]; then start_services=false
elif [ "$#" -ne 0 ]; then echo "usage: $0 [--no-start]" >&2; exit 2; fi
for tool in uv npm systemctl; do command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }; done
/usr/bin/python3 -c "import gi; gi.require_version('AyatanaAppIndicator3', '0.1')" || {
  echo "Install python3-gi and gir1.2-ayatanaappindicator3-0.1" >&2; exit 1;
}
case "$repo_root" in *[[:space:]]*) echo "Checkout path must not contain spaces" >&2; exit 1;; esac
cd "$repo_root"
uv sync --locked --extra dev --python /usr/bin/python3
npm ci
PLAYWRIGHT_BROWSERS_PATH="$repo_root/.playwright-browsers" .venv/bin/python -m playwright install chromium
npm run build
.venv/bin/python -m the_harness.control data-root >/dev/null
mkdir -p "$unit_root" "$application_root"
escaped_root=$(printf '%s' "$repo_root" | sed 's/[&|]/\\&/g')
escaped_npm=$(command -v npm | sed 's/[&|]/\\&/g')
escaped_node_dir=$(dirname "$(command -v node)" | sed 's/[&|]/\\&/g')
for template in "$repo_root"/packaging/systemd/*.service.in; do
  target="$unit_root/$(basename "${template%.in}")"
  sed -e "s|@REPO_ROOT@|$escaped_root|g" -e "s|@NPM@|$escaped_npm|g" -e "s|@NODE_DIR@|$escaped_node_dir|g" "$template" > "$target"
done
sed "s|@REPO_ROOT@|$escaped_root|g" packaging/the-harness.desktop.in > "$application_root/the-harness.desktop"
systemctl --user daemon-reload
systemctl --user enable the-harness.service the-harness-browser.service the-harness-ui.service the-harness-tray.service
if $start_services; then
  systemctl --user restart the-harness-ui.service the-harness-browser.service the-harness.service
  systemctl --user restart the-harness-tray.service
fi
echo "The Harness installed from $repo_root (loopback only)"
