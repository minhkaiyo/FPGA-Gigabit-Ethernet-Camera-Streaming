import socketio
import threading
import time

sio = socketio.Client()

def close_later():
    time.sleep(5)
    sio.disconnect()

@sio.event
def connect():
    print('Connected')
    threading.Thread(target=close_later).start()

@sio.on('system_status')
def on_sys(data):
    print('sys:', data)

@sio.on('device_update')
def on_dev(data):
    print('dev_update RECV')

sio.connect('http://localhost:5000')
sio.wait()
