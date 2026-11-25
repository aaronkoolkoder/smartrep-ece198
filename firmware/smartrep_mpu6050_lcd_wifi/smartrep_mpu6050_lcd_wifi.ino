/* UNO R4 Minima: MPU6050, I2C LCD backpack, Grove buzzer on D2.
   Serial1 at 115200: D1 TX via 1k/2k divider -> ESP32 GPIO16;
   D0 RX <- ESP32 GPIO17, shared GND. Both boards have their own USB power.
   Install hd44780 by Bill Perry. The bridge owns calibration and counts. */
#include <Wire.h>
#include <ctype.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#include <hd44780.h>
#include <hd44780ioClass/hd44780_I2Cexp.h>
const uint8_t BUZZER_PIN=2;
uint32_t buzzUntil=0;
long displayedReps=0;
char participantName[17]="";
bool wasCalibrating=false;
bool calibrationBeeped=false;
hd44780_I2Cexp lcd;
bool lcdReady=false;

#define DEVICE_ID "clip-01"
#define FW_VERSION "1.2.2"
#define SENSOR_MPU6050
// For the optional UNO R3 glove, replace the line above with SENSOR_ADXL335.
#define ADXL_AXES 3
const uint8_t STATUS_RED_PIN=9, STATUS_GREEN_PIN=10, STATUS_BLUE_PIN=11;
uint8_t MPU_ADDR=0x68;
const uint32_t SAMPLE_US=20000, COMMAND_TIMEOUT_MS=10000;
struct LinkState { char buffer[64]; uint8_t used; bool overflow; bool streaming; uint32_t lastCommand; bool diagnostic; };
LinkState usb={};
#if defined(ARDUINO_UNOR4_MINIMA)
LinkState modem={};
#endif
bool sensorOK=false, identityVerified=false;
uint8_t sensorIdentity=0;
uint8_t failures=0, wifiState=0;
uint32_t i2cErrors=0, nextSample=0, lastInfo=0, lastInit=0, lastRawSample=0;


void row(uint8_t number, const char *text) {
  if (!lcdReady) return;
  lcd.setCursor(0,number);
  uint8_t length=strlen(text);
  for(uint8_t i=0;i<16;i++) lcd.write(i<length?text[i]:' ');
}
void initLCD(){
  lcdReady=lcd.begin(16,2)==0;
  Wire.setClock(50000);
  row(0,"SmartRep MPU6050");
  row(1,"Checking sensor");
}
bool displayCommand(char *cmd){
  if(strncmp(cmd,"LCD|",4)) return false;
    char *name=cmd+4;
    char *count=strchr(name,'|');
    if(!count) return true;
    *count++=0;
    char *quality=strchr(count,'|');
    if(!quality) return true;
    *quality++=0;
    bool calibrating=!strncmp(quality,"cal",3);
    bool samePerson=!strncmp(participantName,name,16);
    strncpy(participantName,name,16); participantName[16]=0;
    row(0,name);
    char line[17];
    long reps=atol(count);
    if(reps<0) reps=0;
    if(reps>999999) reps=999999;
    if(!samePerson || !calibrating || reps==0) calibrationBeeped=false;
    bool repCompleted=samePerson && !calibrating && !wasCalibrating &&
        reps==displayedReps+1 && (!strcmp(quality,"good") || !strcmp(quality,"rushed") || !strcmp(quality,"slow"));
    bool calibrationReady=!strcmp(quality,"cal_ready") && !calibrationBeeped;
    if(repCompleted || calibrationReady) {
      tone(BUZZER_PIN,2000,80);
      buzzUntil=millis()+80;
      if(calibrationReady) calibrationBeeped=true;
    }
    displayedReps=reps;
    wasCalibrating=calibrating;
    if(!strcmp(quality,"cal_ready")) strcpy(line,"3 reps captured");
    else if(!strcmp(quality,"cal_saved")) strcpy(line,"Reference saved");
    else if(!strcmp(quality,"cal_error")) strcpy(line,"Retry in app");
    else if(calibrating) snprintf(line,sizeof(line),"Cal reps: %ld",reps);
    else snprintf(line,sizeof(line),"Reps: %ld",reps);
    row(1,line);
  return true;
}

bool writeRegister(uint8_t reg,uint8_t value){
  Wire.beginTransmission(MPU_ADDR); Wire.write(reg); Wire.write(value);
  return Wire.endTransmission()==0;
}
bool readRegisters(uint8_t reg,uint8_t count,uint8_t *buffer){
  Wire.beginTransmission(MPU_ADDR); Wire.write(reg);
  if(Wire.endTransmission(false)!=0)return false;
  if(Wire.requestFrom((uint8_t)MPU_ADDR,(uint8_t)count)!=(size_t)count)return false;
  for(uint8_t i=0;i<count;i++)buffer[i]=(uint8_t)Wire.read();
  return true;
}
bool initSensor(){
#ifdef SENSOR_MPU6050
  for(uint8_t address=0x68;address<=0x69;address++){
    MPU_ADDR=address;
    uint8_t who=0;
    // This project's board is used as an MPU6050; identity is informational.
    if(!readRegisters(0x75,1,&who))continue;
    sensorIdentity=who;identityVerified=who==0x68;
    uint8_t data[14];
    if(writeRegister(0x6B,0)&&writeRegister(0x1A,3)&&writeRegister(0x1B,8)&&
       writeRegister(0x1C,8)&&readRegisters(0x3B,14,data))return true;
  }
  return false;
#else
  return true;
#endif
}
void identity(Stream &out,const char *type){
  out.print(F("{\"t\":\""));out.print(type);out.print(F("\",\"device\":\"" DEVICE_ID "\",\"fw\":\"" FW_VERSION "\",\"sensor\":\""));
#ifdef SENSOR_MPU6050
  out.print(F("mpu6050\",\"hz\":50,\"units\":\"mpu6050_4g_500dps\""));
#else
  #if defined(ARDUINO_UNOR4_MINIMA)
  out.print(F("adxl335\",\"hz\":50,\"units\":\"counts14\""));
  #else
  out.print(F("adxl335\",\"hz\":50,\"units\":\"counts10\""));
  #endif
#endif
  out.print(F(",\"who_am_i\":"));out.print(sensorIdentity);
  out.print(F(",\"identity_verified\":"));out.print(identityVerified?"true":"false");
  out.print(F(",\"sensor_ok\":"));out.print(sensorOK?"true":"false");
  out.print(F(",\"lcd_ok\":"));out.print(lcdReady?"true":"false");
  out.print(F(",\"buzzer_pin\":2"));
  out.print(F(",\"i2c_err\":"));out.print(i2cErrors);out.println('}');
}
void rawSample(Stream &out){
  uint8_t bytes[14]={};
  bool ok=readRegisters(0x3B,14,bytes);
  out.print(F("{\"t\":\"raw\",\"ms\":"));out.print(millis());
  out.print(F(",\"ok\":"));out.print(ok?"true":"false");
  out.print(F(",\"bytes\":["));
  for(uint8_t i=0;i<14;i++){if(i)out.print(',');out.print(bytes[i]);}
  out.println(F("]}"));
}
void command(Stream &out,LinkState &link){
  char *cmd=link.buffer;
  link.lastCommand=millis();
  if(displayCommand(cmd))return;
  for(uint8_t i=0;cmd[i];i++)cmd[i]=(char)toupper((unsigned char)cmd[i]);
  if(!strcmp(cmd,"HELLO"))identity(out,"hello");
  else if(!strcmp(cmd,"RAW")){rawSample(out);}
  else if(!strcmp(cmd,"DIAGSTART")){
    link.streaming=true;link.diagnostic=true;nextSample=micros();
    row(0,"Sensor diagnosis");row(1,"Live raw inputs");
  }
  else if(!strcmp(cmd,"SCAN")){
    out.print(F("{\"t\":\"scan\",\"addresses\":["));
    bool first=true;
    for(uint8_t address=8;address<120;address++){
      Wire.beginTransmission(address);
      if(Wire.endTransmission()==0){if(!first)out.print(',');out.print(address);first=false;}
    }
    out.println(F("]}"));
    for(uint8_t address=0x68;address<=0x69;address++){
      MPU_ADDR=address;uint8_t who=0;bool ok=readRegisters(0x75,1,&who);
      out.print(F("{\"t\":\"probe\",\"address\":"));out.print(address);
      out.print(F(",\"read_ok\":"));out.print(ok?"true":"false");
      out.print(F(",\"who_am_i\":"));out.print(who);out.println('}');
    }
    sensorOK=initSensor();
  }
  else if(!strcmp(cmd,"BUZZTEST")){
    tone(BUZZER_PIN,2000,1000);buzzUntil=millis()+1000;
    out.println(F("{\"t\":\"info\",\"msg\":\"D2 tone test 1000ms\"}"));
  }
  else if(!strcmp(cmd,"TEST")){
    row(0,"LCD test OK");
    row(1,sensorOK?"MPU OK / buzz D2":"MPU not found");
    tone(BUZZER_PIN,2000,120);buzzUntil=millis()+120;
    identity(out,"info");
  }
  else if(!strcmp(cmd,"PING")){out.print(F("{\"t\":\"pong\",\"ms\":"));out.print(millis());out.println('}');}
  else if(!strcmp(cmd,"START")){
    if(sensorOK){link.diagnostic=false;link.streaming=true;out.println(F("{\"t\":\"ack\",\"cmd\":\"START\"}"));}
    else out.println(F("{\"t\":\"err\",\"msg\":\"MPU-6050 not found\"}"));
  }else if(!strcmp(cmd,"STOP")){link.streaming=false;out.println(F("{\"t\":\"ack\",\"cmd\":\"STOP\"}"));}
  else if(!strcmp(cmd,"@WIFI CONNECTING"))wifiState=1;
  else if(!strcmp(cmd,"@WIFI UP"))wifiState=2;
  else if(!strcmp(cmd,"@WIFI BRIDGE"))wifiState=3;
  else if(!strcmp(cmd,"@WIFI DOWN"))wifiState=0;
}
void pollLink(Stream &out,LinkState &link){
  while(out.available()){
    char c=(char)out.read();
    if(c=='\r')continue;
    if(c=='\n'){
      if(!link.overflow){link.buffer[link.used]=0;command(out,link);}
      link.used=0;link.overflow=false;
    }else if(link.used<sizeof(link.buffer)-1&&!link.overflow)link.buffer[link.used++]=c;
    else link.overflow=true;
  }
  if((uint32_t)(millis()-link.lastCommand)>COMMAND_TIMEOUT_MS)link.streaming=false;
}
void statusLight(){
  uint32_t now=millis();bool streaming=usb.streaming;
#if defined(ARDUINO_UNOR4_MINIMA)
  streaming|=modem.streaming;
#endif
  uint8_t red=0,green=0,blue=0;
  if(!sensorOK)red=(now/250)%2?90:0;
  else if(streaming)green=35;
  else if(wifiState==3||(usb.lastCommand&&now-usb.lastCommand<10000))blue=(now%1000<500)?(now%500)/8:(500-now%500)/8;
  else if(wifiState==1||wifiState==2)blue=(now/150)%2?60:0;
  else red=now%3000<100?60:0;
  analogWrite(STATUS_RED_PIN,red);analogWrite(STATUS_GREEN_PIN,green);analogWrite(STATUS_BLUE_PIN,blue);
  digitalWrite(LED_BUILTIN,(now/500)%2);
}
void sample(){
  char line[180];
#ifdef SENSOR_MPU6050
  uint8_t bytes[14];
  if(!readRegisters(0x3B,14,bytes)){
    i2cErrors++;failures++;
    if(failures>=5){
      sensorOK=initSensor();failures=0;
      Serial.println(F("{\"t\":\"err\",\"msg\":\"sensor read failed, re-initialising\"}"));
#if defined(ARDUINO_UNOR4_MINIMA)
      Serial1.println(F("{\"t\":\"err\",\"msg\":\"sensor read failed, re-initialising\"}"));
#endif
    }
    return;
  }
  failures=0;int16_t a[6];
  for(uint8_t i=0;i<3;i++)a[i]=(int16_t)((uint16_t)bytes[i*2]<<8|bytes[i*2+1]);
  for(uint8_t i=0;i<3;i++)a[i+3]=(int16_t)((uint16_t)bytes[8+i*2]<<8|bytes[9+i*2]);
  snprintf(line,sizeof(line),"{\"t\":\"s\",\"ms\":%lu,\"ax\":%d,\"ay\":%d,\"az\":%d,\"gx\":%d,\"gy\":%d,\"gz\":%d}",(unsigned long)millis(),a[0],a[1],a[2],a[3],a[4],a[5]);
#else
  int x=analogRead(A0),y=analogRead(A1),z=ADXL_AXES==3?analogRead(A2):0;
  snprintf(line,sizeof(line),"{\"t\":\"s\",\"ms\":%lu,\"x\":%d,\"y\":%d,\"z\":%d}",(unsigned long)millis(),x,y,z);
#endif
  if(usb.streaming&&!usb.diagnostic)Serial.println(line);
#if defined(ARDUINO_UNOR4_MINIMA)
  if(modem.streaming&&!modem.diagnostic)Serial1.println(line);
#endif
}
void setup(){
  pinMode(BUZZER_PIN,OUTPUT);digitalWrite(BUZZER_PIN,LOW);
  pinMode(STATUS_RED_PIN,OUTPUT);pinMode(STATUS_GREEN_PIN,OUTPUT);pinMode(STATUS_BLUE_PIN,OUTPUT);pinMode(LED_BUILTIN,OUTPUT);
  Serial.begin(115200);
#if defined(ARDUINO_UNOR4_MINIMA)
  Serial1.begin(115200);analogReadResolution(14);
#endif
  // No while(!Serial): the station must boot on its own power adapter.
  Wire.begin();Wire.setClock(50000);
#if defined(ARDUINO_UNOR4_MINIMA) || defined(WIRE_HAS_TIMEOUT)
  Wire.setWireTimeout(25000,true);
#endif
  initLCD();
  sensorOK=initSensor();lastInit=millis();nextSample=micros();
  row(1,sensorOK?"MPU OK / connect":"MPU not found");
}
void loop(){
  if(buzzUntil&&(int32_t)(millis()-buzzUntil)>=0){noTone(BUZZER_PIN);digitalWrite(BUZZER_PIN,LOW);buzzUntil=0;}
  pollLink(Serial,usb);
#if defined(ARDUINO_UNOR4_MINIMA)
  pollLink(Serial1,modem);
  if((uint32_t)(millis()-lastInfo)>=2000){lastInfo=millis();identity(Serial1,"info");identity(Serial,"info");}
#endif
  if(!sensorOK&&(uint32_t)(millis()-lastInit)>=2000){lastInit=millis();sensorOK=initSensor();}
  // A fixed micros deadline avoids drift. Skip a missed deadline instead of
  // flooding the bridge with repeated samples after a sensor timeout.
  if((int32_t)(micros()-nextSample)>=0){
    nextSample+=SAMPLE_US;
    if((int32_t)(micros()-nextSample)>=0)nextSample=micros()+SAMPLE_US;
    if(sensorOK)sample();
    if((uint32_t)(millis()-lastRawSample)>=100){
      lastRawSample=millis();
      if(usb.streaming&&usb.diagnostic)rawSample(Serial);
#if defined(ARDUINO_UNOR4_MINIMA)
      if(modem.streaming&&modem.diagnostic)rawSample(Serial1);
#endif
    }
  }
  statusLight();
}
