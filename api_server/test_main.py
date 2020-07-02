# test_main.py
# Wade J Lykkehoy (WadeLykkehoy@gmail.com)

import sys
import argparse
import pandas as pd
import os
import requests

# Probably a more elegant way to deal with this info; but for now, this will work...
# TODO: Explore configparser
IP_ADDR = '192.168.86.183:8000'
CONFIG_DATA = {'get_count_url': {'readings':      'http://' + IP_ADDR + '/readings/counts/',
                                 'active_alerts': 'http://' + IP_ADDR + '/active-alerts/counts/',
                                 'alert_history': 'http://' + IP_ADDR + '/alert-history/counts/'},
               'delete_url': {'readings':      'http://' + IP_ADDR + '/readings/',
                              'active_alerts': 'http://' + IP_ADDR + '/active-alerts/',
                              'alert_history': 'http://' + IP_ADDR + '/alert-history/'},
               'post_url': {'readings': 'http://'+IP_ADDR+'/readings/'},
               'test_data_subdir': 'test_data'}


# Global var for producing lots of output during execution. Only makes sense
# when NOT running via pytest as pytest will suppress output. Overridden (i.e. set
# to True via command line arg.
verbose = False


def delete_records(collections_to_clear, dev_id=None):
    """
    Utility function to delete all records in the passed list of tables/collections. We do this by sending
    a DELETE request for each specified table/collection. If dev-id is specified, only deletes for the
    specified device, else deletes for all devices.

    Args:
        collections_to_clear:   List of collections (resources) to send
        dev_id (str):           ID of device to delete records for; if not specified records are
                                  deleted for all devices.

    Returns:
        Status code from the HTTP request.
    """
    if verbose:
        print('Clearing collections {}, dev_id=\'{}\''.format(collections_to_clear, dev_id), flush=True)

    assert len(collections_to_clear) > 0        # this should never happen...

    params = {}
    if dev_id is not None:
        params = {'dev-id': dev_id}
    response = None     # here just to get rid of PEP8 warning
    for collection in collections_to_clear:
        response = requests.delete(CONFIG_DATA['delete_url'][collection], params=params)
        if response.status_code != 200:  # stop on the first failing HTTP request
            break

    return response.status_code


def doc_count(collection, dev_id, alert_type=None):
    """
    Utility function to count records in the passed tables/collections for the passed device ID.
    If the alert type is passed, only a count of those specific alert types are returned, else
    a count of any/all alert types is returned.

    Args:
        dev_id (str):       ID of device to count records for
        alert_type (str):   Type of alert to get count for; None returns any/all alert types

    Returns:
        Status code from the HTTP request.
    """
    if verbose:
        print('Counting collection {}, dev_id=\'{}\', alert_type=\'{}\''.format(collection, dev_id, alert_type), flush=True)

    assert dev_id is not None           # Should never happen ....

    params = {'dev-id': dev_id}
    if alert_type is not None:
        params['alert-type'] = alert_type
    response = requests.get(CONFIG_DATA['get_count_url'][collection], params=params)

    if verbose:
        print('  count = {}'.format(int(response.content)), flush=True)

    return response.status_code, int(response.content)


def send_sensor_reading_messages(message_filename):
    """
    Utility function to read the sensor reading data from a file and send via POST.

    Args:
        message_filename (str):     Filename containing the sensor readings.

    Returns:
        Status code from the HTTP request.
    """
    # load the message data up; note the file contains 1 or more messages, one per row, with a header
    full_pathname = os.path.join(CONFIG_DATA['test_data_subdir'], message_filename)
    if verbose:
        print('Reading test data from file: ', full_pathname, flush=True)
    tests = pd.read_csv(full_pathname)      # using pandas to read the file
    if verbose:
        print('The file contains {} device sensor messages'.format(len(tests)), flush=True)
    assert(len(tests) > 0)      # an empty test data file should never happen...

    # For each message to send, package the data and send via POST
    response = None     # here just to get rid of PEP8 warning that reponse may not be set when return is hit
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
    # Wipe the DB for our test device
    delete_records(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

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
    # Wipe the DB for our test device
    delete_records(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

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
    # Wipe the DB for our test device
    delete_records(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_trigger_temp_alert.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = doc_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was generated for temperature
    status, count = doc_count('active_alerts', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 1


def test_trigger_and_clear_temp_alert():
    """
    Test triggering a temperature alert.

    Data file: test_trigger_and_clear_temp_alert_pt1.csv & test_trigger_and_clear_temp_alert_pt2.csv
    """
    # Wipe the DB for our test device
    delete_records(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the first part of the readings; should trigger the alert
    status = send_sensor_reading_messages('test_trigger_and_clear_temp_alert_pt1.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = doc_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 5

    # Confirm alert was generated for temperature
    status, count = doc_count('active_alerts', 'razpi_sim_01', 'temp')
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
    status, count = doc_count('active_alerts', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 0

    # And we should now have a record in alert history
    status, count = doc_count('alert_history', 'razpi_sim_01', 'temp')
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
    test_to_run = args.t

    if test_to_run is not None:        # Was given a single test to run ...
        if test_to_run not in globals():
            print('Test "{}" not found. Check the spelling or run with no arguments to see a list of available tests.'.format(test_to_run))
            sys.exit(2)
        else:
            print('Running test "{}"...'.format(test_to_run), flush=True)
            globals()[test_to_run]()
    else:                              # Just dump the list of tests with their docstrings
        for item in list(globals()):
            if item.startswith('test_'):
                print(item, ':', sep='', end='')
                print('    ', globals()[item].__doc__)


if __name__ == '__main__':
    main()
