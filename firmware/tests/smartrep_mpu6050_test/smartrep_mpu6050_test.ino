// TEST B: UNO R4 Minima + MPU-6050. Serial Monitor: 115200 baud.
// Change ADDRESS to 0x69 only if Test A found 0x69.
#include <Wire.h>
const uint8_t ADDRESS = 0x68;
bool ready = false;
uint32_t nextSample = 0, nextInit = 0;
bool writeReg(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(ADDRESS);
  Wire.write(reg); Wire.write(value);
  return Wire.endTransmission() == 0;
}
bool readReg(uint8_t reg, uint8_t count, uint8_t *data) {
  Wire.beginTransmission(ADDRESS); Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(ADDRESS, count) != count) return false;
  for (uint8_t i = 0; i < count; i++) data[i] = Wire.read();
  return true;
}
int16_t signed16(const uint8_t *p) {
  return (int16_t)(((uint16_t)p[0] << 8) | p[1]);
}
bool initSensor() {
  uint8_t who = 0;
  if (!readReg(0x75, 1, &who)) {
    Serial.println("FAIL: cannot read sensor. Run Test A.");
    return false;
  }
  Serial.print("WHO_AM_I = 0x"); Serial.println(who, HEX);
  if (who != 0x68) {
    Serial.println("FAIL: unexpected chip ID; confirm sensor model.");
    return false;
  }
  bool ok = writeReg(0x6B, 0) && writeReg(0x1A, 3) &&
            writeReg(0x1B, 8) && writeReg(0x1C, 8);
  if (ok) Serial.println("PASS: MPU-6050 configured; accel g, gyro dps.");
  else Serial.println("FAIL: configuration write failed.");
  return ok;
}
void setup() {
  Serial.begin(115200); pinMode(LED_BUILTIN, OUTPUT);
  Wire.begin(); Wire.setClock(100000);
#if defined(ARDUINO_UNOR4_MINIMA) || defined(WIRE_HAS_TIMEOUT)
  Wire.setWireTimeout(25000, true);
#endif
}
void loop() {
  digitalWrite(LED_BUILTIN, ready ? HIGH : (millis() / 250) % 2);
  if (!ready) {
    if ((int32_t)(millis() - nextInit) < 0) return;
    nextInit = millis() + 3000; ready = initSensor(); return;
  }
  if ((int32_t)(millis() - nextSample) < 0) return;
  nextSample = millis() + 100;  // Readable 10 Hz diagnostic output.
  uint8_t data[14];
  if (!readReg(0x3B, 14, data)) {
    Serial.println("FAIL: sensor read; check cable and power.");
    ready = false; return;
  }
  Serial.print("accel_g: ");
  for (uint8_t i = 0; i < 3; i++) {
    Serial.print(signed16(data + 2 * i) / 8192.0, 3);
    Serial.print(i == 2 ? " | gyro_dps: " : ", ");
  }
  for (uint8_t i = 0; i < 3; i++) {
    Serial.print(signed16(data + 8 + 2 * i) / 65.5, 2);
    if (i < 2) Serial.print(", ");
  }
  Serial.println();
}
