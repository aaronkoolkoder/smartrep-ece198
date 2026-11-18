> Firmware 1.2.0: the connected board is treated as an MPU6050. Its identity reply
> is informational, while failed configuration writes or reads still block operation.
> Recalibrate before counting reps. No new physical accuracy tests accompany this change.

# MPU6050 + ESP32 station

The UNO R4 runs `firmware/smartrep_mpu6050_lcd_wifi` (hd44780 library).
The ESP32 runs `firmware/smartrep_esp32_wifi` (WebSockets by Markus Sattler).
Both UARTs use **115200 baud, normal polarity**, with the existing JSON protocol.

## Wiring

- MPU6050 and LCD backpack share the R4 SDA/SCL pins and GND. Confirm the GY-521
  breakout's supply and I2C voltage compatibility; the bare MPU chip is not 5V tolerant.
- Grove buzzer plugs into **D2** on the Base Shield.
- R4 **D1 TX → 1kΩ → divider junction → ESP32 GPIO16**.
- Divider junction **→ 2kΩ → GND**.
- ESP32 **GPIO17 → R4 D0 RX**; both boards share GND.
- Each board gets power through its own USB connector. No Arduino 3.3V power to ESP32.
- ESP32U needs its external 2.4 GHz antenna connected before the Wi-Fi test.
- If either board is unpowered, disconnect the UART signal wires first.

## First test

1. Disconnect the ESP32 signal wires while testing the UNO alone.
2. Connect the UNO USB to the laptop, flash the new UNO sketch.
3. With the bridge and Serial Monitor closed, run
   `bridge/.venv/bin/python tools/test_mpu_station.py /dev/cu.usbmodem...`.
   The reply reports `sensor_ok`, `lcd_ok`, and `buzzer_pin: 2`.
   The LCD should show **LCD test OK** and the buzzer should beep once.
4. Fit the antenna, verify the divider values, then connect both boards by USB
   and restore UART wiring with both unplugged first.
5. Put the laptop and ESP32 on the same 2.4 GHz personal hotspot. Browser-login
   school Wi-Fi is not supported by this firmware.
6. Copy `config.example.h` to ignored `config.h`. Enter hotspot SSID/password,
   and set `BRIDGE_HOST` to the laptop's hotspot IP (recommended), or `smartrep.local`.
   This is a local server address, **not the Cloudflare phone URL**.
7. Flash the ESP32 as **ESP32 Dev Module**. Start the existing server launcher.
   Close Serial Monitor. `/api/devices` must show **link: wifi**, `uart_ok: true`,
   `sensor_ok: true`, `lcd_ok: true`. Wi-Fi takes precedence over a duplicate USB link.
8. Calibrate the MPU again; MMA calibration cannot be reused. Test calibration
   and a real set: phone/LCD counts agree, D2 buzzer beeps once per counted rep.

## Wall-power test

Finish any active set. Move both boards' USB cables from laptop to USB wall
adapters, powering them together with UART connected. Keep the laptop server
awake on the same hotspot. Wait for the device to return online over Wi-Fi,
then start another set and confirm readings, screen updates and beeps.

Cloudflare supplies the phone URL only. This setup still needs the running
laptop server; it is not an independent offline rep counter. Firmware compilation
and software tests alone do not confirm the physical wiring or wireless connection.

## Live diagnostics in the final app

Open `/diagnostics` or Staff setup → Check live MPU inputs. The graphs stream live
raw acceleration and gyro data through the existing bridge connection. Pause, clear
or download diagnostic CSV. **Test buzzer · D2** sends a one-second 2 kHz tone.
Close diagnostics before starting a calibration or exercise: the station is reserved
to avoid competing serial readers. Diagnostic streaming resumes after a link reconnect.
The user confirmed an audible D2 tone on November 18; sensor identity is still unresolved.

## Current wireless status

The ESP32 firmware has now been uploaded and flash-verified. The first wall-powered
check did not register an online device. Both boards' LEDs were on, but the antenna
is absent and the Wi-Fi/UART path remains unverified. Retain wireless in the feature
list with this qualification; use USB as the current data path.
