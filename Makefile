image-name = notsobot
name = bot00
bust = 0
pipbust = 0

build:
	docker build -t $(image-name) . --build-arg CACHEBUST=$(bust) --build-arg PIPBUST=$(pipbust)

dev:
	docker build -t notsodev . --build-arg CACHEBUST=$(bust) --build-arg DEV=""

run:
	python3.6 manager.py

clean:
	docker image prune -f

peek:
	docker exec -it $(name) /bin/bash

all: build run clean

.PHONY: all build run clean peak