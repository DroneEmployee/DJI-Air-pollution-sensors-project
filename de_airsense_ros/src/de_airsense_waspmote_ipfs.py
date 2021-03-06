#! /usr/bin/python

import serial
import time
import array
import os
import errno
import ipfsapi
from std_msgs.msg import UInt8, Float32
from sensor_msgs.msg import NavSatFix
from geometry_msgs.msg import PointStamped
import rospy

DEFAULT_PORT = '/dev/ttyUSB0'
BAUDRATE = 115200
STOP_SYMBOL = b'$'
RATE_HZ = 1
IN_AIR_STANDBY = 3
ON_GROUND = 1

status_in_air = False
status_to_send = False
altitude_rel = 0.0
altitude_gps = 0.0
latitude = 0.0
longitude = 0.0

def ipfs_send (api, file):
    # for i in range(3):
    try:
        res = api.add(file)
        return res
    except:
        return 'IPFS error'

def write_send_data(frame_array, api_loc, api_rem):
    fileName = 'data_'
    dir = os.path.dirname(__file__)
    folderName = os.path.join(dir, 'sensor_data/')
    if not os.path.exists(os.path.dirname(folderName)):
        try:
            os.makedirs(os.path.dirname(folderName))
        except OSError as exc: # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
                
    timestr = time.strftime('%Y-%m-%d_%H-%M-%S')
    path = folderName + fileName + timestr + '.txt'
    with open (path, 'w') as f:
        for string in frame_array:
            f.write(string)
    print ('File wrote in')
    print (path)

    print ('IPFS remote node response:')
    res = ipfs_send(api_rem, path)
    print (res)
    print ('IPFS local node response:')
    res = ipfs_send(api_loc, path)
    print (res)
    
def status_cb(data): 
    global status_in_air
    global status_to_send
    if data.data == IN_AIR_STANDBY and status_in_air == False:
        status_in_air = True
        print 'Start to write data'
    elif data.data == ON_GROUND and status_in_air == True:
        print 'Stop to write data'
        status_to_send = True
        status_in_air = False

def gps_position_cb(data):
    global latitude
    global longitude
    global altitude_gps
    latitude = data.latitude
    longitude = data.longitude
    altitude_gps = data.altitude

def height_above_takeoff_cb(data):
    global altitude_rel
    altitude_rel = data.data

if __name__ == '__main__':
    print 'Starting waspmote gas sensors...'
    print 'Waiting for ROS services...'
    rospy.init_node('de_airsense_waspmore_ipfs')
    rospy.Subscriber('dji_sdk/flight_status', UInt8, status_cb)
    rospy.Subscriber('dji_sdk/gps_position', NavSatFix, gps_position_cb)
    rospy.Subscriber('dji_sdk/height_above_takeoff', Float32, height_above_takeoff_cb)
    ipfs_api_loc = ipfsapi.connect('127.0.0.1', 5001)
    ipfs_api_rem = ipfsapi.connect('52.178.98.62', 9095)

    rate = rospy.Rate(RATE_HZ)
    frame = ''
    frame_array = []
    serial_port = serial.Serial(DEFAULT_PORT, BAUDRATE, parity=serial.PARITY_NONE, 
                                                        stopbits=serial.STOPBITS_ONE, 
                                                        bytesize=serial.EIGHTBITS)
    waspmote_ready = False
    while not rospy.is_shutdown():
        try:    
            while serial_port.in_waiting > 0:
                if waspmote_ready == False:
                    waspmote_ready = True
                    print 'Waspmote gas sensors and ROS are ready'
                byte = serial_port.read()

                if byte == STOP_SYMBOL:
                    # frame += byte.decode()  
                    frame += 'Copter Latitude: {0:.6f}\nCopter Longitude: {1:.6f}\nCopter GPS Altitude: {2:.2f} m\nCopter Relative Altitude: {3:.2f} m\nSystem time: {4:s}\n'.format(   latitude, 
                                                                                                                        longitude, 
                                                                                                                        altitude_gps,
                                                                                                                        altitude_rel, 
                                                                                                                        time.strftime('%Y/%m/%d %H:%M:%S'))
                    frame_array.append(frame)
                    print (frame)
                    frame = ''
                    continue
                elif byte != b'\x86' and byte != b'\x00':
                    frame += byte.decode()

            if status_to_send:
                status_to_send = False
                write_send_data(frame_array, ipfs_api_loc, ipfs_api_rem)
                frame_array = []
            elif status_in_air == False:
                frame_array = []

            rate.sleep()

        except KeyboardInterrupt: 
            print '\nExit'
            break

