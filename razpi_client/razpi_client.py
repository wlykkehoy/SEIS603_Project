# razpi_client.py
# Wade J Lykkehoy (wlykkehoy@gmail.com)
"""
This is the client-side code which runs on the Raspberry Pi. It is run
as follows:

  python3 razpi_client.py [-v]
  
The -v option is for 'verbose' behavior; it prints messages prior to
sending on to the RESTful API and prints return status info.
"""

import argparse
import datetime
import time
import board
import busio
import adafruit_si7021
import requests
import collections


# Some configuration data
# TODO: find a better way to deal with this info
CONFIG_DATA = {
    'device_id': 'RazPi_01',                      # name for the device; used in messages
    'delay_between_readings': 5,                  # delay in seconds between sensor readings; 900 = 15min
    'num_recent_post_status_codes_to_look_at': 4, # we might expect a failed POST periodically,
                                                  #  thus will look at this many most-recent POST reqeust
                                                  #   status codes to determine if there is an issue and
                                                  #   should bail
    'post_readings_url': 'http://192.168.86.183:8000/readings/'
}

TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


def c_to_f(temp_c):
    """
    Utility function that converts a temperature in Celcius to Farenheit.

    Args:
        temp_c (float):  The temperature to covert

    Returns:
        The temperature in Farenheit
    """
    temp_f = (temp_c * 9 / 5) + 32.0
    return temp_f


def main(verbose):
    """
    Main loop of the app & where all the fun happens.

    Args:
        verbose (bool): If True, a lot of info is printed during execution.
    """
    recent_post_status_codes_ok = collections.deque([True] * CONFIG_DATA['num_recent_post_status_codes_to_look_at'],
                                                    maxlen=CONFIG_DATA['num_recent_post_status_codes_to_look_at'])
        
    # Our interface objects to the Adafruit SI7021 temp & humidity sensor
    i2c = busio.I2C(board.SCL, board.SDA)
    sensor = adafruit_si7021.SI7021(i2c)

    try:
        while True:      # Only way to exit is user hitting Ctrl-C
            temp_c = sensor.temperature
            temp_f = int(round(c_to_f(temp_c), 0))                  # only want integer portion
            humidity = int(round(sensor.relative_humidity, 0))     # only want integer portion
            now = datetime.datetime.now()
            timestamp = now.strftime(TIMESTAMP_FORMAT)
            
            # Package up the data to send to the RESTful API
            packaged_data = {'dev_id': CONFIG_DATA['device_id'],
                             'ts': timestamp,
                             'temp':  temp_f,
                             'humidity': humidity}
            if verbose:
                print('Sending Message...\n  =>Data :{}'.format(packaged_data), flush=True)
            response = requests.post(CONFIG_DATA['post_readings_url'], json=packaged_data)
            if verbose:
                print('  <=Status:{}\n    Content:{}'.format(response.status_code, response.content), flush=True)

            # Keep track of the most recent status codes; if none were successful, bail
            recent_post_status_codes_ok.append(response.status_code == 200)
            if not any(recent_post_status_codes_ok):
                print('ERROR: The most recent {} POSTs have failed; halting execution'.format(CONFIG_DATA['num_recent_post_status_codes_to_look_at']))
                break
           
            # A delay before sending the next reading
            time.sleep(CONFIG_DATA['delay_between_readings'])
            
    except KeyboardInterrupt:
        # Just fall back to main
        print('... Ctrl-C detected, ending ...', flush=True)
        

if __name__ == '__main__':
    # Pull off command line args
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument('-v', action='store_true', help='verboase mode; echoes message contents')
    args = my_parser.parse_args()
    verbose = args.v

    print('Client started, press Ctrl-C to stop...', flush=True)
    main(verbose)
    print('Client stopped', flush=True)
