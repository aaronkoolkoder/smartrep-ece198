# Final firmware policy update November 18

At the project owner's request, firmware 1.2.0 uses this board as an MPU6050.
WHO_AM_I is retained as informational metadata, not an initialization gate.
Configuration writes and a complete sensor read must succeed. Read failures still
block normal operation; diagnostic frames cannot be saved as rep references.
The working D2 tone, LCD display, calibration graphs and Excel history are retained.
No additional movement or accuracy tests were performed for this policy change.
Earlier test results below describe their respective revisions, not a new validation.

---

# November 18 integration update

- User confirmed the D2 buzzer's one-second 2 kHz test tone was audible after correcting
  its shield connection. The same tone mechanism is used for counted-rep feedback.
- The temporary six-axis input page is now integrated at `/diagnostics` in the main
  server, accessible through Staff setup. It shares the bridge connection, reserves
  the station, and releases it on close. It includes diagnostic CSV download and a
  buzzer test button. Raw read failures are shown explicitly, not graphed as zeros.
- **58 backend tests pass**, including raw WebSocket data, failed-read reporting,
  exclusive station ownership/release, and diagnostic reconnect mode.
- The current R4 firmware compiles and was uploaded (64,324 bytes flash, 5,740 bytes
  global RAM). Browser check at 390×844 passes without JavaScript errors or horizontal
  overflow; the current board reports failed raw reads, displayed honestly in the UI.
- Earlier in this session the standalone 10 Hz checker received live changing values.
  The later failed reads show the hardware path is not yet repeatably reliable.
  The unexpected sensor identity and physical count/angle validation remain unresolved.
- ESP32 antenna/wireless validation and rep-feedback during real validated movements
  are still pending. Successful buzzer and graph checks do not establish those results.

---

# Current verification status

Updated November 16, 2026. Automated software evidence and physical observations
are kept separate. See [SYMPOSIUM_READINESS.md](SYMPOSIUM_READINESS.md) for the
course requirements, system diagram, validation procedure and unresolved items.

## Software checks

- **56 backend tests passed**, including start-failure persistence and station cleanup.
  Reproduce with `bridge/.venv/bin/python -m pytest bridge/tests -q`.
- UNO R4 MPU/I2C-LCD/D2 firmware and ESP32 Wi-Fi modem compile successfully with
  Renesas UNO core 1.6.0 and Espressif ESP32 core 2.0.17 respectively.
- JavaScript syntax checked with `node --check bridge/static/app.js`.
- Mobile calibration UI exercised in Chrome at 390×844: actual serial diagnostic
  frames reach the six-axis graph, with no JavaScript errors or horizontal overflow.
- Excel endpoint tested for readable XML package structure, per-patient isolation,
  literal user text, saved set waveforms and flagged diagnostic samples.
- Tests isolate USB discovery so they cannot seize a connected physical Arduino.
- Wi-Fi transport tests use a software WebSocket device; they are not radio tests.

## Physical observations

- The new UNO R4 firmware was uploaded over USB and replies as `clip-01`.
- I2C scan acknowledges LCD at `0x27` and sensor at `0x68`.
- The sensor identity register reply observed was decimal **117 / 0x75**, while
  a genuine MPU6050 should identify as **0x68**. This remains unresolved.
- Sixty raw 14-byte replies were captured while the user tilted the board;
  all were different. This establishes changing register replies, not correct scale.
- The LCD reports detected and the user saw **MPU not found**. Output test commands
  were sent; software cannot confirm the audible buzzer without user observation.
- A live staff diagnostic graph was then verified through the running app.
- ESP32 Wi-Fi firmware is compiled/configured locally but **not uploaded**. The
  photographed ESP32U has no external antenna available. Its UART divider values
  were described in the handoff but have not been measured/independently verified.
- No real rep-count/angle accuracy, Wi-Fi range, wall-powered end-to-end session,
  or clinical usefulness has been established. Do not claim those tests passed.

## Current safeguards

Unexpected identity prevents normal rep counting/reference saving. Staff can inspect
and export diagnostic frames, which are labelled and kept out of validated reps.
Station/dashboard status shows sensor failure instead of presenting it as ready.
Changing from MMA7361 to MPU requires a new compatible calibration. USB cannot replace
an active Wi-Fi identity repeatedly. Lost samples reset motion; session history survives
restarts and disconnects. Small-movement demo mode is explicitly labelled.

Graph samples are now stored at 10 Hz for calibration and live sets. Previous waveform
history was not stored, although existing sets/reps remain in the Excel export.
Local Wi-Fi secrets, databases, captures, tunnel logs and temporary QR codes stay out
of Git. This remains a fictional-data classroom prototype, without production access
controls; the demo PIN is not security for real patient information.

---

## Historical verification record (November 3)

The following is the earlier baseline, not the current station status.

# Verification notes

Verified November 3, 2026 on macOS. The simulation is operational; physical sensing still needs the actual station.

## Checks completed

- **44 backend tests passed.** Includes unit conversion; gyro bias and orientation; calibration and all five simulator noise seeds; full, half, fast, slow and inverted reps; sensor gaps; station exclusivity; SQLite persistence; status rules; WebSocket events and reconnect snapshots; idle/disconnect recovery; calibration PIN and persistence; multi-line device frames; duplicate identity replacement; actual pyserial reading over a pseudo-terminal; and app routes.
- **Real browser walkthrough passed** in installed Google Chrome: plan → station → exercise → start → live rep → saved summary; staff calibration with three real-time simulated curls; dashboard crowd, search and set history; Expo web connection and sign-in. No page errors. A 390 px mobile viewport had no horizontal overflow. Desktop, mobile, live-set and dashboard screenshots were visually reviewed.
- **Expo TypeScript check passed** and `expo install --check` reported compatible SDK 58 dependencies. Web, iOS and Android Metro/Hermes exports succeeded. Expo web screens were exercised against the live bridge. No real phone was attached.
- **UNO R4 Minima firmware compiled** with Renesas UNO core 1.6.0: 58,696 bytes flash, 5,632 bytes global RAM.
- **UNO R3 ADXL variant compiled** with AVR core 1.8.8: 6,562 bytes flash, 569 bytes global RAM.
- **Station QR PDF reviewed** after rendering all three pages. Five PNGs are also generated. Printed scanning distance needs a phone test.
- **USB and Wi-Fi protocols tested without physical hardware.** USB uses pyserial against a pseudo-terminal board; Wi-Fi uses a fake WebSocket device with identity, samples, health and replacement scenarios.

## Limits and next physical checks

The ESP32 modem sketch is prepared, but its compiler check was not completed: the Espressif toolchain download failed partway through. Install the board package in Arduino IDE and compile it during modem bring-up. The R4 USB route is the first recommended physical test and does not require that modem.

No firmware was uploaded. Module voltage, transistor wiring, long-cable I2C behavior, Wi-Fi range, real rep accuracy and mounting orientation require the actual kit. Phone camera permissions, torch, haptics, silent-mode sound and largest system font settings also need device checks. mDNS is best effort; use the printed IP as fallback.

Expo's dependency audit reports five moderate findings inherited through development-tool filesystem/glob dependencies. The proposed forced fix downgrades Expo across SDK versions; it was not applied because that breaks SDK alignment. This local student prototype has no production authentication or real records.

## Design references

Original SmartRep source and copy were informed by [21st dashboard components](https://21st.dev/community/components/explore/dashboard-component), [Mito Health](https://mitohealth.com/), [Modern Health](https://www.modernhealth.com/), [Hinge Health](https://www.hingehealth.com/), [Omada](https://www.omadahealth.com/) and [Sword](https://sword.com/). No proprietary component source, brand imagery or clinical outcomes were imported.
