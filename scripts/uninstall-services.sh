#!/bin/sh
set -eu
unit_root="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
application_root="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
for unit in the-harness-tray.service the-harness-ui.service the-harness-browser.service the-harness.service; do
  if systemctl --user cat "$unit" >/dev/null 2>&1; then systemctl --user disable --now "$unit"; fi
  rm -f "$unit_root/$unit"
done
rm -f "$application_root/the-harness.desktop"
systemctl --user daemon-reload
echo "Services removed; ~/.the_harness_assistant and ~/TheHarnessAssistant preserved."
