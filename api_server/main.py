

# {
#   "dev_id": "razpi_1",
#   "timestamp": "2020-06-18T11:06:00Z",
#   "temp": 68,
#   "humidity":42
# }

# uvicorn --host 192.168.86.183 main:app --reload

# 192.168.86.183:8000/docs
# 192.168.86.183:8000/redock

# curl -X POST "http://192.168.86.183:8000/readings/" -H "accept: application/json" -H "Content-Type: application/json" -d "{\"dev_id\":\"razpi_1\",\"timestamp\":\"2020-06-18T11:06:00Z\",\"temp\":68,\"humidity\":42}"



from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class ReadingsMsgBody(BaseModel):
    dev_id: str
    timestamp: str
    temp: int
    humidity: int


@app.post("/readings/")
def create_item(msg_body: ReadingsMsgBody):
    print('<<< ', msg_body, ' >>>')
    return 'OK'    # what do I want to return if anything??

