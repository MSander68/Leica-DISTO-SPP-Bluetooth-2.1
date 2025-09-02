# disto_d8_ack_probe.py
# Quick tester: try different confirms (cfm\n, ACK 0x06, both)
# Run this on COM7 while you press the D8’s send key. 
# It prints tokens and immediately sends the chosen confirm. You can switch mode at the top.


import sys, time, re
from datetime import datetime

MODE = "cfm"   # "cfm", "ack06", or "both"
PORT = "COM7"
BAUD = 9600

import serial

TOKEN_RE = re.compile(r"^(?P<cmd>\d{2})\.\.(?P<unit>\d{2})(?P<sign>[+-])(?P<val>\d{5,10})$")

def confirm(ser: serial.Serial):
    if MODE in ("cfm", "both"):
        ser.write(b"cfm\n")
        ser.flush()
        print("TX: cfm\\n")
    if MODE in ("ack06", "both"):
        ser.write(b"\x06")
        ser.flush()
        print("TX: ACK (0x06)")

with serial.Serial(PORT, BAUD, timeout=2) as ser:
    print(f"Opened {PORT} @ {BAUD}. Mode={MODE}. Press SEND on D8.")
    buf = bytearray()
    while True:
        chunk = ser.read(256)
        if not chunk:
            time.sleep(0.02); continue
        buf.extend(chunk)
        # lines may contain multiple tokens
        while b"\r" in buf or b"\n" in buf:
            for eol in (b"\r\n", b"\n", b"\r"):
                if eol in buf:
                    line, _, rest = buf.partition(eol)
                    buf = bytearray(rest)
                    break
            text = line.decode(errors="ignore").strip()
            if not text: continue
            if text.startswith("@"):
                print("STATUS:", text); continue
            for tok in text.split():
                m = TOKEN_RE.fullmatch(tok)
                if m:
                    sign = -1 if m["sign"] == "-" else 1
                    mm = sign * int(m["val"])
                    print(f"{datetime.now().isoformat(timespec='seconds')}  {mm/1000:.3f} m  ({mm} mm)  [{tok}]")
                    confirm(ser)
                else:
                    print("UNPARSED:", tok)
