#!/bin/bash

if docker compose ps | grep "uvicorn"; then
    echo "docker compose exec backend bash"
    docker compose exec backend bash
fi
