# test_main.py
# Wade J Lykkehoy (WadeLykkehoy@gmail.com)
"""
This is the server testing code. It is based on the pytest framework. It also
allows running tests to be run directly (vs through pytest). This allows a 
'verboase' mode where key points of the processing are echoed to stdout. Handy
when developing individual tests to ensure the sequence is as intended.

When run directly rather than via pytest the behavior depends on the
command line arguments:
    no arguments - Dump a list of tests in this file
    -t <test>    - Run only <test>
    -v           - Verbose mode; really only makes sense with -t <test>; this combo
                   is handy for running a single test outside of pytest for debugging
                 
Examples:

    pytest test_main.py                     - Runs all tests via pytest
    pytest test_main.py:test-name           - Runs test, test-name, under pytest 
    
    python test_main.py                     - Dumps a list of tests
    python test_main.py -v -t test-name     - Runs test, test-name, in verbose mode
"""

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


def delete_resources(resource_names, dev_id=None):
    """
    Utility function to delete instances of the specified resource(s) (i.e. docs from the specified
    collections in our MongoDB). We do this by sending a DELETE reqeust for each
    specified resource. If a device ID is specified, only instances of the resouce(s) for that device ID
    are deleted. If a device ID is not specified, all instances of the resource(s) are deleted.

    Args:
        resource_names:   List of the names of the resources to delete
        dev_id (str):     ID of device to delete resource instances for; if not specified instances are
                            deleted for all devices.

    Returns:
        Status code from the HTTP request.
    """
    if verbose:
        print('Deleting {}, dev_id=\'{}\''.format(resource_names, dev_id), flush=True)

    assert len(resource_names) > 0        # this should never happen...

    params = {}
    if dev_id is not None:
        params = {'dev-id': dev_id}
    response = None     # here just to get rid of PEP8 warning
    for resource in resource_names:
        response = requests.delete(CONFIG_DATA['delete_url'][resource], params=params)
        if response.status_code != 200:  # stop on the first failing HTTP request
            break

    return response.status_code


def resource_count(resource_name, dev_id, reading_type=None):
    """
    Utility function to count the number of a specified resource for the specified device ID (i.e.
    the number of docs in our MongoDB). If the reading type is passed, only a count of those
    specific reading types are returned, else a count of any/all reading types is returned.

    Args:
        resource_name (str):  Resource to get counts for
        dev_id (str):         ID of device to get count for
        reading_type (str):   Type of reading to get count for; None returns any/all reading types

    Returns:
        Status code from the HTTP request.
    """
    if verbose:
        print('Counting {}, dev_id=\'{}\', reading_type=\'{}\''.format(resource_name, dev_id, reading_type), flush=True)

    assert dev_id is not None           # Should never happen ....

    params = {'dev-id': dev_id}
    if reading_type is not None:
        params['reading-type'] = reading_type
    response = requests.get(CONFIG_DATA['get_count_url'][resource_name], params=params)

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
    response = None     # here just to get rid of PEP8 warning that response may not be set when return is hit
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
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_1_message_in_range.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 1

    # Confirm no alert was generated
    status, count = resource_count('active_alerts', 'razpi_sim_01')
    assert status == 200
    assert count == 0

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_10_messages_in_range():
    """
    Test for the successful send of 10 sensor reading messages with all readings
    in range thus no alerts should occur.

    Data file: test_10_messages_in_range.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_10_messages_in_range.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm no alert was generated
    status, count = resource_count('active_alerts', 'razpi_sim_01')
    assert status == 200
    assert count == 0

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_trigger_temp_alert_high_readings():
    """
    Test triggering a temperature alert based on high temperature readings.

    Data file: test_trigger_temp_alert_high_readings.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_trigger_temp_alert_high_readings.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was generated for temperature
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 1

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_trigger_temp_alert_low_readings():
    """
    Test triggering a temperature alert based on low temperature readings.

    Data file: test_trigger_temp_alert_low_readings.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_trigger_temp_alert_low_readings.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was generated for temperature
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 1

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_trigger_and_clear_temp_alert():
    """
    Test triggering a temperature alert then clearing it.

    Data file: test_trigger_and_clear_temp_alert_pt1.csv & test_trigger_and_clear_temp_alert_pt2.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the first part of the readings; should trigger the alert
    status = send_sensor_reading_messages('test_trigger_and_clear_temp_alert_pt1.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 5

    # Confirm alert was generated for temperature
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 1

    # Send the second part of the readings; should clear the alert
    status = send_sensor_reading_messages('test_trigger_and_clear_temp_alert_pt2.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was cleared
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 0

    # And we should now have a record in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 1


def test_temp_alert_then_readings_in_and_out_of_range():
    """
    Test triggering a temp alert, then readings continue, alternating in and
    out of range. The alert condition should continue.

    Data file: test_temp_alert_then_readings_in_and_out_of_range.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_temp_alert_then_readings_in_and_out_of_range.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 15

    # Confirm alert was generated for temperature
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 1

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_temp_readings_in_and_out_of_range():
    """
    Test temperature readings alternating between in and out of range. No alert should
    occur.

    Data file: test_temp_readings_in_and_out_of_range.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_temp_readings_in_and_out_of_range.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 15

    # Confirm no alert was generated for temperature
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 0

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_trigger_humidity_alert_high_readings():
    """
    Test triggering a humidity alert based on high humidity readings.

    Data file: test_trigger_humidity_alert_high_readings.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_trigger_humidity_alert_high_readings.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was generated for humidity
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'humidity')
    assert status == 200
    assert count == 1

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_trigger_humidity_alert_low_readings():
    """
    Test triggering a humidity alert based on low humidity readings.

    Data file: test_trigger_humidity_alert_low_readings.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_trigger_humidity_alert_low_readings.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was generated for humidity
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'humidity')
    assert status == 200
    assert count == 1

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_trigger_and_clear_humidity_alert():
    """
    Test triggering a temperature alert then clearing it.

    Data file: test_trigger_and_clear_humidity_alert_pt1.csv & test_trigger_and_clear_humidity_alert_pt2.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the first part of the readings; should trigger the alert
    status = send_sensor_reading_messages('test_trigger_and_clear_humidity_alert_pt1.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 5

    # Confirm alert was generated for humidity
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'humidity')
    assert status == 200
    assert count == 1

    # Send the second part of the readings; should clear the alert
    status = send_sensor_reading_messages('test_trigger_and_clear_humidity_alert_pt2.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was cleared
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'humidity')
    assert status == 200
    assert count == 0

    # And we should now have a record in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01', 'humidity')
    assert status == 200
    assert count == 1


def test_humidity_alert_then_readings_in_and_out_of_range():
    """
    Test triggering a humidity alert, then readings continue, alternating in and
    out of range. The alert condition should continue.

    Data file: test_humidity_alert_then_readings_in_and_out_of_range.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_humidity_alert_then_readings_in_and_out_of_range.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 15

    # Confirm alert was generated for temperature
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'humidity')
    assert status == 200
    assert count == 1

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_humidity_readings_in_and_out_of_range():
    """
    Test humidity readings alternating between in and out of range. No alert should
    occur.

    Data file: test_humidity_readings_in_and_out_of_range.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_humidity_readings_in_and_out_of_range.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 15

    # Confirm alert was generated for temperature
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'humidity')
    assert status == 200
    assert count == 0

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def test_trigger_temp_and_humidity_alert():
    """
    Test triggering both a temperature and a humidity alert.

    Data file: test_trigger_temp_and_humidity_alert.csv
    """
    # Wipe the DB for our test device
    delete_resources(['readings', 'active_alerts', 'alert_history'], 'razpi_sim_01')

    # Send the readings
    status = send_sensor_reading_messages('test_trigger_temp_and_humidity_alert.csv')
    assert status == 200

    # Confirm the correct count of readings got stored in the DB
    status, count = resource_count('readings', 'razpi_sim_01')
    assert status == 200
    assert count == 10

    # Confirm alert was generated for temperature
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'temp')
    assert status == 200
    assert count == 1

    # Confirm alert was generated for humidity
    status, count = resource_count('active_alerts', 'razpi_sim_01', 'humidity')
    assert status == 200
    assert count == 1

    # And there should be nothing in alert history
    status, count = resource_count('alert_history', 'razpi_sim_01')
    assert status == 200
    assert count == 0


def main():
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
