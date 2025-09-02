# Leica-DISTO-SPP-Bluetooth-2.1
Leica DISTO™ D3a BT / D330i / D8 back from the dead!

# Leica DISTO D8
<img width="1037" height="708" alt="GUI" src="https://github.com/user-attachments/assets/649761e4-90bd-4678-b6ec-fc553eda6419" />
 — SPP (Bluetooth 2.1) Toolkit

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




---

# PROTOCOL.md (concise summary you can include)

```markdown
# Leica DISTO D8 SPP — observed protocol

**Transport:** Bluetooth Classic SPP → COMx @ 9600 8N1

## Host → Device (ASCII + CRLF)

| Cmd | Meaning | Reply / Behavior |
| --- | --- | --- |
| `G` / `g` | Single distance | Returns `31..00±xxxxxxxx` (mm). |
| `H` / `h` | Start tracking | Streams `31..` (and sometimes `51..`) until stopped. |
| `P` / `p` | Stop / Laser OFF | Returns `?` (OK). |
| `O` | Laser ON | Often `?`, sometimes `@E203` (state-dependent). |
| `c` | Clear/stop (soft) | Returns `?`. |
| `T` | Temperature | Returns `40..±xxxxxxxx` (0.1 °C). |
| `K` | Signal strength | Returns/streams `53..±xxxxxxxx` (mV). |
| `a` | Reset (Danger) | Returns `?`, unit resets. |
| `b` | Power OFF (Danger) | Returns `?`, device powers down. |

> Commands not listed above usually return `@E203` on our D8 test unit.

## Device → Host (lines, space-separated tokens)

### Word index tokens
Format: `WW..UU±VVVVVVVV` (ASCII; lengths vary; leading zeros used)

- `31..` → **distance**; `UU=00` → mm. Convert: meters = `VVVVVVVV / 1000`.
- `40..` → **temperature**; value/10 = °C.
- `53..` → **signal strength**; value = mV.
- `51..` → compatibility/status filler — safe to log/ignore.

### Push mode confirm
When you press **SEND** on the device, it pushes a value; the host should reply:
- `cfm\n` (**LF**, not CRLF!) to acknowledge and avoid Info 240.

## Notes
- CRLF (`\r\n`) was the most reliable line ending for ONLINE commands on our unit.
- Some commands behave differently across firmware; test on your device.
