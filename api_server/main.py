# main.py
# Wade J Lykkehoy (WadeLykkehoy@gmail.com)


# Incoming payload:
# {
#   "dev_id": "razpi_1",
#   "ts": "2020-06-18T11:06:00Z",
#   "temp": 68,
#   "humidity":42
# }

# uvicorn --host 192.168.86.183 main:app --reload

# 192.168.86.183:8000/docs
# 192.168.86.183:8000/redock

# curl -X POST "http://192.168.86.183:8000/readings/" -H "accept: application/json" -H "Content-Type: application/json" -d "{\"dev_id\":\"razpi_1\",\"ts\":\"2020-06-18T11:06:00Z\",\"temp\":68,\"humidity\":42}"


from fastapi import FastAPI, Query
from pydantic import BaseModel
import pymongo
import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

CONFIG_DATA = {'monbodb_server_url': 'mongodb+srv://razpi:razpipzar@cluster0-ylplp.mongodb.net/basement_data?retryWrites=true&w=majority',
               'num_continuous_readings_to_check': 4,
               'temp_range_min': 60,
               'temp_range_max': 75,
               'humidity_range_min': 40,
               'humidity_range_max': 55,
               'alert_renotification_delay': 1,     # num minutes to wait to resend an alert notification email
               'email_from': 'WadeLykkehoy@ZenDataAnalytics.com',
               'email_to': ' WadeLykkehoy@gmail.com'
               }

# TODO: This info should be coming from an environment variable;
SECRET_DATA = {'SENDGRID_API_KEY': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxx'}

TIMESTAMP_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

TRACE_MESSAGE_PROCESSING = True         # For debugging; echos message processing calls to stdout

app = FastAPI()                        # Our FastAPI instance object


# Defines the message body that we will receive when a 'reading' message is posted
class ReadingsMsgBody(BaseModel):
    dev_id: str
    ts: str
    temp: int
    humidity: int


@app.get("/readings/counts/")
def get_readings_counts(dev_id: str = Query(None, alias='dev-id')):
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


def send_alert_notification_email(dev_id, alert_type, current_value):
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> send_alert_notification_email({}, {}, {})'.format(dev_id, alert_type, current_value))

    if alert_type == 'temp':
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
    sendgrid_client = SendGridAPIClient(SECRET_DATA['SENDGRID_API_KEY'])
    sendgrid_client.send(message)


def send_alert_cleared_notification_email(dev_id, alert_type, current_value):
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> send_alert_cleared_notification_email({}, {}, {})'.format(dev_id, alert_type, current_value))

    if alert_type == 'temp':
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
    sendgrid_client = SendGridAPIClient(SECRET_DATA['SENDGRID_API_KEY'])
    sendgrid_client.send(message)


def is_an_existing_active_alert(db, dev_id, alert_type):
    # Check if there is currently an active alert by counting
    #  active alert records for this device/alert_type in the DB
    query = {'dev_id': dev_id,
             'type': alert_type}
    num_docs = db.active_alerts.count_documents(query)
    return num_docs > 0


def renotify_if_notification_delay_exceeded(db, dev_id, alert_type, reading_value):
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> renotify_if_notification_delay_exceeded({}, {}, {})'.format(dev_id, alert_type, reading_value))
    # First, fetch the active alert record from the DB
    query = {'dev_id': dev_id,
             'type': alert_type}
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

        send_alert_notification_email(dev_id, alert_type, reading_value)


def handle_alert_condition(db, dev_id, alert_type, reading_value):
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> handle_alert_condition({}, {}, {})'.format(dev_id, alert_type, reading_value))
    if is_an_existing_active_alert(db, dev_id, alert_type):
        renotify_if_notification_delay_exceeded(db, dev_id, alert_type, reading_value)
    else:  # Is no existing alert, so insert an active alert record into the DB & send a notification
        now = datetime.datetime.now()
        formatted_ts = now.strftime(TIMESTAMP_FORMAT)
        data = {'dev_id': dev_id,
                'type': alert_type,
                'originated_ts': formatted_ts,
                'notification_ts': formatted_ts}
        db.active_alerts.insert_one(data)

        send_alert_notification_email(dev_id, alert_type, reading_value)


def clear_active_alert_if_is_one(db, dev_id, alert_type, reading_value):
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> clear_active_alert_if_is_one({}, {}, {})'.format(dev_id, alert_type, reading_value))
    if is_an_existing_active_alert(db, dev_id, alert_type):
        # First, fetch the active alert record
        query = {'dev_id': dev_id,
                 'type': alert_type}
        docs = db.active_alerts.find(query)

        # Put a record into our alert history
        now = datetime.datetime.now()
        formatted_ts = now.strftime(TIMESTAMP_FORMAT)
        data = {'dev_id': dev_id,
                'type': alert_type,
                'originated_ts': docs[0]['originated_ts'],
                'cleared_ts': formatted_ts}
        db.alert_history.insert_one(data)

        # Remove the active alert record (should be just 1, however
        #  using delete_many is a 'DB self cleaning' tactic
        query = {'dev_id': dev_id,
                 'type': alert_type}
        db.active_alerts.delete_many(query)

        # Send an email indicating an active alert was cleared
        send_alert_cleared_notification_email(dev_id, alert_type, reading_value)


def continue_current_condition(db, dev_id, alert_type, reading_value):
    if TRACE_MESSAGE_PROCESSING:
        print('  ==> continue_current_condition({}, {}, {})'.format(dev_id, alert_type, reading_value))
    if is_an_existing_active_alert(db, dev_id, alert_type):  # Check if it it time to resend notification
        renotify_if_notification_delay_exceeded(db, dev_id, alert_type, reading_value)
    else:
        pass  # If not in alert condition, nothing needs to be done


def recent_readings_range_check(db, dev_id):
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

    # Check recent readings to see if they are all out of range
    temp_all_out_of_range, temp_all_in_range, \
        humidity_all_out_of_range, humidity_all_in_range = recent_readings_range_check(db, msg_body.dev_id)

    # Take appropriate action depending on the recent readings
    if temp_all_out_of_range:
        handle_alert_condition(db, msg_body.dev_id, 'temp', msg_body.temp)
    elif temp_all_in_range:
        clear_active_alert_if_is_one(db, msg_body.dev_id, 'temp', msg_body.temp)
    else:
        continue_current_condition(db, msg_body.dev_id, 'temp', msg_body.temp)

    # Take appropriate action depending on the recent readings
    if humidity_all_out_of_range:
        handle_alert_condition(db, msg_body.dev_id, 'humidity', msg_body.humidity)
    elif humidity_all_in_range:
        clear_active_alert_if_is_one(db, msg_body.dev_id, 'humidity', msg_body.humidity)
    else:
        continue_current_condition(db, msg_body.dev_id, 'humidity', msg_body.humidity)

    # Clean up by closing our MongoDB connection
    mongodb.close()

    # if TRACE_MESSAGE_PROCESSING:
    #     print('==> post_readings({})'.format(msg_body), flush=True)
    #
    # # #######################################################
    # # TODO: plug code in from the other file
    # # #######################################################
    #
    # # Connect to the MongoDB database; note it is hosted on Mongo Atlas
    # client = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    # db = client.basement_data       # This is the database we are using
    #
    # # Package the data into a dict for sending to MongoDB
    # packaged_data = {'dev_id': msg_body.dev_id,
    #                  'ts': msg_body.ts,
    #                  'temp': msg_body.temp,
    #                  'humidity': msg_body.humidity}
    # # print(packaged_data, flush=True)
    # readings = db.readings
    # foo = readings.insert_one(packaged_data)
    # # print(foo.acknowledged)
    #
    # # Close the MongoDB connection when we are done with it
    # client.close()
    #
    # # TODO: what do I want to return if anything??
    # return 'OK'


@app.delete("/readings/")
def delete_readings(dev_id: str = Query(None, alias='dev-id')):
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


@app.get("/active-alerts/counts/")
def get_active_alerts_counts(dev_id: str = Query(None, alias='dev-id'),
                             alert_type: str = Query(None, alias='alert-type')):
    if TRACE_MESSAGE_PROCESSING:
        print('==> get_active_alerts_counts({}, {})'.format(dev_id, alert_type), flush=True)

    # Connect to the MongoDB database; note it is hosted on Mongo Atlas
    client = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    db = client.basement_data       # This is the database we are using

    # Do the count for the specified device or specified alert type or specified device and alert type
    query = {}
    if dev_id is not None:
        query['dev_id'] = dev_id
    if alert_type is not None:
        query['type'] = alert_type
    num_docs = db.active_alerts.count_documents(query)

    # Close the MongoDB connection when we are done with it
    client.close()

    return num_docs


@app.delete("/active-alerts/")
def delete_active_alerts(dev_id: str = Query(None, alias='dev-id')):
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


@app.get("/alert-history/counts/")
def get_alert_history_counts(dev_id: str = Query(None, alias='dev-id'),
                             alert_type: str = Query(None, alias='alert-type')):
    if TRACE_MESSAGE_PROCESSING:
        print('==> get_alert_history_counts({}, {})'.format(dev_id, alert_type), flush=True)

    # Connect to the MongoDB database; note it is hosted on Mongo Atlas
    client = pymongo.MongoClient(CONFIG_DATA['monbodb_server_url'])
    db = client.basement_data       # This is the database we are using

    # Do the count for the specified device or specified alert type or specified device and alert type
    query = {}
    if dev_id is not None:
        query['dev_id'] = dev_id
    if alert_type is not None:
        query['type'] = alert_type
    num_docs = db.alert_history.count_documents(query)

    # Close the MongoDB connection when we are done with it
    client.close()

    return num_docs


@app.delete("/alert-history/")
def delete_alert_history(dev_id: str = Query(None, alias='dev-id')):
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
