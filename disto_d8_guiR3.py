# disto_d8_gui_R3.py
# Leica DISTO D8 Remote GUI (SPP / RFCOMM)
# R3 adds: Signal (K), Temperature (T), Clear (c), Device Info (N00N..N03N),
# AVG ×N (spinner), Danger Zone (Reset/Power-off) with confirmation,
# CRLF command framing + push-mode confirm (cfm\n) with suppression.
# Build Instruction
# pyinstaller --noconsole --onefile disto_d8_gui_R3.py


import threading, queue, time, re, csv, os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

try:
    import serial
    import serial.tools.list_ports as list_ports
except Exception:
    raise SystemExit("pyserial missing. Install: python -m pip install --upgrade pyserial")

# -------- Parsing --------
DIST_RE = re.compile(r"^(?P<cmd>\d{2})\.\.(?P<unit>\d{2})(?P<sign>[+-])(?P<val>\d{5,10})$")
# Word index rough map (compatibility stream)
# 31.. : distance (mm) — we parse to meters
# 40.. : temperature (0.1°C)
# 53.. : signal strength (mV)
def parse_word(tok: str):
    m = DIST_RE.fullmatch(tok)
    if not m:
        return None
    gd = m.groupdict()
    wi = int(gd["cmd"])   # word index high
    sign = -1 if gd["sign"] == "-" else 1
    raw = int(gd["val"])
    unit_code = gd["unit"]

    kind = "unknown"
    value = None
    display = None

    if wi == 31:  # distance, assume unit_code 00 = mm
        mm = sign * raw
        meters = mm / 1000.0
        kind = "distance"
        value = meters
        display = f"{meters:.3f} m"
    elif wi == 40:  # temperature 0.1°C
        t = sign * raw / 10.0
        kind = "temperature"
        value = t
        display = f"{t:.1f} °C"
    elif wi == 53:  # signal mV
        mv = sign * raw
        kind = "signal"
        value = mv
        display = f"{mv} mV"
    else:
        kind = f"wi{wi}"
        value = raw
        display = f"{tok}"

    return {
        "word_index": wi,
        "unit_code": unit_code,
        "sign": gd["sign"],
        "raw": raw,
        "kind": kind,
        "value": value,
        "display": display,
        "token": tok,
    }

# -------- Serial worker --------
class SerialWorker(threading.Thread):
    def __init__(self, port, baud, out_q, status_cb,
                 confirm_push=True, idle_seconds=10):
        super().__init__(daemon=True)
        self.port = port
        self.baud = baud
        self.out_q = out_q
        self.status_cb = status_cb
        self.confirm_push = confirm_push
        self.idle_seconds = idle_seconds

        self.stop_flag = threading.Event()
        self.ser = None
        self.buf = bytearray()
        self.last_rx = time.time()
        self.last_cmd_time = 0.0
        self.cmd_q = queue.Queue()

        # States
        self.tracking = False
        self.avg_capture = False
        self.avg_target = 10
        self.avg_vals = []

    # --- emit/log ---
    def emit(self, item): self.out_q.put(item)
    def log(self, msg):   self.emit({"type":"debug","text":msg})

    # --- writing ---
    def _write(self, data: bytes):
        if not self.ser or not self.ser.is_open:
            self.log("Write failed: port not open")
            return
        try:
            self.ser.write(data); self.ser.flush()
        except Exception as e:
            self.log(f"Write error: {e}")

    def send_cmd(self, cmd_char: str):
        """Queue an ONLINE command (ASCII + CRLF)."""
        self.cmd_q.put(("cmd", cmd_char))

    def set_confirm_push(self, enabled: bool):
        self.confirm_push = enabled

    def start_avg(self, n: int):
        self.avg_target = n
        self.avg_vals = []
        self.avg_capture = True
        # ensure tracking ON
        if not self.tracking:
            self.send_cmd("H")
        self.emit({"type":"avg_state","active":True,"count":0,"target":self.avg_target})

    def stop_avg(self):
        self.avg_capture = False
        self.emit({"type":"avg_state","active":False,"count":len(self.avg_vals),"target":self.avg_target})

    def stop_tracking(self):
        self.send_cmd("P")

    # --- thread loop ---
    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.05)
            self.status_cb("connected")
            self.log(f"Opened {self.port} @ {self.baud}. Ready.")
        except Exception as e:
            self.status_cb("disconnected")
            self.log(f"ERROR opening {self.port}: {e}")
            return

        try:
            while not self.stop_flag.is_set():
                # outgoing commands
                try:
                    kind, payload = self.cmd_q.get_nowait()
                except queue.Empty:
                    kind = None
                if kind == "cmd":
                    ch = payload
                    data = (ch + "\r\n").encode("ascii")
                    self._write(data)
                    self.last_cmd_time = time.time()
                    self.emit({"type":"debug","text":f"TX CMD: {repr(ch)} (CRLF)"})
                    if ch in ("H","h"):
                        self.tracking = True
                        self.emit({"type":"tracking","active":True})
                    elif ch in ("P","p","c","C"):
                        self.tracking = False
                        self.emit({"type":"tracking","active":False})

                # idle
                if time.time() - self.last_rx > self.idle_seconds:
                    self.status_cb("idle")

                # read
                try:
                    chunk = self.ser.read(256)
                except Exception as e:
                    self.log(f"Serial read error: {e}")
                    break
                if not chunk:
                    continue

                self.last_rx = time.time()
                self.status_cb("connected")
                self.buf.extend(chunk)

                # lines
                while b"\r" in self.buf or b"\n" in self.buf:
                    line = None
                    for eol in (b"\r\n", b"\n", b"\r"):
                        if eol in self.buf:
                            line, _, rest = self.buf.partition(eol)
                            self.buf = bytearray(rest)
                            break
                    if line is None: break

                    text = line.decode(errors="ignore").strip()
                    if not text: continue

                    # device status lines
                    if text == "?":
                        self.emit({"type":"status","text":"?"})
                        continue
                    if text.startswith("@"):
                        self.emit({"type":"status","text":text})
                        continue

                    # split tokens, parse
                    tokens = text.split()
                    for tok in tokens:
                        w = parse_word(tok)
                        if w:
                            ts = datetime.now().isoformat(timespec="seconds")
                            self.emit({"type":"word","ts":ts, **w})
                            # handle behaviors
                            if w["kind"] == "distance":
                                # AVG capture
                                if self.avg_capture:
                                    self.avg_vals.append(w["value"])
                                    self.emit({"type":"avg_state","active":True,"count":len(self.avg_vals),"target":self.avg_target})
                                    if len(self.avg_vals) >= self.avg_target:
                                        avg_m = sum(self.avg_vals)/len(self.avg_vals)
                                        self.emit({"type":"avg_done","avg_m":avg_m,"count":len(self.avg_vals)})
                                        self.stop_avg()
                                        self.stop_tracking()
                                # Push confirm (only for push-mode; suppress after our own cmd)
                                if self.confirm_push and (time.time() - self.last_cmd_time) > 1.0 and not self.tracking:
                                    try:
                                        self._write(b"cfm\n")
                                        self.emit({"type":"debug","text":"TX: cfm\\n"})
                                    except Exception as e:
                                        self.emit({"type":"debug","text":f"Confirm failed: {e}"})
                        else:
                            self.emit({"type":"unparsed","text":tok})
        finally:
            try:
                if self.ser and self.ser.is_open: self.ser.close()
            except Exception: pass
            self.status_cb("disconnected")
            self.log("Disconnected.")

    def stop(self): self.stop_flag.set()

# -------- GUI --------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Leica DISTO D8 — Remote R3")
        self.geometry("1040x680")

        self.out_q = queue.Queue()
        self.worker = None

        self.latest_distance_m = None
        self.latest_temp_c = None
        self.latest_signal_mv = None

        self.csv_path = None
        self.csv_enabled = tk.BooleanVar(value=False)
        self.auto_copy = tk.BooleanVar(value=False)
        self.confirm_push = tk.BooleanVar(value=True)
        self.tracking_active = tk.BooleanVar(value=False)

        self.mark_next = None
        self.avg_progress_var = tk.StringVar(value="")
        self.avg_n_var = tk.IntVar(value=10)

        self.make_ui()
        self.after(50, self.drain)

    def make_ui(self):
        top = ttk.Frame(self, padding=8); top.pack(fill="x")
        ttk.Label(top, text="Port:").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(top, textvariable=self.port_var, width=14, state="readonly")
        self.refresh_ports(); self.port_combo.pack(side="left", padx=(4,12))

        ttk.Label(top, text="Baud:").pack(side="left")
        self.baud_var = tk.StringVar(value="9600")
        self.baud_combo = ttk.Combobox(top, textvariable=self.baud_var, values=("9600","115200"), width=10, state="readonly")
        self.baud_combo.pack(side="left", padx=(4,12))

        self.connect_btn = ttk.Button(top, text="Connect", command=self.toggle_connect); self.connect_btn.pack(side="left", padx=(0,8))

        ttk.Checkbutton(top, text="CSV on", variable=self.csv_enabled).pack(side="right")
        self.csv_btn = ttk.Button(top, text="CSV…", command=self.pick_csv); self.csv_btn.pack(side="right", padx=(0,8))
        self.refresh_btn = ttk.Button(top, text="Rescan Ports", command=self.refresh_ports); self.refresh_btn.pack(side="right", padx=(0,8))

        # Status
        status = ttk.Frame(self, padding=(8,0,8,8)); status.pack(fill="x")
        self.led = tk.Canvas(status, width=18, height=18, highlightthickness=0); self.led.pack(side="left")
        self.led_id = self.led.create_oval(2,2,16,16, fill="#aa3333", outline="")
        ttk.Label(status, text="Status:").pack(side="left", padx=(8,4))
        self.status_var = tk.StringVar(value="Disconnected"); ttk.Label(status, textvariable=self.status_var).pack(side="left")

        # Big numbers row
        mid = ttk.Frame(self, padding=8); mid.pack(fill="x")
        self.dist_var = tk.StringVar(value="—.— m")
        ttk.Label(mid, textvariable=self.dist_var, font=("Segoe UI", 32, "bold")).pack(side="left")
        self.copy_btn = ttk.Button(mid, text="Copy", command=self.copy_distance, state="disabled"); self.copy_btn.pack(side="left", padx=12)
        ttk.Checkbutton(mid, text="Auto-copy", variable=self.auto_copy).pack(side="left", padx=(0,12))
        ttk.Checkbutton(mid, text="Confirm push (cfm)", variable=self.confirm_push, command=self._on_confirm_toggle).pack(side="left", padx=(0,12))
        # small quick stats: temp/signal
        self.temp_var = tk.StringVar(value="— °C")
        self.signal_var = tk.StringVar(value="— mV")
        ttk.Label(mid, textvariable=self.temp_var).pack(side="left", padx=(12,8))
        ttk.Label(mid, textvariable=self.signal_var).pack(side="left")

        # Remote control buttons
        cmdf = ttk.Labelframe(self, text="Remote Control", padding=8); cmdf.pack(fill="x", padx=8, pady=(0,8))
        ttk.Button(cmdf, text="Measure (G)", width=16, command=lambda:self.send_cmd("G")).pack(side="left", padx=4)
        ttk.Button(cmdf, text="Start Tracking (H)", width=18, command=lambda:self.send_cmd("H")).pack(side="left", padx=4)
        ttk.Button(cmdf, text="Stop / Laser OFF (P)", width=20, command=lambda:self.send_cmd("P")).pack(side="left", padx=4)
        ttk.Button(cmdf, text="Laser ON (O) ⚠", width=16, command=lambda:self.send_cmd("O")).pack(side="left", padx=4)
        ttk.Button(cmdf, text="Clear (c)", width=12, command=lambda:self.send_cmd("c")).pack(side="left", padx=4)
        ttk.Button(cmdf, text="Temperature (T)", width=16, command=lambda:self.send_cmd("T")).pack(side="left", padx=4)
        ttk.Button(cmdf, text="Signal (K)", width=12, command=lambda:self.send_cmd("K")).pack(side="left", padx=4)

        # AVG
        avgf = ttk.Labelframe(self, text="Average", padding=8); avgf.pack(fill="x", padx=8, pady=(0,8))
        ttk.Label(avgf, text="Samples:").pack(side="left")
        ttk.Spinbox(avgf, from_=3, to=50, textvariable=self.avg_n_var, width=5).pack(side="left", padx=(4,12))
        ttk.Button(avgf, text="Start AVG (auto start/stop)", command=self._avg_start, width=28).pack(side="left", padx=(0,8))
        ttk.Label(avgf, textvariable=self.avg_progress_var).pack(side="left")

        # Info + Danger Zone
        bot = ttk.Labelframe(self, text="Info / Danger Zone", padding=8); bot.pack(fill="x", padx=8, pady=(0,8))
        ttk.Button(bot, text="Device Info (N00/01/02/03)", command=self._device_info).pack(side="left", padx=4)
        ttk.Button(bot, text="Reset (a) ⚠", command=self._danger_reset).pack(side="left", padx=12)
        ttk.Button(bot, text="Power OFF (b) ⚠", command=self._danger_poweroff).pack(side="left")

        # Mark + Log
        markf = ttk.Frame(self, padding=8); markf.pack(fill="x")
        ttk.Button(markf, text="Mark", command=self._mark, state="normal").pack(side="left")

        logf = ttk.Labelframe(self, text="Log", padding=8); logf.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.log = tk.Text(logf, height=16, wrap="word"); self.log.pack(fill="both", expand=True); self.log.configure(state="disabled")

    # UI helpers
    def refresh_ports(self):
        ports = [p.device for p in list_ports.comports()]
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def toggle_connect(self):
        if self.worker:
            self.worker.stop(); self.worker = None
            self.connect_btn.config(text="Connect")
            self._set_status("disconnected"); return
        port = self.port_var.get()
        if not port: messagebox.showerror("No port","Select a COM port."); return
        try: baud = int(self.baud_var.get())
        except: messagebox.showerror("Baud error","Invalid baud."); return
        self.worker = SerialWorker(port, baud, self.out_q, self._set_status,
                                   confirm_push=self.confirm_push.get(), idle_seconds=10)
        self.worker.start(); self.connect_btn.config(text="Disconnect")

    def _set_status(self, state: str):
        if state=="connected": color="#2daa4a"; txt="Connected"
        elif state=="idle":    color="#d8a800"; txt="Idle"
        else:                  color="#aa3333"; txt="Disconnected"
        self.led.itemconfig(self.led_id, fill=color); self.status_var.set(txt)

    def send_cmd(self, ch: str):
        if self.worker: self.worker.send_cmd(ch)

    def _avg_start(self):
        if not self.worker: return
        self.worker.start_avg(self.avg_n_var.get())

    def _mark(self):
        self.mark_next = datetime.now().strftime("Mark %H:%M:%S")
        self._log(f"Mark armed: {self.mark_next} (will tag next distance)")

    def _device_info(self):
        if not self.worker: return
        for cmd in ("N00N","N01N","N02N","N03N"):
            self.worker._write((cmd + "\r\n").encode("ascii"))
            self._log(f"TX CMD: {cmd} (CRLF)")
            time.sleep(0.15)

    def _danger_reset(self):
        if not self.worker: return
        if messagebox.askyesno("Confirm Reset", "Send 'a' (reset)?"):
            self.worker.send_cmd("a")

    def _danger_poweroff(self):
        if not self.worker: return
        if messagebox.askyesno("Confirm Power OFF", "Send 'b' (power off)? Device will shut down."):
            self.worker.send_cmd("b")

    def pick_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if path: self.csv_path = path; self._log(f"CSV path: {path}")

    def copy_distance(self):
        if self.latest_distance_m is None: return
        txt = f"{self.latest_distance_m:.3f}"
        self.clipboard_clear(); self.clipboard_append(txt)
        self._log(f"Copied: {txt} m")

    def _on_confirm_toggle(self):
        if self.worker: self.worker.set_confirm_push(self.confirm_push.get())

    def _log(self, msg: str):
        self.log.configure(state="normal"); self.log.insert("end", msg+"\n")
        self.log.see("end"); self.log.configure(state="disabled")

    # queue drain
    def drain(self):
        while True:
            try: item = self.out_q.get_nowait()
            except queue.Empty: break
            t = item.get("type")
            if t == "debug":
                self._log(item["text"])
            elif t == "status":
                self._log(f"STATUS: {item['text']}")
            elif t == "tracking":
                self.tracking_active.set(item["active"])
                self._log(f"Tracking: {'ON' if item['active'] else 'OFF'}")
            elif t == "avg_state":
                if item["active"]:
                    self.avg_progress_var.set(f"Sampling {item['count']}/{item['target']}…")
                else:
                    self.avg_progress_var.set("")
            elif t == "avg_done":
                avg_m = item["avg_m"]; cnt = item["count"]
                self._log(f"AVG DONE: {cnt} samples → {avg_m:.3f} m")
                self.latest_distance_m = avg_m
                self.dist_var.set(f"{avg_m:.3f} m (avg)")
                if self.auto_copy.get(): self.copy_distance()
            elif t == "word":
                kind = item["kind"]; disp = item["display"]; tok = item["token"]
                ts = item["ts"]
                if kind == "distance":
                    self.latest_distance_m = item["value"]
                    self.dist_var.set(disp)
                    self.copy_btn.config(state="normal")
                    tag = f"  <{self.mark_next}>" if self.mark_next else ""
                    self._log(f"{ts}  {disp}  [{tok}]"+tag)
                    if self.mark_next: self.mark_next = None
                    if self.auto_copy.get(): self.copy_distance()
                    if self.csv_enabled.get() and self.csv_path: self._write_csv(ts, item)
                elif kind == "temperature":
                    self.latest_temp_c = item["value"]
                    self.temp_var.set(disp)
                    self._log(f"{ts}  TEMP: {disp}  [{tok}]")
                elif kind == "signal":
                    self.latest_signal_mv = item["value"]
                    self.signal_var.set(disp)
                    self._log(f"{ts}  SIGNAL: {disp}  [{tok}]")
                else:
                    self._log(f"{ts}  {disp}")
            elif t == "unparsed":
                self._log(f"UNPARSED: {item['text']}")
        self.after(50, self.drain)

    def _write_csv(self, ts, item):
        hdr = ["timestamp","token","word_index","unit_code","sign","raw","kind","value"]
        need_header = not (self.csv_path and os.path.exists(self.csv_path) and os.path.getsize(self.csv_path) > 0)
        try:
            with open(self.csv_path,"a",newline="",encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=hdr)
                if need_header: w.writeheader()
                w.writerow({
                    "timestamp": ts,
                    "token": item["token"],
                    "word_index": item["word_index"],
                    "unit_code": item["unit_code"],
                    "sign": item["sign"],
                    "raw": item["raw"],
                    "kind": item["kind"],
                    "value": item["value"],
                })
        except Exception as e:
            self._log(f"CSV write failed: {e}")

if __name__ == "__main__":
    App().mainloop()
