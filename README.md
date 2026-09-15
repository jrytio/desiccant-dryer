# desiccant-dryer

ESPHome firmware for an ESP32-S2 replacement of the Azco VMD-08 desiccant
air dryer control board. Swaps packs on measured humidity and pack
temperature instead of a fixed timer. See `CLAUDE.md` for decisions,
`docs/hardware.md` for wiring and BOM, `docs/control-logic.md` for the
state machine, `docs/virtual-testing.md` for testing without hardware,
`docs/host-preview.md` for the display on your Mac.

Three builds share `esphome/packages/base.yaml`:

| Build | File | Sensors | Runs on |
|---|---|---|---|
| Production | `esphome/desiccant-dryer.yaml` | SHT45 + 3× DS18B20 (`packages/hw-real.yaml`) | ESP32-S2 |
| Virtual | `esphome/desiccant-dryer-virtual.yaml` | On-device plant model (`packages/hw-virtual.yaml`) | ESP32-S2, nothing attached |
| Host | `esphome/desiccant-dryer-host.yaml` | Same plant model | Your Mac, display in an SDL window |

```
cp esphome/secrets.yaml.example esphome/secrets.yaml   # fill in
esphome run esphome/desiccant-dryer-virtual.yaml       # bare board
esphome run esphome/desiccant-dryer.yaml               # real hardware
esphome run esphome/desiccant-dryer-host.yaml          # no board; brew install sdl2 first
```

CI compiles all three on every pull request.
