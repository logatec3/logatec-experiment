# this fale contains functions and classes for UWB data transformation and PROCESSING
import numpy as np
import math


"""
    Calculate signal power
"""
def signal_power(rss, fp1, fp2, fp3, rxpacc, prfr):
    """
        calculate vector of first path power and total signal power
    """
    # RCPE first path
    rcpe_fp = 10 * np.log10((np.power(fp1, 2) + np.power(fp2, 2) +
                             np.power(fp3, 2)) / (np.power(rxpacc, 2)))
    # RCPE
    rcpe = 0.0
    if rxpacc == 0.0:
        rcpe = rcpe_fp
    else:
        rcpe = 10 * np.log10((rss * np.power(2.0, 17)) / (np.power(rxpacc, 2)))
    # compensate for PRFR
    if int(prfr) == 16:
        rcpe = rcpe - 115.72
        rcpe_fp = rcpe_fp - 115.72
    else:
        rcpe = rcpe - 121.74
        rcpe_fp = rcpe_fp - 121.74

    return rcpe, rcpe_fp


'''
    get cir in numerical absolute value and convert it to dBm values
'''
def cir2dbm(cir, rxpacc, prfr):
    # RCPE
    cirdbm = 10 * np.log10((cir * np.power(2.0, 17)) / (np.power(rxpacc, 2)))
    # compensate for PRFR
    offset = 0.0
    if int(prfr) == 16:
        offset = 115.72
    else:
        offset = 121.74
    cirdbm =  cirdbm - offset
    
    return cirdbm


def parseCIR2abs(data):
    length = int(len(data) / 4)
    tempreal = None
    tempcpx = None
    cpx_data = []

    for x in range(length):
        tempreal = ((data[(x * 4)]) << 8) + (data[(x * 4) + 1])
        # convert unsigned integer to signed integer
        if (tempreal & 0x8000):
            tempreal = -0x10000 + tempreal
        tempcpx = ((data[(x * 4) + 2]) << 8) + (data[(x * 4) + 3])
        if (tempcpx & 0x8000):
            tempcpx = -0x10000 + tempcpx
        cpx_data.append(abs(complex(tempreal, tempcpx)))

    return np.asarray(cpx_data)
