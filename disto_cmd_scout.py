# This script:
# Tries a set of likely commands (A/g/h/o/p etc.),
# Tests both endings (CR and CRLF),
# Retries each command a couple of times with pacing,
# Logs hex + text so we can see WI31… vs @E203 vs nothing,
# Lets you enter online at the start (optional).
# Save as disto_cmd_scout.py and run:
# python disto_cmd_scout.py COM7

import sys, time, serial, binascii

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM7"
BAUD = 9600

# Candidate commands (based on the old ONLINE manual + common variants)
CANDIDATES = [
    "A",        # enter online (some firmwares)
    "g", "G",   # single measure
    "h", "H",   # start tracking (continuous)
    "o", "O",   # laser ON
    "p", "P",   # laser OFF
    "q", "Q",   # stop tracking (guess)
    "V",        # version (guess)
    "t", "T",   # Temperature
    "c", "C",   # Stop/Clear
    "k", "K",   # Signal Strength 
    "N999N",    # help (may not exist on D8)
    "N00N",     # Software version
    "N01N",     # Hardware version
    "N03N",     # Serial number
    "N03N",     # Date of manufacture
]

# Endings to try per command
ENDINGS = ["\r\n", "\r"]   # CRLF first, then CR

REPEATS = 2        # send each variant twice
READ_WINDOW = 1.2  # seconds to read after send
PAUSE_BETWEEN = 0.25  # seconds between repeats

def hx(b): return binascii.hexlify(b).decode()

def read_for(ser, seconds):
    t0 = time.time()
    buf = bytearray()
    while time.time() - t0 < seconds:
        chunk = ser.read(1024)
        if chunk:
            buf.extend(chunk)
        else:
            time.sleep(0.02)
    return bytes(buf)

def flush_input(ser):
    try:
        _ = ser.read(ser.in_waiting or 1)
    except Exception:
        pass

def send_and_log(ser, cmd, ending):
    payload = (cmd + ending).encode("ascii")
    print(f"\n--- CMD: {repr(cmd)} END:{repr(ending)} ---")
    print("TX HEX:", hx(payload))
    ser.write(payload); ser.flush()
    time.sleep(0.05)
    data = read_for(ser, READ_WINDOW)
    if data:
        txt = data.decode(errors="ignore").replace("\r","\\r").replace("\n","\\n")
        print("RX HEX:", hx(data))
        print("RX TXT:", txt)
    else:
        print("RX: <no response>")

def main():
    with serial.Serial(PORT, BAUD, timeout=0.05) as ser:
        print(f"Opened {PORT} @ {BAUD}")
        # Optional: try to enter online first; uncomment if helpful
        # for ending in ENDINGS:
        #     flush_input(ser); send_and_log(ser, "A", ending); time.sleep(0.5)

        for cmd in CANDIDATES:
            for ending in ENDINGS:
                for i in range(REPEATS):
                    flush_input(ser)
                    send_and_log(ser, cmd, ending)
                    time.sleep(PAUSE_BETWEEN)

if __name__ == "__main__":
    main()
