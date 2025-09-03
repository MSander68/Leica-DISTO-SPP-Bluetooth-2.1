Helper tools (short descriptions)

**disto_alpha_sweep.py**
Alphabet brute tester. Sends A–Z/a–z with CRLF/CR, logs hex/text to CSV, classifies replies (distance/ok/error/none), and tries to auto-stop if a command starts streaming.

**disto_cmd_scout.py**
Systematic probe of a curated command list (G/g, H/h, P/p, O/o, T/t, K/k, etc.), with retries, pacing, and readable console output.

**disto_d8_ack_probe.py**
Tiny console tester to compare MODE=cfm vs MODE=ack06 vs MODE=both for push-mode confirmation.

**disto_raw_console.py**
Interactive REPL for the COM port. Type plain text (sends ASCII + LF) or hex:... to send raw bytes. Displays RX as hex and text.

**disto_send_cmd.py**
One-shot command sender for scripting/automation. python disto_send_cmd.py COM7 g → sends g<CR> and prints any reply.
