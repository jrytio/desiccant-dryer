# hardware/dryer_board/pinmap.py
"""Header position -> function, the wiring the main board commits to. The GPIO behind a
position differs per Thing Plus and lives in esphome/packages/board-*.yaml; tests/test_pinmap.py
holds both against each other. Source: docs/pinout-verification.md."""

# function: (header pin count, position counted from the USB end)
FUNCTIONS = {
    "usb_5v":    (12, 3),
    "heater_a":  (12, 4),
    "heater_b":  (12, 5),
    "valve_a":   (12, 6),
    "valve_b":   (12, 7),
    "fan":       (12, 8),
    "i2c_scl":   (12, 11),   # Qwiic; not wired on the main board
    "i2c_sda":   (12, 12),   # Qwiic; not wired on the main board
    "3v3":       (16, 2),
    "gnd":       (16, 4),
    "lcd_bl":    (16, 5),
    "lcd_rst":   (16, 8),
    "lcd_dc":    (16, 9),
    "lcd_cs":    (16, 10),
    "spi_clk":   (16, 11),
    "spi_mosi":  (16, 12),
    "onewire":   (16, 13),
}

# Positions that must stay unconnected because a board gives them a job.
RESERVED = {(12, 9): "C6 RGB LED data", (12, 10): "C6 boot strap GPIO15",
            (16, 15): "C6 UART0 TX", (16, 16): "C6 BOOT strap GPIO9",
            (16, 1): "ESP reset", (12, 2): "LDO enable", (12, 1): "battery"}

# position -> GPIO, per board, from docs/pinout-verification.md
POSITION_GPIO = {
    "s2": {(16, 5): 17, (16, 8): 9, (16, 9): 7, (16, 10): 5, (16, 11): 36, (16, 12): 35, (16, 13): 37,
           (12, 4): 13, (12, 5): 12, (12, 6): 11, (12, 7): 10, (12, 8): 8, (12, 11): 2, (12, 12): 1},
    "c6": {(16, 5): 0, (16, 8): 3, (16, 9): 4, (16, 10): 5, (16, 11): 19, (16, 12): 20, (16, 13): 21,
           (12, 4): 18, (12, 5): 22, (12, 6): 11, (12, 7): 10, (12, 8): 8, (12, 11): 7, (12, 12): 6},
}

# firmware substitution name -> function
SUBSTITUTIONS = {"pin_heater_a": "heater_a", "pin_heater_b": "heater_b", "pin_valve_a": "valve_a",
                 "pin_valve_b": "valve_b", "pin_fan": "fan", "pin_i2c_sda": "i2c_sda", "pin_i2c_scl": "i2c_scl",
                 "pin_onewire": "onewire", "pin_spi_clk": "spi_clk", "pin_spi_mosi": "spi_mosi",
                 "pin_lcd_cs": "lcd_cs", "pin_lcd_dc": "lcd_dc", "pin_lcd_rst": "lcd_rst", "pin_lcd_bl": "lcd_bl"}
