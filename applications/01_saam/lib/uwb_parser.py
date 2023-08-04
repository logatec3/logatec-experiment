import os
import sys
import copy
import time

from lib import uwb_objects
prof = 0.0

def parse(uart_line):
    # Line parser for uart streams from uwb device
    packet = None

    # active devices report
    if (uart_line[:10].find('_DEV{') >= 0):
        try:
            packet = uwb_objects.ActiveDevices(uart_line)
        except:
            print("Exception while processing _DEV frame")

    # CIR measurement report
    elif (uart_line[:10].find('_CIR{') >= 0):
        if(918 != len(uart_line)):
            packet = None
        elif('\x00' in uart_line):
            packet = None
        else:
            try:
                packet = uwb_objects.CIR(uart_line)
            except:
                print("Exception while processing _CIR frame")

    # ranging report
    elif (uart_line[:10].find('_RNG{') >= 0):
        if('\x00' in uart_line):
            packet = None
        if('}' == uart_line.split(sep='{')[1]):
            packet = None
        else:
            try:
                packet = uwb_objects.RangingReport(uart_line)
            except:
                print("Exception while processing _RNG frame")
    
    # Empty object
    if None == packet:
        packet = uwb_objects.EmptyObject()
                
    return packet
