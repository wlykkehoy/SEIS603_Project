import time
import board
import busio
import adafruit_si7021

i2c = busio.I2C(board.SCL, board.SDA)

sensor = adafruit_si7021.SI7021(i2c)

while True:
    tempC = sensor.temperature
    tempF = (tempC * 9 / 5) + 32
    humidity = sensor.relative_humidity
    print('Temp: {:>6.2f}C / {:>6.2f}F   Humidity: {:>6.2f}'.format(tempC, tempF, humidity))
    time.sleep(1.0)


