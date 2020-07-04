# This is a powershell script to run the server
clear
uvicorn --host 192.168.86.183 main:app --reload
