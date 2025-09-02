# Leica-DISTO-SPP-Bluetooth-2.1
Leica DISTO™ D3a BT / D330i / D8 back from the dead!

# Leica DISTO D8 — SPP (Bluetooth 2.1) Toolkit

**Windows-friendly tools to talk to legacy Leica DISTO models (D8 / D3a BT) over Bluetooth Classic SPP (virtual COM).**  
Confirmed working with DISTO D8 on COMx @ 9600 8N1.

## What’s inside

- `disto_d8_gui_R3.py` — GUI: **Measure (G)**, **Tracking (H)**, **Stop (P)**, **Laser ON (O, experimental)**, **Clear (c)**, **Temperature (T)**, **Signal (K)**, **AVG ×N**, **Auto-copy**, optional **CSV**, and **push-mode confirm (cfm)**.
- `disto_alpha_sweep.py` — Alphabet brute tester. Tries A–Z/a–z with CRLF/CR, logs to CSV.
- `disto_cmd_scout.py` — Focused command matrix test (retry, pacing, logging).
- `disto_d8_ack_probe.py` — Quick check for `cfm\n` vs `ACK 0x06` vs both.
- `disto_raw_console.py` — Interactive console: sends ASCII (adds LF) or raw bytes via `hex:...`.
- `disto_send_cmd.py` — One-shot sender (e.g., `python disto_send_cmd.py COM7 g` sends `g<CR>`).

## Install

```bash
python -m pip install --upgrade pyserial
python disto_d8_gui_R3.py
