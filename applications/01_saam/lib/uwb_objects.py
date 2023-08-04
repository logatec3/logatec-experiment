import os
import sys
import base64
import numpy as np
import string
import logging
import copy
import time

from lib import cirtools
#from ..tomography import cspeedups


EMPTY_MSG = 0
ACTIVE_DEVICES_MSG = 1
CIR_MSG = 2


class Device(object):
    """
    This class implements the active device object
        
    @param shortAddr: 	16-bit short address string
    @param devAddr:		64-bit device address string
    @param devType:		device type ('master', 'slave', 'tag')
    @param miss:		number of slots the device was missing
    """
    def __init__(self, shortAddr, devAddr, devType, miss):
        self._type = 'Device'
        self._shortAddr = shortAddr
        self._devAddr = devAddr
        self._devType = devType
        self._miss = miss
        self._position = []

    def type(self):
        return self._type

    def updatePosition(self, position):
        self._position = position

    def updateDevice(self, miss):
        self._miss = miss

    def shortAddress(self):
        return self._shortAddr

    def deviceAddress(self):
        return self._devAddr

    def deviceType(self):
        return self._devType

    def miss(self):
        return self._miss

    def position(self):
        return self._position

    def toDictionary(self):
        # returns a dictionary of selected device
        device_dict = {}
        device_dict['shortAddr'] = self._shortAddr
        device_dict['devAddr'] = self._devAddr
        device_dict['devType'] = self._devType
        device_dict['miss'] = self._miss
        return device_dict


class EmptyObject(object):
    def __init__(self):
        self._type = 'EmptyObject'
    
    def type(self):
        return self._type


class ActiveDevices(object):
    """
    This object holds the device report message

    @param msg_str: message string containing complete message information
    """
    def __init__(self, msg_str):
        self._type = 'ActiveDevices'
        self._hexdigits = set(string.hexdigits)
        self._devices = []
        try:
            self.__parse_msg_string(msg_str)
        except:
            self._type = 'EmptyObject'

    def type(self):
        return self._type

    def devices(self):
        # return the active devices table
        return self._devices

    def __parse_msg_string(self, input_string):
        spl = input_string.strip()[5:-1].split(';')
        # last item is empty
        for item in spl[:-1]:
            try:
                # check if string is hexadecimal
                if not all(c in self._hexdigits for c in item):
                    raise TypeError("Input string contains non-HEX characters")
                shortAddr = item[:4]
                devAddr = item[4:20]
                dt = int(item[20:22], 16)
                devType = None
                if(0 == dt):
                    devType = 'master'
                elif(1 == dt):
                    devType = 'slave'
                elif(2 == dt):
                    devType = 'tag'
                miss = int(item[22:24], 16)
                # create device object
                self._devices.append(Device(shortAddr, devAddr, devType, miss))
            except:
                print("Data format error")
                print(input_string)

    def toDictionary(self):
        # returns the dictionary of active devices
        devices_dict = {}
        devices_dict['type'] = 'dev'
        devices = {}
        for dev in self._devices:
            dd = dev.toDictionary()
            devices[dd['devAddr']] = dd
        devices_dict['devices'] = devices
        return devices_dict


class RngItem(object):
    """
    Contains ranging report for one device pair
    """
    def __init__(self, msg_str):
        self._range = 0.0
        self._source = None
        self._destination = None
        try:
            self.__parseInput(msg_str)
        except:
            self._type = 'EmptyObject'

    def range(self):
        return self._range

    def source(self):
        return self._source

    def destination(self):
        return self._destination

    def __parseInput(self, msg_str):
        tmp = msg_str.split(',')
        self._source = str(tmp[0])
        self._destination = str(tmp[1])
        self._range = float(tmp[2])


class RangingReport(object):
    """
    Contains range/distance measurement report between all UWB anchors. 
    """
    def __init__(self, msg_str):
        # define properties
        self._type = 'RngReport'
        self._rangeTable = []
        try:
            self.__parseInput(msg_str)
        except:
            self._type = 'EmptyObject'

    def type(self):
        return self._type

    def rng_items(self):
        return self._rangeTable

    def __parseInput(self, msg_str):
        tmp = msg_str[5:-1].split(';')
        for item in tmp:
            self._rangeTable.append(RngItem(item))


class CIR(object):
    """
    Contains one CIR measurements. Parsing the input string.
        
    @param msg_str: whole message string
    """
    def __init__(self, msg_str):
        self._type = 'CIR'
        self._srcAddress = ''
        self._destAddress = ''
        # resulting/output values
        self._rss = 0
        self._fp = 0
        self._cir = []
        # init local properties by parsing input string
        try:
            self.__parse_msg_string(msg_str)
        except:
            self._type = 'EmptyObject'

    def type(self):
        return self._type

    def __parse_msg_string(self, msg_str):
        spl = msg_str[5:-1].split(';')
        self._srcAddress = spl[0][4:]
        self._destAddress = spl[1][5:]
        cpwr = int(spl[2][4:], 16)
        fp1 = int(spl[3][4:], 16)
        fp2 = int(spl[4][4:], 16)
        fp3 = int(spl[5][4:], 16)
        rxpacc = int(spl[6][7:], 16)
        prfr = int(spl[7][5:], 16)
        self._rss, self._fp = cirtools.signal_power(
            cpwr, fp1, fp2, fp3, rxpacc, prfr)
        dec64 = base64.b64decode(spl[8])
        cir = cirtools.parseCIR2abs(dec64)
        if (0.0 == np.amin(cir)):
            idx = np.where(0.0 == cir)
            for item in idx[0]:
                cir[item] = np.mean(
                    [cir[item-1], cir[item+1]])
        self._cir = cirtools.cir2dbm(cir, rxpacc, prfr)
    
    def __parse_msg_string_cython(self, msg_str):
        pass

    def srcAddress(self):
        return self._srcAddress

    def destAddress(self):
        return self._destAddress

    def cir(self):
        return self._cir

    def fp(self):
        return self._fp

    def rss(self):
        return self._rss

    def toDictionary(self):
        # return CIR report dictionary
        cir_dict = {}
        cir_dict['type'] = 'cir'
        cir_dict['srcAddr'] = self._srcAddress
        cir_dict['destAddr'] = self._destAddress
        cir_dict['rss'] = self._rss
        cir_dict['rss_fp'] = self._fp
        cir_dict['cir'] = self._cir
        return cir_dict
