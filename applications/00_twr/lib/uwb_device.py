"""
This file takes serial input from serial line and
takes care of importing data for Classification
@author: Klemen Bregar
"""
import os
import sys
import serial
import time
import Adafruit_BBIO.GPIO as GPIO
import base64
import io
#import numpy as np
import multiprocessing
import queue
import logging
import copy


class Node(multiprocessing.Process):
    def __init__(self, output_queue, serial_port, baudrate, loglevel):
        multiprocessing.Process.__init__(self)
        self._data_out_q = output_queue
        self._serial_port = serial_port
        self._baudrate = baudrate
       
        self.logger = logging.getLogger(__name__+'.Node')
        self.logger.setLevel(loglevel)
        self.logger.info('Init Node')
        
        """ Init serial interface """
        self._ser = serial.Serial(self._serial_port, self._baudrate, timeout=1)
        # wait for serial port to open
        time.sleep(1)
        GPIO.setup("GPIO1_25", GPIO.OUT)
        GPIO.output("GPIO1_25", GPIO.LOW)
        self.hw_reset()
        self._linebuffer = ''
        self._nl = False
        self.serial_flush()

    def close(self):
        """ Close serial connection """
        self._ser.close()
        GPIO.cleanup()

    # get line and pack data in a dictionary -> json
    def run(self):
        while True:
            msg = None
            # check if linebuffer already contains the newline character
            self._nl = False
            msg_str = ''
            spl = self._linebuffer.split('\n', 1)
            if(len(spl) > 1):
                msg_str = spl[0]
                self._linebuffer = spl[1]
                self._nl = True
            try:
                while(False == self._nl):
                    i = max(1, min(2048, self._ser.in_waiting))
                    buff = self._ser.read(i)
                    #if logging.DEBUG == self._loglevel:
                    #    self._raw_debug_file.write(buff)
                    if(b'\x00' in buff):
                        self.logger.debug("Error char")
                    buff = buff.decode('ascii')
                    spl = buff.split('\n', 1)
                    if(len(spl) > 1):
                        self._linebuffer += spl[0]
                        msg_str = self._linebuffer
                        self._linebuffer = spl[1]
                        self._nl = True
                    else:
                        self._linebuffer += spl[0]
            except:
                self.logger.exception('Exception')
                
            try:
                if not self._data_out_q.full():
                    self._data_out_q.put(msg_str, False)
            except:
                self.logger.exception("Exception")

    def hw_reset(self):
        """
        Reset the UWB node by a hardware reset pin sequence
        """
        GPIO.output("GPIO1_25", GPIO.LOW)
        time.sleep(2)
        GPIO.output("GPIO1_25", GPIO.HIGH)
        time.sleep(2)
        GPIO.output("GPIO1_25", GPIO.LOW)
        time.sleep(0.5)
        self.serial_flush()
    
    def serial_flush(self):
        """
        Read all from serial buffer
        """
        self._ser.timeout = 0.01
        for i in range(10):
            line = self._ser.readline()
        self._ser.timeout = 1


    

    

    def sendSTOP(self):
        # send STOP command
        self._ser.write(b'AT+STOP\n')

    def sendSTART(self):
        # send STOP command
        self._ser.write(b'AT+START\n')

    def sendRESET(self):
        # send STOP command
        self._ser.write(b'AT+RESET\n')

    def sendNodeIDRequest(self):
        # send command to get node id
        self._ser.write(b'AT+GETID\n')

    def sendSettings(self, cmd_dict):
        # send settings to UWB node based on cmd_dict
        device_mode = 0
        if('anchor' == cmd_dict['device_mode']):
            device_mode = 1
        else:
            device_mode = 0
        prfr = None
        datarate = None
        plen = None
        pacsize = None
        nssfd = None
        cir = None
        # prfr
        if 16 == cmd_dict['prfr']:
            prfr = 1
        elif 64 == cmd_dict['prfr']:
            prfr = 2
        # datarate
        if 110 == cmd_dict['datarate']:
            datarate = 0
        elif 850 == cmd_dict['datarate']:
            datarate = 1
        elif 6800 == cmd_dict['datarate']:
            datarate = 2
        # plen
        if 64 == cmd_dict['plen']:
            plen = 0x04
        elif 128 == cmd_dict['plen']:
            plen = 0x14
        elif 256 == cmd_dict['plen']:
            plen = 0x24
        elif 512 == cmd_dict['plen']:
            plen = 0x34
        elif 1024 == cmd_dict['plen']:
            plen = 0x08
        elif 1536 == cmd_dict['plen']:
            plen = 0x18
        elif 2048 == cmd_dict['plen']:
            plen = 0x28
        elif 4096 == cmd_dict['plen']:
            plen = 0x0C
        # pacsize
        if 8 == cmd_dict['pacsize']:
            pacsize = 0
        if 16 == cmd_dict['pacsize']:
            pacsize = 1
        if 32 == cmd_dict['pacsize']:
            pacsize = 2
        if 64 == cmd_dict['pacsize']:
            pacsize = 3
        # nssfd
        if True == cmd_dict['nssfd']:
            nssfd = 1
        elif False == cmd_dict['nssfd']:
            nssfd = 0
        # cir
        if True == cmd_dict['cir']:
            cir = 1
        elif False == cmd_dict['cir']:
            cir = 0
            
        templine = b'AT+SETUP:%01x,%02x,%02x,%02x,%02x,%02x,%02x,%02x,%04x,%02x,%02x\n' % (
            device_mode, cmd_dict['channel'], prfr, datarate, cmd_dict['pcode'], plen, pacsize, nssfd, cmd_dict['sfdto'],
            cmd_dict['rfpow'], cir)
        self._ser.write(templine)
    
    def _sendStop(self):
        """
        Send STOP command and wait for confirmation
        return: finished status
        """
        state = 'STOP'
        finished = False
        retry = 0
        max_retry = 2
        while False == finished:
            if 'STOP' == state:
                self.sendSTOP()
                retry = 0
                state = 'WAIT_STOP_CONF'
        
            if 'WAIT_STOP_CONF' == state:
                response = self.getMessage()
                if 0 <= response[1].find(b'AT+STOP:OK'):
                    finished = True
                elif retry <= max_retry:
                    state = 'WAIT_STOP_CONF'
                    retry += 1
                else:
                    state = 'RESET'
            
            if 'RESET' == state:
                self.logger.debug("hw reset")
                self.hw_reset()
                state = 'STOP'

        return finished
        
    def _sendStart(self, settings):
        """
        Sensd SETUP and START command and wait for confirmation
        return: finished status
        """
        state = 'SETUP'
        finished = False
        retry = 0
        max_retry = 2
        while False == finished:
            if 'SETUP' == state:
                self.logger.debug("uwb device setup")
                retry = 0
                self.sendSettings(settings)
                state = 'WAIT_SETUP_CONF'
        
            if 'WAIT_SETUP_CONF' == state:
                self.logger.debug("uwb device setup conf")
                response = self.getMessage()
                if 0 <= response[1].find(b'AT+SETUP:OK'):
                    state = 'START'
                elif retry <= max_retry:
                    state = 'WAIT_SETUP_CONF'
                    retry += 1
                else:
                    state = 'RESET'
        
            if 'START' == state:
                self.logger.info("uwb device start")
                retry = 0
                self.sendSTART()
                state = 'WAIT_START_CONF'
        
            if 'WAIT_START_CONF' == state:
                self.logger.debug("uwb device start conf")
                response = self.getMessage()
                if 0 <= response[1].find(b'AT+START:OK'):
                    finished = True
                elif retry <= max_retry:
                    state = 'WAIT_START_CONF'
                    retry += 1
                else:
                    state = 'RESET'
            
            if 'RESET' == state:
                self.logger.debug("uwb device hw reset")
                self.hw_reset()
                state = 'SETUP'
        
        return finished
                
