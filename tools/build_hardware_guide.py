"""Build the shareable USB station guide from the compiled diagnostic sketches."""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.enums import TA_LEFT

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/pdf/SmartRep_Hardware_Build_Guide.pdf'
INK=colors.HexColor('#173c36');MUTED=colors.HexColor('#526760');LINE=colors.HexColor('#d9e2dc');MINT=colors.HexColor('#e9f2e8');CREAM=colors.HexColor('#f6f7f2');AMBER=colors.HexColor('#fff2d8')
W,H=612,792;L=44;CW=524
c=canvas.Canvas(str(OUT),pagesize=(W,H));c.setTitle('SmartRep Arduino hardware build and test guide');c.setAuthor('SmartRep ECE 198 team')
body=ParagraphStyle('body',fontName='Helvetica',fontSize=10.5,leading=15,textColor=INK,spaceAfter=8)
small=ParagraphStyle('small',parent=body,fontSize=9,leading=12)
cell=ParagraphStyle('cell',parent=body,fontSize=9,leading=12)
y=0;page_number=0

def page(title,subtitle=''):
 global y,page_number
 if page_number:c.showPage()
 page_number+=1
 c.setFillColor(INK);c.rect(0,H-16,W,16,fill=1,stroke=0)
 c.setFont('Helvetica-Bold',9);c.drawString(L,753,'SMARTREP  /  ECE 198')
 c.setFont('Helvetica',9);c.setFillColor(MUTED);c.drawRightString(W-L,753,'BUILD AND TEST  |  NOV 5, 2026')
 c.setFillColor(INK);c.setFont('Helvetica-Bold',22);c.drawString(L,718,title)
 y=695
 if subtitle:para(subtitle,small)
 c.setStrokeColor(LINE);c.line(L,52,W-L,52)
 c.setFont('Helvetica',8);c.setFillColor(MUTED);c.drawString(L,34,'UNO R4 Minima + MPU-6050  |  USB first  |  Student prototype')
 c.drawRightString(W-L,34,f'{page_number} / 8')

def para(text,style=body,gap=7):
 global y
 p=Paragraph(text,style);_,h=p.wrap(CW,1000)
 if y-h<63:raise ValueError(f'Page {page_number} overflow at {text[:40]} y={y} h={h}')
 p.drawOn(c,L,y-h);y-=h+gap

def heading(text):
 global y
 y-=6;c.setFillColor(INK);c.setFont('Helvetica-Bold',12);c.drawString(L,y-12,text);y-=25

def box(text,fill=MINT):
 global y
 p=Paragraph(text,body);_,h=p.wrap(CW-28,1000);h+=24
 if y-h<63:raise ValueError(f'Box overflow page {page_number}')
 c.setFillColor(fill);c.roundRect(L,y-h,CW,h,10,fill=1,stroke=0);p.drawOn(c,L+14,y-h+12);y-=h+13

def table(headers,rows,widths):
 global y
 headstyle=ParagraphStyle('headcell',parent=cell,textColor=colors.white,fontName='Helvetica-Bold')
 data=[[Paragraph(escape(str(v)),headstyle if i==0 else cell) for v in row] for i,row in enumerate([headers]+rows)]
 t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.5,LINE),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,CREAM])]))
 _,h=t.wrap(CW,1000)
 if y-h<63:raise ValueError(f'Table overflow page {page_number} y={y} h={h}')
 t.drawOn(c,L,y-h);y-=h+14

def code(text,size=9,leading=11,top=None):
 global y
 if top is not None:y=top
 lines=text.rstrip().splitlines();height=len(lines)*leading+20
 if y-height<61:raise ValueError(f'Code overflow page {page_number} lines={len(lines)} bottom={y-height}')
 c.setFillColor(CREAM);c.roundRect(L,y-height,CW,height,7,fill=1,stroke=0)
 c.setFillColor(INK);c.setFont('Courier',size)
 for i,line in enumerate(lines):
  if c.stringWidth(line,'Courier',size)>CW-20:raise ValueError(f'Code too wide: {line}')
  c.drawString(L+10,y-13-i*leading,line)
 y-=height+10

page('Build the first physical station','A handoff guide for a teammate. Follow the pages in order; the two diagnostic sketches are complete and copyable.')
box('<b>Goal:</b> get a real MPU-6050 detected, prove its readings change with movement, then upload the SmartRep firmware and count physical reps in the app. Start with USB; the ESP32 is optional.')
heading('What you are building')
para('<b>Sensor on the dumbbell &rarr; Arduino UNO R4 Minima &rarr; USB data cable &rarr; laptop bridge &rarr; phone app and instructor dashboard.</b> The Arduino measures motion. The laptop estimates orientation, calibrates the exercise, counts reps and saves sets.')
heading('Parts and software')
table(['Item','What to prepare'],[
('Arduino','UNO R4 Minima. These instructions are not for an ESP32 or UNO R4 WiFi.'),
('Motion sensor','MPU-6050 breakout, commonly GY-521. Confirm the actual module and its supply/logic ratings.'),
('Signal translation','Bidirectional I2C level converter suitable for 5 V to 3.3 V, with pull-ups on both sides. Needed unless the breakout explicitly supports 5 V I2C.'),
('Basic wiring','Breadboard, short jumpers, USB-C DATA cable, laptop. Multimeter recommended.'),
('Optional later','Common-cathode RGB LED plus three 1 kohm resistors; ESP32 modem only after USB passes.'),
('Software','Arduino IDE 2.x and Arduino UNO R4 Boards package; SmartRep project on the laptop.')],[110,414])
heading('Work in stages')
para('<b>1.</b> Confirm power and wire the sensor (page 2). <b>2.</b> Upload Test A and find its I2C address (page 3). <b>3.</b> Upload Test B and verify motion readings (pages 4-5). <b>4.</b> Upload production firmware and calibrate the app (page 6). <b>5.</b> Mount the sensor and record a ten-rep trial (pages 7-8).')
para('<b>Verification:</b> both test sketches compile for UNO R4 Minima with Arduino Renesas UNO core 1.6.0. No physical board or sensor has been tested by the author. Compilation does not establish correct wiring or real-world accuracy.',small)

page('Wire power and I2C first','Unplug USB before changing wiring. Use short jumpers for this first test. References [1]-[3] are on page 8.')
box('<b>Power decision:</b> the Arduino uses 5 V logic; the bare MPU-6050 is a lower-voltage device. Check your exact breakout documentation. A regulator on a module does not automatically make SDA/SCL 5 V tolerant. If the module is unidentified, stop and send clear photos of both sides before powering it.',AMBER)
para('The following is the conservative arrangement for a breakout confirmed to accept <b>3.3 V power and 3.3 V I2C</b>. Use an I2C-rated bidirectional converter, not the inverting UART circuit intended for the optional ESP32.')
# A diagram communicates the two separate voltage domains without inventing pin positions.
for x,width,label,detail,fill in [(44,149,'UNO R4 MINIMA','5 V logic',MINT),(231,150,'I2C CONVERTER','HV side  |  LV side',CREAM),(419,149,'MPU-6050','3.3 V logic',MINT)]:
 c.setFillColor(fill);c.setStrokeColor(LINE);c.roundRect(x,y-56,width,56,8,fill=1,stroke=1);c.setFillColor(INK);c.setFont('Helvetica-Bold',10);c.drawCentredString(x+width/2,y-22,label);c.setFont('Helvetica',9);c.drawCentredString(x+width/2,y-39,detail)
for a,b in [(196,223),(389,411)]:
 c.setStrokeColor(INK);c.line(a,y-28,b,y-28);c.line(b-4,y-31,b,y-28);c.line(b-4,y-25,b,y-28)
y-=72
table(['From','Connect to'],[
('Arduino 5V','Converter HV reference only in this 3.3 V sensor arrangement.'),
('Arduino 3.3V','Converter LV reference AND sensor breakout VCC, if rated for this input.'),
('Arduino GND','Converter GND AND sensor GND; all grounds common.'),
('Arduino A4 / SDA','Converter HV1.'),
('Converter LV1','Sensor SDA.'),
('Arduino A5 / SCL','Converter HV2.'),
('Converter LV2','Sensor SCL.'),
('Sensor AD0','Sensor GND. This selects I2C address 0x68.'),
('Sensor INT, XDA, XCL','Leave disconnected for this project.')],[135,389])
para('<b>If the breakout requires a documented 5 V VCC input:</b> follow that module specification for VCC while keeping the sensor-side I2C logic correctly level shifted. Do not guess from a generic GY-521 label, and do not power a bare sensor chip from 5 V.',small)
para('<b>Before USB:</b> check the actual pin labels, no short between supply and ground, correct HV/LV sides, and continuous ground. A4/SDA and A5/SCL are the Arduino signal pins; numbered converter channels can vary by module.',small)

page('Test A find the sensor','Create a new Arduino sketch and replace its contents with this entire code block. File: smartrep_i2c_scan.ino')
para('<b>IDE setup:</b> install Arduino IDE 2.x from arduino.cc/en/software. In Boards Manager install <b>Arduino UNO R4 Boards</b>. Select <b>Arduino UNO R4 Minima</b>, choose its USB port, then click Upload. Open Serial Monitor at <b>115200 baud</b>. No extra sensor library is needed.')
code((ROOT/'firmware/tests/smartrep_i2c_scan/smartrep_i2c_scan.ino').read_text(),size=9.1,leading=11.2)
para('<b>Pass:</b> expect <font face="Courier">Found device at 0x68</font> every five seconds. <b>0x69</b> means AD0 is high; ground AD0 to match the SmartRep firmware. No devices, many unexpected addresses, or intermittent results mean stop and check wiring before continuing.',small)

page('Test B verify motion readings','Copy all code below into a new sketch. Upload to UNO R4 Minima. Serial Monitor: 115200 baud.')
# A single page keeps selection/copying simple; source is also included in the ZIP.
code((ROOT/'firmware/tests/smartrep_mpu6050_test/smartrep_mpu6050_test.ino').read_text(),size=8.3,leading=8.6,top=680)

page('Interpret Test B and fix failures','The diagnostic sketches run by themselves. They do not count reps and do not implement the app protocol.')
box('<b>Expected startup:</b> <font face="Courier">WHO_AM_I = 0x68</font>, then <font face="Courier">PASS: MPU-6050 configured; accel g, gyro dps.</font> If Test A found address 0x69, change ADDRESS in Test B to 0x69; the chip ID still normally reads 0x68.')
heading('Three movement checks')
table(['Check','What should happen'],[
('Rest on a flat surface','One accelerometer axis should be approximately +1 g or -1 g; the others near 0 g. Which axis depends on mounting. Gyro values should be near 0 dps with small bias/noise.'),
('Tilt slowly, then hold','The gravity reading transfers between accelerometer axes. Gyro values change while turning, then return near zero when held still.'),
('Rotate in your hand','At least one gyro axis changes clearly. Values should not remain frozen, all zero, or persistently at the range limits.')],[125,399])
para('Example only: <font face="Courier">accel_g: 0.010, -0.020, 0.998 | gyro_dps: 0.20, -0.40, 0.10</font>. Your numbers will differ. Test B uses +/-4 g and +/-500 dps settings, prints about 10 lines/second, and does not remove gyro bias. SmartRep production firmware streams at 50 Hz.',small)
heading('Troubleshooting')
table(['Symptom','Next action'],[
('No USB port / upload fails','Try a known data cable, another USB port and the correct board selection. Close other serial programs. Confirm the board is UNO R4 Minima.'),
('Gibberish text','Set Serial Monitor to 115200 baud.'),
('Test A finds nothing','Check common ground, module supply rating, SDA/SCL order, converter HV/LV references and pull-ups. Check breadboard rail breaks.'),
('Unexpected WHO_AM_I','Confirm the printed chip/module model. A different IMU or clone may need different firmware; do not treat any responding address as a pass.'),
('Intermittent read failures','Shorten the cable, secure connections and check supply voltage. Keep the 100 kHz I2C setting. Do not extend the cable until short-wire tests pass.'),
('Port busy / access denied','Close Serial Monitor, the SmartRep bridge and any other program using that port before uploading or running a standalone recorder.')],[125,399])

page('Move from test code to SmartRep','After Test A and Test B pass, replace the diagnostic sketch with the production sketch supplied in the companion ZIP.')
heading('1 upload the production sketch')
para('Open <font face="Courier">firmware/smartrep_arduino/smartrep_arduino.ino</font> in Arduino IDE. Keep the folder and .ino filename together. Check the settings below, select UNO R4 Minima and upload. Only Wire is required; no third-party MPU library is used.')
code('#define DEVICE_ID "clip-01"\n#define SENSOR_MPU6050',size=10,leading=14)
para('In Serial Monitor, use <b>115200 baud</b> and <b>Newline</b> line ending. Send <font face="Courier">HELLO</font> for identity, <font face="Courier">START</font> for raw JSON samples, <font face="Courier">PING</font> for a pong and <font face="Courier">STOP</font> to stop. START expires after 10 seconds without a command. HELLO alone does not prove the sensor works; START must produce changing samples.')
heading('2 close Serial Monitor and start the bridge')
para('The teammate needs the full project and its installed Python environment. The private GitHub repo is <b>aaronkoolkoder/ece198-projects</b>; the owner must grant access or supply the project files. The guide ZIP contains firmware, not the entire app. Stop the simulated bridge before using port 8000.')
para('<b>macOS / Linux, from the project folder:</b>',small)
code('cd bridge\n.venv/bin/python -m smartrep --db smartrep-hardware.db',size=9,leading=13)
para('<b>Windows PowerShell, from the project folder:</b>',small)
code('cd bridge\n.\\.venv\\Scripts\\python.exe -m smartrep --db smartrep-hardware.db',size=9,leading=13)
para('If auto-detection misses the board, append <font face="Courier">--port COM4</font> on Windows, or <font face="Courier">--port /dev/cu.usbmodemXXXX</font> on macOS, using the real port. Do <b>not</b> add --simulate. The separate hardware DB preserves the simulation and avoids reusing fake motion references.',small)
heading('3 calibrate and run a set')
para('Open <b>http://127.0.0.1:8000/</b> on the laptop. Continue to the app and choose Mary, ID <b>123129</b>. Check Instructor view: clip-01 should be online at Dumbbells 5 lb. Open <b>Staff calibration</b>, PIN <b>0000</b>, and choose Bicep curl. Hold still for at least half a second, do three controlled full reps, return to the start and save. Then choose the 5 lb station, Bicep curl and Start set.')
para('If a teammate has not installed Python dependencies, follow the project README first. The phone can open the laptop LAN address on a shared hotspot/router. School WiFi can block that route; a temporary tunnel is another option. The laptop must stay awake.',small)

page('Mounting status light and later WiFi','First prove the short-wire USB station. Add optional parts one at a time, repeating the sensor test after each change.')
heading('Mount the sensor so it cannot slip')
para('Attach only the sensor securely to the dumbbell; keep the Arduino and breadboard in a stationary station box. Add strain relief at the sensor and box. Keep wires away from fingers and moving equipment. Test unloaded or with a light object first. A shifting sensor invalidates the saved motion reference.')
para('After the short-wire setup works, trial the planned 1-1.5 m cable at 100 kHz. Longer I2C wiring is sensitive to capacitance, pull-ups and interference. Start short and increase gradually; a planned length is not a guarantee of reliable operation. Re-run the motion test and watch for read errors before using it for a demo.')
heading('Optional RGB station light')
para('Use a <b>common-cathode</b> RGB LED. Identify its pins from its datasheet; do not assume a leg order. Give each color its own <b>1 kohm series resistor</b>. The production firmware works without this LED attached.')
table(['Arduino pin','LED connection'],[('D9','Through 1 kohm to RED anode.'),('D10','Through 1 kohm to GREEN anode.'),('D11','Through 1 kohm to BLUE anode.'),('GND','LED common cathode.')],[125,399])
para('Production indications: red blink = sensor error; fast blue = WiFi connecting; blue pulse = bridge idle; dim green = streaming; brief red every three seconds = no bridge. The built-in LED provides a heartbeat. The phone supplies rep sounds and vibration.',small)
heading('Optional ESP32 after USB passes')
para('An ESP32 is needed only to remove the USB data cable from the Arduino to the laptop. The UNO R4 Minima itself has no WiFi. The prepared modem lives in <font face="Courier">firmware/smartrep_esp32_wifi/</font>. It needs an ESP32 board package, WebSockets by Markus Sattler, and a local config.h made from config.example.h.')
box('The prepared modem assumes <b>two inverting UART voltage translators</b>: Arduino D1 TX to ESP32 GPIO16 RX, and ESP32 GPIO17 TX to Arduino D0 RX, with common ground. Its UART invert flag is true. This is a separate electrical circuit from the bidirectional I2C converter. Do not connect 5 V TX directly to an ESP32 input. Have the actual translator schematic checked before powering it.',AMBER)
para('Attach the WROOM-32U external antenna. Keep ESP32 USB power and the Arduino-to-ESP32 5 V feed from powering the rail simultaneously. The ESP32 sketch has not been compiler-verified in this environment because its toolchain download failed. Treat WiFi as a separate bring-up step; it is not required for the USB milestone.',small)

page('Handoff checklist and references','Share this PDF and SmartRep_Hardware_Handoff.zip. Both diagnostic code blocks match the .ino files in the ZIP.')
heading('Record these before handing it back')
table(['Check','Record result'],[
('Board and sensor','UNO R4 Minima confirmed; exact sensor breakout model and photo of both sides.'),
('Power and translation','Documented sensor VCC input; converter HV/LV and ground checked.'),
('Test A','Found address: __________   Stable over 30 seconds: yes / no'),
('Test B','WHO_AM_I: __________   At rest near 1 g total: yes / no'),
('Motion and cable','Acceleration and rotation change; no recurring read errors: yes / no'),
('Production firmware','clip-01 identity received; START streams samples: yes / no'),
('App','Hardware mode, station online, personal calibration saved: yes / no'),
('Three 10-rep trials','Human / app: 10 / ____    10 / ____    10 / ____')],[145,379])
para('<b>Target:</b> at least 9 of 10 reps correctly counted in each of three trials, while also checking that resting motion does not add reps. Try a few deliberate short attempts and confirm they are flagged rather than added to completed reps. This target has not yet been established on real hardware.',small)
heading('What to send to the project owner')
para('Send the checklist, sensor and wiring photos, board port, module supply information, test output, and any error messages. If the sensor moves on the dumbbell, recalibrate. If the short-wire setup works but the long cable fails, report that distinction instead of changing multiple parts at once.')
heading('Reference documents')
para('[1] <b>Arduino UNO R4 Minima datasheet</b> - 5 V operation, USB power, A4/A5 I2C and board pinout. <link href="https://docs.arduino.cc/resources/datasheets/ABX00080-datasheet.pdf" color="#24634f">Official Arduino datasheet</link>.<br/>[2] <b>InvenSense MPU-6000/6050 product specification</b> - chip supply and logic ratings, I2C addressing and sensor scales. This is the manufacturer document hosted by a distributor. <link href="https://www.haoyuelectronics.com/Attachment/GY-521/mpu6050.pdf" color="#24634f">MPU-6050 datasheet</link>.<br/>[3] <b>Arduino Wire reference</b> - board I2C pin mapping and API. <link href="https://github.com/arduino/reference-en/blob/master/Language/Functions/Communication/Wire.adoc" color="#24634f">Arduino Wire reference</link>.<br/>[4] <b>Arduino IDE download</b>. <link href="https://www.arduino.cc/en/software" color="#24634f">arduino.cc/en/software</link>.',small)
para('Compiled on November 5, 2026 for arduino:renesas_uno:minima, core 1.6.0. Test A: 45,140 bytes flash / 5,096 bytes global RAM. Test B: 46,496 bytes flash / 5,104 bytes global RAM. The production sketch had previously compiled for R4. Physical wiring, sensor accuracy and long-cable behavior remain to be verified.',small)
c.save();print(OUT)
