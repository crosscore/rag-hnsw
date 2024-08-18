#!/bin/bash

if docker compose ps | grep "uvicorn"; then
    echo "docker compose down"
    docker compose down
else
    echo "Starting Docker containers..."
    docker compose up --build
fi
