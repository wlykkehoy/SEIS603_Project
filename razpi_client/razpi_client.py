import argparse
import time
import board
import busio
import adafruit_si7021


# Some configuration data
CONFIG_DATA = {
    'DEVICE_ID': 'RazPi',                  # name for the device; used in messages
    'DELAY_BETWEEN_READINGS': 2,           # delay in seconds between sensor readings
    'API_URL': 'http://192.168.86.183:8000/readings/'
}


def c_to_f(temp_c):
    temp_f = (temp_c * 9 / 5) + 32.0
    return temp_f


def main_loop(verbose):
    i2c = busio.I2C(board.SCL, board.SDA)
    sensor = adafruit_si7021.SI7021(i2c)

    try:
        while True:
            temp_c = sensor.temperature
            temp_f = int(round(c_to_f(temp_c), 0))
            humidity =  int(round(sensor.relative_humidity, 0))         
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%Sz', time.gmtime(time.time()))
            packaged_data = {'dev_id': CONFIG_DATA['DEVICE_ID'],
                             'ts': timestamp,
                             'temp':  temp_f,
                             'humidity': humidity}
            if verbose:
                print('\nMessage:\n=>Data :{}'.format(packaged_data), flush=True)
            #response = requests.post(CONFIG_DATA['API_URL'], json=packaged_data)
            #if verbose:
            #    print('=>Response Status:{}\n=>Content:{}'.format(response.status_code, response.content), flush=True)
#        if response.status_code != 200:         # stop on the first failing POST
#            break
            
#            if verbose:
#                print('Temp: {:6.2f}C / {}F   Humidity: {}%'.format(temp_c, temp_f, humidity))
    
            time.sleep(CONFIG_DATA['DELAY_BETWEEN_READINGS'])
            
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
    main_loop(verbose)
    print('Client stopped', flush=True)

    


