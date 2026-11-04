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
