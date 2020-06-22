import sys
import argparse
import pandas as pd
import os
import requests


# Probably a more elegant way to deal with this info; but for now, this will work...
CONFIG_DATA = {'API_URL': 'http://192.168.86.183:8000/readings/',
               'TEST_DATA_SUBDIR': 'test_data'}

# Global var for producing lots of output during execution; only makes sense
# when NOT running via pytest
verbose = False


def send_sensor_reading_messages(message_filename):
    # load the message data up; note the file contains 1 or more messages, one per row, with a header
    full_pathname = os.path.join(CONFIG_DATA['TEST_DATA_SUBDIR'], message_filename)
    if verbose: print('Reading test data from file: ', full_pathname, flush=True)
    tests = pd.read_csv(full_pathname)
    if verbose: print('The file contains {} device sensor messages'.format(len(tests)), flush=True)
    assert(len(tests) > 0)      # an empty test data file should never happen...

    # For each message to send, package the data and send via POST
    response = None     # here just to get rid of PEP8 warning
    for idx, message_data in tests.iterrows():
        packaged_data = {'dev_id': message_data['dev_id'],
                         'ts': message_data['ts'],
                         'temp': message_data['temp'],
                         'humidity': message_data['humidity']}
        if verbose: print('\nMessage {}:\n=>Data :{}'.format((idx + 1), packaged_data), flush=True)
        response = requests.post(CONFIG_DATA['API_URL'], json=packaged_data)
        if verbose: print('=>Response Status:{}\n=>Content:{}'.format(response.status_code, response.content), flush=True)
        if response.status_code != 200:         # stop on the first failing POST
            break

    return response


def test_1_message_in_range():
    """
    Test for the successful send of a single sensor reading message.
    Data file: test_1_message_in _range.csv
    """
    response = send_sensor_reading_messages('test_1_message_in_range.csv')
    assert response.status_code == 200


def test_10_messages_in_range():
    """
    Test for the successful send of 10 sensor reading messages.
    Data file: test_10_messages_in_range.csv
    """
    response = send_sensor_reading_messages('test_10_messages_in_range.csv')
    assert response.status_code == 200


def main():
    # When run directly rather than via pytest the behavior depends on the
    # command line arguments:
    #   no arguments - Dump a list of tests in this file
    #   -t <test>    - Run only <test>
    #   -v           - Verbose mode; really only makes sense with -t <test>; this combo
    #                  is handy for running a single test outside of pytest for debugging

    global verbose     # I know, not good practice...

    # Extract command line args
    my_parser = argparse.ArgumentParser()
    my_parser.add_argument('-v', action='store_true')
    my_parser.add_argument('-t', action='store', type=str)
    args = my_parser.parse_args()
    verbose = args.v
    single_test_name = args.t

    if single_test_name is not None:        # Was given a single test to run ...
        if single_test_name not in globals():
            print('Test "{}" not found. Check the spelling or run with no arguments to see a list of available tests.'.format(single_test_name))
            sys.exit(2)
        else:
            print('Running test "{}"...'.format(single_test_name))
            globals()[single_test_name]()
    else:                                   # Just dump the list of tests
        for item in list(globals()):
            if item.startswith('test_'):
                print(item, ':', sep='', end='')
                print('    ', globals()[item].__doc__)


if __name__ == '__main__':
    main()

