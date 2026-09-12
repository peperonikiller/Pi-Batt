#!/usr/bin/env python3
import smbus
import time

I2C_BUS = 1
I2C_ADDR = 0x2D

CHARGE_STATES = {
    0: "Standby",
    1: "Trickle charge",
    2: "Constant current charge",
    3: "Constant voltage charge",
    4: "Charging waiting",
    5: "Full charge",
    6: "Charge timeout",
}

class UPSHatE:
    def __init__(self, bus=I2C_BUS, address=I2C_ADDR):
        self.bus_no = bus
        self.address = address
        self.bus = smbus.SMBus(bus)

    def close(self):
        try:
            self.bus.close()
        except Exception:
            pass

    def _u8(self, reg):
        return self.bus.read_byte_data(self.address, reg)

    def _u16(self, reg_lo):
        lo = self._u8(reg_lo)
        hi = self._u8(reg_lo + 1)
        return (hi << 8) | lo

    def _s16(self, reg_lo):
        value = self._u16(reg_lo)
        return value - 65536 if value & 0x8000 else value

    @staticmethod
    def _valid_time(value):
        return None if value in (0xFFFF, 0xFFFE) else value

    def read_all(self):
        ident = self._u8(0x00)
        trigger_reg = self._u8(0x01)
        status = self._u8(0x02)
        comm = self._u8(0x03)
        control = self._u8(0x40)
        version_raw = self._u8(0x50)

        charge_state_code = status & 0x07
        cells = [self._u16(0x30 + i * 2) for i in range(4)]

        data = {
            "id": ident,
            "trigger_register": trigger_reg,
            "status_register": status,
            "communication_register": comm,
            "charging": bool(status & 0x80),
            "fast_charging": bool(status & 0x40),
            "vbus_powered": bool(status & 0x20),
            "charge_state_code": charge_state_code,
            "charge_state": CHARGE_STATES.get(charge_state_code, f"Unknown ({charge_state_code})"),
            "bq4050_ok": bool(comm & 0x02),
            "ip2368_ok": bool(comm & 0x01),
            "vbus_voltage_mv": self._u16(0x10),
            "vbus_current_ma": self._s16(0x12),
            "vbus_power_mw": self._u16(0x14),
            "battery_voltage_mv": self._u16(0x20),
            "battery_current_ma": self._s16(0x22),
            "battery_percent": min(100, self._u16(0x24)),
            "remaining_capacity_mah": self._u16(0x26),
            "remaining_discharge_min": self._valid_time(self._u16(0x28)),
            "remaining_charge_min": self._valid_time(self._u16(0x2A)),
            "cells_mv": cells,
            "cell_delta_mv": max(cells) - min(cells),
            "control_register": control,
            "watchdog_enabled": bool(control & 0x02),
            "auto_start_on_power": bool(control & 0x01),
            "software_version_raw": version_raw,
            "software_version": f"{version_raw / 10.0:.1f}",
        }
        data["communications_ok"] = data["bq4050_ok"] and data["ip2368_ok"]
        return data

    def trigger_power_cut(self):
        # Waveshare documents 0x55 -> 0x01 as a one-time delayed power cut.
        self.bus.write_byte_data(self.address, 0x01, 0x55)

    def set_auto_start_on_power(self, enabled: bool):
        value = self._u8(0x40)
        value = (value | 0x01) if enabled else (value & ~0x01)
        self.bus.write_byte_data(self.address, 0x40, value)
        time.sleep(0.05)
        return bool(self._u8(0x40) & 0x01)
