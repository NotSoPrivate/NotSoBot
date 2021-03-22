#!/bin/bash

wait_time=1

while true
do
	start_date=`date +%s`
	python3.8 /discord/bot.py $SHARDS $SHARD_COUNT
	dead_date=`date +%s`
	if [[ $((dead_date-start_date)) -ge 30 ]]; then
		wait_time=1
	else
		wait_time=$(($wait_time * 2))
		wait_time=$(($wait_time > 30 ? 30 : $wait_time))
	fi
	echo sleeping $wait_time
	sleep $wait_time
done
