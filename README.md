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
| Virtual | `esphome/desiccant-dryer-virtual.yaml` | On-device plant model (`packages/hw-virtual.yaml`) | ESP32-S2, nothing attached |
| Host | `esphome/desiccant-dryer-host.yaml` | Same plant model | Your Mac, display in an SDL window |
| Screen scenarios | `esphome/desiccant-dryer-scenarios.yaml` | Fixed table of twelve screen states, no controller | Your Mac; `scripts/scenario-shots.sh` renders them to `docs/display/` |

```
cp esphome/secrets.yaml.example esphome/secrets.yaml   # fill in
esphome run esphome/desiccant-dryer-virtual.yaml       # bare board
esphome run esphome/desiccant-dryer.yaml               # real hardware
esphome run esphome/desiccant-dryer-host.yaml          # no board; brew install sdl2 first
```

CI compiles all four on every pull request. Pushing a `vX.Y.Z` tag
(`scripts/release.sh`) publishes the production build so Home Assistant
offers it as an update; see `docs/releasing.md`.
