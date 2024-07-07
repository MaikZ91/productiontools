from __future__ import print_function
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from DFRobot_GP8403 import *

DAC = DFRobot_GP8403(0x5f)  
while DAC.begin() != 0:
    print("init error")
    time.sleep(1)
print("init succeed")
  
#Set output range  
DAC.set_DAC_outrange(OUTPUT_RANGE_10V)

while True:
    DAC.set_DAC_out_voltage(0, 1)     # Setzt die Spannung auf 0 V
    time.sleep(2)                     # Wartet 2 Sekunden
    DAC.set_DAC_out_voltage(10000, 1) # Setzt die Spannung auf 10 V
    time.sleep(2)

