# desiccant-dryer

ESPHome firmware for an ESP32-S2 replacement of the Azco VMD-08 desiccant
air dryer control board. Swaps packs on measured humidity and pack
temperature instead of a fixed timer. See `CLAUDE.md` for decisions,
`docs/hardware.md` for wiring and BOM, `docs/control-logic.md` for the
state machine, `docs/virtual-testing.md` for testing without hardware,
`docs/host-preview.md` for the display on your Mac, `docs/screen-in-ha.md` for the live screen in Home Assistant,
`docs/releasing.md` for numbered production releases and updates through Home Assistant.

Three builds share `esphome/packages/base.yaml`:

| Build | File | Sensors | Runs on |
|---|---|---|---|
| Production | `esphome/desiccant-dryer.yaml` | SHT45 + 3× DS18B20 (`packages/hw-real.yaml`) | ESP32-S2 |
| Hardware test | `esphome/desiccant-dryer-hw-test.yaml` | Same real sensors, dev credentials, OTA and `/screen.png` | ESP32-S2 |
| Virtual | `esphome/desiccant-dryer-virtual.yaml` | On-device plant model (`packages/hw-virtual.yaml`) | ESP32-S2, nothing attached |
| Host | `esphome/desiccant-dryer-host.yaml` | Same plant model | Your Mac, display in an SDL window |
| Screen scenarios | `esphome/desiccant-dryer-scenarios.yaml` | Fixed table of twelve screen states, no controller | Your Mac; `scripts/scenario-shots.sh` renders them to `docs/display/` |

```
cp esphome/secrets.yaml.example esphome/secrets.yaml   # fill in (test builds only)
esphome run esphome/desiccant-dryer-virtual.yaml       # bare board
esphome run esphome/desiccant-dryer.yaml               # real hardware; no secrets, WiFi set at flash time
esphome run esphome/desiccant-dryer-host.yaml          # no board; brew install sdl2 first
```

CI compiles all of these on every pull request. Pushing a `vX.Y.Z` tag
(`scripts/release.sh`) publishes the production build; owners install it
once over USB with web.esphome.io, and the unit then installs later
releases itself from the published manifest, on a 6 h poll, through the
`Firmware` update entity in Home Assistant. See `docs/releasing.md`,
which also records the accepted security trade-offs of that arrangement.

## License

Copyright (C) 2026 jrytio. Released under the GNU Affero General Public
License v3.0; see [`LICENSE`](LICENSE). If you run a modified version where
others interact with it over a network (the web server, `/screen.png`, the
API), the AGPL requires you to offer them your source.

Exceptions: the vendor documents in `docs/datasheets/` belong to their
manufacturers and are not covered. Release firmware also contains ESPHome's
C++ runtime (MIT), ESP-IDF (Apache 2.0) and the Barlow and Inter fonts
(SIL Open Font License 1.1), each under its own license.
