#!/usr/bin/python3

# ----------------------------------------------------------------------------------------
# Example of experiment with LGTC device. Application is made out of 2 threads:
#   * main for experiment controll
#   * client thread for communication with the controller.
#
# Modules used:
#   * controller_client.py communicates with controller server.
#   * file_logger.py stores all the measurements of the experiment.
# ----------------------------------------------------------------------------------------


from queue import Queue
import sys
import os
import logging
import time
from timeit import default_timer as timer
from subprocess import Popen, PIPE

from lib import file_logger

import controller_client



# ----------------------------------------------------------------------------------------
# EXPERIMENT DEFINITIONS AND CONFIGURATION
# ----------------------------------------------------------------------------------------

# DEFINITIONS
LOG_LEVEL = logging.DEBUG

#ROUTER_HOSTNAME = "tcp://192.168.2.191:5562"
#SUBSCR_HOSTNAME = "tcp://192.168.2.191:5561"
ROUTER_HOSTNAME = "tcp://193.2.205.19:5562"
SUBSCR_HOSTNAME = "tcp://193.2.205.19:5561"

SERIAL_TIMEOUT = 2  # In seconds

RESULTS_FILENAME = "node_results"
LOGGING_FILENAME = "logger"

# ENVIRONMENTAL VARIABLES
# Device id should be given as argument at start of the script
try:
    LGTC_ID = sys.argv[1]
    LGTC_ID = LGTC_ID.replace(" ", "")
except:
    print("No device name was given...going with default")
    LGTC_ID = "xy"

LGTC_NAME = "LGTC" + LGTC_ID
RESULTS_FILENAME += ("_" + LGTC_ID + ".txt")
LOGGING_FILENAME += ("_" + LGTC_ID + ".log")

# Application name and duration should be defined as variable while running container
try:
    APP_DURATION = int(os.environ['APP_DURATION_MIN'])
except:
    print("No app duration was defined...going with default 60min")
    APP_DURATION = 10

try:
    APP_DIR = os.environ['APP_DIR']
except:
    print("No application was given...aborting!")
    #sys.exit(1) TODO
    APP_DIR = "02_acs"

# TODO: change when in container
APP_PATH = "/root/logatec-experiment/applications/" + APP_DIR
#APP_PATH = "/home/logatec/magistrska/logatec-experiment/applications/" + APP_DIR
APP_NAME = APP_DIR[3:]





# ----------------------------------------------------------------------------------------
# EXPERIMENT APPLICATION
# ----------------------------------------------------------------------------------------
class experiment():

    def __init__(self, input_q, output_q, filename, lgtcname):

        self.log = logging.getLogger(__name__)
        self.log.setLevel(LOG_LEVEL)

        # Init lib
        self.f = file_logger.file_logger()

        # controller_client.py - link multithread input output queue
        self.in_q = input_q
        self.out_q = output_q

        # file_logger.py - prepare measurements file
        self.f.prepare_file(filename, lgtcname)
        self.f.open_file()  

        # Experiment vars
        self._is_app_running = False
        self._lines_stored = 0



    def runApp(self):

        self.log.info("Starting experiment application!")

        # Init everything

        while(True):

            # -------------------------------------------------------------------------------
            # Do the measurement
            if(self._is_app_running):
                
                self._lines_stored += 1
                print("Measurement no." + self._lines_stored)

                if(self._lines_stored == 10):
                    self._is_app_running = False
                    self.queuePut("INFO", "END")

            # -------------------------------------------------------------------------------
            # CONTROLLER CLIENT - GET COMMANDS
            # Check for incoming commands
            if not self.in_q.empty():

                sqn, cmd = self.queueGet()

                # SYSTEM COMMANDS
                # Act upon system command
                if sqn == "SYS":

                    if cmd == "EXIT":
                        self.stop()
                        break

                    elif cmd == "RESET":
                        print("Reset all variables")

                    #TODO tuki ti pridejo še ukazi APP_STARTED in APP_STOPPED...reši tu pr VESNI drgači

                    else:
                        self.log.warning("Unsupported SYS command " + cmd)


                # EXPERIMENT COMMANDS
                else:

                    self.f.store_lgtc_line("Got command [" + sqn + "]: " + cmd)
                    self.log.info("Got command [" + sqn + "]: " + cmd)

                    if cmd == "START":
                        self._is_app_running = True
                        self.queuePut(sqn, cmd)

                    elif cmd == "STOP":
                        self._is_app_running = False
                        self.queuePut(sqn, cmd)

                    if cmd == "LINES":
                        resp = "Lines stored: " + str(self._lines_stored)
                        self.queuePut(sqn, resp)
                        self.f.store_lgtc_line(resp)


    

    def clean(self):
        self.f.close()

    def stop(self):
        self.f.store_lgtc_line("Application exit!")
        self.log.info("Application exit!")

    def queuePut(self, sqn, resp):
        self.out_q.put([sqn, resp])

    def queueGet(self):
        tmp = self.in_q.get()
        return tmp[0], tmp[1]




# ----------------------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------------------
if __name__ == "__main__":

    # Config logging module format for all scripts. Log level is defined in each submodule with var LOG_LEVEL.
    logging.basicConfig(format="%(asctime)s [%(levelname)7s]:[%(module)26s > %(funcName)16s() > %(lineno)3s] - %(message)s", level=LOG_LEVEL, filename=LOGGING_FILENAME)
    #logging.basicConfig(format="[%(levelname)5s:%(funcName)16s() > %(module)17s] %(message)s", level=LOG_LEVEL)

    logging.info("Testing application " + APP_NAME + " for " + str(APP_DURATION) + " minutes on device " + LGTC_NAME + "!")

    # Create 2 queue for communication between threads
    # Client -> LGTC
    C_L_QUEUE = Queue()
    # LGTC -> Client
    L_C_QUEUE = Queue()

    # Start client thread (communication with controller)
    client_thread = controller_client.zmq_client_thread(L_C_QUEUE, C_L_QUEUE, LGTC_NAME, SUBSCR_HOSTNAME, ROUTER_HOSTNAME)
    client_thread.start()

    # Init main application thread 
    app_thread = experiment(C_L_QUEUE, L_C_QUEUE, RESULTS_FILENAME, LGTC_NAME)
    app_thread.runApp()
    app_thread.clean()

    logging.info("Main thread stopped, trying to stop client thread.")

    # Wait for a second so client can finish its transmission
    time.sleep(1)

    # Notify zmq client thread to exit its operation and join until quit
    client_thread.stop()
    client_thread.join()

    logging.info("Exit!")
