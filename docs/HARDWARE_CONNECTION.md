# Connect a physical SmartRep station

The app and bridge already have a hardware path. Start with USB so sensor and rep tuning can be checked independently of the ESP32 link. No firmware has been uploaded to your boards by this task.

## First test with USB

1. Confirm the board is an **Arduino UNO R4 Minima** and the sensor module is a **GY-521 / MPU-6050**. Verify the module's power and I2C voltage requirements from its actual markings before wiring; a bare MPU-6050 and a breakout board are not interchangeable power inputs. Use the board's labeled SDA/SCL pins, common ground, and a short cable for the first test. Add the intended 1–1.5 m sensor cable after the basic signal works. Firmware runs I2C at 100 kHz.
2. Install [Arduino IDE 2](https://www.arduino.cc/en/software) and **Arduino UNO R4 Boards** through Boards Manager. The R4 sketch was compiled with core 1.6.0. Open `firmware/smartrep_arduino/smartrep_arduino.ino`, select **UNO R4 Minima**, confirm `DEVICE_ID` is `clip-01`, select the USB port and upload. Leave `SENSOR_MPU6050` enabled. It uses Wire directly, with no MPU library to install.
3. Optionally open Serial Monitor at 115200 with Newline ending. Send `HELLO` (identity), `START` (raw samples), `PING` (pong) and `STOP`. START expires after 10 seconds without another command. Close Serial Monitor before starting the bridge.
4. Stop the simulated bridge with Ctrl+C. From `bridge/` run:

```sh
.venv/bin/python -m smartrep --db smartrep-hardware.db
```

On Windows use `.\.venv\Scripts\python.exe`. Auto-detection looks for Arduino IDs and descriptions. Force the port if needed:

```sh
.venv/bin/python -m smartrep --db smartrep-hardware.db --port /dev/cu.usbmodemXXXX
# Windows: .\.venv\Scripts\python.exe -m smartrep --db smartrep-hardware.db --port COM4
```

5. Open the instructor dashboard. `clip-01` should be online at **Dumbbells 5 lb**. The default routing is `db-5lb → clip-01`, `glove-1 → clip-02`, `db-3lb → clip-03`, `db-8lb → clip-04`, `kb-10lb → clip-05`. Change `[devices]` in `bridge/config.toml` if your IDs differ.
6. Open the participant app as Mary (`123129`). Use Staff calibration with PIN `0000`, select Bicep curl, hold still for at least half a second, then do three controlled full reps with staff guidance. Save the reference. Start a normal set at the 5 lb station.
7. Do 10 counted curls across three trials and compare against a person counting. Target at least 9/10 correctly detected in each trial. Check the measured angle range, cable robustness and motion orientation; calibration is not a substitute for physical validation. Tune `bridge/config.toml` from recordings if necessary.

## Add the ESP32 modem

Use an **ESP32 DevKitC / WROOM-32U** with its external 2.4 GHz antenna attached. Install **esp32 by Espressif Systems** in Boards Manager and **WebSockets by Markus Sattler** in Library Manager. Select **ESP32 Dev Module**.

Copy `firmware/smartrep_esp32_wifi/config.example.h` to `config.h`. Enter the hotspot name/password and the laptop's printed LAN IP as `BRIDGE_HOST` (or `smartrep.local` when mDNS works). `config.h` is ignored by Git. Do not commit real Wi-Fi credentials.

The firmware expects **two inverting transistor level-shifter stages** as specified in the original brief:

| Signal | Path |
| --- | --- |
| Arduino TX | D1 → verified 5 V to 3.3 V inverting stage → ESP32 GPIO16 RX |
| ESP32 TX | GPIO17 → verified 3.3 V to 5 V inverting stage → Arduino D0 RX |
| Ground | Common reference between both boards |

`Serial2.begin(115200, SERIAL_8N1, 16, 17, true)` enables inversion on the ESP32 to compensate for those circuits. If you use a non-inverting level translator, that flag must change. Verify the actual transistor resistor arrangement and voltage levels before connecting the boards; do not wire a 5 V Arduino TX directly into an ESP32 pin.

For upload, disconnect the Arduino-to-ESP32 5 V power wire before plugging the ESP32 into USB. Upload the modem sketch (hold BOOT if needed), unplug the ESP32's USB, and reconnect the intended station power wiring. Avoid powering that rail simultaneously from the ESP32 USB and Arduino supply. The initial bring-up prompt below should include how you have powered both boards.

Run the hardware bridge on the same 2.4 GHz hotspot. The ESP32 learns the Arduino ID from periodic info lines, then connects to `/device`; its first frame identifies the device. The dashboard exposes RSSI and UART health. If both USB and Wi-Fi claim the same device ID, the newest connection replaces the older one—use one active route per station for the test.

## Station LED

| State | RGB light |
| --- | --- |
| Sensor problem / boot | Red blink |
| Wi-Fi connecting | Fast blue blink |
| Bridge connected and idle | Blue pulse |
| Streaming a set/calibration | Dim green |
| No bridge connection | Brief red blink every three seconds |

The built-in LED has a heartbeat. The phone handles rep sounds and vibration.

## Optional UNO R3 glove

Use `DEVICE_ID "clip-02"`, replace `#define SENSOR_MPU6050` with `#define SENSOR_ADXL335`, and use A0/A1/A2 for the accelerometer channels. The UNO R3 build has no Serial1 and uses 10-bit ADC counts. It works over USB. The same sketch's ADXL variant compiles for UNO R3 without dynamic String objects. A two-axis board can set `ADXL_AXES 2`; the unused Z channel is zero and should not be selected in calibration.

## Next prompt when the board is ready

> I have connected my Arduino UNO R4 Minima and MPU-6050. Continue the SmartRep hardware bring-up using docs/HARDWARE_CONNECTION.md. My connection is [USB / ESP32 Wi-Fi], the port is [port if known], and the module/power wiring is [describe or attach a photo]. Detect the board, verify the wiring assumptions and firmware target, upload the prepared sketch, switch the bridge to the separate hardware database, calibrate Mary’s curl, and help me test 10 reps. Preserve the working simulation.

A connected board and that prompt provide the context for the next step. Actual sensor voltage, wiring, mounting orientation and accuracy cannot be established from this repository alone.
