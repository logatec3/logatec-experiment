import logging
import sys
import multiprocessing
from timeit import default_timer as timer

import lib.uwb_device as uwb_device

LOG_LEVEL = logging.DEBUG
RESULTS_FILENAME = "devid"

try:
    LGTC_ID = sys.argv[1]
    LGTC_ID = LGTC_ID.replace(" ", "")
except:
    print("No device name was given...going with default")
    LGTC_ID = "xy"

LGTC_NAME = "LGTC" + LGTC_ID
RESULTS_FILENAME += ("_" + LGTC_ID + ".txt")

logging.basicConfig(format="%(asctime)s [%(levelname)7s]:%(module)15s > %(message)s", level=LOG_LEVEL)
log = logging.getLogger("Monitor")
log.setLevel(LOG_LEVEL)   

file = open(RESULTS_FILENAME, mode="a+")
_start_time = timer()

if __name__ == "__main__" :

    log.info('Starting UWB node UART process')
    q_uwb = multiprocessing.Queue()
    p_uart = uwb_device.Node(q_uwb, '/dev/ttyS2', 921600, LOG_LEVEL)
    p_uart.start()

    try:
        while(True):
            try:
                if not q_uwb.empty():
                    line = q_uwb.get()
                    if(line[0] == "I" and line[1] == "D"):
                        file.write(line)
                        file.write("\n")
                        break

            except Exception as e:
                if type(e) == multiprocessing.Queue.Empty:
                    log.debug("Empty Q")
                    pass
                else:
                    log.exception("Exception")

            # Temp solution for time measuring
            if((timer() - _start_time) > (1 * 10) ):
                log.info("Application time elapsed ...")
                break

            p_uart.sendNodeIDRequest()

    except:
        log.debug("Exiting main process")

    file.close()
    p_uart.close()
    p_uart.terminate()
    p_uart.join()
    log.info("Exiting monitor app!")
