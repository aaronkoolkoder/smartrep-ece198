# Grove LCD RGB Backlight quick start

For UNO R4 Minima with a standard Grove Base Shield. Unplug USB before fitting the shield or changing wires.

1. Stack the shield onto the Arduino with its headers correctly aligned.
2. For the LCD-only check, disconnect the MPU-6050 and set the Grove shield supply switch to 5V. Older Grove RGB LCD versions require 5V; V5 supports 3.3V/5V. This switch selects Grove power, not I2C voltage translation.
3. Plug the LCD's four-wire Grove cable into any shield connector labelled I2C. Do not use a D, A or UART connector. Grove cable signals: yellow SCL, white SDA, red VCC, black GND. Follow connector labels if cable colors differ.
4. Install **Grove - LCD RGB Backlight** by Seeed Studio in Arduino IDE Library Manager. Version 1.0.2 was used for compile checks; it handles LCD backlight versions 4 and 5.
5. Select **Arduino UNO R4 Minima** and its USB port. Open and upload `firmware/tests/smartrep_grove_lcd_test/smartrep_grove_lcd_test.ino`. Serial Monitor: 115200 baud. Expected LCD: `SmartRep LCD OK` / `Screen test only`.
6. Before combining the LCD and MPU, verify the MPU breakout's SDA/SCL voltage tolerance. Both devices share the shield's I2C bus. A 5V LCD or its pull-ups must not expose a 3.3V-only sensor to 5V. The shield power switch does not solve that. If you lack a level translator, the exact sensor and LCD version must be checked before sharing their bus. Send clear photos of their front/back and the shield labels. The MPU's header pins must be soldered.
7. After voltage compatibility and wiring are verified, upload `firmware/tests/smartrep_mpu_lcd_test/smartrep_mpu_lcd_test.ino`. The sensor connects to SDA, SCL, common GND and its documented VCC supply. AD0 low selects 0x68; the diagnostic also accepts 0x69. Expect `MPU OK AX:...` on the LCD and acceleration/gyro values in Serial Monitor. This diagnostic tests hardware; it does not count reps.
8. For the actual app upload `firmware/smartrep_arduino_lcd/smartrep_arduino_lcd.ino`. This is the production firmware with LCD enabled. Close Serial Monitor and run the hardware bridge from the project root:

```sh
cd bridge
.venv/bin/python -m smartrep --db smartrep-hardware.db
```

Windows uses `.\.venv\Scripts\python.exe`. Do not add --simulate. Follow the main hardware guide for reference calibration. When a real set starts, the bridge sends the participant's name and completed rep count. Screen: first line name (up to 16 ASCII characters), second line `Reps: N`. Green = normal, amber = short/rushed, blue = finished. Short attempts do not increase the completed count.

To test the production LCD text manually before the app, use Serial Monitor at 115200 with Newline and send `LCD|Mary|7|good`. It should show `Mary` / `Reps: 7`. That is a manual screen test, not a detected rep. Close Serial Monitor before starting the bridge.

The LCD uses address 0x3E; RGB backlight is typically 0x62 (older) or 0x30 (V5). Those do not conflict with MPU addresses 0x68/0x69. An I2C scan with only the screen connected should normally find its text controller and backlight controller.

Verification: all three LCD sketches compile for UNO R4 Minima, Renesas UNO core 1.6.0, Seeed RGB LCD library 1.0.2. Physical screen and sensor tests remain to be performed. The original `smartrep_arduino.ino` keeps LCD disabled by default so sensor-only builds do not need the library.

Official wiring/library reference: https://wiki.seeedstudio.com/Grove-LCD_RGB_Backlight/
