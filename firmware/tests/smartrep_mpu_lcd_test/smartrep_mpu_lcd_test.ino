// COMBINED TEST: UNO R4 Minima, MPU-6050, Grove LCD RGB Backlight.
// Share I2C only after the sensor breakout/bus voltages are verified.
// Solder the MPU headers. This sketch displays motion; it does not count reps.
#include <Wire.h>
#include <rgb_lcd.h>
rgb_lcd lcd;
uint8_t sensorAddress = 0;
bool lcdReady = false, sensorReady = false;
uint32_t nextRead = 0, nextRetry = 0;
bool present(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}
bool writeReg(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(sensorAddress);
  Wire.write(reg); Wire.write(value);
  return Wire.endTransmission() == 0;
}
bool readReg(uint8_t reg, uint8_t n, uint8_t *out) {
  Wire.beginTransmission(sensorAddress); Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(sensorAddress, n) != n) return false;
  for (uint8_t i = 0; i < n; i++) out[i] = Wire.read();
  return true;
}
int16_t signed16(const uint8_t *p) {
  return (int16_t)(((uint16_t)p[0] << 8) | p[1]);
}
void row(uint8_t r, const char *text) {
  if (!lcdReady) return;
  lcd.setCursor(0, r);
  for (uint8_t i = 0; i < 16; i++) {
    if (*text) lcd.write(*text++); else lcd.write(' ');
  }
}
void discover() {
  if (!lcdReady && present(0x3E)) {
    lcd.begin(16, 2); Wire.setClock(100000);
    lcdReady = true; row(0, "LCD connected");
    Serial.println("LCD found at 0x3E");
  }
  if (!sensorReady) {
    sensorAddress = present(0x68) ? 0x68 : present(0x69) ? 0x69 : 0;
    uint8_t who = 0;
    sensorReady = sensorAddress && readReg(0x75, 1, &who) && who == 0x68 &&
      writeReg(0x6B, 0) && writeReg(0x1A, 3) &&
      writeReg(0x1B, 8) && writeReg(0x1C, 8);
  }
  if (lcdReady) lcd.setRGB(sensorReady ? 40 : 220, sensorReady ? 170 : 30, 30);
  if (!sensorReady) {
    row(0, "MPU not found"); row(1, "Check wiring");
    Serial.println("FAIL: MPU not detected; check soldered pins and wiring.");
  }
  if (!lcdReady) Serial.println("LCD not detected at 0x3E.");
}
void setup() {
  Serial.begin(115200); Wire.begin(); Wire.setClock(100000);
  Wire.setWireTimeout(25000, true);
}
void loop() {
  if ((int32_t)(millis() - nextRetry) >= 0) {
    nextRetry = millis() + 3000; discover();
  }
  if (!sensorReady || (int32_t)(millis() - nextRead) < 0) return;
  nextRead = millis() + 250;
  uint8_t data[14];
  if (!readReg(0x3B, 14, data)) {
    sensorReady = false; Serial.println("Sensor read failed."); return;
  }
  float ax = signed16(data) / 8192.0;
  float ay = signed16(data + 2) / 8192.0;
  float az = signed16(data + 4) / 8192.0;
  Serial.print("PASS accel_g: "); Serial.print(ax, 3);
  Serial.print(", "); Serial.print(ay, 3);
  Serial.print(", "); Serial.print(az, 3);
  Serial.print(" | gyro_dps: ");
  for (uint8_t i = 0; i < 3; i++) {
    Serial.print(signed16(data + 8 + 2 * i) / 65.5, 2);
    Serial.print(i < 2 ? ", " : "\n");
  }
  char top[17], bottom[17];
  snprintf(top, sizeof(top), "MPU OK AX:%+.2fg", ax);
  snprintf(bottom, sizeof(bottom), "Y:%+.2f Z:%+.2f", ay, az);
  row(0, top); row(1, bottom);
}
