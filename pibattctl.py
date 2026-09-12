#!/usr/bin/env python3
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pibatt_hw import UPSHatE

STATUS=Path('/run/pi-batt/status.json')

def main():
    cmd=sys.argv[1] if len(sys.argv)>1 else 'status'
    if cmd=='status':
        if not STATUS.exists():
            print('Pi-Batt daemon has not published status yet.'); return 1
        d=json.load(STATUS.open())
        if not d.get('connected'):
            print('UPS disconnected:',d.get('error','unknown error')); return 2
        print(f"{d['battery_percent']}% | {d['mode']} | Battery {d['battery_voltage_mv']/1000:.3f}V {d['battery_current_ma']/1000:+.3f}A | Input {d['vbus_power_mw']/1000:.2f}W | ETA {d.get('eta_text') or '—'}")
        print('Cells:', ' '.join(f"{x/1000:.3f}V" for x in d['cells_mv']), f"delta {d['cell_delta_mv']}mV")
        return 0
    if cmd=='probe':
        hw=UPSHatE()
        try: print(json.dumps(hw.read_all(),indent=2))
        finally: hw.close()
        return 0
    print('Usage: pi-battctl [status|probe]'); return 2
if __name__=='__main__': raise SystemExit(main())
