# main.py
# Wade J Lykkehoy (WadeLykkehoy@gmail.com)

import os
import datetime
from fastapi import FastAPI, Query
from pydantic import BaseModel
import pymongo
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

# TODO: Find a better way to deal with this; maybe configparser or store in the MongoDB?
CONFIG_DATA = {'monbodb_server_url': 'mongodb+srv://razpi:razpipzar@cluster0-ylplp.mongodb.net/basement_data?retryWrites=true&w=majority',
               'num_continuous_readings_to_check': 4,
               'temp_range_min': 65,
               'temp_range_max': 70,
               'humidity_range_min': 40,
               'humidity_range_max': 50,
               'alert_renotification_delay': 1,     # num minutes to wait to resend an alert notification email
               'email_from': 'WadeLykkehoy@ZenDataAnalytics.com',
               'email_to': ' WadeLykkehoy@gmail.com'
               }

TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

TRACE_MESSAGE_PROCESSING = True         # For debugging; echos message processing calls to stdout
                                        # TODO: explore the logging library/module for this


# =================================================================================================
# The following code loads our secret data (keys) and instantiates the FastAPI instances.
# The FastAPI implementation requires this code to be here vs inside a main() function.
# =================================================================================================

# Our API keys and other secret/secure items; load from environment variables
SECRET_DATA = {'sendgrid_api_key': os.environ.get('sendgrid_api_key')}
assert SECRET_DATA['sendgrid_api_key'] is not None

app = FastAPI()                        # Our FastAPI instance object


# =================================================================================================
# The following code process readings related messages; post / get count / delete
# =================================================================================================

# Defines the message body that we will receive when a 'reading' message is posted
class ReadingsMsgBody(BaseModel):
    dev_id: str     # a unique ID for the device
    ts: str         # reading timestamp; in UTC: "2020-06-18T11:06:00Z"
    temp: int       # temperature in Fahrenheit
    humidity: int   # humidity as an integer percentage (e.g. 45 for 45%)


@app.get("/readings/counts/")
def get_readings_counts(dev_id: str = Query(None,
                                            alias='dev-id',
                                            description='ID of the device')):
    # Note the docstring is picked up by the OpenAPI doc tools, thus only include info
    # that makes sense from an API end-user's perspective.
    """
    Process a GET request for resource 'readings/counts'.

    The request supports one optional parameter, dev-id, which is the ID for the device
    to return the count for. If not specified, a total count of readings is returned.
    """
    if TRACE_MESSAGE_PROCESSING:
        print('==> get_readings_counts({})'.format(dev_id), flush=True)

    # Connect to the MongoDB database; note it is hosted on Mongo Atlas
    client = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    db = client.basement_data       # This is the database we are using

    # Do the count for either all or the specified device
    query = {}
    if dev_id is not None:
        query['dev_id'] = dev_id
    num_docs = db.readings.count_documents(query)

    # Close the MongoDB connection when we are done with it
    client.close()

    return num_docs


def send_alert_notification_email(dev_id, reading_type, current_value):
    """
    Send an alert notification email using SendGrid.

    Args:
        dev_id (int):           ID of the device for which the alert occurred
        reading_type (str):     Type of reading; either 'temp' or 'humidity'
        current_value (int):    Current value for either 'temp' or 'humidity'

    Returns:
        None
    """
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> send_alert_notification_email({}, {}, {})'.format(dev_id, reading_type, current_value))

    if reading_type == 'temp':
        subject = '{} - Temperature Alert'.format(dev_id)
        html_content = '<p><h2>{} Temperature Alert</h2></p>'.format(dev_id)
        html_content += '<p>Current temperature is {}F.</p>'.format(current_value)
    else:
        subject = '{} - Humidity Alert'.format(dev_id)
        html_content = '<p><h2>{} Humidity Alert</h2></p>'.format(dev_id)
        html_content += '<p>Curent humidity is {}%.</p>'.format(current_value)

    message = Mail(from_email=CONFIG_DATA['email_from'],
                   to_emails=CONFIG_DATA['email_to'],
                   subject=subject,
                   html_content=html_content)
    sendgrid_client = SendGridAPIClient(SECRET_DATA['sendgrid_api_key'])
    sendgrid_client.send(message)


def send_alert_cleared_notification_email(dev_id, reading_type, current_value):
    """
    Send an alert cleared notification email using SendGrid.

    Args:
        dev_id (int):           ID of the device for which the alert occurred and is now cleared
        reading_type (str):     Type of reading; either 'temp' or 'humidity'
        current_value (int):    Current value for either 'temp' or 'humidity' for the device

    Returns:
        None
    """

    if TRACE_MESSAGE_PROCESSING:
        print('  ==> send_alert_cleared_notification_email({}, {}, {})'.format(dev_id, reading_type, current_value))

    if reading_type == 'temp':
        subject = '{} - Temperature Alert Cleared'.format(dev_id)
        html_content = '<p><h2>{} Temperature Alert Cleared</h2></p>'.format(dev_id)
        html_content += '<p>Current temperature is {}F.</p>'.format(current_value)
    else:
        subject = '{} - Humidity Alert Cleared'.format(dev_id)
        html_content = '<p><h2>{} Humidity Alert Cleared</h2></p>'.format(dev_id)
        html_content += '<p>Curent humidity is {}%.</p>'.format(current_value)

    message = Mail(from_email=CONFIG_DATA['email_from'],
                   to_emails=CONFIG_DATA['email_to'],
                   subject=subject,
                   html_content=html_content)
    sendgrid_client = SendGridAPIClient(SECRET_DATA['sendgrid_api_key'])
    sendgrid_client.send(message)


def is_an_existing_active_alert(db, dev_id, reading_type):
    """
    Utility function to check if there is currently an active alert by counting
    active alert records for this device/reading_type in the DB.

    Args:
        db:                   Connection to our MongoDB database
        dev_id (str):         Device ID to check for active alerts
        reading_type (str):   Type of reading; 'temp' or 'humidity'

    Returns:
        True if there is an existing alert of type reading_type for dev_id; else False
    """
    query = {'dev_id': dev_id,
             'reading_type': reading_type}
    num_docs = db.active_alerts.count_documents(query)
    return num_docs > 0


def renotify_if_notification_delay_exceeded(db, dev_id, reading_type, current_value):
    """
    Called when we continue in an alert condition for the specified device / reading type
    to check if we should re-send an alert notification email. To avoid being spammed with
    email, we have a delay time between email sends.

    Args:
        db:                   Connection to our MongoDB database
        dev_id (str):         Device ID to check for active alerts
        reading_type (str):   Type of reading; 'temp' or 'humidity'
        current_value (int):  Current value for either 'temp' or 'humidity' for the device

    Returns:
        None
    """
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> renotify_if_notification_delay_exceeded({}, {}, {})'.format(dev_id, reading_type, current_value))

    # First, fetch the active alert record from the DB
    query = {'dev_id': dev_id,
             'reading_type': reading_type}
    docs = db.active_alerts.find(query)

    # Calculate how much time has elapsed since a notification was sent
    now = datetime.datetime.now()
    alert_notification_datetime = datetime.datetime.strptime(docs[0]['notification_ts'], TIMESTAMP_FORMAT)
    elapsed_time = now - alert_notification_datetime
    elapsed_time_minutes = elapsed_time.seconds // 60

    # If the elapsed time exceeds our alert notification delay, update timestamp in DB and resend a notification
    if elapsed_time_minutes >= CONFIG_DATA['alert_renotification_delay']:
        formatted_ts = now.strftime(TIMESTAMP_FORMAT)
        update = {'$set': {'notification_ts': formatted_ts}}
        db.active_alerts.update_one(query, update)

        send_alert_notification_email(dev_id, reading_type, current_value)


def handle_out_of_range_condition(db, dev_id, reading_type, current_value):
    """
    Handles action(s) to take for readings being out of range. If we already have an active alert,
    treat it as a continuation of that active alert. If there is no active alert, create one.

    Args:
        db:                   Connection to our MongoDB database
        dev_id (str):         Device ID to check for active alerts
        reading_type (str):   Type of reading; 'temp' or 'humidity'
        current_value (int):  Current value for either 'temp' or 'humidity' for the device

    Returns:
        None
    """
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> handle_alert_condition({}, {}, {})'.format(dev_id, reading_type, current_value))

    if is_an_existing_active_alert(db, dev_id, reading_type):     # we are continuing an existing out of range condition
        renotify_if_notification_delay_exceeded(db, dev_id, reading_type, current_value)
    else:  # Is no existing alert, so insert an active alert record into the DB & send a notification
        now = datetime.datetime.now()
        formatted_ts = now.strftime(TIMESTAMP_FORMAT)
        data = {'dev_id': dev_id,
                'reading_type': reading_type,
                'originated_ts': formatted_ts,
                'notification_ts': formatted_ts}
        db.active_alerts.insert_one(data)

        send_alert_notification_email(dev_id, reading_type, current_value)


def handle_in_range_condition(db, dev_id, reading_type, current_value):
    """
    Handles actions to take for readings being in range. If there is an active alert, cancel it. If there
    is no active alert, no action needed.

    Args:
        db:                   Connection to our MongoDB database
        dev_id (str):         Device ID to check for active alerts
        reading_type (str):   Type of reading; 'temp' or 'humidity'
        current_value (int):  Current value for either 'temp' or 'humidity' for the device

    Returns:
        None
    """
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> clear_active_alert_if_is_one({}, {}, {})'.format(dev_id, reading_type, current_value))

    if is_an_existing_active_alert(db, dev_id, reading_type):
        # First, fetch the active alert record
        query = {'dev_id': dev_id,
                 'reading_type': reading_type}
        docs = db.active_alerts.find(query)

        # Put a record into our alert history
        now = datetime.datetime.now()
        formatted_ts = now.strftime(TIMESTAMP_FORMAT)
        data = {'dev_id': dev_id,
                'reading_type': reading_type,
                'originated_ts': docs[0]['originated_ts'],
                'cleared_ts': formatted_ts}
        db.alert_history.insert_one(data)

        # Remove the active alert record (should be just 1, however
        #  using delete_many is a 'DB self cleaning' tactic
        query = {'dev_id': dev_id,
                 'reading_type': reading_type}
        db.active_alerts.delete_many(query)

        # Send an email indicating an active alert was cleared
        send_alert_cleared_notification_email(dev_id, reading_type, current_value)


def handle_mixed_in_and_out_of_range_condition(db, dev_id, reading_type, current_value):
    """
    Handles situation where we have readings both out of range and in range. If there is an
    active alert, treat it as a continuation of that active alert. If there is no active
    alert, treat it as a non-alert condition, hence no additional action needed.

    Args:
        db:                   Connection to our MongoDB database
        dev_id (str):         Device ID to check for active alerts
        reading_type (str):   Type of reading; 'temp' or 'humidity'
        current_value (int):  Current value for either 'temp' or 'humidity' for the device

    Returns:
        None
    """
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> continue_current_condition({}, {}, {})'.format(dev_id, reading_type, current_value))

    if is_an_existing_active_alert(db, dev_id, reading_type):  # Check if it it time to resend notification
        renotify_if_notification_delay_exceeded(db, dev_id, reading_type, current_value)


def recent_readings_range_check(db, dev_id):
    """
    Checks if the most recent readings (number is based on configuration value num_continuous_readings_to_check)
    are all within range or all outside of range for temp and humidity.

    Args:
        db:                   Connection to our MongoDB database
        dev_id (str):         Device ID to check for active alerts

    Returns:
        4-tuple of booleans: (all temperature readings are outside of range,
                              all temperature readings are inside range,
                              all humidity readings are outside of range,
                              all humidity readings are inside of range)
    """
    # Will build up a list of True/False values; one per reading indicating whether it is out of range
    temp_out_of_range = []
    humidity_out_of_range = []

    # Fetch the most recent num_continuous_readings_to_check readings and check if they are in range
    query = {'dev_id': dev_id}
    docs = db.readings.find(query).sort("ts", pymongo.DESCENDING).limit(CONFIG_DATA['num_continuous_readings_to_check'])
    for doc in docs:
        check_result = (doc['temp'] < CONFIG_DATA['temp_range_min']) or \
                       (doc['temp'] > CONFIG_DATA['temp_range_max'])
        temp_out_of_range.append(check_result)

        check_result = (doc['humidity'] < CONFIG_DATA['humidity_range_min']) or \
                       (doc['humidity'] > CONFIG_DATA['humidity_range_max'])
        humidity_out_of_range.append(check_result)

    return all(temp_out_of_range), not any(temp_out_of_range), all(humidity_out_of_range), not any(
        humidity_out_of_range)


@app.post("/readings/")
def post_readings(msg_body: ReadingsMsgBody):
    # Note the docstring is picked up by the OpenAPI doc tools, thus only include info
    # that makes sense from an API end-user's perspective.
    """
    Process a POST request for resource 'readings'.
    """
    if TRACE_MESSAGE_PROCESSING:
        print('==> post_readings({})'.format(msg_body.__dict__), flush=True)

    # Connect to the MongoDB server and select the database
    mongodb = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    db = mongodb.basement_data

    # Store this reading into our DB
    data = {'dev_id': msg_body.dev_id,
            'ts': msg_body.ts,
            'temp': msg_body.temp,
            'humidity': msg_body.humidity}
    db.readings.insert_one(data)

    # Check recent readings to see if they are all out of range / all in range
    temp_all_out_of_range, temp_all_in_range, \
        humidity_all_out_of_range, humidity_all_in_range = recent_readings_range_check(db, msg_body.dev_id)

    # Take appropriate action for temp
    if temp_all_out_of_range:
        handle_out_of_range_condition(db, msg_body.dev_id, 'temp', msg_body.temp)
    elif temp_all_in_range:
        handle_in_range_condition(db, msg_body.dev_id, 'temp', msg_body.temp)
    else:
        handle_mixed_in_and_out_of_range_condition(db, msg_body.dev_id, 'temp', msg_body.temp)

    # Take appropriate action for humidity
    if humidity_all_out_of_range:
        handle_out_of_range_condition(db, msg_body.dev_id, 'humidity', msg_body.humidity)
    elif humidity_all_in_range:
        handle_in_range_condition(db, msg_body.dev_id, 'humidity', msg_body.humidity)
    else:
        handle_mixed_in_and_out_of_range_condition(db, msg_body.dev_id, 'humidity', msg_body.humidity)

    # Clean up by closing our MongoDB connection
    mongodb.close()


@app.delete("/readings/")
def delete_readings(dev_id: str = Query(None,
                                        alias='dev-id',
                                        description='ID of the device')):
    # Note the docstring is picked up by the OpenAPI doc tools, thus only include info
    # that makes sense from an API end-user's perspective.
    """
    Process a DELETE request for resource 'readings'.

    The request supports one optional parameter, dev-id, which is the device
    to delete readings for. If not specified, all readings are deleted.
    """
    if TRACE_MESSAGE_PROCESSING:
        print('==> delete_readings({})'.format(dev_id), flush=True)

    # Connect to the MongoDB database; note it is hosted on Mongo Atlas
    client = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    db = client.basement_data       # This is the database we are using

    # Whack 'em; either all or for a specified device id
    query = {}
    if dev_id is not None:
        query['dev_id'] = dev_id
    db.readings.delete_many(query)

    # Close the MongoDB connection when we are done with it
    client.close()

    return


# =================================================================================================
# The following code processes active_alerts related messages; get count / delete
# =================================================================================================

@app.get("/active-alerts/counts/")
def get_active_alerts_counts(dev_id: str = Query(None,
                                                 alias='dev-id',
                                                 description='ID of the device'),
                             reading_type: str = Query(None,
                                                       alias='reading-type',
                                                       description='Reading type; \'temp\' or \'humidity\'')):
    # Note the docstring is picked up by the OpenAPI doc tools, thus only include info
    # that makes sense from an API end-user's perspective.
    """
    Process a GET request for resource 'active-alerts/counts'.

    The request supports two optional parameters. dev-id, is the ID for the device
    to return the count for. If not specified, a total count of active alerts is returned.
    reading-type is the reading type (temp or humidity) to return the count for. If not
    specified, a count of both is returned.
    """
    if TRACE_MESSAGE_PROCESSING:
        print('==> get_active_alerts_counts({}, {})'.format(dev_id, reading_type), flush=True)

    # Connect to the MongoDB database; note it is hosted on Mongo Atlas
    client = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    db = client.basement_data       # This is the database we are using

    # Fetch the count
    query = {}
    if dev_id is not None:
        query['dev_id'] = dev_id
    if reading_type is not None:
        query['reading_type'] = reading_type
    num_docs = db.active_alerts.count_documents(query)

    # Close the MongoDB connection when we are done with it
    client.close()

    return num_docs


@app.delete("/active-alerts/")
def delete_active_alerts(dev_id: str = Query(None,
                                             alias='dev-id',
                                             description='ID of the device')):
    # Note the docstring is picked up by the OpenAPI doc tools, thus only include info
    # that makes sense from an API end-user's perspective.
    """
    Process a DELETE request for resource 'active-alerts'.

    The request supports one optional parameter, dev-id, which is the device
    to delete active alerts for. If not specified, all active alerts are deleted.
    """
    if TRACE_MESSAGE_PROCESSING:
        print('==> delete_active_alerts({})'.format(dev_id), flush=True)

    # Connect to the MongoDB database; note it is hosted on Mongo Atlas
    client = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    db = client.basement_data       # This is the database we are using

    # Whack 'em; either all or for a specified device id
    query = {}
    if dev_id is not None:
        query['dev_id'] = dev_id
    db.active_alerts.delete_many(query)

    # Close the MongoDB connection when we are done with it
    client.close()

    return


# =================================================================================================
# The following code processes alert_history related messages; get count / delete
# =================================================================================================

@app.get("/alert-history/counts/")
def get_alert_history_counts(dev_id: str = Query(None,
                                                 alias='dev-id',
                                                 description='ID of the device'),
                             reading_type: str = Query(None,
                                                       alias='reading-type',
                                                       description='Reading type; \'temp\' or \'humidity\'')):
    # Note the docstring is picked up by the OpenAPI doc tools, thus only include info
    # that makes sense from an API end-user's perspective.
    """
    Process a GET request for resource 'alert-history/counts'.

    The request supports two optional parameters. dev-id, is the ID for the device
    to return the count for. If not specified, a total count of alert history is returned.
    reading-type is the reading type (temp or humidity) to return the count for. If not
    specified, a count of both is returned.
    """
    if TRACE_MESSAGE_PROCESSING:
        print('==> get_alert_history_counts({}, {})'.format(dev_id, reading_type), flush=True)

    # Connect to the MongoDB database; note it is hosted on Mongo Atlas
    client = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    db = client.basement_data       # This is the database we are using

    # Do the count
    query = {}
    if dev_id is not None:
        query['dev_id'] = dev_id
    if reading_type is not None:
        query['reading_type'] = reading_type
    num_docs = db.alert_history.count_documents(query)

    # Close the MongoDB connection when we are done with it
    client.close()

    return num_docs


@app.delete("/alert-history/")
def delete_alert_history(dev_id: str = Query(None,
                                             alias='dev-id',
                                             description='ID of the device')):
    # Note the docstring is picked up by the OpenAPI doc tools, thus only include info
    # that makes sense from an API end-user's perspective.
    """
    Process a DELETE request for resource 'alert-history'.

    The request supports one optional parameter, dev-id, which is the device
    to delete alert history for. If not specified, all alert history is deleted.
    """
    if TRACE_MESSAGE_PROCESSING:
        print('==> delete_alert_history({})'.format(dev_id), flush=True)

    # Connect to the MongoDB database; note it is hosted on Mongo Atlas
    client = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    db = client.basement_data       # This is the database we are using

    # Whack 'em; either all or for a specified device id
    query = {}
    if dev_id is not None:
        query['dev_id'] = dev_id
    db.alert_history.delete_many(query)

    # Close the MongoDB connection when we are done with it
    client.close()

    return
