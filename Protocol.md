Protocol (compat notes)

Transport: Bluetooth Classic SPP → virtual COM → 9600 8N1.

Commands (ASCII + CRLF):

G / g → single distance (distance returned as 31..00±xxxxxxxx where mm → meters = value/1000)
H / h → start tracking (continuous 31.. stream)
P / p → stop / laser off (returns ?)
O → laser on (sometimes ?, sometimes @E203) — experimental
c → clear/stop (returns ?)
T → temperature (returns 40.. word; °C = value/10)
K → signal (returns/streams 53.. word; mV integer)

Push mode (device SEND key): device pushes value → host should confirm with cfm\n (LF).

Error lines look like @E203 (unsupported/invalid state).

We intentionally hide dangerous commands:

a (reset) and b (power-off) are behind confirmations in the GUI.

N70N y N (baud change) is not exposed to avoid bricking comms.

Legal & docs
This repo contains only original code and protocol notes derived from observation and publicly shared info.
Do not add proprietary Leica PDFs here. Summaries of behavior and your own screenshots are fine.

License
MIT — do cool stuff, at your own risk. Contributions welcome.


---
tiny warning:
b powers the device off.
a resets.
N70N y N (baud) is intentionally not exposed.

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

