# disto_send_cmd.py
# Usage: python disto_send_cmd.py COM7 "g"    # sends 'g<cr>'
# just to test different commans
#        python disto_send_cmd.py COM7 "N999N"
#        python disto_send_cmd.py COM7 g
import sys, time, serial

if len(sys.argv) < 3:
    print("Usage: python disto_send_cmd.py COM7 \"g\"")
    sys.exit(1)

PORT, CMD = sys.argv[1], sys.argv[2]
BAUD = 9600

def send_and_read(cmd, crlf=False):
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        print(f"Opened {PORT} @ {BAUD}. Sending: {cmd}\\r")
        payload = (cmd + ("\r\n" if crlf else "\r")).encode("ascii")
        ser.write(payload); ser.flush()
        time.sleep(0.05)
        # Read whatever arrives for ~1s
        t0 = time.time(); buf = bytearray()
        while time.time() - t0 < 1.0:
            chunk = ser.read(1024)
            if chunk: buf.extend(chunk)
            else: time.sleep(0.02)
        if buf:
            try:
                print("RX TEXT:", buf.decode(errors="ignore").replace("\r","\\r").replace("\n","\\n"))
            except:
                pass
            print("RX HEX :", buf.hex())
        else:
            print("No reply.")

# Try with CR first; if empty, try CRLF
send_and_read(CMD, crlf=False)
