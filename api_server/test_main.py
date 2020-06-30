# test_main.py
# Wade J Lykkehoy (WadeLykkehoy@gmail.com)

import sys
import argparse
import pandas as pd
import os
import requests

# Probably a more elegant way to deal with this info; but for now, this will work...
IP_ADDR = '192.168.86.183:8000'
CONFIG_DATA = {'get_count_url': {'readings':      'http://' + IP_ADDR + '/readings/counts/',
                                 'active_alerts': 'http://' + IP_ADDR + '/active-alerts/counts/',
                                 'alert_history': 'http://' + IP_ADDR + '/alert-history/counts/'},
               'delete_url': {'readings':      'http://' + IP_ADDR + '/readings/',
                              'active_alerts': 'http://' + IP_ADDR + '/active-alerts/',
                              'alert_history': 'http://' + IP_ADDR + '/alert-history/'},
               'post_url': {'readings': 'http://'+IP_ADDR+'/readings/'},
               'test_data_subdir': 'test_data'}


# Global var for producing lots of output during execution; only makes sense
# when NOT running via pytest as pytest will suppress output
verbose = False


def clear_collections(collections_to_clear, dev_id=None):
    assert len(collections_to_clear) > 0        # this should never happen...

    if verbose:
        print('Clearing collections {}, dev_id=\'{}\''.format(collections_to_clear, dev_id), flush=True)

    params = {}
    if dev_id is not None:
        params = {'dev-id': dev_id}
    response = None     # here just to get rid of PEP8 warning
    for collection in collections_to_clear:
        response = requests.delete(CONFIG_DATA['delete_url'][collection], params=params)
        if response.status_code != 200:  # stop on the first failing POST
            break

    return response.status_code


def doc_count(collection, dev_id):
    if verbose:
        print('Counting collection {}, dev_id=\'{}\''.format(collection, dev_id), flush=True)

    params = {'dev-id': dev_id}
    response = requests.get(CONFIG_DATA['get_count_url'][collection], params=params)

    if verbose:
        print('  count = {}'.format(int(response.content)), flush=True)

    return response.status_code, int(response.content)


def send_sensor_reading_messages(message_filename):
    # load the message data up; note the file contains 1 or more messages, one per row, with a header
    full_pathname = os.path.join(CONFIG_DATA['test_data_subdir'], message_filename)
    if verbose:
        print('Reading test data from file: ', full_pathname, flush=True)
    tests = pd.read_csv(full_pathname)
    if verbose:
        print('The file contains {} device sensor messages'.format(len(tests)), flush=True)
    assert(len(tests) > 0)      # an empty test data file should never happen...

    # For each message to send, package the data and send via POST
    response = None     # here just to get rid of PEP8 warning
    for idx, message_data in tests.iterrows():
        packaged_data = {'dev_id': message_data['dev_id'],
                         'ts': message_data['ts'],
                         'temp': message_data['temp'],
                         'humidity': message_data['humidity']}
        if verbose:
            print('Sending Message {}...\n  =>Data :{}'.format((idx + 1), packaged_data), flush=True)
        response = requests.post(CONFIG_DATA['post_url']['readings'], json=packaged_data)
        if verbose:
            print('  <= Status:{}\n     Content:{}'.format(response.status_code, response.content), flush=True)
        if response.status_code != 200:         # stop on the first failing POST
            break

    return response.status_code


def test_1_message_in_range():
    """
    Test for the successful send of a single sensor reading message wth all readings
    in range.

    Data file: test_1_message_in _range.csv
    """
    # Wipe the DB
    clear_collections(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_1_message_in_range.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = doc_count('readings', 'razpi_sim_01')

    assert status == 200
    assert count == 1


def test_10_messages_in_range():
    """
    Test for the successful send of 10 sensor reading messages with all readings
    in range thus no alerts should occur.

    Data file: test_10_messages_in_range.csv
    """
    # Wipe the DB
    clear_collections(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_10_messages_in_range.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = doc_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm no alert was generated
    status, count = doc_count('active_alerts', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_trigger_temp_alert():
    """
    Test triggering a temperature alert.

    Data file: test_trigger_temp_alert.csv
    """
    # Wipe the DB
    clear_collections(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_trigger_temp_alert.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = doc_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was generated
    status, count = doc_count('active_alerts', 'razpi_sim_01')
    assert status == 200
    assert count == 1


def test_trigger_and_clear_temp_alert():
    """
    Test triggering a temperature alert.

    Data file: test_trigger_and_clear_temp_alert_pt1.csv & test_trigger_and_clear_temp_alert_pt2.csv
    """
    # Wipe the DB
    clear_collections(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the first part of the readings; should trigger the alert
    status = send_sensor_reading_messages('test_trigger_and_clear_temp_alert_pt1.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = doc_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 5

    # Confirm alert was generated
    status, count = doc_count('active_alerts', 'razpi_sim_01')
    assert status == 200
    assert count == 1

    # Send the second part of the readings; should clear the alert
    status = send_sensor_reading_messages('test_trigger_and_clear_temp_alert_pt2.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = doc_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was cleared
    status, count = doc_count('active_alerts', 'razpi_sim_01')
    assert status == 200
    assert count == 0

    # And we should now have a record in alert history
    status, count = doc_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 1


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
            print('Running test "{}"...'.format(single_test_name), flush=True)
            globals()[single_test_name]()
    else:                                   # Just dump the list of tests
        for item in list(globals()):
            if item.startswith('test_'):
                print(item, ':', sep='', end='')
                print('    ', globals()[item].__doc__)


if __name__ == '__main__':
    main()

