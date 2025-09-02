# Use like this
# python disto_alpha_sweep.py COM7
# or tweak knobs:
# python disto_alpha_sweep.py COM7 --read-window 1.5 --repeats 2 --only "gGhHoOpP" --csv sweep_D8.csv

import sys, time, csv, argparse, binascii, re
from datetime import datetime

try:
    import serial
except Exception as e:
    print("pyserial missing. Install: python -m pip install --upgrade pyserial")
    sys.exit(1)

DIST_RE = re.compile(r"^(?P<cmd>\d{2})\.\.(?P<unit>\d{2})(?P<sign>[+-])(?P<val>\d{5,10})$")

def hx(b: bytes) -> str:
    return binascii.hexlify(b).decode()

def classify_and_parse(text: str):
    """
    Returns (classification, meters_or_None, tokens_found)
    classification in {'distance','ok','error','status','none'}
    """
    t = text.strip()
    if not t:
        return ("none", None, [])
    if t == "?":
        return ("ok", None, [])
    if t.startswith("@E"):
        return ("error", None, [t])

    meters = None
    tokens = []
    # split whitespace; check each token against 31.. pattern
    for tok in t.split():
        m = DIST_RE.fullmatch(tok)
        if m:
            sign = -1 if m["sign"] == "-" else 1
            raw = int(m["val"])
            # assume unit 00 = mm
            mm = sign * raw
            meters = (mm / 1000.0)
            tokens.append(tok)
        else:
            tokens.append(tok)
    if any(DIST_RE.fullmatch(tok) for tok in tokens):
        return ("distance", meters, tokens)
    # not distance; treat as generic status (e.g., 51.., others)
    return ("status", None, tokens)

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

def send(ser, cmd, ending):
    payload = (cmd + ending).encode("ascii")
    ser.write(payload); ser.flush()
    return payload

def try_stop_tracking(ser):
    """Attempt to stop after a suspected streaming start."""
    try:
        ser.write(b"P\r\n"); ser.flush()
        time.sleep(0.05)
        resp = read_for(ser, 0.6)
        return resp
    except Exception:
        return b""

def looks_streamy(text: str, rx_bytes: bytes):
    # heuristic: long response or multiple distance tokens or newline bursts
    if len(rx_bytes) >= 80:
        return True
    tokens = text.split()
    dist_count = sum(1 for tok in tokens if DIST_RE.fullmatch(tok))
    if dist_count >= 2:
        return True
    if text.count("\\n") >= 2:
        return True
    return False

def main():
    ap = argparse.ArgumentParser(description="Leica DISTO D8 alphabet sweep (ONLINE commands)")
    ap.add_argument("port", help="COM port (e.g., COM7)")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--only", default="", help="Only these commands (e.g., 'gGhHoOpP')")
    ap.add_argument("--exclude", default="", help="Exclude these commands")
    ap.add_argument("--repeats", type=int, default=1, help="Repeats per variant")
    ap.add_argument("--read-window", type=float, default=1.2, help="Seconds to read after each send")
    ap.add_argument("--pause", type=float, default=0.25, help="Pause between sends (s)")
    ap.add_argument("--csv", default="disto_alpha_sweep.csv", help="CSV output path")
    ap.add_argument("--endings", default="CRLF,CR", help="Comma list of endings to try: CRLF,CR")
    args = ap.parse_args()

    # candidate set
    all_cmds = [chr(c) for c in range(ord('A'),ord('Z')+1)] + [chr(c) for c in range(ord('a'),ord('z')+1)]
    cmds = all_cmds
    if args.only:
        cmds = list(args.only)
    if args.exclude:
        excl = set(list(args.exclude))
        cmds = [c for c in cmds if c not in excl]

    endings = []
    for e in [x.strip().upper() for x in args.endings.split(",") if x.strip()]:
        if e == "CRLF":
            endings.append("\r\n")
        elif e == "CR":
            endings.append("\r")
        else:
            print(f"Unknown ending: {e}")

    print(f"Port={args.port} @{args.baud} | cmds={''.join(cmds)} | endings={[ 'CRLF' if x=='\r\n' else 'CR' for x in endings ]}")
    print(f"Repeats={args.repeats} read_window={args.read_window}s pause={args.pause}s")
    print(f"Logging CSV → {args.csv}")

    with serial.Serial(args.port, args.baud, timeout=0.05) as ser, open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "timestamp","cmd","ending","repeat","tx_hex","rx_hex","rx_txt","class","meters","tokens","stream_stop_hex","stream_stop_txt"
        ])
        w.writeheader()

        for cmd in cmds:
            for ending in endings:
                for r in range(args.repeats):
                    # flush input
                    try:
                        _ = ser.read(ser.in_waiting or 1)
                    except Exception:
                        pass

                    ts = datetime.now().isoformat(timespec="seconds")
                    tx = send(ser, cmd, ending)
                    time.sleep(0.05)
                    rx = read_for(ser, args.read_window)
                    rx_txt = rx.decode(errors="ignore").replace("\r","\\r").replace("\n","\\n")
                    cls, meters, tokens = classify_and_parse(rx.decode(errors="ignore"))

                    stop_hex = stop_txt = ""
                    # if it looks like tracking started, try to stop politely with P
                    if looks_streamy(rx_txt, rx):
                        srx = try_stop_tracking(ser)
                        if srx:
                            stop_hex = hx(srx)
                            stop_txt = srx.decode(errors="ignore").replace("\r","\\r").replace("\n","\\n")

                    row = {
                        "timestamp": ts,
                        "cmd": cmd,
                        "ending": "CRLF" if ending == "\r\n" else "CR",
                        "repeat": r+1,
                        "tx_hex": hx(tx),
                        "rx_hex": hx(rx),
                        "rx_txt": rx_txt,
                        "class": cls,
                        "meters": f"{meters:.3f}" if meters is not None else "",
                        "tokens": " ".join(tokens),
                        "stream_stop_hex": stop_hex,
                        "stream_stop_txt": stop_txt,
                    }
                    w.writerow(row); f.flush()

                    # console echo for quick eyeballing
                    print(f"\n[{ts}] CMD {cmd!r} {row['ending']} rep {r+1}")
                    print("TX:", row["tx_hex"])
                    print("RX:", row["rx_txt"] or "<no response>")
                    if row["class"] == "distance":
                        print(f"→ DIST: {row['meters']} m")
                    elif row["class"] == "ok":
                        print("→ OK (?)")
                    elif row["class"] == "error":
                        print("→ ERROR")

                    time.sleep(args.pause)

    print("\nDone. Check CSV for the full matrix.")
    print("Tip: focus on cmds that return 'distance' or 'ok'; ignore '@E203' spam.")
if __name__ == "__main__":
    main()
