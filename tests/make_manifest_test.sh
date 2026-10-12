#!/usr/bin/env bash
# Exercises scripts/make-manifest.sh with stand-in images: twelve bytes of
# image header, the two chip-id bytes, then filler. Run from the repo root:
#   bash tests/make_manifest_test.sh
# It is not a tests/cases/ case: it tests the release packaging script, not
# the firmware. The lint-config job in .github/workflows/build.yml runs it.
set -u
t=$(mktemp -d); trap 'rm -rf "$t"' EXIT
mk() { # mk <dir> <chip id bytes, e.g. '\x02\x00'>
  mkdir -p "$1"
  { printf '\xe9\x05\x02\x20\x00\x00\x00\x00\xee\x00\x00\x00'; printf "$2"; printf 'payload-%s' "$1"; } > "$1/firmware.ota.bin"
  printf 'factory-%s' "$1" > "$1/firmware.factory.bin"
}
mk "$t/s2" '\x02\x00'; mk "$t/c6" '\x0d\x00'
fail=0
ok()   { if "$@" >/dev/null 2>&1; then echo "ok    $name"; else echo "FAIL  $name"; fail=1; fi; }
nok()  { if "$@" >/dev/null 2>&1; then echo "FAIL  $name (accepted)"; fail=1; else echo "ok    $name"; fi; }
name="both chips"; ok scripts/make-manifest.sh 9.9.9 "$t/out" https://example.test/r "esp32s2=$t/s2" "esp32c6=$t/c6"
name="manifest is JSON with two builds"; ok python3 -c "
import json,hashlib,sys,pathlib
o=pathlib.Path('$t/out'); m=json.loads((o/'manifest.json').read_text())
assert m['version']=='9.9.9' and [b['chipFamily'] for b in m['builds']]==['ESP32-S2','ESP32-C6'], m
for b,chip in zip(m['builds'],['esp32s2','esp32c6']):
    assert b['ota']['path']=='desiccant-dryer-9.9.9-%s.ota.bin'%chip, b
    assert b['parts']==[{'path':'desiccant-dryer-9.9.9-%s.factory.bin'%chip,'offset':0}], b
    assert b['ota']['md5']==hashlib.md5((o/b['ota']['path']).read_bytes()).hexdigest(), b
    assert b['ota']['release_url']=='https://example.test/r'
assert sorted(p.name for p in o.iterdir())==sorted(['manifest.json']+['desiccant-dryer-9.9.9-%s.%s.bin'%(c,k) for c in ['esp32s2','esp32c6'] for k in ['ota','factory']])
"
name="chips in the other order"; ok scripts/make-manifest.sh 9.9.9 "$t/rev" "" "esp32c6=$t/c6" "esp32s2=$t/s2"
name="other order still lists both"; ok python3 -c "
import json
m=json.load(open('$t/rev/manifest.json'))
assert sorted(b['chipFamily'] for b in m['builds'])==['ESP32-C6','ESP32-S2'], m
"
name="one chip alone"; ok scripts/make-manifest.sh 9.9.9 "$t/one" "" "esp32s2=$t/s2"
name="swapped build dirs refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x1" "" "esp32s2=$t/c6" "esp32c6=$t/s2"
name="same chip twice refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x2" "" "esp32s2=$t/s2" "esp32s2=$t/s2"
name="unknown chip refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x3" "" "esp32=$t/s2"
name="missing image refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x4" "" "esp32c6=$t/nope"
name="no chips refused"; nok scripts/make-manifest.sh 9.9.9 "$t/x5" ""
exit $fail
