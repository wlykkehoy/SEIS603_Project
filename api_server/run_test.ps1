# This is a powershell script to run tests. Note there is a call to run each
# individual test directly with verbose mode as well as running the entire
# test suite via pytest.


# *** Individual generic tests; uncomment the one(s) you wish to run ***
#clear; python test_main.py -v -t test_1_message_in_range
#clear; python test_main.py -v -t test_10_messages_in_range


# *** Individual temperature tests; uncomment the one(s) you wish to run ***
#clear; python test_main.py -v -t test_trigger_temp_alert_high_readings
#clear; python test_main.py -v -t test_trigger_temp_alert_low_readings
#clear; python test_main.py -v -t test_trigger_and_clear_temp_alert
#clear; python test_main.py -v -t test_temp_alert_then_readings_in_and_out_of_range
#clear; python test_main.py -v -t test_temp_readings_in_and_out_of_range


# *** Individual humidity tests; uncomment the one(s) you wish to run ***
#clear; python test_main.py -v -t test_trigger_humidity_alert_high_readings
#clear; python test_main.py -v -t test_trigger_humidity_alert_low_readings
#clear; python test_main.py -v -t test_trigger_and_clear_humidity_alert
#clear; python test_main.py -v -t test_humidity_alert_then_readings_in_and_out_of_range
#clear; python test_main.py -v -t test_humidity_readings_in_and_out_of_range


# *** Individual combo tests; uncomment the one(s) you wish to run ***
#clear; python test_main.py -v -t test_trigger_temp_and_humidity_alert


# *** Run the entire test suite via pytest; uncomment to run ***
#clear; pytest test_main.py
