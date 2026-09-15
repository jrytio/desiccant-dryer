# Component datasheets

Reference copies of the manufacturer documents for the parts in the
[hardware BOM](../hardware.md#bill-of-materials), so the driver-stage numbers
and the protoboard layout can be checked against datasheets without leaving
the repo, and so a later re-check sees the same revision. All files were
retrieved on 2026-09-15 from the source in the table; the SHA-256 prefix is
there to tell whether a file was replaced. Manufacturer datasheets stay
their owners' copyright and are kept here for reference only; SparkFun's
hardware files are CC BY-SA 4.0 (`mcu/SPARKFUN-LICENSE.md`).

Prefer the manufacturer's current document when a number matters: a copy
here may be a revision behind. Where the manufacturer site refused a scripted
download, the table says whose copy this is.

| File | Part / where used | Document | Source | Pages | SHA-256 (first 16) | What to read |
|---|---|---|---|---|---|---|
| [mcu/sparkfun-esp32-s2-thing-plus.brd](mcu/sparkfun-esp32-s2-thing-plus.brd) | SparkFun ESP32-S2 Thing Plus (WRL-17743), the controller board | Eagle board file (CC BY-SA 4.0, see SPARKFUN-LICENSE.md) | [link](https://github.com/sparkfun/ESP32-S2_Thing_Plus/blob/main/Hardware/ESP32-S2_Thing_Plus.brd) |  | `3f91041525fae7df` | Outline (layer 20) is 22.86 × 64.77 mm; header pad positions; connector placement |
| [mcu/sparkfun-esp32-s2-thing-plus.sch](mcu/sparkfun-esp32-s2-thing-plus.sch) | SparkFun ESP32-S2 Thing Plus | Eagle schematic (CC BY-SA 4.0) | [link](https://github.com/sparkfun/ESP32-S2_Thing_Plus/blob/main/Hardware/ESP32-S2_Thing_Plus.sch) |  | `0bbf12487fef34cc` | Nets behind pinout-verification.md: V_USB → D2 → VIN → AP2112 → 3.3V; GPIO13 LED; USB jumper |
| [mcu/sparkfun-esp32-s2-thing-plus-dimensions.pdf](mcu/sparkfun-esp32-s2-thing-plus-dimensions.pdf) | SparkFun ESP32-S2 Thing Plus | Dimensional drawing (inches) | [link](https://github.com/sparkfun/ESP32-S2_Thing_Plus/blob/main/Documents/ESP32-S2_Thing_Plus_DIMENSIONS.pdf) | 1 | `a04efc248ad8fc7d` | Board 2.55 × 0.90 in; header rows start 0.55 in (16-pin) and 0.95 in (12-pin) from the USB end |
| [mcu/sparkfun-esp32-s2-thing-plus-dimensions.png](mcu/sparkfun-esp32-s2-thing-plus-dimensions.png) | SparkFun ESP32-S2 Thing Plus | Same drawing as PNG | [link](https://github.com/sparkfun/ESP32-S2_Thing_Plus/blob/main/Documents/ESP32-S2_Thing_Plus_DIMENSIONS.png) |  | `3d97430a1adcbfc2` |  |
| [mcu/espressif-esp32-s2-wroom-datasheet.pdf](mcu/espressif-esp32-s2-wroom-datasheet.pdf) | ESP32-S2-WROOM module on the Thing Plus | Espressif datasheet v1.1 (2020), SparkFun's copy | [link](https://github.com/sparkfun/ESP32-S2_Thing_Plus/blob/main/Documents/esp32-s2-wroom_esp32-s2-wroom-i_datasheet_en.pdf) | 27 | `f9521959bb886423` | Module pinout, antenna keep-out, current consumption |
| [mcu/espressif-esp32-s2-datasheet.pdf](mcu/espressif-esp32-s2-datasheet.pdf) | ESP32-S2 chip | Espressif datasheet v1.1 (2020), SparkFun's copy | [link](https://github.com/sparkfun/ESP32-S2_Thing_Plus/blob/main/Documents/esp32-s2_datasheet_en.pdf) | 45 | `58cc0a634ddb939a` | Strapping pins, GPIO drive strength, USB pins 19/20 |
| [relay/songle-srd-relay.pdf](relay/songle-srd-relay.pdf) | Songle SRD-05VDC-SL-C heater relays | Songle SRD series datasheet (2-page mirror hosted by circuitbasics.com) | [link](https://www.circuitbasics.com/wp-content/uploads/2015/11/SRD-05VDC-SL-C-Datasheet.pdf) | 2 | `9967e9a62db84c57` | Coil table (5 V: 70 Ω, 71.4 mA for the 0.36 W "L" coil), contact ratings, outline and pin drawing |
| [discretes/onsemi-pn2222a.pdf](discretes/onsemi-pn2222a.pdf) | PN2222A relay driver (the usual "2N2222" in TO-92) | onsemi PN2222/PN2222A, Rev. 1.1.0 | [link](https://web.archive.org/web/2022id_/https://www.onsemi.com/pdf/datasheet/pn2222a-d.pdf) | 8 | `f1eda8482f5f227f` | TO-92 pin order is E-B-C (flat face toward you, legs down); hFE and V<sub>CE(sat)</sub> tables |
| [discretes/onsemi-p2n2222a.pdf](discretes/onsemi-p2n2222a.pdf) | P2N2222A, an alternative TO-92 "2N2222" with the REVERSE pin order | onsemi P2N2222A, Rev. 7 | [link](https://cdn.sparkfun.com/datasheets/Components/General/P2N2222A-D.PDF) | 6 | `e8d9dd9bde7e379f` | Pin 1 is the collector: C-B-E. Check which part you have before fitting |
| [discretes/infineon-irlz44n.pdf](discretes/infineon-irlz44n.pdf) | IRLZ44N valve and fan drivers | Infineon / IR IRLZ44NPbF, PD-94831 | [link](https://www.infineon.com/dgdl/irlz44npbf.pdf?fileId=5546d462533600a40153567217c32129) | 10 | `b4f1361a4486b8ec` | V<sub>GS(th)</sub>, R<sub>DS(on)</sub> at 4 V and 5 V, transfer characteristic (3.3 V drive is not a specified point), TO-220 pin order G-D-S |
| [discretes/vishay-1n4001-1n4007.pdf](discretes/vishay-1n4001-1n4007.pdf) | 1N4007 flyback diodes | Vishay General Semiconductor, Revision 29 | [link](https://www.vishay.com/docs/88503/1n4001.pdf) | 5 | `56a77c6615c90c11` | Ratings; the band marks the cathode, which goes to the supply side |
| [power/meanwell-lrs-35.pdf](power/meanwell-lrs-35.pdf) | Mean Well LRS-35-24 supply | Mean Well LRS-35 spec sheet | [link](https://www.meanwell.com/Upload/PDF/LRS-35/LRS-35-SPEC.PDF) | 4 | `43ceb7255f0613bf` | 24 V / 1.5 A, protections, derating, mounting and safety notes |
| [power/diodes-ap2112.pdf](power/diodes-ap2112.pdf) | AP2112K-3.3 LDO on the Thing Plus (U3) | Diodes Inc. AP2112 | [link](https://www.diodes.com/assets/Datasheets/AP2112.pdf) | 18 | `ef8d376f2ec356e2` | 600 mA, dropout vs current: sets how much drop the USB-pin feed can tolerate |
| [power/diodes-dmg2307l.pdf](power/diodes-dmg2307l.pdf) | DMG2307L battery cut-off P-FET on the Thing Plus (Q1) | Diodes Inc. DMG2307L, Rev. 6 (marked not for new design) | [link](https://www.diodes.com/assets/Datasheets/DMG2307L.pdf) | 7 | `51e506995ea31c15` | Why 5 V must not be fed into the BAT pin |
| [power/microchip-mcp73831.pdf](power/microchip-mcp73831.pdf) | MCP73831 LiPo charger on the Thing Plus (U4) | Microchip DS20001984H | [link](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP73831-Family-Data-Sheet-DS20001984H.pdf) | 29 | `75297f2a52355993` | Behaviour with no battery while V_USB is fed from the buck |
| [sensors/sensirion-sht4x.pdf](sensors/sensirion-sht4x.pdf) | Sensirion SHT45 outlet humidity sensor | Sensirion SHT4x datasheet, Version 6.4 (November 2023) | [link](https://sensirion.com/media/documents/33FD6951/6555C40E/Sensirion_Datasheet_SHT4x.pdf) | 24 | `c615676c5b1ddc7b` | Supply range, I2C address 0x44, accuracy at low RH, heater/self-heating |
| [sensors/analog-ds18b20.pdf](sensors/analog-ds18b20.pdf) | DS18B20 pack and case temperature probes | Maxim / Analog Devices DS18B20 (REV 042208), Adafruit's copy; analog.com refuses scripted downloads | [link](https://cdn-shop.adafruit.com/datasheets/DS18B20.pdf) | 22 | `39d191cd1fb657e4` | 3.0–5.5 V supply, 4.7 kΩ pull-up, −55 to +125 °C, ±0.5 °C from −10 to +85 °C |
| [sensors/sitronix-st7789v.pdf](sensors/sitronix-st7789v.pdf) | ST7789V controller in the 1.54" 240×240 display | Sitronix ST7789V, Version 1.3 (hosted by Newhaven Display) | [link](https://www.newhavendisplay.com/appnotes/datasheets/LCDs/ST7789V.pdf) | 316 | `8ecf0e438aa25554` | Logic supply range, 4-line SPI timing, reset timing |
| [sensors/lcdwiki-msp1541-user-manual.pdf](sensors/lcdwiki-msp1541-user-manual.pdf) | A typical 1.54" 8-pin ST7789 module (LCDWIKI MSP1541) | LCDWIKI MSP1541 user manual Rev1.0 | [link](http://www.lcdwiki.com/res/MSP1541/1.54inch_4-line-SPI_IPS_Module_MSP1541_User_Manual_EN.pdf) | 18 | `f942da1ba5fbb2ce` | Pin order GND VCC SCL SDA RES DC CS BLK and what BLK drives; confirm against the module actually bought |

## Still to add

These could not be downloaded by script (the vendor sites serve a page or
block automated clients). Drop the PDF into the directory named and add a
row above.

- `power/mps-mp1584.pdf`: MPS MP1584 / MP1584EN buck converter, the IC on
  the "MP1584 mini" 24 V → 5 V module. monolithicpower.com serves its
  datasheets through a viewer.
- `power/st-bat20j.pdf`: ST BAT20J Schottky, the Thing Plus's D2 between the
  USB pin and the 3.3 V regulator; needed for the drop budget when the buck
  feeds the USB pin. st.com blocks scripted downloads.
- `valves/smc-vdw.pdf`: SMC VDW series catalogue for the VDW22 valves (coil
  power, part-number decode, surge-suppressor option).
- `relay/`: Songle's current revision (V1, 3 pages, 13 MB, CorelDRAW print
  with a broken text layer) is at
  <https://www.songlerelay.com/upload/8670/srd-t73-relay-290486.pdf>. Left
  out for its size; the 2-page mirror above is the earlier revision with the
  same coil table and hole pattern (COM at the coil end, 2.0 mm outboard;
  rows 12.0 mm and columns 12.2 mm apart; holes 1.3 mm).
- A datasheet for the 24 V case fan once a part is chosen.
