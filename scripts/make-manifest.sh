#!/usr/bin/env bash
# Assemble the release files for one production build.
#   scripts/make-manifest.sh <version> <build-dir> <out-dir> [release-url]
# <build-dir> is esphome/.esphome/build/desiccant-dryer/.pioenvs/desiccant-dryer
# after `esphome compile esphome/desiccant-dryer.yaml`. Writes
# desiccant-dryer-<version>.ota.bin, desiccant-dryer-<version>.factory.bin
# and manifest.json (esp-web-tools format: read by the device's
# `update: platform: http_request` and usable by web.esphome.io) to <out-dir>.
set -euo pipefail
version=$1 build=$2 out=$3 release_url=${4:-}
ota="desiccant-dryer-${version}.ota.bin"
factory="desiccant-dryer-${version}.factory.bin"
mkdir -p "$out"
cp "$build/firmware.ota.bin" "$out/$ota"
cp "$build/firmware.factory.bin" "$out/$factory"
if command -v md5sum >/dev/null; then
  md5=$(md5sum "$out/$ota" | cut -d' ' -f1)
else
  md5=$(md5 -q "$out/$ota")
fi
cat > "$out/manifest.json" <<JSON
{
  "name": "Desiccant Dryer",
  "version": "${version}",
  "home_assistant_domain": "esphome",
  "new_install_prompt_erase": true,
  "builds": [
    {
      "chipFamily": "ESP32-S2",
      "ota": {
        "path": "${ota}",
        "md5": "${md5}",
        "summary": "Desiccant Dryer ${version}",
        "release_url": "${release_url}"
      },
      "parts": [{ "path": "${factory}", "offset": 0 }]
    }
  ]
}
JSON
echo "wrote $out/manifest.json ($ota md5 $md5)"
