// TEST A: UNO R4 Minima I2C scanner. Serial Monitor: 115200 baud.
// Standalone diagnostic only; do not run the SmartRep bridge with this sketch.
#include <Wire.h>
uint32_t nextScan = 0;
void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  Wire.begin();
  Wire.setClock(100000);
#if defined(ARDUINO_UNOR4_MINIMA) || defined(WIRE_HAS_TIMEOUT)
  Wire.setWireTimeout(25000, true);
#endif
}
void loop() {
  digitalWrite(LED_BUILTIN, (millis() / 500) % 2);
  if ((int32_t)(millis() - nextScan) < 0) return;
  nextScan = millis() + 5000;
  Serial.println("Scanning I2C...");
  uint8_t found = 0;
  for (uint8_t address = 8; address < 120; address++) {
    Wire.beginTransmission(address);
    uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.print("Found device at 0x");
      if (address < 16) Serial.print('0');
      Serial.println(address, HEX);
      found++;
    }
  }
  Serial.print("Devices found: ");
  Serial.println(found);
  Serial.println("MPU-6050 normally appears at 0x68 or 0x69.");
  Serial.println();
}
