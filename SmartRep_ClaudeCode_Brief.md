# SmartRep: Scan & Lift Prototype

## Project brief for Claude Code

How to use this file: put it in an empty folder named smartrep/, open Claude Code there, and say: "Read SmartRep_ClaudeCode_Brief.md. Propose a plan and ask me any questions before writing code."

## Table of contents

- Who we are and what this is

- The problem

- The concept: Scan & Lift

- Hardware we have (constraints)

- System architecture

- Repository layout

- Component 1: Firmware (Arduino + ESP32)

- Component 2: Bridge server

- Component 3: Rep detection algorithm

- Component 4: Simulator

- Component 5: Phone app

- Component 6: Instructor dashboard

- Component 7: QR codes

- Data model

- API reference

- WebSocket message catalog

- Configuration

- Error handling and edge cases

- Testing plan

- Milestones and acceptance criteria

- README requirements

- Demo script

- Future work (do not build now)

- Working agreement with Claude Code

## 1. Who we are and what this is

- Team: Triple A + H (Aaron, Harvey, Arvind, Ali), first-year engineering students, ECE 198, University of Waterloo.

- Client: CCCARE (Centre for Community, Clinical & Applied Research Excellence), a community exercise clinic for older adults, cancer patients and survivors, stroke survivors, and graduates of those programs.

- Goal: a working demo prototype that shows one participant using a sensor-equipped dumbbell (only a small motion sensor on the dumbbell, cabled to a station box with the Arduino main chip + ESP32 Wi-Fi modem), a phone app and QR codes, while an instructor dashboard shows their progress live.

- Prototype vs. product: in the prototype the sensor is cabled to the station box. In the envisioned product, the sensor, a tiny wireless chip and a battery would be one thumb-sized wireless clip. Design the software so that change needs no changes outside the firmware and sources/.

- Experience level: we know basic Arduino C++ and some Python. We're new to React Native and web servers. Prefer clear, well-commented, beginner-friendly code over clever code. Explain non-obvious decisions in comments.

- This is not a medical device. No real patient data. All participant data is fake seed data.

## 2. The problem

At CCCARE, each participant has a personalised exercise "dose": specific exercises, 1–2 sets of 10–20 reps, at a set load. It's prescribed by a Registered Kinesiologist (R.Kin) or Clinical Exercise Physiologist (CEP). One instructor supervises 10–12 participants, or up to 30 in graduate sessions. Results:

- Some participants don't finish their dose; others overdo it.

- Nobody can judge rep quality (full range of motion, controlled tempo) for everyone.

- Sets, reps and loads are written on paper logs, so staff only see results after the session.

- CCCARE's progression rule: once a participant completes 20 reps with proper form for two sessions in a row, their load is increased. Today nobody can check this automatically.

Every session also includes cardio at 40–60% of heart rate reserve. That's out of scope for this prototype except as a stretch goal.

## 3. The concept: Scan & Lift

- Each piece of equipment (e.g. the 5 lb dumbbell rack) has a station box with the station QR code on its lid. Only a small motion sensor is attached to the dumbbell, cabled to the box.

- A participant opens the app, enters their 6-digit participant ID once, and scans the station's QR code.

- The app shows only the exercises from their dose that use that equipment, with target sets, reps and load.

- They pick an exercise and start a set. The sensor's motion data flows from the station box over Wi-Fi to the bridge, which counts reps and judges each one against the participant's saved reference rep for that exercise.

- The phone shows a live rep counter and the quality of each rep. The set is logged automatically.

- The instructor dashboard shows everyone live, with alerts sorted to the top: behind on dose, over dose, ready to progress.

- Calibration: in a one-time setup with staff, the participant does 3 correct reps. The system saves that motion as their personal reference for that exercise.

## 4. Hardware we have (constraints)

Design rule from our team: the Arduino UNO R4 Minima is the main chip. It reads the sensor, runs the station's status light, and decides when to stream. All participant-facing feedback (rep sounds, vibration, finishing a set) happens on the phone, which does it better than extra parts on the station.

Physical layout: only the MPU-6050 is on the dumbbell. A 1–1.5 m, 4-wire cable runs to a station box on the rack or bench, which holds the Arduino, ESP32, breadboard and status light. The station's QR code is on the box lid. The ESP32 is only a Wi-Fi modem: it passes text lines between the Arduino and the laptop. This mirrors Arduino's own UNO R4 WiFi board, which pairs the same main chip with an ESP32-S3 for Wi-Fi.

Parts marked ALIS PART come from Ali's personal starter kit, not the course kit.

| Item | Detail |
| --- | --- |
| Main chip | Arduino UNO R4 Minima (course kit). Renesas RA4M1, 5 V logic, 48 MHz. I/O pins can only supply ~8 mA, so the LED uses 1 kΩ resistors. |
| Wi-Fi modem | ESP32 DevKitC (WROOM-32U, external 2.4 GHz antenna on U.FL, 3.3 V logic). Transparent pipe: Arduino UART ⇄ WebSocket to the bridge. |
| Motion sensor (on the dumbbell) | MPU-6050 (GY-521 module) — ALIS PART. The only part on the dumbbell, connected to the Arduino's SDA/SCL through a 1–1.5 m 4-wire cable (twisted pairs: SDA+GND, SCL+VCC). Because of the long cable, run I²C at 100 kHz. 6-axis: 3-axis accelerometer plus 3-axis gyroscope. I²C address 0x68. Configure accel ±4 g (8192 LSB/g), gyro ±500 °/s (65.5 LSB per °/s), and the digital low-pass filter at 44 Hz (CONFIG register = 3). The gyro lets us measure joint angle and range of motion in degrees, which is far better for judging rep quality than acceleration alone. |
| Status light | RGB LED — ALIS PART (common cathode). Red → D9, green → D10, blue → D11, each through 1 kΩ — ALIS PART. Shows the station box's own state (powered, Wi-Fi, streaming, error), which the phone can't show. Not used for rep feedback; the phone does that. |
| Arduino ⇄ ESP32 link | Two-way UART at 115200 baud, through two PN2222 transistor level shifters — ALIS PART (plus 10 kΩ resistors — ALIS PART). Each transistor stage translates the voltage (5 V ⇄ 3.3 V) and inverts the signal. The ESP32 un-inverts both directions in hardware with Serial2.begin(115200, SERIAL_8N1, 16, 17, true) (the last argument is invert). The Arduino side is completely normal Serial1 (D0/D1). Arduino TX D1 → Q1 → ESP32 RX GPIO16; ESP32 TX GPIO17 → Q2 → Arduino RX D0. |
| Power | The station box is powered by the 9 V power adapter — ALIS PART into the Arduino's DC barrel jack (preferred, since the box doesn't move), or a power bank into its USB-C. Arduino 5V → ESP32 5V, grounds common. 100 µF capacitor — ALIS PART across the ESP32's 5V/GND to smooth Wi-Fi current spikes. Never plug the ESP32's USB in while the 5V wire is connected. |
| Second station (glove, optional) | Arduino UNO R3 — ALIS PART + the requested Grove ADXL335 analog accelerometer (A0/A1/A2) over USB only (no Wi-Fi). 10-bit ADC, units counts10. |
| Optional | GY-MAX30102 pulse oximeter on the same I²C bus (0x57). Stretch goal. |
| Wired fallback | The Arduino's USB-C straight to the laptop: same firmware, no ESP32. |
| Phones | Android + iPhone, via Expo Go only (no native builds, no paid developer accounts). |
| Laptops | Windows + macOS. |
| Network | Phone hotspot on 2.4 GHz (iPhone: Maximize Compatibility). eduroam blocks device-to-device traffic. |

Why not ESP32 Bluetooth straight to the phone? BLE in React Native needs a native module that does not run in Expo Go. Wi-Fi to the bridge keeps Expo Go working and keeps rep detection in one place.

## 5. System architecture

```
 ┌─────────── dumbbell ── 1–1.5 m cable ──▶ station box (on the rack/bench) ───────────┐
 │                                                                                     │
 │  MPU-6050 ══I²C══▶ ARDUINO R4 MINIMA  ◀══ UART (two-way, ══▶  ESP32  ──Wi-Fi──────┼──┐
 │  (ALIS PART)       main chip:              2× PN2222 level      Wi-Fi modem          │  │
 │                    • reads sensor @50 Hz   shifters)            (transparent pipe)   │  │
 │  RGB LED ◀──────── • start/stop streaming                                          │  │
 │  (status)          • status light                                                  │  │
 │                                                                                     │  │
 │  9V adapter ──jack──▶ Arduino ──5V/GND──▶ ESP32     (QR code on the box lid)       │  │
 └─────────────────────────────────────────────────────────────────────────────────────┘  │
   (fallback: Arduino USB-C ──USB serial──▶ laptop, no ESP32)                              │
                                                                                          ▼
                                                   ┌─────────────────────────────────────┐
                                                   │            BRIDGE (Python)          │
                                                   │  SensorSource (wifi|serial|sim)     │
                                                   │  Orientation → RepDetector          │
                                                   │  SessionManager · SQLite            │
                                                   │  FastAPI REST + WebSocket           │
                                                   └───┬───────────────────────┬─────────┘
                                                       │ Wi-Fi (hotspot)       │
                                        ┌──────────────▼─────────┐  ┌──────────▼──────────┐
                                        │ Phone app (Expo / RN)  │  │ Instructor dashboard│
                                        └────────────────────────┘  └─────────────────────┘
```

Key decisions:

- Only the sensor is on the dumbbell. All electronics live in the station box.

- The Arduino runs the station. Sampling, timestamps, device identity, streaming on/off and the status light all live on the Arduino. Commands from the bridge go to the Arduino.

- The phone handles everything the participant interacts with: rep sounds, vibration, finishing a set. No buttons or buzzers on the station.

- The ESP32 is a transparent modem. Lines from the Arduino go to the WebSocket, and frames from the bridge go to the Arduino as lines. It adds only its own Wi-Fi status messages. No sensor or session logic on the ESP32.

- Identical protocol on both links. The same Arduino firmware talks the same line protocol over USB (fallback) and over UART→ESP32→Wi-Fi. The bridge can't tell the difference except for the link field.

- Rep detection runs in the bridge, not on either chip. It's easy to tune in Python, unit-tested, and the simulator uses the same path.

- Stations map to devices. Station db-5lb uses clip clip-01.

- One active set per device. A second participant gets "station in use".

- The bridge is the single source of truth. The app and dashboard are thin clients.

## 6. Repository layout

```
smartrep/
├── README.md                         # beginner setup guide (see §21)
├── SmartRep_ClaudeCode_Brief.md      # this file
├── firmware/
│   ├── smartrep_arduino/             # MAIN CHIP: Arduino R4 Minima (also builds for UNO R3)
│   │   └── smartrep_arduino.ino      #   MPU-6050 or ADXL335 → lines over USB + Serial1
│   └── smartrep_esp32_wifi/          # WI-FI MODEM: ESP32 DevKitC
│       ├── smartrep_esp32_wifi.ino   #   inverted UART ⇄ WebSocket
│       ├── config.example.h          #   Wi-Fi name/password, bridge host
│       └── config.h                  #   real values, git-ignored
├── bridge/
│   ├── pyproject.toml
│   ├── config.toml                   # all tunable values (§17)
│   ├── smartrep/
│   │   ├── __init__.py
│   │   ├── main.py                   # CLI entry: python -m smartrep
│   │   ├── api.py                    # FastAPI routes + WebSocket hub
│   │   ├── sources/
│   │   │   ├── base.py               # SensorSource interface
│   │   │   ├── wifi_source.py        # clips via ESP32 over WebSocket
│   │   │   ├── serial_source.py      # Arduino straight over USB (fallback)
│   │   │   └── sim_source.py         # simulator
│   │   ├── units.py                  # raw → g, °/s per sensor type
│   │   ├── orientation.py            # complementary filter → pitch/roll angles
│   │   ├── reps.py                   # RepDetector + Calibrator
│   │   ├── filters.py                # smoothing helpers
│   │   ├── session.py                # SessionManager: active sets, alerts
│   │   ├── db.py                     # SQLite access (plain sqlite3)
│   │   ├── seed.py                   # fake participants, stations, doses
│   │   └── models.py                 # pydantic models
│   ├── static/dashboard.html
│   ├── recordings/
│   └── tests/
│       ├── test_units_orientation.py
│       ├── test_reps.py
│       ├── test_calibration.py
│       ├── test_session.py
│       ├── test_wifi_source.py
│       └── test_api.py
├── app/                              # Expo (React Native, TypeScript)
└── tools/
    ├── make_qr.py
    └── record.py
```

## 7. Component 1: Firmware

There are two sketches, one per chip.

### 7A. Arduino: main chip (firmware/smartrep_arduino/)

Settings at the top of the file:

```
#define DEVICE_ID   "clip-01"
#define FW_VERSION  "1.0.0"
#define SENSOR_MPU6050          // or SENSOR_ADXL335 (for the UNO R3 glove station)
#define ADXL_AXES   3           // ADXL335 only: 2 for the 2-axis Grove board
```

It must compile for both the UNO R4 Minima and the UNO R3 (ALIS PART). Use #if defined(ARDUINO_UNOR4_MINIMA) for analogReadResolution(14); the R3 stays at 10-bit. The R3 has no Serial1, so on the R3 only the USB link exists. Keep RAM use small: the R3 has only 2 KB, so avoid String, and use fixed char buffers and F() strings.

Sensor:

- MPU-6050 (ALIS PART): use plain Wire (no library). At boot: write PWR_MGMT_1 (0x6B) = 0x00 (wake), CONFIG (0x1A) = 0x03 (44 Hz DLPF), GYRO_CONFIG (0x1B) = 0x08 (±500 °/s), ACCEL_CONFIG (0x1C) = 0x08 (±4 g). Each sample: burst-read 14 bytes from 0x3B (accel X/Y/Z, temp, gyro X/Y/Z), with Wire.setClock(100000) (100 kHz, for the long cable). Check WHO_AM_I (0x75) == 0x68 at boot. If it fails, report an err and blink red.

- Long-cable robustness: use Wire.setWireTimeout() (R4 core) so a glitch can't hang the sketch. If a read fails or times out, skip that sample (don't send garbage) and count the failure. After 5 consecutive failures, re-initialise the MPU and send {"t":"err","msg":"sensor read failed, re-initialising"}. Include the failure count in info ("i2c_err":3), so the dashboard can warn about a bad cable.

- ADXL335: analogRead(A0/A1/A2).

Sampling: exactly 50 Hz using a micros() scheduler (no delay() anywhere).

Links: the Arduino listens for commands on both USB Serial and Serial1 (R4 only), at 115200. It replies on the link the command came from, and streams samples only to links that have sent START.

Messages it sends (one JSON object per line):

| Message | When | Example |
| --- | --- | --- |
| info | every 2 s on Serial1 (so the ESP32 always knows who it's attached to) | {"t":"info","device":"clip-01","fw":"1.0.0","sensor":"mpu6050","hz":50,"units":"mpu6050_4g_500dps"} |
| hello | reply to HELLO | same fields as info, "t":"hello" |
| sample (MPU) | 50 Hz while streaming | {"t":"s","ms":123456,"ax":-412,"ay":8090,"az":1203,"gx":15,"gy":-2210,"gz":40} (raw int16) |
| sample (ADXL) | 50 Hz while streaming | {"t":"s","ms":123456,"x":5402,"y":6511,"z":5398} (units counts14 on R4, counts10 on R3) |
| ack / pong / err | replies and errors | {"t":"ack","cmd":"START"} · {"t":"pong","ms":123456} · {"t":"err","msg":"MPU-6050 not found"} |

Commands it accepts (plain text, \n-terminated, case-insensitive):

| Command | Effect |
| --- | --- |
| HELLO, PING | Replies hello / pong |
| START / STOP | Streaming on/off for that link. Auto-stop if no command arrives on that link for 10 s |
| @WIFI CONNECTING / @WIFI UP / @WIFI BRIDGE / @WIFI DOWN | Status lines from the ESP32 itself, which drive the idle light (below) |

Status light (RGB):

| State | Light |
| --- | --- |
| Booting / sensor error | Red blink |
| Wi-Fi connecting (@WIFI CONNECTING) | Blue fast blink |
| Connected to bridge, idle (@WIFI BRIDGE, or a USB HELLO received) | Blue slow pulse (1 Hz) |
| Streaming | Dim green solid |
| No Wi-Fi and no USB host | Blue off, single red blink every 3 s |

The Arduino's on-board LED gives a 1 Hz heartbeat. Never use while (!Serial), because on a wall adapter or power bank there's no USB host. Comment every block; we need to explain this code in our report.

### 7B. ESP32: Wi-Fi modem (firmware/smartrep_esp32_wifi/)

Toolchain: Arduino IDE 2.x + "esp32 by Espressif Systems", board "ESP32 Dev Module". Library: WebSockets by Markus Sattler.

config.h (git-ignored; ship config.example.h):

```
#define WIFI_SSID      "SmartRepHotspot"
#define WIFI_PASSWORD  "changeme"
#define BRIDGE_HOST    "smartrep.local"   // mDNS; or an IP like "192.168.43.17"
#define BRIDGE_PORT    8000
```

Behaviour:

- UART: Serial2.begin(115200, SERIAL_8N1, 16, 17, true). invert = true is essential, because both transistor level shifters invert the signal. Explain this in a comment.

- Identity: learn device, sensor, units, fw from the Arduino's info lines (they arrive every 2 s). Don't open the WebSocket until the first info has arrived.

- Wi-Fi: connect to the hotspot with WiFi.setSleep(false). Send @WIFI CONNECTING to the Arduino, then @WIFI UP. Find the bridge with mDNS (smartrep), falling back to BRIDGE_HOST. Connect to ws://<bridge>:<port>/device and send @WIFI BRIDGE to the Arduino.

- On connect: send a hello frame built from the Arduino's info, plus "link":"wifi","via":"esp32","rssi":…,"mac":"…".

- Arduino → bridge: forward every complete line except info (the ESP32 consumes those). To save Wi-Fi overhead, pack up to 5 lines (or 100 ms' worth) into one WebSocket text frame, separated by \n.

- Bridge → Arduino: write every text frame to Serial2 as a line, unchanged.

- Health: every 5 s send {"t":"status","rssi":-58,"uptime_s":312,"uart_ok":true}. uart_ok is false if nothing has arrived from the Arduino for 3 s; also send {"t":"err","msg":"no data from Arduino"} once when that happens.

- Reconnect: if the WebSocket drops, send @WIFI DOWN to the Arduino and reconnect with backoff (1, 2, 5 s, then every 5 s).

- Debug: mirror human-readable status to USB Serial at 115200.

- Antenna comment: the WROOM-32U has no on-board antenna. Attach the external one before powering on.

### 7C. Protocol summary

- Device → bridge: JSON lines (hello, s, ack, pong, err from the Arduino; hello, status, err from the ESP32). Over Wi-Fi, a WebSocket frame may contain several lines, so the bridge must split on \n.

- Bridge → device: plain-text commands from §7A. These are identical over USB and Wi-Fi.

- Sensor units the bridge must support: mpu6050_4g_500dps, counts14, counts10.

## 8. Component 2: Bridge server

Stack: Python 3.11+, FastAPI, uvicorn, pyserial, pydantic, the standard-library sqlite3, and pytest. Avoid heavier dependencies unless you justify them.

### 8.1 CLI

```
python -m smartrep                       # real hardware: accept clips over Wi-Fi (via ESP32) + auto-detect Arduinos on USB
python -m smartrep --simulate            # no hardware; simulated clips
python -m smartrep --port COM4           # force a port (repeatable for multiple clips)
python -m smartrep --reset-db            # wipe and re-seed the database
python -m smartrep --host 0.0.0.0 --http-port 8000
```

On startup, print a friendly banner. Use all local IPv4 addresses, so a student can easily find the right one on a hotspot:

```
SmartRep bridge running
  Phone app:  connect to http://192.168.43.17:8000
  Dashboard:  http://192.168.43.17:8000/dashboard
  Clips connect to: ws://192.168.43.17:8000/device  (mDNS: smartrep.local)
  Devices:    clip-01 wifi via esp32 (-58 dBm, 3 axes, uart ok) | simulator: off
```

Also print the connect URL as a QR code in the terminal (e.g. with the qrcode package's ASCII output), so the phone can scan it to connect instantly. See §11.3.

### 8.2 Wi-Fi source (Arduino clips via the ESP32)

- WebSocket endpoint /device on the same FastAPI server.

- The first message must be hello. Register the device by DEVICE_ID. If the same ID reconnects, replace the old connection.

- Expand b batch messages into individual samples with timestamps ms0 + i·dt, then feed the same pipeline as serial samples.

- Mark offline after 3 missed pongs (PING every 3 s) or when the socket closes.

- Advertise mDNS as smartrep.local (_http._tcp, port 8000) using the zeroconf package, so clips can find the bridge without hard-coding an IP. If zeroconf fails (some hotspots block multicast), log a warning and print the IP prominently so we can put it in config.h.

- Frames may contain several JSON lines, so split on \n.

- Expose RSSI, uptime and uart_ok from status messages to the dashboard's device panel. Show "Arduino not sending" prominently when an err arrives or uart_ok is false, because it means the UART link or Arduino power is the problem, not Wi-Fi.

### 8.3 Serial source (Arduino over USB, fallback)

- Auto-detect: list ports, try each likely Arduino (by USB VID/PID or description), send HELLO, and wait up to 2 s for a hello reply.

- One background reader thread (or asyncio task) per device.

- Parse each line; skip malformed lines with a debug log and don't crash.

- Every 3 s, send PING to each device; mark it offline after 3 missed pongs.

- Reconnect automatically if a cable is unplugged and replugged.

- Expose: devices() (id, link, sensor, online, streaming), start(device_id), stop(device_id), and a sample callback.

### 8.4 SessionManager

- Tracks active participant sessions (signed-in participant, current station, current set).

- Starting a set: validate that the participant has this exercise in their dose, the station's equipment matches, and the device is online and free. Then START the device and create a RepDetector using that participant's reference for that exercise.

- No reference yet? Refuse to start and return NEEDS_CALIBRATION. The app shows "Ask staff to set up this exercise first."

- On each rep event: broadcast it to the app and dashboard. The phone gives the sound and vibration.

- Set ends when (a) the user taps Finish, (b) there's no rep for set_idle_timeout_s, or (c) the app disconnects for more than disconnect_grace_s. It then saves the set, STOPs the device, and broadcasts set_complete.

- Computes dashboard status per participant (§12.2).

### 8.5 Logging

Use the standard logging module, at INFO by default and DEBUG via --verbose. Log device connects and disconnects, set start and end, and calibration results. Never log every sample at INFO.

## 9. Component 3: Rep detection algorithm

The most important piece. It goes in reps.py, must be pure, deterministic and unit-tested, and must not import FastAPI or serial code.

### 9.1 Signal pipeline (per sample)

- Convert units (units.py), driven by the device's declared units:

- mpu6050_4g_500dps: accel g = raw / 8192; gyro °/s = raw / 65.5.

- counts14 (ADXL335 on R4): g = (raw − 5400) / 1080.

- counts10 (ADXL335 on UNO R3): g = (raw − 338) / 68.

All constants live in config.

- Gyro bias (MPU only): estimate the bias per gyro axis from the first 0.5 s of each set and calibration, while the participant holds still (the app says "Hold still…" for that moment). Subtract it.

- Orientation (MPU only, orientation.py): a complementary filter (α = 0.98) fuses gyro and accel into pitch and roll angles in degrees. Explain the idea in comments: the gyro is smooth but drifts, and the accel is noisy but doesn't drift.

- Candidate signals:

- MPU: pitch, roll (degrees), plus ax, ay, az (g) as backups.

- ADXL: x, y, z (g).

- Smooth: exponential moving average, α = 0.2 (configurable).

- Select the signal chosen at calibration (§9.2). For MPU clips this will almost always be an angle, so the reference range and every rep's range of motion are reported in degrees (e.g. "range 112°"). Show that on the dashboard set detail and the app summary.

### 9.2 Calibration (Calibrator)

Input: a stream of samples while the participant does 3 correct reps, guided by staff.

- Collect samples until the staff member taps Done, or until calibration_max_s (default 30 s).

- For each candidate signal (§9.1), compute its variance, normalised by that signal's typical noise. Pick the signal with the largest normalised variance. Prefer an angle signal when its swing is ≥ 20°.

- On that signal, find the rep cycles. Use simple peak/valley detection with a minimum prominence of 30% of the overall range, and a minimum spacing of 0.8 s.

- Require exactly 3 cycles (±1). Otherwise fail with a helpful reason: "Detected 1 rep; please do 3 slow, full reps."

- Compute the reference:

- ref_low = median of the valleys

- ref_high = median of the peaks

- ref_range = ref_high − ref_low

- ref_duration_s = median cycle duration

- direction: +1 if the rep's working phase raises the signal, −1 if it lowers it (from the sign of the first major move)

- Reject if ref_range is too small (angle < min_ref_range_deg, default 25°; accel < min_ref_range_g, default 0.25 g). In that case the sensor is probably loose or the movement too small.

Output: {signal, units, ref_low, ref_high, ref_range, ref_duration_s, direction}, where signal is e.g. pitch and units is deg or g. Stored per participant per exercise.

### 9.3 Counting (RepDetector)

Use hysteresis on a normalised signal so noise near a threshold can't double-count.

- Normalise: p = (y − ref_low) / ref_range, flipped if direction is −1, so that 0 means "start position" and 1 means "end of the movement".

- Thresholds (configurable): top_line = 0.75, bottom_line = 0.25.

- State machine:

```
          p ≥ top_line                    p ≤ bottom_line
 READY ───────────────▶ IN_REP ──────────────────────────▶ READY  (+1 rep)
   ▲                      │  track peak_p, start_time
   │                      │
   └── p ≤ bottom_line ◀──┘ (only after a rep completes)
```

- In practice: start in READY. When p rises above top_line, enter IN_REP and remember the start time and the peak. When p falls back below bottom_line, one rep completes.

- Partial-rep detection: reps that never cross top_line would otherwise be invisible. Also track "attempts": if p rises above attempt_line (default 0.35), peaks, and returns below bottom_line without reaching top_line, emit a rep with quality short. It counts toward attempts, not toward completed reps.

- Debounce: ignore any rep completing less than min_rep_s (default 0.6 s) after the previous one.

### 9.4 Quality per rep

| Quality | Rule (defaults configurable) | Counts toward the dose? |
| --- | --- | --- |
| good | peak_p ≥ 0.85 and duration ≥ 1.2 s | ✅ yes |
| short | peak_p < 0.85 (including attempts that never reached the top line) | ❌ no |
| rushed | duration < 1.2 s (full range but too fast) | ⚠️ yes, but flagged |
| slow | duration > 8 s (informational only) | ✅ yes |

Return per rep: {index, quality, peak_p, duration_s, t_start, t_end}.

### 9.5 Why these choices (explain in code comments)

- Hysteresis with two lines makes it robust to sensor noise.

- Normalising to the participant's own reference means the same code works for curls, rows and presses, and adapts to each person's range of motion. That matters a lot for stroke survivors and older adults with limited mobility.

- Every number is in config.toml, because we'll tune them with real data.

### 9.6 Tools for tuning

- tools/record.py --device clip-01 --seconds 30 --label curls_good (or --port COM4 for an Arduino on USB) saves raw samples, converted to g, to bridge/recordings/*.csv (columns: ms,gx,gy,gz,label,device,units).

- python -m smartrep.reps replay recordings/curls_good.csv --ref recordings/curls_cal.csv runs calibration on one file and detection on another. It prints each rep and, if matplotlib is installed, an optional plot with the threshold lines. We want to make a real-data version of the rep graph for our report.

## 10. Component 4: Simulator

Build this first. It lets the app, dashboard and algorithm be developed with no hardware.

- sim_source.py implements the same SensorSource interface as the serial source.

- It creates sim-01 … sim-04 devices and maps them to the seeded stations.

- When a device is started, it generates 50 Hz samples in MPU-6050 format (units: mpu6050_4g_500dps), so the full pipeline including orientation is exercised. Model a curl as the forearm pitch angle following a smooth raised-cosine between ~0° and ~110°. Generate consistent accel (gravity projected at that angle) and gyro (the angle's derivative) values, plus realistic noise and a small constant gyro bias.

- Scripted rep patterns, chosen at random per set or forced via the API (§15) for demos:

- mostly good reps (period 2–3 s)

- a mix with ~20% short (reaching 50–70% range) and ~10% rushed (period 0.8 s)

- stopping early (fewer reps than the dose), to trigger "Behind"

- Calibration in the simulator produces 3 clean reps and then pauses.

- Fake participants: optionally run 4 background "virtual participants" moving through their doses, so the dashboard looks like a real busy session. Enable with --simulate --crowd.

## 11. Component 5: Phone app

Stack: Expo SDK (current stable), React Native, TypeScript, expo-camera (CameraView with barcode scanning), @react-native-async-storage/async-storage to remember settings, and the native fetch + WebSocket APIs. Navigation: expo-router or @react-navigation/native-stack, whichever is simpler to explain. Must run in Expo Go.

### 11.1 Design rules (users are older adults)

- Body text ≥ 18 pt, headings ≥ 28 pt, the rep counter ≥ 96 pt.

- Contrast ≥ 4.5:1 for all text.

- Tap targets ≥ 56 × 56 px, with generous spacing.

- Never rely on colour alone: every status also has a word and an icon (✓ Good rep, ↕ Go further, 🐢 Slow down).

- One main action per screen, as a big button at the bottom.

- Plain-language copy, no jargon: "Go a little further" instead of "insufficient ROM".

- Sound + vibration on every rep, on by default. This is the participant's main feedback, since the station has no buzzer. Use three clearly different sounds: good rep (short chime), adjust (two low tones), set complete (longer chime). Use expo-audio (or expo-av, whichever the current Expo Go supports) plus expo-haptics. Sounds must play even with the phone on silent where the OS allows. Settings has a toggle and a volume note.

- Phone on a stand: design the Live set screen to be read from ~1 m away, with the phone propped up facing the participant.

- Support system font scaling, and test with the largest font setting.

### 11.2 Screens and flows

```
Connect ──▶ Sign in ──▶ Home ──▶ Scan station ──▶ Exercises here ──▶ Live set ──▶ Set summary
                         │                                   ▲              │
                         │                                   └── Next set ◀─┘
                         └──▶ Staff mode (PIN) ──▶ Calibrate
```

| Screen | Contents | Behaviour |
| --- | --- | --- |
| Connect | Big "Scan bridge QR" button, plus a manual URL field | Scans the QR printed in the bridge terminal (§8.1) or accepts typed http://IP:8000. Calls /api/health. Saves on success. Skipped automatically next launch if reachable |
| Sign in | 6-digit ID entry with a large numeric keypad | GET /api/participants/{id}. Shows "Welcome, Mary". Remembers the last ID, with a "Not you?" link |
| Home | Today's dose summary (exercises done / total), big "Scan a station" button | Pulls /api/participants/{id}/today |
| Scan station | Full-screen camera with a framing box and a "Point at the code on the equipment" hint | Accepts only smartrep://station/<id>. Anything else shows "That's not a SmartRep code". Torch toggle for dim gyms |
| Exercises here | Station label ("Dumbbells — 5 lb"), list of matching exercises from the dose: name, "2 sets × 10–15 reps", progress ticks | Tap → start set. If NEEDS_CALIBRATION, show "Ask a staff member to set this up". If STATION_BUSY, show "Someone is using this station" |
| Live set | Huge rep count ("7 / 15"), set number ("Set 1 of 2"), last-rep badge (word + icon + colour), small live signal graph (optional), big Finish set button. Brief "Hold still…" moment at set start (gyro bias, §9.1) | Subscribes to WebSocket events for this set. Haptic on each rep. "Connection lost, reconnecting…" banner if the socket drops |
| Set summary | Reps, good/short/rushed breakdown, average range of motion (degrees, when available), encouragement message, "Next set" / "Back to exercises" | If the dose for this exercise is complete: "Exercise complete ✓" |
| Staff mode | PIN entry (default 0000 in config) | Unlocks Calibrate and a device list |
| Calibrate | Choose participant + exercise, "Start", instructions ("Do 3 slow, full reps"), live graph, "Done" | Shows success ("Reference saved") or the failure reason from §9.2, with "Try again" |
| Settings | Bridge URL, sound/haptics toggle, text size boost, sign out |  |

### 11.3 Connection handling

- A single WebSocket connection to ws://<bridge>/ws?participant=<id>.

- Auto-reconnect with backoff (1 s, 2 s, 5 s, then every 5 s). On reconnect, resync state via REST.

- If the bridge is unreachable at launch, show the Connect screen with a tip: "Make sure your phone and the laptop are on the same hotspot."

### 11.4 Code quality

- Small, typed components. One API client module, so no fetch calls are scattered through screens.

- Shared types are generated from or mirrored by the bridge's pydantic models. Keep a single types.ts.

- No state library unless needed. React context plus hooks is fine.

## 12. Component 6: Instructor dashboard

File: bridge/static/dashboard.html, served at /dashboard. Plain HTML + CSS + JS, no build step, no framework, no external CDNs (it must work offline on a hotspot).

### 12.1 Layout

- Header: "SmartRep · Instructor dashboard", session clock, count of participants active, connection indicator.

- Alerts strip at the top: cards for any participant with an alert, newest first.

- Main table: participant ID, name, current station, current exercise, progress ("Set 1 of 2 · 6/15"), last-rep quality, status.

- Click a row → side panel with today's sets for that participant, each with a good/short/rushed breakdown and a tiny bar chart (drawn with inline SVG, no libraries).

- Device panel: each station box, online/offline, streaming, Wi-Fi signal, sensor-cable health (i2c_err), and which station it serves.

- Large readable text. It might be shown on a laptop across the room.

### 12.2 Status rules (computed in the bridge, session.py)

| Status | Rule | Colour + label |
| --- | --- | --- |
| Over dose | More sets than prescribed today, or more than reps_max + 5 reps in a set | Orange · "Over dose" |
| Behind | Left a station (scanned another or went idle > 10 min) with that exercise's sets incomplete, or session ended with dose incomplete | Orange · "Behind" |
| Form check | ≥ 30% of the last set's reps were short or rushed | Amber · "Check form" |
| Ready to progress | For an exercise: two consecutive sessions each with a set of ≥ 20 good reps | Green · "Ready to progress" |
| On track | Otherwise, while active | Blue · "On track" |
| Done | Full dose complete today | Grey · "Done ✓" |

Sort order: Over dose → Behind → Form check → Ready to progress → On track → Done.

## 13. Component 7: QR codes

Tool: tools/make_qr.py (packages: qrcode[pil], reportlab).

- Payload: smartrep://station/<station_id>, e.g. smartrep://station/db-5lb.

- Reads stations from the bridge database (or --from-seed).

- Outputs station_qr_codes.pdf: one station per half-page (US Letter), with:

- the QR code at ≥ 8 cm wide (scannable from arm's length)

- the station label in large text ("Dumbbells · 5 lb")

- a small instruction line: "Open SmartRep and scan this code"

- a dashed cut line

- Error correction level M or higher, with a quiet zone of ≥ 4 modules.

- Also outputs individual PNGs (qr_<station_id>.png), so we can put them on slides.

- A separate bridge connect QR (http://IP:8000) is printed in the terminal at startup (§8.1).

## 14. Data model

Plain sqlite3. Create tables on startup if missing. Timestamps are ISO-8601 UTC strings.

```
CREATE TABLE participants (
  id            TEXT PRIMARY KEY,          -- 6-digit string, e.g. '123129'
  display_name  TEXT NOT NULL,             -- first name only (fake)
  program       TEXT NOT NULL              -- 'general' | 'cancer' | 'stroke' | 'graduate'
);
CREATE TABLE equipment_types (
  id     TEXT PRIMARY KEY,                 -- 'dumbbell' | 'kettlebell' | 'glove'
  label  TEXT NOT NULL
);
CREATE TABLE stations (
  id              TEXT PRIMARY KEY,        -- 'db-5lb'
  label           TEXT NOT NULL,           -- 'Dumbbells · 5 lb'
  equipment_type  TEXT NOT NULL REFERENCES equipment_types(id),
  load_lb         REAL,                    -- NULL for bodyweight/glove
  device_id       TEXT                     -- 'clip-01' / 'sim-01'
);
CREATE TABLE exercises (
  id              TEXT PRIMARY KEY,        -- 'bicep-curl'
  name            TEXT NOT NULL,
  category        TEXT NOT NULL,           -- mobility|squat|push|hinge|pull|carry|core|stretch
  equipment_type  TEXT NOT NULL REFERENCES equipment_types(id)
);
CREATE TABLE doses (
  participant_id  TEXT NOT NULL REFERENCES participants(id),
  exercise_id     TEXT NOT NULL REFERENCES exercises(id),
  sets            INTEGER NOT NULL,        -- 1 or 2
  reps_min        INTEGER NOT NULL,        -- 10..20
  reps_max        INTEGER NOT NULL,
  load_lb         REAL,
  PRIMARY KEY (participant_id, exercise_id)
);
CREATE TABLE rep_references (
  participant_id  TEXT NOT NULL,
  exercise_id     TEXT NOT NULL,
  signal          TEXT NOT NULL,           -- 'pitch' | 'roll' | 'ax' | 'ay' | 'az' | 'x' | 'y' | 'z'
  units           TEXT NOT NULL,           -- 'deg' | 'g'
  ref_low         REAL NOT NULL,
  ref_high        REAL NOT NULL,
  ref_duration_s  REAL NOT NULL,
  direction       INTEGER NOT NULL,        -- +1 / -1
  device_id       TEXT,
  created_at      TEXT NOT NULL,
  PRIMARY KEY (participant_id, exercise_id)
);
CREATE TABLE sessions (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  participant_id  TEXT NOT NULL,
  date            TEXT NOT NULL,           -- 'YYYY-MM-DD'
  started_at      TEXT NOT NULL,
  ended_at        TEXT
);
CREATE TABLE sets (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id      INTEGER NOT NULL REFERENCES sessions(id),
  participant_id  TEXT NOT NULL,
  exercise_id     TEXT NOT NULL,
  station_id      TEXT NOT NULL,
  set_number      INTEGER NOT NULL,
  load_lb         REAL,
  started_at      TEXT NOT NULL,
  ended_at        TEXT,
  end_reason      TEXT,                    -- 'user' | 'idle' | 'disconnect'
  reps_completed  INTEGER NOT NULL DEFAULT 0,   -- good + rushed + slow
  good            INTEGER NOT NULL DEFAULT 0,
  short           INTEGER NOT NULL DEFAULT 0,
  rushed          INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE reps (
  set_id      INTEGER NOT NULL REFERENCES sets(id),
  idx         INTEGER NOT NULL,
  quality     TEXT NOT NULL,
  peak_p      REAL NOT NULL,
  rom         REAL,                        -- range of motion in ref units (degrees for MPU clips)
  duration_s  REAL NOT NULL,
  t_start_ms  INTEGER NOT NULL,
  PRIMARY KEY (set_id, idx)
);
```

### 14.1 Seed data (seed.py)

- Participants (5): 123129 Mary (general), 204417 Raj (stroke), 311802 Linda (cancer), 118560 Tom (graduate), 150093 Grace (graduate).

- Stations (4): db-3lb, db-5lb, db-8lb, kb-10lb. Plus glove-1 (equipment glove) for bodyweight. Map them to sim-01…sim-05 in simulate mode and to clip-01, etc. for real hardware (configurable in config.toml).

- Exercises: bicep curl, hammer curl, bent-over row, shoulder press, front raise (dumbbell); goblet squat, kettlebell deadlift (kettlebell); wall push-up, bird dog, arm rainbow (glove).

- Doses: 3–5 exercises per participant, each 1–2 sets × 10–20 reps, with loads matching the stations.

- History: give Tom two past sessions with ≥ 20 good reps on bicep curl, so he shows Ready to progress on first launch. Give Raj a past session with many short reps.

- Pre-made references for the simulator, so demos work without calibrating first.

## 15. API reference

Base URL: http://<bridge>:8000. All JSON. Errors are returned as {"error": {"code": "STATION_BUSY", "message": "…"}} with an appropriate HTTP status.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/health | {ok, version, devices_online, simulate} |
| GET | /api/participants/{id} | Participant profile |
| GET | /api/participants/{id}/today | Today's dose with progress per exercise |
| GET | /api/stations/{station_id} | Station details + device status |
| GET | /api/participants/{id}/stations/{station_id}/exercises | Dose exercises available at this station, with progress |
| POST | /api/sets | Body {participant_id, station_id, exercise_id} → {set_id, set_number, target}. Errors: NOT_IN_DOSE, WRONG_EQUIPMENT, NEEDS_CALIBRATION, STATION_BUSY, DEVICE_OFFLINE |
| POST | /api/sets/{set_id}/finish | Ends the set → set summary |
| GET | /api/sets/{set_id} | Set detail with reps |
| POST | /api/calibrations | Body {participant_id, exercise_id, station_id, pin} → {calibration_id}; starts recording |
| POST | /api/calibrations/{id}/done | Runs calibration → reference or failure reason |
| GET | /api/dashboard | Full dashboard snapshot (participants, statuses, alerts, devices) |
| GET | /api/devices | Device list |
| POST | /api/sim/pattern | (simulate mode only) {device_id, pattern: "good"\|"mixed"\|"stop_early"} for demos |
| GET | /dashboard | Dashboard page |

Include automatic OpenAPI docs at /docs (FastAPI provides this for free).

## 16. WebSocket message catalog

Endpoint: ws://<bridge>:8000/ws?participant=<id> for the app, or ?role=dashboard for the dashboard. Server → client messages:

```
{"type":"set_started","set_id":42,"exercise_id":"bicep-curl","set_number":1,"target":{"reps_min":10,"reps_max":15}}
{"type":"rep","set_id":42,"count":7,"attempts":8,"quality":"good","peak_p":0.93,"duration_s":2.3,"rom":108,"rom_units":"deg"}
{"type":"signal","set_id":42,"p":[0.12,0.18,0.31,0.47]}
{"type":"set_complete","set_id":42,"reason":"user","reps_completed":12,"good":10,"short":1,"rushed":1,"avg_rom":106}
{"type":"calibration_progress","calibration_id":7,"cycles_seen":2}
{"type":"calibration_done","calibration_id":7,"ok":true,"signal":"pitch","units":"deg","ref_low":-12.0,"ref_high":104.5}
{"type":"calibration_done","calibration_id":7,"ok":false,"reason":"Detected 1 rep; please do 3 slow, full reps."}
{"type":"device_status","device_id":"clip-01","online":true,"streaming":false}
{"type":"dashboard_update","participant_id":"123129","status":"on_track","progress":"Set 1 of 2 · 6/15"}
{"type":"alert","participant_id":"204417","status":"behind","message":"Raj left Seated row with 1 of 2 sets done"}
```

- signal is downsampled to ~10 Hz (normalised p values), so the app's small live graph stays light.

- Client → server: {"type":"ping"} every 15 s; the server replies {"type":"pong"}.

## 17. Configuration

bridge/config.toml. Every tunable number lives here, with a comment explaining it:

```
[server]
host = "0.0.0.0"
port = 8000
staff_pin = "0000"
[serial]
baud = 115200
ping_interval_s = 3
offline_after_missed_pings = 3
[signal]
sample_hz = 50
ema_alpha = 0.2
[units.mpu6050_4g_500dps]   # MPU-6050 (ALIS PART), ±4 g, ±500 °/s
accel_per_g = 8192
gyro_per_dps = 65.5
[units.counts14]            # ADXL335 on Arduino R4 Minima, 14-bit ADC
zero = 5400
per_g = 1080
[units.counts10]            # ADXL335 on Arduino UNO R3 (ALIS PART), 10-bit ADC
zero = 338
per_g = 68
[orientation]
complementary_alpha = 0.98
gyro_bias_still_s = 0.5
[wifi]
device_ws_path = "/device"
mdns_name = "smartrep"   # → smartrep.local
[calibration]
reps_required = 3
max_seconds = 30
min_prominence_frac = 0.30
min_cycle_s = 0.8
min_ref_range_deg = 25
min_ref_range_g = 0.25
[reps]
top_line = 0.75
bottom_line = 0.25
attempt_line = 0.35
good_min_peak = 0.85
rushed_max_s = 1.2
slow_min_s = 8.0
min_rep_s = 0.6
[sets]
idle_timeout_s = 8
disconnect_grace_s = 20
[status]
form_check_frac = 0.30
progress_good_reps = 20
progress_sessions_in_row = 2
left_station_idle_min = 10
[devices]
# station_id = device_id (real hardware)
"db-5lb" = "clip-01"     # station box: R4 + ESP32, MPU-6050 on the dumbbell
"glove-1" = "clip-02"    # UNO R3 (ALIS PART) + ADXL335, USB
```

## 18. Error handling and edge cases

Handle each of these gracefully, with a clear message to the user:

| Situation | Expected behaviour |
| --- | --- |
| ESP32 connected but no data from the Arduino (UART wire loose, Arduino crashed) | Device shows "Arduino not sending" on the dashboard; the app says "Sensor problem, ask staff"; the open set is held for disconnect_grace_s |
| ESP32 loses Wi-Fi or the station box loses power mid-set | Same as unplugged: device offline, the set is held for disconnect_grace_s, and the app says "Station disconnected, ask staff." The box auto-reconnects and the set resumes |
| Sensor cable glitch (gaps in samples, i2c_err rising, re-init err) | The bridge tolerates gaps up to 200 ms (interpolate for the filter; don't count reps across a longer gap). The dashboard device panel shows "Check sensor cable" if i2c_err grows by more than 10 per minute |
| ESP32 signal weak (RSSI below −80 dBm) | Dashboard device panel shows a warning icon; the README says to check the antenna is attached |
| Two clips claim the same DEVICE_ID | The newest connection wins; log a WARNING naming both addresses |
| Arduino unplugged mid-set | Device goes offline. The set stays open for disconnect_grace_s, and the app shows "Sensor disconnected, check the cable." Auto-resumes on reconnect; otherwise the set ends with reason disconnect and keeps the reps so far |
| Phone loses Wi-Fi mid-set | Bridge keeps counting. On reconnect, the app resyncs and shows the correct count |
| Two phones start a set on the same station | The second gets STATION_BUSY |
| QR from another app scanned | "That's not a SmartRep code" |
| Station scanned has no matching exercises in the dose | "Nothing from your plan uses this equipment today", with a "Scan another" button |
| No reference for the exercise | NEEDS_CALIBRATION, with staff instructions |
| Calibration fails | Show the specific reason and a Retry button |
| Malformed serial line | Skip and log at DEBUG |
| Serial port busy (Serial Monitor open) | Clear startup error: "COM4 is in use. Close the Arduino Serial Monitor and try again." |
| Bridge restarted | Open sets in the DB are closed with reason disconnect on startup |
| Participant ID not found | "We couldn't find that ID. Check with staff." |

## 19. Testing plan

### 19.1 Unit tests (pytest), required

- test_reps.py:

- 10 clean synthetic reps → exactly 10, all good.

- Noise (σ = 50 counts) on clean reps → still exactly 10 (no double counts).

- 3 reps at 60% range → 3 short, 0 completed.

- 3 reps at 0.8 s period → 3 rushed, counted.

- Inverted direction (−1) → counts correctly.

- Signal sitting right at top_line with jitter → no false reps.

- Two reps closer than min_rep_s → debounced.

- test_calibration.py: 3 clean simulated MPU curls → picks pitch, reference ≈ 0–110° (±8°); 1 rep → fails with a reason; flat signal → fails with a reason; an ADXL clip with the dominant movement on Y → picks y.

- test_session.py: status rules from §12.2, including Tom → Ready to progress from seed history.

- test_units_orientation.py: unit conversion for all three unit types; a synthetic curl (pitch swinging 0→110° at 0.4 Hz, generated as consistent accel + gyro samples with noise and a gyro bias) → the complementary filter recovers the angle within ±5° and the bias estimate removes drift.

- test_wifi_source.py: a fake WebSocket device sends hello, then multi-line frames of samples → correct sample count and order; reconnect with the same ID replaces the old connection; err "no data from Arduino" marks the device unhealthy.

- test_api.py: FastAPI TestClient happy path (sign in → station → start set → simulated reps → finish), plus each error code.

### 19.2 Recorded-data tests

When we add real CSVs to bridge/recordings/ (from tools/record.py), add parametrised tests that assert the detected rep count matches the count in the filename (e.g. curls_good_10.csv → 10).

### 19.3 Manual end-to-end checklist (put it in the README)

- python -m smartrep --simulate --crowd, then open the dashboard and see 4 virtual participants.

- Phone: connect, sign in as 123129, scan db-5lb, start bicep curls, and watch reps appear on both phone and dashboard.

- Finish the set and check the summary and dashboard update.

- Real hardware (station box: R4 + ESP32, MPU-6050 on the dumbbell via the long cable): power the box from its adapter, check it appears in the device panel with RSSI and "uart ok", calibrate, then do 10 real curls. Accuracy target: ≥ 9/10 counted correctly across 3 trials. Check the reported range of motion is plausible (a full curl is roughly 100–140°). 4b. Pull the Arduino-TX wire mid-set: the dashboard should show "Arduino not sending" within ~3 s. Reconnect it and streaming resumes.

- Put the station box 10 m away from the laptop and confirm it stays connected (RSSI shown).

- Turn the hotspot off for 10 s mid-set, then on again. The station box should reconnect and the set should continue.

- Repeat step 4 with the Arduino plugged straight into the laptop by USB (no ESP32).

## 20. Milestones and acceptance criteria

Build in this order. Stop after each milestone, show us how to run it, and wait for our go-ahead.

| # | Milestone | Done when |
| --- | --- | --- |
| M1 | Bridge skeleton + DB + seed + simulator + /api/health | python -m smartrep --simulate starts and prints the banner and connect QR; /docs loads |
| M2 | Rep detection + calibration + unit tests | pytest passes all §19.1 tests; replay works on a synthetic CSV |
| M3 | Sets, sessions, WebSocket events, status rules | The API test happy path passes; WebSocket clients receive rep events from the simulator |
| M4 | Instructor dashboard | With --crowd, the dashboard shows live rows, sorted alerts, and Tom as "Ready to progress" |
| M5 | Phone app: connect, sign in, home, scan, exercises, live set, summary | End-to-end on a real phone via Expo Go against the simulator |
| M6 | Staff mode + calibration flow in the app | A calibration in simulate mode saves a reference and the next set uses it |
| M7 | QR generator | The PDF prints, and the phone scans each code from ~50 cm |
| M8 | Arduino firmware (MPU-6050) + USB serial source | The Arduino streams MPU samples over USB; HELLO / START / STOP work; the RGB status light is correct; real curls are counted on the phone with range of motion in degrees |
| M8b | ESP32 Wi-Fi modem + Wi-Fi source | Two-way UART works through the transistor level shifters (PING→pong over Wi-Fi); the station box on its own power shows "uart ok" + RSSI; real curls are counted with no cable to the laptop and the MPU-6050 on the long cable; the RGB light shows Wi-Fi status |
| M8c | (optional) UNO R3 glove station (ALIS PART) | The same smartrep_arduino sketch built with SENSOR_ADXL335 runs on the UNO R3 over USB; glove exercises are counted |
| M9 | Tuning tools + README polish | record.py + replay work on real data; a teammate who didn't write the code can set up from the README alone |

## 21. README requirements

Written for first-year students on Windows and macOS who have never run a Python server or an Expo app. It must include:

- What SmartRep is (2–3 sentences) and a diagram.

- Prerequisites with exact install links and versions: Python 3.11+, Node LTS, Arduino IDE 2.x, the Expo Go app on the phone, the esp32 by Espressif board package, and the USB-to-serial driver for the DevKitC (CP210x or CH340, depending on the chip printed on the board).

- Copy-paste commands for each OS: creating a virtual environment, installing dependencies, running the bridge, running the app (npx expo start), and uploading the firmware.

- Hotspot setup: turn on the hotspot in 2.4 GHz mode (iPhone: Maximize Compatibility), join the laptop, find the bridge URL (it's printed in the banner), and scan the connect QR.

- Station box setup (two chips): upload smartrep_arduino to the Arduino (set DEVICE_ID; SENSOR_MPU6050). Then unplug the Arduino→ESP32 5V wire, attach the ESP32's antenna, fill in config.h, and upload smartrep_esp32_wifi to the ESP32 over its own USB (hold BOOT if it stalls on "Connecting…"). Unplug the ESP32's USB, reconnect the 5V wire, and power the box from the 9 V adapter (or a power bank). Include a table of what the RGB light colours mean, and a short section on making the sensor cable (Ethernet cable or twisted jumpers, 1–1.5 m max).

- How to print QR codes.

- How to calibrate and run a set.

- How to record and replay real data for tuning.

- Troubleshooting: port busy, phone can't connect, firewall prompts (Windows "Allow access" for Python, which also blocks the ESP32 if denied), Expo Go version mismatch, ESP32 can't find the hotspot (5 GHz band), smartrep.local not resolving (use the IP in config.h).

- Disclaimer: student prototype, fake data, not a medical device.

## 22. Demo script

What we want to show in about 2 minutes. Make sure this works smoothly:

- Laptop shows the dashboard (simulator crowd running, plus the real station box next to the 5 lb dumbbell, with only the small sensor on the dumbbell itself). Tom shows Ready to progress.

- A teammate opens the app, signs in as Mary (123129), and scans the 5 lb dumbbell QR.

- The app lists Mary's dumbbell exercises → she picks Bicep curl, Set 1 of 2.

- She does 8 good curls, with only the thumb-sized sensor on the dumbbell: the phone (on a stand facing her) counts up with green "✓ Good rep" and a chime on each one. The summary later shows her range of motion in degrees.

- She does 2 half-reps: the phone shows amber "↕ Go a little further", and those don't count.

- She taps Finish set → the "set complete" sound plays and the summary appears. The dashboard row updates, and Mary shows Behind (set 2 not done) until she does it.

- Close by showing the set history panel for Mary on the dashboard.

## 23. Future work (do not build now)

Mention these in comments or the README as next steps, but don't implement them:

- Thumb-sized wireless clip: sensor + tiny Wi-Fi/BLE chip + small battery in one enclosure on the dumbbell, removing the cable and the station box. Our sources/ interface means only firmware and one source class change.

- Arduino UNO R4 WiFi: the same main chip with an ESP32-S3 Wi-Fi co-processor built in. It would replace our two-board clip with one board.

- Bluetooth LE straight to the phone (no laptop needed), using an Expo dev build with react-native-ble-plx.

- Battery-powered clip with a small LiPo + charger and deep sleep between sets; a 3D-printed enclosure.

- Pulse oximeter during cardio, with alerts outside 40–60% heart rate reserve.

- Real accounts, encryption, privacy and consent (PHIPA in Ontario) before any real participant data.

- Integration with CCCARE's existing systems (AirTable scheduling, the Access database).

- Home-exercise mode for program graduates.

## 24. Working agreement with Claude Code

- Start by summarising this brief back in ~10 bullet points and listing your questions. Don't write code until we confirm.

- Work one milestone at a time (§20). At the end of each: what you built, how to run it, how you tested it, and what's next.

- Run the code and tests yourself before saying something works. If something can't be tested here (e.g. the phone camera or real serial hardware), say so clearly and tell us exactly how to test it.

- Keep dependencies minimal, and pin versions.

- Comment generously. We need to explain this code in our ECE 198 report.

- If something in this brief is wrong or a better approach exists, tell us and explain the trade-off instead of silently changing the design.

- Never commit secrets. Use .gitignore for node_modules/, .venv/, *.db and recordings/ (we may want to commit some recordings, so ask first).
