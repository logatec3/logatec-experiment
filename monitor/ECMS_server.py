
#!/usr/bin/python3

import eventlet
eventlet.monkey_patch()

from threading import Thread, Lock, Event
from queue import Queue
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit
import zmq
import ast  # From str to json conversion
import logging


# --------------------------------------------------------------------------------------------
# GLOBAL DEFINITIONS
# --------------------------------------------------------------------------------------------

# Variable stores active experiment type
EXPERIMENT = "None"

# IP address of controller container (canged in SMS with start.sh script to 193.2.205.19:5563)
CONTROLLER_HOSTNAME = "tcp://193.2.205.202:5563"


# --------------------------------------------------------------------------------------------
# INIT
# --------------------------------------------------------------------------------------------
# Thread 
lock = Lock()
thread = Thread()
thread_stop_event = Event()
ZMQ_queue = Queue()

# Flask and SocketIO config
app = Flask(__name__, static_url_path="", static_folder="static", template_folder="templates")
socketio = SocketIO(app, async_mode="eventlet", cors_allowed_origins="*", path="/socket.io")

# Logging module
logging.basicConfig(format="%(asctime)s [%(levelname)7s]:[%(name)5s > %(funcName)17s() > %(lineno)3s] - %(message)s", level=logging.DEBUG, filename="ECMS_server.log")
f_log = logging.getLogger("Flask")
z_log = logging.getLogger("ZMQ")


# --------------------------------------------------------------------------------------------
# FLASK
# --------------------------------------------------------------------------------------------

# Store essential values and use it in case of page reload-TODO from DB
templateData ={
    "example_string" : "monitor" 
}

# Serve templates
@app.route("/")
def index():
    # TODO templateData?
    return render_template("index.html", **templateData)


# Serve static files 
@app.route("/static/js/<path:path>")
def send_js(path):
    return send_from_directory("static/js/", path)

@app.route("/static/css/<path:path>")
def send_css(path):
    return send_from_directory("static/css/", path)

@app.route("/static/img/<path:path>")
def send_img(path):
    return send_from_directory("static/img/", path)



# --------------------------------------------------------------------------------------------
# SocketIO
# --------------------------------------------------------------------------------------------
@socketio.on("connect")
def SIO_connect():
    f_log.debug("Client connected!")

    # Start ZMQ background thread if it is not active
    global thread
    if not thread.is_alive():
        f_log.debug("Start ZMQ thread")
        thread = socketio.start_background_task(ZMQ_thread)

    lock.acquire()
    global EXPERIMENT
    reply = {"data":EXPERIMENT}
    lock.release()
    
    emit("after connect", reply)

@socketio.on("disconnect")
def SIO_disconnect():
    f_log.debug("Client disconnected!")

    # Stop the ZMQ thread
    #thread_stop_event.set()

@socketio.on("new command")
def SIO_received_command(cmd):
    f_log.info("Client sent: ")
    f_log.debug(cmd)

    message_to_send = [cmd["sequence"].encode(), cmd["device"].encode(), cmd["data"].encode()] # From dict to byte array
    ZMQ_queue.put({"type":"command", "data":message_to_send})

@socketio.on("testbed update")
def SIO_get_tb_state():
    f_log.info("Client wants to update testbed state.")

    ZMQ_queue.put({"type":"system", "data":"update testbed"})




# --------------------------------------------------------------------------------------------
# ZeroMQ
# --------------------------------------------------------------------------------------------
def ZMQ_thread(input_q):


    queue = input_q
    context = zmq.Context()
    zmq_soc = context.socket(zmq.DEALER)
    zmq_soc.setsockopt(zmq.IDENTITY, b"flask_process")
    zmq_soc.connect(CONTROLLER_HOSTNAME) 

    poller = zmq.Poller()
    poller.register(zmq_soc, zmq.POLLIN)

    z_log.info("Initialized 0MQ thread!")

    socketio.sleep(1)
 
    while not thread_stop_event.is_set():

        # Check input from background (boker)
        socks = dict(poller.poll(0))

        if socks.get(zmq_soc) == zmq.POLLIN:

            global EXPERIMENT

            sequence, device, data = zmq_soc.recv_multipart()

            # From bytes to string [device, count, data]
            msg = [sequence.decode(), device.decode(), data.decode()]

            # Received new device state
            if msg[0] == "DEVICE_UPDATE":
                z_log.info("Received new device state from brokers database!")

                message = {
                        "sequence" : "Update",
                        "device" : msg[1],
                        "data" : msg[2]
                    }
                socketio.emit("device state update", message, broadcast=True)

            # Received whole testbed device state
            elif msg[0] == "TESTBED_UPDATE":
                z_log.info("Received testbed state from brokers database!")

                # From string to list of dicts
                json_data = ast.literal_eval(msg[2])

                message = {
                    "sequence" : "Update",
                    "device" : msg[1],
                    "data" : json_data
                }
                socketio.emit("testbed state update", message, broadcast=True)

            # Sync between broker and flask server in the beginning
            elif msg[0] == "EXP_START":
                z_log.info("Experiment has started!")

                radio_type = msg[2]
                
                lock.acquire()
                EXPERIMENT = radio_type
                lock.release()

                socketio.emit("experiment started", {"data":radio_type}, broadcast=True)

            # When broker exits, inform the user
            elif msg[0] == "EXP_STOP":
                z_log.info("Experiment has stopped!")

                lock.acquire()
                EXPERIMENT = "None"
                lock.release()

                socketio.emit("experiment stopped", {}, broadcast=True)

            elif msg[0] == "INFO":
                z_log.info("Received info from device " + msg[1])

                message = {
                    "sequence" : "info",
                    "device" : msg[1],
                    "data" : msg[2]
                }

                socketio.emit("info", message, broadcast=True)

            elif msg[0] == "LOC":
                z_log.info("received RSSI measurement")

                response = {
                    "sequence" : "loc",
                    "device" : msg[1],
                    "data" : msg[2]
                }

                socket.emit("localization", message, broadcast=True)

            # Received command response
            else:
                z_log.info("Received message from broker!")
    
                response = {
                    "sequence" : msg[0],
                    "device" : msg[1],
                    "data" : msg[2]
                }

                # Forward message to the client over websockets
                socketio.emit("command response", response, broadcast=True)

        # Check input queue (from Flask process)
        elif not queue.empty():
            msg = queue.get()

            if msg["type"] == "system":

                if msg["data"] == "update testbed":
                    zmq_soc.send_multipart([b"TESTBED_UPDATE", b"", b""])

            elif msg["type"] == "command":
                zmq_soc.send_multipart(msg["data"])
        
        # Else sleep a little - give control to Flask thread
        else:
            socketio.sleep(0.5)
    
    z_log.info("Leaving 0MQ thread...")



# --------------------------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------------------------

# Run the ZMQ thread in the beginning
thread = socketio.start_background_task(ZMQ_thread, ZMQ_queue)


if __name__ == '__main__':
    try:
        print("Start the server!")
        socketio.run(app, host="localhost", port=8001, debug=False)
    except KeyboardInterrupt:
        print("Stopping Flask server.")
        thread_stop_event.set()
        thread.join()









# --------------------------------------------------------------------------------------------
# DEPLOYMENT WITH GUNICORN & EVENTLET
#
# A WSGI server is recommended for Flask app deployment - Gunicorn with eventlet  
# https://flask-socketio.readthedocs.io/en/latest/#deployment
# Run with: gunicorn --bind localhost:8001 --worker-class eventlet -w 1 fserver:app
# 
# Optional: you can deploy Flask app only with eventlet (without Gunicorn)
# Than use monkey patching on the begining of the script
# https://flask-socketio.readthedocs.io/en/latest/#using-multiple-workers
# Run with: python3 fserver.py
# --------------------------------------------------------------------------------------------
# STATIC FILES
# 
# Recommended way of serving static files is to use Nginx. 
#
# location /controller/static {
#                alias /.../monitoring/static;
# }
#
# But if we don't want it, Flask can also serve static files...
# (https://stackoverflow.com/questions/20646822/how-to-serve-static-files-in-flask)
# --------------------------------------------------------------------------------------------
# SOCKET MULTIPLEXING
#
# If multiple connections on single websockets are needed, add "namespaces" to 
# the application...
# usecase: if SMS portal will need another WebSocket communication on default URL
# https://socket.io/docs/v3/namespaces/index.html
# https://flask-socketio.readthedocs.io/en/latest/
# --------------------------------------------------------------------------------------------
# CORS
# 
# For security reasons, CORS is not enabled by default, thus disabling WebSockets
# on different domains names than default server name - problem because of Nginx 
# proxying. WS client (script.js) can now connect to the WS server (fserver.py)
#
# Enableing all domains:
#       cors_allowed_origins="*"
# exposes potential risks (https://flask-socketio.readthedocs.io/en/latest/)
# so solution for now is:
#       cors_allowed_origins="http://localhost"
# 
# Read more on:
# https://socket.io/docs/v3/client-initialization/
# https://flask-socketio.readthedocs.io/en/latest/#cross-origin-controls
# --------------------------------------------------------------------------------------------
# ZMQ
# 
# Is used to communicate with Controller Docker container (zmq-broker.py) over
# 0MQ TCP sockets. ZMQ is not threadsafe (using zmq context in multiple threads
# is not safe), while SocketIO is. That's why they exchange messages via global 
# variables. Use Lock() before accessing them.
#
# IPC (inter process communication) sockets can be used if this script is 
# running on the same machine as broker script. Otherwise use TCP sockets.
# zmq.connect() must have parametrized address!
# While in Docker container, 127.0.0.1 won't work - use machine IP address
#
# TODO:
# Still haven't found a way to stop the background task when gunicorn exits.
# Now daemon task keeps running...but not so important because container dies.


    """
    { "type":"system", "data":message for controller}
    { "type":"command", "data":[message for device]}
    """