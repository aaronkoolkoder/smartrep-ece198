"""Run the actual LCD command handler with host-side Arduino output stubs."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_buzzer_only_sounds_for_completed_reps_or_ready_calibration(tmp_path):
    compiler=shutil.which('c++')
    if not compiler:pytest.skip('C++ compiler unavailable')
    sketch=(Path(__file__).resolve().parents[2]/'firmware/smartrep_mpu6050_lcd_wifi/smartrep_mpu6050_lcd_wifi.ino').read_text()
    handler=sketch[sketch.index('bool displayCommand('):sketch.index('\nbool writeRegister(')]
    source=tmp_path/'feedback.cpp'
    source.write_text('''
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <cassert>
#include <cstdint>
int BUZZER_PIN=2,beeps=0;unsigned long buzzUntil=0;
long displayedReps=0;char participantName[17]="";
bool wasCalibrating=false,calibrationBeeped=false;
void row(int,const char*){} unsigned long millis(){return 1000;}
void tone(int,int,int){beeps++;}
'''+handler+'''
void command(const char* value){char buffer[64];strcpy(buffer,value);displayCommand(buffer);}
int main(){
 command("LCD|Mary|0|cal");command("LCD|Mary|1|cal");
 command("LCD|Mary|0|cal");command("LCD|Mary|1|cal");command("LCD|Mary|2|cal");
 assert(beeps==0);
 command("LCD|Mary|3|cal_ready");command("LCD|Mary|3|cal_ready");
 command("LCD|Mary|3|cal_saved");assert(beeps==1);
 command("LCD|Mary|0|good");command("LCD|Mary|0|short");assert(beeps==1);
 command("LCD|Mary|1|good");command("LCD|Mary|1|good");
 command("LCD|Mary|1|done");assert(beeps==2);
 command("LCD|Mary|1|short");assert(beeps==2);
 command("LCD|Mary|2|rushed");assert(beeps==3);
 command("LCD|Raj|5|good");assert(beeps==3);
}
''')
    executable=tmp_path/'feedback'
    subprocess.run([compiler,'-std=c++11',str(source),'-o',str(executable)],check=True,capture_output=True)
    subprocess.run([str(executable)],check=True,capture_output=True)
