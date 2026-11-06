/* SmartRep main controller. Sensor acquisition and station status only.
   Upload to UNO R4 Minima; UNO R3 also works with SENSOR_ADXL335.
   The bridge owns participant data, calibration and rep detection. */
#include <Wire.h>
#include <ctype.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

// Set to 1 for the optional Grove LCD (install Seeed rgb_lcd library).
#define SMARTREP_LCD 0
#if SMARTREP_LCD
#include <rgb_lcd.h>
#endif

#define DEVICE_ID "clip-01"
#define FW_VERSION "1.0.0"
#define SENSOR_MPU6050
// For the optional UNO R3 glove, replace the line above with SENSOR_ADXL335.
#define ADXL_AXES 3
const uint8_t STATUS_RED_PIN=9, STATUS_GREEN_PIN=10, STATUS_BLUE_PIN=11, MPU_ADDR=0x68;
const uint32_t SAMPLE_US=20000, COMMAND_TIMEOUT_MS=10000;
struct LinkState { char buffer[64]; uint8_t used; bool overflow; bool streaming; uint32_t lastCommand; };
LinkState usb={};
#if defined(ARDUINO_UNOR4_MINIMA)
LinkState modem={};
#endif
bool sensorOK=false;
uint8_t failures=0, wifiState=0;
uint32_t i2cErrors=0, nextSample=0, lastInfo=0, lastInit=0;


#if SMARTREP_LCD
rgb_lcd lcd;
bool lcdReady=false;
char displayName[17]="", displayLine[17]="";
void lcdRow(uint8_t row,const char *text){
  lcd.setCursor(0,row);
  for(uint8_t i=0;i<16;i++)lcd.write(text[i]?text[i]:' ');
}
void initLCD(){
  Wire.beginTransmission(0x3E);
  lcdReady=Wire.endTransmission()==0;
  if(lcdReady){
    lcd.begin(16,2);Wire.setClock(100000);lcd.setRGB(160,160,160);
    strcpy(displayName,"SmartRep        ");
    strcpy(displayLine,"Ready for a set ");
    lcdRow(0,displayName);lcdRow(1,displayLine);
  }
}
bool displayCommand(char *cmd){
  // LCD|name|completed-reps|quality. The bridge supplies the authoritative count.
  if(strncmp(cmd,"LCD|",4)!=0)return false;
  char *name=cmd+4,*separator=strchr(name,'|');
  if(!separator)return true;
  *separator=0;char *count=separator+1;
  separator=strchr(count,'|');if(!separator)return true;
  *separator=0;const char *quality=separator+1;
  if(!lcdReady)return true;
  char padded[17];memset(padded,' ',16);padded[16]=0;
  for(uint8_t i=0;i<16&&name[i];i++)padded[i]=name[i];
  if(strcmp(displayName,padded)){strcpy(displayName,padded);lcdRow(0,displayName);}
  char next[17];memset(next,0,sizeof(next));
  snprintf(next,sizeof(next),"Reps: %u",(unsigned)atoi(count));
  // Pad before comparing, so old digits disappear without clearing/flickering.
  uint8_t length=strlen(next);for(uint8_t i=length;i<16;i++)next[i]=' ';
  next[16]=0;
  if(strcmp(displayLine,next)){strcpy(displayLine,next);lcdRow(1,displayLine);}
  if(!strcmp(quality,"short")||!strcmp(quality,"rushed"))lcd.setRGB(220,130,0);
  else if(!strcmp(quality,"done"))lcd.setRGB(50,100,220);
  else lcd.setRGB(40,170,60);
  return true;
}
#endif

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
  uint8_t who=0;
  return readRegisters(0x75,1,&who)&&who==0x68&&writeRegister(0x6B,0)&&
    writeRegister(0x1A,3)&&writeRegister(0x1B,8)&&writeRegister(0x1C,8);
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
  out.print(F(",\"i2c_err\":"));out.print(i2cErrors);out.println('}');
}
void command(Stream &out,LinkState &link){
  char *cmd=link.buffer;
#if SMARTREP_LCD
  if(displayCommand(cmd))return;
#endif
  for(uint8_t i=0;cmd[i];i++)cmd[i]=(char)toupper((unsigned char)cmd[i]);
  link.lastCommand=millis();
  if(!strcmp(cmd,"HELLO"))identity(out,"hello");
  else if(!strcmp(cmd,"PING")){out.print(F("{\"t\":\"pong\",\"ms\":"));out.print(millis());out.println('}');}
  else if(!strcmp(cmd,"START")){
    if(sensorOK){link.streaming=true;out.println(F("{\"t\":\"ack\",\"cmd\":\"START\"}"));}
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
  if(usb.streaming)Serial.println(line);
#if defined(ARDUINO_UNOR4_MINIMA)
  if(modem.streaming)Serial1.println(line);
#endif
}
void setup(){
  pinMode(STATUS_RED_PIN,OUTPUT);pinMode(STATUS_GREEN_PIN,OUTPUT);pinMode(STATUS_BLUE_PIN,OUTPUT);pinMode(LED_BUILTIN,OUTPUT);
  Serial.begin(115200);
#if defined(ARDUINO_UNOR4_MINIMA)
  Serial1.begin(115200);analogReadResolution(14);
#endif
  // No while(!Serial): the station must boot on its own power adapter.
  Wire.begin();Wire.setClock(100000);
#if defined(ARDUINO_UNOR4_MINIMA) || defined(WIRE_HAS_TIMEOUT)
  Wire.setWireTimeout(25000,true);
#endif
#if SMARTREP_LCD
  initLCD();
#endif
  sensorOK=initSensor();lastInit=millis();nextSample=micros();
}
void loop(){
  pollLink(Serial,usb);
#if defined(ARDUINO_UNOR4_MINIMA)
  pollLink(Serial1,modem);
  if((uint32_t)(millis()-lastInfo)>=2000){lastInfo=millis();identity(Serial1,"info");}
#endif
  if(!sensorOK&&(uint32_t)(millis()-lastInit)>=2000){lastInit=millis();sensorOK=initSensor();}
  // A fixed micros deadline avoids drift. Skip a missed deadline instead of
  // flooding the bridge with repeated samples after a sensor timeout.
  if((int32_t)(micros()-nextSample)>=0){
    nextSample+=SAMPLE_US;
    if((int32_t)(micros()-nextSample)>=0)nextSample=micros()+SAMPLE_US;
    if(sensorOK)sample();
  }
  statusLight();
}
