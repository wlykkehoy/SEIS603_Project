

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



from fastapi import FastAPI
from pydantic import BaseModel
from pymongo import MongoClient

app = FastAPI()


class ReadingsMsgBody(BaseModel):
    dev_id: str
    ts: str
    temp: int
    humidity: int


@app.post("/readings/")
def create_item(msg_body: ReadingsMsgBody):
    print('<<< ', msg_body, ' >>>', flush=True)

    # Package the data into a dict for sending to MongoDB
    packaged_data = {'dev_id': msg_body.dev_id,
                     'ts': msg_body.ts,
                     'temp': msg_body.temp,
                     'humidity': msg_body.humidity}
    print(packaged_data, flush=True)


    client = MongoClient("mongodb+srv://razpi:razpipzar@cluster0-ylplp.mongodb.net/basement_data?retryWrites=true&w=majority")
    db = client.basement_data
    readings = db.readings
    foo = readings.insert_one(packaged_data)
    print(foo.acknowledged)
    client.close()
    
    return 'OK'    # what do I want to return if anything??

