#!/bin/bash

if docker compose ps | grep "uvicorn"; then
    echo "docker compose exec batch bash"
    docker compose exec batch bash
fi
