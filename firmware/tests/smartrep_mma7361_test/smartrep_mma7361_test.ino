// UNO R4 Minima + MMA7361 ANALOG sensor test. No libraries needed.
// X -> A0, Y -> A1, Z -> A2. Sensor power/control pins use 3.3V.
// SL/SLEEP -> 3.3V (awake), GS/g-Select -> GND (+/-1.5g), ST -> GND.
// Confirm the breakout's actual power-input labels before wiring its supply.
const float ADC_REFERENCE = 5.0;  // Approximate default R4 ADC reference.
const float ADC_MAXIMUM = 16383.0;
uint32_t nextPrint = 0;
float readAverage(uint8_t pin) {
  analogRead(pin);  // Discard first conversion after changing channels.
  delayMicroseconds(200);
  uint32_t total = 0;
  for (uint8_t i = 0; i < 16; i++) {
    total += analogRead(pin);
    delayMicroseconds(200);
  }
  return total / 16.0;
}
void setup() {
  Serial.begin(115200);
  analogReadResolution(14);
  pinMode(LED_BUILTIN, OUTPUT);
}
void loop() {
  digitalWrite(LED_BUILTIN, (millis() / 500) % 2);
  if ((int32_t)(millis() - nextPrint) < 0) return;
  nextPrint = millis() + 250;
  float x = readAverage(A0), y = readAverage(A1), z = readAverage(A2);
  Serial.print("Raw X="); Serial.print(x, 0);
  Serial.print(" Y="); Serial.print(y, 0);
  Serial.print(" Z="); Serial.print(z, 0);
  Serial.print(" | Approx volts X=");
  Serial.print(x * ADC_REFERENCE / ADC_MAXIMUM, 3);
  Serial.print(" Y="); Serial.print(y * ADC_REFERENCE / ADC_MAXIMUM, 3);
  Serial.print(" Z="); Serial.println(z * ADC_REFERENCE / ADC_MAXIMUM, 3);
}
