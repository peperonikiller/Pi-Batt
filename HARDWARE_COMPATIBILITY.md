# Pi-Batt hardware compatibility

Pi-Batt 1.0.2 is currently designed around the **Waveshare UPS HAT (E)** register protocol.

## Fully supported

| Manufacturer | Model | Status | Notes |
|---|---|---|---|
| Waveshare | UPS HAT (E), SKU 27966 | **Supported / tested** | I2C MCU at `0x2D`, ID `0x0A`, four cell-voltage registers, BQ4050 fuel gauge status, IP2368 Type-C/charging status, native charge/discharge ETA, auto-start control and delayed power-cut command. |

Pi-Batt will also normally work with a reseller/rebranded board **only if it is electrically and firmware-identical to the Waveshare UPS HAT (E)** and exposes the same MCU register map. Those rebrands are not individually tested or guaranteed.

## Not currently supported

| Manufacturer | Model | Status | Why |
|---|---|---|---|
| Waveshare | UPS HAT (D) | **Not supported** | Battery telemetry is provided through an INA219 at `0x43`; although it also has an MCU at `0x2D`, its telemetry and power-control behavior are different from UPS HAT (E). |
| Waveshare | UPS HAT (B) | **Not supported** | Uses an INA219-based telemetry implementation rather than the UPS HAT (E) MCU register map. |
| Waveshare | UPS HAT (C) | **Not supported** | Uses INA219 telemetry and a single-cell Li-Po design; register layout and battery model differ from UPS HAT (E). |
| Waveshare | UPS HAT (original) | **Not supported** | Uses INA219 telemetry (documented at `0x42`) instead of the UPS HAT (E) protocol. |
| Waveshare | UPS Module 3S | **Not supported** | Uses INA219 telemetry and a different battery/power architecture. |
| SBCShop | UPS HAT for Raspberry Pi | **Not supported** | INA219-based monitoring; different protocol and hardware design. |
| Other UPS HATs / battery boards | Various | **Not supported unless an explicit Pi-Batt backend is added** | Pi-Batt does not currently auto-detect arbitrary INA219/MAX1704x/INA226 or vendor-specific UPS protocols. |

## How Pi-Batt identifies the supported hardware

The current backend expects the Waveshare UPS HAT (E) MCU protocol:

- I2C bus: `1`
- Default MCU address: `0x2D`
- ID register `0x00`: expected value `0x0A`
- Status/charger registers at `0x02` and `0x03`
- Type-C telemetry at `0x10`–`0x15`
- Battery telemetry at `0x20`–`0x2B`
- Four cell-voltage channels at `0x30`–`0x37`
- Control register at `0x40`
- Firmware revision at `0x50`

A board sharing only the `0x2D` address is **not enough** to be compatible; it must implement this register map and semantics.

## Planned compatibility architecture

Future Pi-Batt releases can add separate hardware backends for other UPS families without changing the GUI or history database. Good candidates are Waveshare UPS HAT (B)/(C)/(D), the original Waveshare UPS HAT, and generic INA219-based boards.
