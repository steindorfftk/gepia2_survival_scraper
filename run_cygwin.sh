#!/bin/sh

rm log.log

.venv/Scripts/python.exe main.py 1>log.log 2>&1
