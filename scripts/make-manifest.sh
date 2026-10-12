#!/usr/bin/env bash
# Assemble the release files for one production release: an image pair per
# chip and one manifest listing them all.
#   scripts/make-manifest.sh <version> <out-dir> <release-url> <chip>=<build-dir>...
# <chip> is esp32s2 or esp32c6. <build-dir> is that chip's build directory
# after `esphome compile` of its selector:
#   esp32s2=esphome/.esphome/build/desiccant-dryer/build      (desiccant-dryer.yaml)
#   esp32c6=esphome/.esphome/build/desiccant-dryer-c6/build   (desiccant-dryer-c6.yaml)
# <release-url> may be "" for a dry run. Writes
# desiccant-dryer-<version>-<chip>.ota.bin and .factory.bin for each chip and
# manifest.json (esp-web-tools format: read by the device's
# `update: platform: http_request`, which takes the build whose chipFamily
# is its own chip, and by web.esphome.io) to <out-dir>.
set -euo pipefail
usage="usage: $0 <version> <out-dir> <release-url> <chip>=<build-dir>..."
[ $# -ge 4 ] || { echo "$usage" >&2; exit 2; }
version=$1 out=$2 release_url=$3
shift 3
mkdir -p "$out"
builds="" seen=""
for pair in "$@"; do
  chip=${pair%%=*} build=${pair#*=}
  # chipFamily is the name esp-web-tools and ESPHome's ESPHOME_VARIANT use.
  # id is esp_chip_id_t from ESP-IDF, as it appears little-endian in bytes
  # 12-13 of an application image.
  case $chip in
    esp32s2) family="ESP32-S2" id="0200" ;;
    esp32c6) family="ESP32-C6" id="0d00" ;;
    *) echo "unknown chip '$chip' in '$pair' (esp32s2 or esp32c6)" >&2; exit 2 ;;
  esac
  case " $seen " in
    *" $chip "*) echo "chip '$chip' given twice" >&2; exit 2 ;;
  esac
  seen="$seen $chip"
  for f in firmware.ota.bin firmware.factory.bin; do
    [ -f "$build/$f" ] || { echo "$build/$f is missing; compile that chip's selector first" >&2; exit 1; }
  done
  # A build directory handed to the wrong chip would publish that chip's
  # units an image they cannot run. Refuse it here, from the image itself.
  got=$(od -An -tx1 -j12 -N2 "$build/firmware.ota.bin" | tr -d ' \n')
  [ "$got" = "$id" ] || { echo "$build/firmware.ota.bin is not an $family image (chip id bytes $got, expected $id)" >&2; exit 1; }
  ota="desiccant-dryer-${version}-${chip}.ota.bin"
  factory="desiccant-dryer-${version}-${chip}.factory.bin"
  cp "$build/firmware.ota.bin" "$out/$ota"
  cp "$build/firmware.factory.bin" "$out/$factory"
  if command -v md5sum >/dev/null; then
    md5=$(md5sum "$out/$ota" | cut -d' ' -f1)
  else
    md5=$(md5 -q "$out/$ota")
  fi
  [ -z "$builds" ] || builds="$builds,"
  builds="$builds
    {
      \"chipFamily\": \"${family}\",
      \"ota\": {
        \"path\": \"${ota}\",
        \"md5\": \"${md5}\",
        \"summary\": \"Desiccant Dryer ${version}\",
        \"release_url\": \"${release_url}\"
      },
      \"parts\": [{ \"path\": \"${factory}\", \"offset\": 0 }]
    }"
  echo "$family: $ota md5 $md5"
done
cat > "$out/manifest.json" <<JSON
{
  "name": "Desiccant Dryer",
  "version": "${version}",
  "home_assistant_domain": "esphome",
  "new_install_prompt_erase": true,
  "builds": [${builds}
  ]
}
JSON
echo "wrote $out/manifest.json"
