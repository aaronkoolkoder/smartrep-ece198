# SmartRep Scan and Lift

SmartRep is a working ECE 198 exercise-tracking prototype for a fictional CCCARE participant cohort. The participant app guides station selection, live sets and personal calibration; the instructor dashboard shows progress, alerts and connected stations. A Python bridge counts motion from either simulated sensors or Arduino stations.

```text
Simulation ───────────────────────────────────────┐
MPU-6050 → UNO R4 → USB ──────────────────────────┤
MPU-6050 → UNO R4 → ESP32 → Wi-Fi WebSocket ──────┤
                                                 ▼
                                  Python bridge + SQLite
                                     │               │
                              Participant app   Instructor dashboard
                              browser / Expo      browser
```

This is a student prototype with fake participant data, not a medical device. No real participant records belong in this demo.

## Use the running app

- Participant app: [localhost:8000](http://127.0.0.1:8000/).
- Instructor dashboard: [localhost:8000/dashboard](http://127.0.0.1:8000/dashboard).
- Native-screen web preview: [localhost:8000/phone](http://127.0.0.1:8000/phone), after building the Expo export.
- API docs: [localhost:8000/docs](http://127.0.0.1:8000/docs).
- Printable station labels: [station-qr.pdf](http://127.0.0.1:8000/station-qr.pdf).

Mary (`123129`) is selected by default in the browser demo. Click **Scan a station → Dumbbells 5 lb → Bicep curl → Start set**. The simulator supplies real raw MPU-style samples to the same orientation and rep-detection pipeline used for hardware. Reps update live; **Finish set** saves the summary. The simulator menu can introduce short or rushed reps or stop after eight reps.

The instructor view’s **Start room simulation** button runs virtual participants using the actual set manager, database and rep detector. It leaves Mary's station available. Participants stop after their prescribed number of demonstration sets; the room simulation does not run forever. Tom begins with two past sessions of 20 good curls and a Ready to progress status. The account circle changes participants.

For staff calibration: click **Staff calibration**, enter a participant ID and the demo PIN **0000**, choose an exercise, wait for three simulated reps (about eight seconds), then save. A failed recording gives a reason and a retry action. Calibration reserves the station so nobody can start a set simultaneously.

## Start on macOS

Install [Python 3.12](https://www.python.org/downloads/) or newer (3.12 was used for verification). Open Terminal in this project:

```sh
cd bridge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pip install -e '.[test]'
python -m smartrep --simulate --crowd
```

On this computer the environment is already installed. To relaunch from the project root, use `./start-smartrep.command`, or:

```sh
cd bridge
.venv/bin/python -m smartrep --simulate --crowd
```

## Start on Windows PowerShell

Install Python and open PowerShell in this project:

```powershell
cd bridge
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m smartrep --simulate --crowd
```

Stop with Ctrl+C. Use a different port with `--http-port 8001`. If the address is already in use, stop the previous bridge before relaunching. The current running demo and launcher use `bridge/smartrep-demo.db`; the earlier `smartrep.db` is preserved. The CLI default DB is `bridge/smartrep.db` when launched from `bridge/`. Restarting preserves activity. `--reset-db` deletes the selected demo database and re-seeds it; use it only when intentionally clearing demo history. `--db other-demo.db` keeps a separate run.

## Use a phone

The responsive browser app works immediately on a phone: join the same 2.4 GHz hotspot as the laptop and open the LAN URL printed by the bridge. The laptop's `127.0.0.1` URL does not work from a different device. iPhone hotspots should use **Maximize Compatibility**. eduroam often blocks device-to-device traffic. If prompted, allow Python through the laptop firewall.

For native camera QR scanning and sound/haptics, the `app/` folder contains an Expo React Native TypeScript app. Install [Node.js LTS](https://nodejs.org/en/download) (Node 26 was used for the Expo checks) and [Expo Go](https://expo.dev/go) on the phone:

```sh
cd app
npm ci
npm start
```

Scan Expo's development QR with Expo Go. Inside SmartRep, scan the **bridge** QR from the Python terminal or enter `http://<laptop-LAN-IP>:8000`. Enter Mary’s ID `123129`, then choose a simulated station or scan a printed station label. The bridge QR and the Expo development QR serve different purposes. The app remembers the bridge and participant. Its home screen includes sound/vibration settings and staff calibration.

The project pins Expo SDK 58 and matching dependencies; use an Expo Go version supporting that SDK. If Expo Go reports a mismatch, see [Expo's mismatch guide](https://docs.expo.dev/troubleshooting/expo-go-version-mismatch/). Browser camera scanning depends on browser support and a secure origin; manual station selection is always available. Real-phone camera permission, haptics and silent-mode audio need verification on the actual phone.

To check the native source and build its browser preview:

```sh
cd app
npm run typecheck
npx expo install --check
npx expo export --platform web
```

Restart the bridge after the first export to enable `/phone`. This native-screen preview is additional to the main browser app at `/`.

## Connect the Arduino later

Read [the hardware connection guide](docs/HARDWARE_CONNECTION.md). The fastest first hardware test is **UNO R4 Minima + MPU-6050 over USB**, then add the ESP32 modem. Both use the same data path and app. The repository includes both sketches, a USB serial reader, a Wi-Fi device endpoint and reconnect handling. Start hardware mode without `--simulate`, using a separate database so simulated references are not reused for physical movements.

The physical cable, voltage-level circuits, sensor orientation and real rep accuracy still require verification with your actual kit. Compilation and simulated protocol tests do not replace that check.

## Print codes and record motion

From the project root with bridge dependencies installed:

```sh
bridge/.venv/bin/python tools/make_qr.py --from-seed
bridge/.venv/bin/python tools/record.py --port /dev/cu.usbmodemXXXX --seconds 30 --label curls_good_10
```

On Windows replace `bridge/.venv/bin/python` with `bridge\.venv\Scripts\python.exe` and use a port such as `COM4`. The recorder talks directly to the USB Arduino: stop the bridge and close Serial Monitor first. `--device clip-01` can select an automatically discovered Arduino by ID instead. Recording saves raw values and identity/units metadata in `bridge/recordings/`.

Replay without hardware:

```sh
cd bridge
.venv/bin/python -m smartrep.synthetic
.venv/bin/python -m smartrep.reps replay recordings/curls_good_10.csv --ref recordings/curls_cal.csv
```

Expected: pitch around 0–110 degrees, 10 completed reps and 10 attempts. Raw MPU CSV columns are `ms,ax,ay,az,gx,gy,gz`. ADXL CSVs use `ms,x,y,z`; pass `--units counts10` or `--units counts14`. Hold still for the first half-second of every recording. Calibration uses three slow, full reps and must end at the starting position. Timestamps must increase. Sensor gaps over 200 ms cancel the partial movement; calibration gaps cause a retry.

## How it behaves

- Short attempts do not count toward the dose. Full rushed reps count with a warning; very slow reps are informational.
- Rep duration is measured between leaving and returning to the bottom threshold. This is shorter than the complete start-to-start cycle.
- Motion is normalized to the participant's reference. A six-axis IMU estimates the calibrated movement plane; it cannot measure absolute yaw or independently prove exercise form.
- One set or calibration can own a station at a time. Starting validates participant, prescribed exercise, equipment/load, reference and device availability.
- Each rep is committed before its WebSocket event is sent. A phone dropping Wi-Fi does not stop the station; reconnecting restores saved counts.
- Eight seconds without a rep on a healthy sensor finishes the set as idle. A disconnected sensor has a 20-second grace period; reconnect resumes its stream. Shutdown and crash recovery close abandoned sets while retaining saved reps.
- Alerts follow the brief's priority: Over dose, Behind, Check form, Ready to progress, On track, Done. Today uses America/Toronto; stored timestamps are UTC.
- All tunable processing values are in `bridge/config.toml`. The staff PIN is a demo gate, not production authentication.

## Verification

```sh
cd bridge
.venv/bin/python -m pytest -q
```

Tests cover raw unit conversion, biased/noisy orientation, calibration, good/short/rushed/slow and inverted reps, sample gaps, data persistence, API validation, station exclusivity, real-time events, disconnect recovery, device frame parsing, duplicate identity replacement, staff PIN and reference persistence. Browser checks exercise station selection → live rep → saved summary and inspect desktop/mobile layouts. See [verification notes](docs/VERIFICATION.md) for actual tested platforms and remaining physical checks.

## Troubleshooting

- **Can't connect from phone:** use the laptop's LAN address, the same hotspot, and allow Python through the firewall. Some hotspots block multicast; use the printed IP instead of `smartrep.local`.
- **Serial port busy:** close Arduino Serial Monitor, the standalone recorder, or the other bridge process.
- **ESP32 can't see hotspot:** enable 2.4 GHz mode and check its external antenna.
- **Arduino not sending:** inspect Arduino power and UART wiring; this differs from a Wi-Fi failure.
- **Needs calibration:** hardware mode deliberately rejects seeded simulated references. Do a staff calibration with the actual sensor.
- **Station in use:** finish the active set or calibration, or pause the room simulation.
- **Camera not available in browser:** choose a station manually, or use the native Expo Go app.
- **Too many historical demo sets:** use a fresh `--db` filename, or intentionally reset the demo DB.

A battery-powered wireless clip, direct BLE, cardio sensing, real accounts and clinic integration remain future work. UI references and design decisions are documented in [UI direction](docs/UI_DIRECTION.md).
