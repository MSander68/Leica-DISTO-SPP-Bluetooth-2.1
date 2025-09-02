# disto_raw_console.py
# Usage: python disto_raw_console.py COM7 9600
# Try raw commands yourself (safe, zero-risk)
# Quick console tool: it shows incoming bytes and lets you type something to send (it auto-adds \n unless you prefix hex:). 
# Great for testing cfm, then poking “laser on/off” guesses without touching the GUI.

import sys, time, threading, serial, binascii

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM7"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 9600

def reader(ser):
    buf = bytearray()
    while True:
        try:
            chunk = ser.read(1024)
        except Exception as e:
            print("READ ERR:", e); break
        if not chunk:
            time.sleep(0.02); continue
        print("RX HEX:", binascii.hexlify(chunk).decode())
        try:
            txt = chunk.decode(errors="ignore")
            print("RX TXT:", txt.replace("\r","\\r").replace("\n","\\n"))
        except: pass

with serial.Serial(PORT, BAUD, timeout=0.1) as ser:
    print(f"Opened {PORT} @ {BAUD}. Type to send. Examples: cfm  |  hex:060a")
    t = threading.Thread(target=reader, args=(ser,), daemon=True); t.start()
    try:
        while True:
            s = input("> ").strip()
            if not s: continue
            if s.startswith("hex:"):
                #data = binascii.unhexlify(s[4:])
                data = bytes.fromhex(s[4:])
            else:
                # send ASCII + LF
                # data = (s + "\n").encode()
                data = (s + "\r\n").encode()
            ser.write(data); ser.flush()
            print("TX:", data)
    except KeyboardInterrupt:
        pass
