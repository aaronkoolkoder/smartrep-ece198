// LCD ONLY test. Disconnect the MPU for this first display check.
// Grove LCD RGB Backlight -> a Grove Base Shield port labelled I2C.
// Install "Grove - LCD RGB Backlight" by Seeed Studio, version 1.0.2+.
#include <Wire.h>
#include <rgb_lcd.h>
rgb_lcd lcd;
bool screenReady = false;
uint32_t nextCheck = 0;
void setup() {
  Serial.begin(115200);
  Wire.begin(); Wire.setClock(100000);
  Wire.setWireTimeout(25000, true);
}
void loop() {
  if ((int32_t)(millis() - nextCheck) < 0) return;
  nextCheck = millis() + 3000;
  Wire.beginTransmission(0x3E);
  if (Wire.endTransmission() != 0) {
    Serial.println("LCD not found at 0x3E. Check I2C port and power.");
    screenReady = false; return;
  }
  if (!screenReady) {
    lcd.begin(16, 2); Wire.setClock(100000);
    lcd.setRGB(80, 180, 100);
    lcd.setCursor(0, 0); lcd.print("SmartRep LCD OK ");
    lcd.setCursor(0, 1); lcd.print("Screen test only");
    screenReady = true;
  }
  Serial.println("PASS: LCD responds at 0x3E.");
}
