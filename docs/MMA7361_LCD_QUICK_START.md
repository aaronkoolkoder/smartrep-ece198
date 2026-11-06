# SmartRep: MMA7361 + I2C LCD

Board: UNO R4 Minima. Install **hd44780 by Bill Perry** in Arduino Library Manager.
Upload `firmware/smartrep_mma7361_lcd/smartrep_mma7361_lcd.ino`.

With USB unplugged, wire:

| Module pin | Arduino |
|---|---|
| MMA 3V3 and Sleep | 3.3V |
| MMA GND, g-Select and Selftest | GND |
| MMA X, Y, Z | A0, A1, A2 |
| LCD VCC | 5V |
| LCD GND | GND (shared with MMA) |
| LCD SDA, SCL | SDA, SCL |

Leave MMA 5V and 0g-Detect empty. Keep the sensor firmly attached to the moving object.

Close Arduino Serial Monitor. Stop any running simulation server before launching
**start-smartrep-hardware.command**. It serves the same port 8000 using a separate
hardware database, with USB auto-detection. Do not run both launchers simultaneously.

Open http://127.0.0.1:8000/app and refresh. The badge should say HARDWARE MODE.
The Arduino is clip-01, mapped to **Dumbbells · 5 lb**, station code **db-5lb**.
Participant **123129** is the sample person **Mary**. Switch participants using the
account button if needed. Names are sample data; the LCD shows up to 16 ASCII characters.

First, open **Staff setup**, participant **123129**, PIN **0000**, then **Bicep curl**.
Do three slow full movements, finishing at the starting position, and save the reference.
Calibrate again after changing the sensor mounting or exercise. This accelerometer
measures acceleration/gravity; it has no gyro or absolute position tracking.

Then choose **Scan a station → Dumbbells · 5 lb → Bicep curl → Start set**.
LCD line 1 shows the participant name; line 2 shows **Reps: 0** and updates from the
same app counter. Short movements do not increment completed reps. Finish the set
in the app to save it. During calibration, the app and LCD show detected reps, with a beep per detection.
The LCD shows whether saving succeeded.

If the station is offline, close Serial Monitor, check USB, and wait a few seconds.
If the LCD is blank, adjust its contrast screw. For LCD connection diagnostics,
run Arduino's hd44780 → ioClass → hd44780_I2Cexp → I2CexpDiag example, then restore
this firmware. Firmware compilation and software integration tests do not validate
physical wiring or movement quality.

## Start without Terminal commands

Double-click **Start SmartRep.command** in the project folder. It starts the
small-movement hardware demo, creates a phone link, and opens its QR code.
Keep its Terminal window open and the laptop awake. Close Arduino Serial Monitor.
Press Control+C in that window to stop. Each launch can produce a new phone link.
The separate normal hardware and simulation launchers remain available.

On another Mac, set up the Python environment from README.md and install
cloudflared first; the local copy of that binary is not stored in Git.
