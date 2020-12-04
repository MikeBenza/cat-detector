#!/bin/bash

while : 
do
	./venv/bin/python3 -u detector.py | tee detector.log
	sleep 10
	hciconfig hci0 down
	sleep 10
	hciconfig hci0 up
	sleep 10
done
