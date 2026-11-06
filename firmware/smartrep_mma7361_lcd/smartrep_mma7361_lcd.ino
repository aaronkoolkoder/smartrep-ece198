/* UNO R4 Minima: MMA7361 + standard I2C 16x2 LCD backpack.
   Install hd44780 by Bill Perry. The app owns calibration and rep counts.
   MMA: 3V3 + Sleep -> 3.3V; GND + g-Select + Selftest -> GND;
   X/Y/Z -> A0/A1/A2. LCD: VCC -> 5V, GND -> GND, SDA/SCL -> SDA/SCL.
   Leave MMA 5V and 0g-Detect unconnected. */
#include <Wire.h>
#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>
#include <stdlib.h>
#include <string.h>

const uint8_t BUZZER_PIN=6;
uint32_t buzzUntil=0;
long displayedReps=0;
char participantName[17]="";
bool wasCalibrating=false;
hd44780_I2Cexp lcd;
bool lcdReady=false, streaming=false, overflow=false;
char commandBuffer[96];
uint8_t used=0;
uint32_t nextSample=0, lastCommand=0;

void row(uint8_t number, const char *text) {
  if (!lcdReady) return;
  lcd.setCursor(0,number);
  uint8_t length=strlen(text);
  for(uint8_t i=0;i<16;i++) lcd.write(i<length?text[i]:' ');
}
void hello() {
  Serial.println(F("{\"t\":\"hello\",\"device\":\"clip-01\",\"sensor\":\"mma7361\",\"units\":\"mma7361_counts12\",\"hz\":50,\"fw\":\"1.0.0\"}"));
}
void command() {
  lastCommand=millis();
  if(!strcmp(commandBuffer,"HELLO")) hello();
  else if(!strcmp(commandBuffer,"PING")) Serial.println(F("{\"t\":\"pong\"}"));
  else if(!strcmp(commandBuffer,"START")) {
    streaming=true;
    nextSample=micros();
    Serial.println(F("{\"t\":\"ack\",\"cmd\":\"START\"}"));
  } else if(!strcmp(commandBuffer,"STOP")) {
    streaming=false;
    Serial.println(F("{\"t\":\"ack\",\"cmd\":\"STOP\"}"));
  } else if(!strncmp(commandBuffer,"LCD|",4)) {
    char *name=commandBuffer+4;
    char *count=strchr(name,'|');
    if(!count) return;
    *count++=0;
    char *quality=strchr(count,'|');
    if(!quality) return;
    *quality++=0;
    bool calibrating=!strncmp(quality,"cal",3);
    // Buzz only when the count increases within the same mode.
    bool samePerson=!strncmp(participantName,name,16);
    strncpy(participantName,name,16); participantName[16]=0;
    row(0,name);
    char line[17];
    long reps=atol(count);
    if(reps<0) reps=0;
    if(reps>999999) reps=999999;
    if(samePerson && calibrating==wasCalibrating && reps>displayedReps) {
      digitalWrite(BUZZER_PIN,HIGH);
      buzzUntil=millis()+120;
    }
    displayedReps=reps;
    wasCalibrating=calibrating;
    if(!strcmp(quality,"cal_saved")) strcpy(line,"Reference saved");
    else if(!strcmp(quality,"cal_error")) strcpy(line,"Retry in app");
    else if(calibrating) snprintf(line,sizeof(line),"Cal reps: %ld",reps);
    else snprintf(line,sizeof(line),"Reps: %ld",reps);
    row(1,line);
  }
}
int readAxis(uint8_t pin) {
  analogRead(pin);
  delayMicroseconds(200);
  uint32_t total=0;
  for(uint8_t i=0;i<8;i++) total+=analogRead(pin);
  return (total+4)/8;
}
void setup() {
  pinMode(BUZZER_PIN,OUTPUT);
  digitalWrite(BUZZER_PIN,LOW);
  Serial.begin(115200);
  analogReadResolution(12);
  Wire.begin();
  lcdReady=(lcd.begin(16,2)==0);
  row(0,"SmartRep");
  row(1,"Connect the app");
  pinMode(LED_BUILTIN,OUTPUT);
}
void loop() {
  if(buzzUntil && (int32_t)(millis()-buzzUntil)>=0) {
    digitalWrite(BUZZER_PIN,LOW);
    buzzUntil=0;
  }
  // Limit serial processing to keep sampling on schedule.
  for(uint8_t n=0;n<96 && Serial.available();n++) {
    char c=Serial.read();
    if(c=='\r') continue;
    if(c=='\n') {
      if(!overflow) {commandBuffer[used]=0; command();}
      used=0; overflow=false;
    } else if(!overflow && used<sizeof(commandBuffer)-1) commandBuffer[used++]=c;
    else overflow=true;
  }
  if(streaming && (uint32_t)(millis()-lastCommand)>10000) {
    streaming=false;
    row(1,"App disconnected");
  }
  if(streaming && (int32_t)(micros()-nextSample)>=0) {
    nextSample+=20000;
    if((int32_t)(micros()-nextSample)>=0) nextSample=micros()+20000;
    uint32_t ms=millis();
    int x=readAxis(A0), y=readAxis(A1), z=readAxis(A2);
    Serial.print(F("{\"t\":\"s\",\"ms\":")); Serial.print(ms);
    Serial.print(F(",\"x\":")); Serial.print(x);
    Serial.print(F(",\"y\":")); Serial.print(y);
    Serial.print(F(",\"z\":")); Serial.print(z);
    Serial.println('}');
  }
  digitalWrite(LED_BUILTIN,streaming?HIGH:((millis()/1000)%2));
}
