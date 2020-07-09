-----------

# SEIS603 Class Project

SEIS 603 - Foundations of Software Development - Python  
Section 02  
Instructor: Eric V. Level  
July 13, 2020  

----------------

# Overview
This project implements a simple application to monitor temperature and humidity. When either goes outside a specified range, an 'alert' email is sent. Likewise, when the temperature or humidity go back into range, an 'alert cleared' email is sent. 

To avoid being spammed with email, a couple of mechanisms are implemented. First, to prevent receiving alert emails for one-off anomalous readings, the most recent N readings are looked at. They must **all** be out of range for an alert email to be sent. Likewise, they must **all** be in range for an alert cleared email to be sent. I have found N=4 to work well. Second, if the reading continues out of range, we do not want an email generated for each reading. A delay, or you can think of it as a 'send an email no more than every N minutes',  is implemented. I have found N=1,440 minutes (1 day) to work well. 

The temperature and humidity ranges are configurable via defined min and max values. The frequency of readings is configurable. I have found a reading every 15 minutes to provide adequate granularity while not creating a deluge of data.

The application is implemented entirely in Python and follows a microservice architecture approach. Tus there is a client application collecting the temperature/humidity readings and sending them to a server application via a RESTful API. 

The client application runs on a Raspberry Pi 4 connected to an Adafruit Si7021 temperature/humidity sensor. Adafruit provides a Python library for the sensor, [adafruit-circuitpython-si7021 3.2.1](https://pypi.org/project/adafruit-circuitpython-si7021/), which makes reading data from the sensor very straight-forward. The [Requests](https://requests.readthedocs.io/en/master/) library is used to send the data to the server via an HTTP POST.

The server side code is running on Windows 10. Given it is Python based, it should run without modification on Linux as well. The server code implements the RESTful API service using [FastAPI](https://fastapi.tiangolo.com/). I chose FastAPI over the more popular Flask as FastAPI has higher performance (although for this app, I am definitely not pushing performance boundaries) and additional functionality with respect to documentation ala Swagger and other tools based on the [OpenAPI](https://www.openapis.org/) specification. FastAPI is a relatively new library and, IMO, poised to become *the* go-to for building RESTful APIs in Python. I found it easy to use and has excellent documentation. For data persistence I am using  [MongoDB Atlas](https://www.mongodb.com/cloud/atlas), which is a cloud hosted instance of MongoDB. Interfacing with the MongoDB instance is via [PyMongo](https://pymongo.readthedocs.io/en/stable/#). I found PyMongo to provide a very easy to use MongoDB interface. If you have experience using MongoDB Shell, you will be very comfortable with PyMongo. For sending email, I am using a cloud email service, [SendGrid](https://sendgrid.com/). They provide an easy to use library for interfacing with their service. At this time, there is no security implemented for the API. Thus if exposed outside a firewall, anyone can hit it. This is on my 'list of things to add'.

I implemented a server test application which functions like the client, though rather than obtaining readings from a sensor, it obtains them from CSV files. This makes testing the logic of the server much easier than heating/cooling/etc the physical sensor in order to produce out of range readings. This server test application can be run either on the server or on the client via [Pytest](https://docs.pytest.org/en/stable/) or directly.


# Setup
This application leverages two web-based services. The first, [MongoDB Atlas](https://www.mongodb.com/cloud/atlas), provides a managed MongoDB instance. MongoDB is a (perhaps 'the') leading NoSQL document store database. The second web-based service is [SendGrid](https://sendgrid.com/), which provides an email service. Both provide easy to use and well documented Python interface libraries. And best of all, they both offer a free tier of service.

#### MongoDB Atlas
If you do not already have a MongoDB Atlas  account, you can set one up at [https://www.mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas). The free account is more than sufficient for running this application.

As part of the account creation process, you will set up a project and a MongoDB cluster. Once these are set up, it is a good idea to set up some additional security measures, including a non-admin level user ID for accessing the database and a restriction on the IP addresses that can connect to the database:  
1. In the MongoDB Atlas dashboard, select the project you set up (the dashboard may automatically have selected it for you)
2. On the left, you will see a menu; under heading 'Security', click 'Database Access'
3. Click 'Add New Database User'
4. In the dialog that appears,
	1. Choose 'Authentication Method' of 'Password'
	2. Enter a user name and password (remember these as they will be needed shortly)
	3. Set 'Database User Privileges' to 'Read and write to any database'
	4. Click 'Add User'
5. In the menu on the left, select 'Network Access':
	1. Click 'Add IP Address'
	2. Add the externally visible IP address of the computer you will be using as the server. To find the externally visible address, open a browser and do a search for 'my IP Address'
	3. Click 'Confirm'

Now, we need the connection string that will be used to connect to the MongoDB cluster:
1. Click 'Clusters' under heading 'Data Storage' in the menu on the left
2. Click 'Connect'
3. In the dialog that appears, click 'Connect your application'
4. For Driver, select 'Python' and Version '3.6 or later'
5. Copy the connection string; it should look like the following.  
`mongodb+srv://<user-id>:<password>@cluster0-ylplp.mongodb.net/<dbname>?retryWrites=true&w=majority`   
	Notice there are place-holders for the password and db name. Go ahead and plug those in now and save somewhere.
6. Click Close to close the dialog.

Last step here is to create the initial database:
1. Click 'Collections'
2. Click 'Create Database'
3. While you can use any name you wish for the database, if you use 'basement_data', you will alleviate the need for a code configuration change later on. Note when you create the database, you must also name a collection, use 'Readings'.

And that is it for MongoDB Atlas. Whew! 

#### SendGrid
You can set up a free tier SendGrid account at [https://sendgrid.com/](https://sendgrid.com/). Once the account is created, go to their dashboard at [https://app.sendgrid.com/](https://app.sendgrid.com/) and log in. There are two tasks we will need to perform here, creating an API key and authenticate a sender email address.

To generate the API key, click on 'Settings' on the menu on the left. It should expand showing many options. 
1. Click 'API Keys'
2. Click 'Create API Key'
3. Give the key a name; any name will do and select 'Full Access'
4. Click 'Create & View'; make note of this key as it will be needed later on

To authenticate the sender email address, click on 'Settings' on the menu on the left and:
1. Click 'Sender Authentication'
2. Click 'Verify a Single Sender'
3. Enter the requested information and click 'Create'
4. An email will be sent to that email address; follow the provided instructions.

And that's it for SendGrid.

#### Server 
First, make sure this code is located somewhere on the PC that will be acting as the server. Easiest is to clone this repo onto that PC. 

Next,  we need to set up a couple of environment variables to hold the MongoDB connection string and SendGrid API key. If you are running Windows (which is what I developed the code on), bring up the Control Panel (or easier is to search for 'edit environment').  Add the following variables; it should not matter if they are added as user variables or system variables:

`mongodb_server_url` - set to the value saved in the MongoDB Atlas setup above  
`sendgrid_api_key` - set to the value of the SendGrid API key from above  

The server app uses some additional Python libraries; they can be installed as follows:
- FastAPI  
`pip install fastapi[all]`  
- Requests  
`pip install requests`  
- SendGrid  
`pip install sendgrid`  
- pymongo and dnspython (dnspython is required due to the "mongodb+srv" URL prefix used to access the MongoDB Atlas cluster)  
`pip install pymongo`   
`pip install dnspython`  

One last thing to set up is the IP address of the server in the test code. In file api_server\test_main.py, change the following line (at approximately line 33) to the IP address of the PC running the server code (be careful to NOT change the port number):  
`IP_ADDR = '192.168.86.183:8000'`   

#### Raspberry Pi
This code takes readings from an Adafruit Si7021 temperature and humidity sensor and sends them via the RESTful API to the server. The following assumes the sensor is connected to the Raspberry Pi and setup. If not, see [here](https://learn.adafruit.com/adafruit-si7021-temperature-plus-humidity-sensor/circuitpython-code) for an excellent step by step tutorial.

Make sure this code is located somewhere on the Raspberry Pi. Easiest is to clone this repo onto the Pi. 

A couple of additional libraries are used in this code thus must be installed on the Raspberry Pi (note the use of 'sudo pip3' here):
- Adafruit Si7021 sensor interface library  
`sudo pip3 install adafruit-circuitpython-si7021`  
- Requests library  
`sudo pip3 install requests`  

And as we did above for the test code, we need to set the IP address of server PC. In file razpi_client\razpi_client.py, change the following line (at approximately line 12) to the IP address of the PC running the server code (be careful to NOT change the port number):  
`'API_URL': 'http://192.168.86.183:8000/readings/'`  

# Running the App
Now that all of the setup is complete, we can finally run the app!

#### Running the Server
On the PC where the server will run:
1. Start an Anaconda PowerShell prompt
2. Go to folder api_server  
`cd api_server`  
4. Run the server, replacing the IP address below with yours  
`uvicorn --host 192.168.86.183 main:app --reload`  

#### Running the Server Tests
Also on the server PC:
1. Start an Anaconda PowerShell prompt
2. Go to folder api_server  
`cd api_server`  
3. Run the entire set of tests via pytest  
`pytest test_main.py`  

You can also run the test app directly to either dump a list of individual tests or run an individual test in verbose mode (which echos out details of the messages being sent to the server plus verification checks):
```
python test_main.py
python test_main.py -v -t test_1_message_in_range
```

#### Running the Raspberry Pi Client
On the Raspberry Pi:
1. Start a shell prompt
2. Go to folder razpi_client  
`cd razpi_client`  
3. Run the client app (note the use of "python3" here):  
`python3 razpi_client.py`  

The client app also supports a verbose mode which echos the messages it sends to the server:    
`python3 razpi_client.py - v`

# Additional Information and Resources
Additional information and resources may be found in the Docs directory.

# GitHub Repo
[https://github.com/wlykkehoy/SEIS603_Project](https://github.com/wlykkehoy/SEIS603_Project)
