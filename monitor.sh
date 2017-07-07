#!/bin/sh
while inotifywait -q -e close_write main.py; do python main.py; done
