/* Transparent Arduino UART <-> Wi-Fi WebSocket modem.
   ESP32 DevKitC / WROOM-32U. Attach its external antenna before powering.
   Library: WebSockets by Markus Sattler. Copy config.example.h to config.h. */
#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebSocketsClient.h>
#include "config.h"

WebSocketsClient socket;
char line[256], identity[512], batch[1200];
uint16_t used=0,batchUsed=0;
bool overflow=false,haveIdentity=false,configured=false,bridgeUp=false,uartWasOK=true;
uint32_t lastUART=0,lastFlush=0,lastStatus=0,lastWiFiTry=0;
uint8_t batchLines=0;

void tellArduino(const char *message){Serial2.println(message);Serial.println(message);}
void flushBatch(){
  if(batchUsed&&bridgeUp){batch[batchUsed]=0;socket.sendTXT(batch);}
  batchUsed=0;batchLines=0;lastFlush=millis();
}
void onSocket(WStype_t type,uint8_t *payload,size_t length){
  if(type==WStype_CONNECTED){
    bridgeUp=true;tellArduino("@WIFI BRIDGE");
    // Preserve Arduino identity; append transport metadata, without owning any
    // sensor or participant logic on this modem.
    String hello(identity);hello.replace("\"t\":\"info\"","\"t\":\"hello\"");
    if(hello.endsWith("}"))hello.remove(hello.length()-1);
    hello+=",\"link\":\"wifi\",\"via\":\"esp32\",\"rssi\":"+String(WiFi.RSSI())+",\"mac\":\""+WiFi.macAddress()+"\"}";
    socket.sendTXT(hello);
  }else if(type==WStype_DISCONNECTED){bridgeUp=false;tellArduino("@WIFI DOWN");batchUsed=0;batchLines=0;}
  else if(type==WStype_TEXT){
    Serial2.write(payload,length);Serial2.write('\n');
  }
}
void completeLine(){
  line[used]=0;
  if(strstr(line,"\"t\":\"info\"")){
    strncpy(identity,line,sizeof(identity)-1);identity[sizeof(identity)-1]=0;haveIdentity=true;
  }else if(bridgeUp&&used){
    if(batchUsed+used+2>=sizeof(batch))flushBatch();
    memcpy(batch+batchUsed,line,used);batchUsed+=used;batch[batchUsed++]='\n';batchLines++;
    if(batchLines>=5)flushBatch();
  }
}
void setup(){
  Serial.begin(115200);
  // Both PN2222 level-shifter stages invert their signal. invert=true tells
  // the ESP32 UART to undo the inversion on RX AND TX; Arduino Serial1 stays normal.
  Serial2.begin(115200,SERIAL_8N1,16,17,true);
  WiFi.mode(WIFI_STA);WiFi.setSleep(false);
  tellArduino("@WIFI CONNECTING");WiFi.begin(WIFI_SSID,WIFI_PASSWORD);lastWiFiTry=millis();
  socket.onEvent(onSocket);socket.setReconnectInterval(5000);
}
void loop(){
  while(Serial2.available()){
    char c=(char)Serial2.read();lastUART=millis();
    if(c=='\r')continue;
    if(c=='\n'){if(!overflow)completeLine();used=0;overflow=false;}
    else if(used<sizeof(line)-1&&!overflow)line[used++]=c;
    else overflow=true;
  }
  if(WiFi.status()==WL_CONNECTED){
    if(!configured&&haveIdentity){
      tellArduino("@WIFI UP");MDNS.begin("smartrep-modem");
      IPAddress address=MDNS.queryHost("smartrep");
      String host=address==IPAddress(0,0,0,0)?String(BRIDGE_HOST):address.toString();
      socket.begin(host.c_str(),BRIDGE_PORT,"/device");configured=true;
    }
    if(configured)socket.loop();
  }else if((uint32_t)(millis()-lastWiFiTry)>5000){
    lastWiFiTry=millis();tellArduino("@WIFI CONNECTING");WiFi.reconnect();
  }
  if(batchUsed&&(uint32_t)(millis()-lastFlush)>=100)flushBatch();
  bool uartOK=lastUART&&(uint32_t)(millis()-lastUART)<3000;
  if(!uartOK&&uartWasOK&&bridgeUp)socket.sendTXT("{\"t\":\"err\",\"msg\":\"no data from Arduino\"}");
  uartWasOK=uartOK;
  if(bridgeUp&&(uint32_t)(millis()-lastStatus)>=5000){
    lastStatus=millis();char status[160];
    snprintf(status,sizeof(status),"{\"t\":\"status\",\"rssi\":%d,\"uptime_s\":%lu,\"uart_ok\":%s}",WiFi.RSSI(),(unsigned long)(millis()/1000),uartOK?"true":"false");
    socket.sendTXT(status);
  }
}
