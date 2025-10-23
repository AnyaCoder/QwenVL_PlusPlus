#!/bin/bash

CUDA_VISIBLE_DEVICES=0,1 \
uvicorn server:app --host 0.0.0.0 --port 8000
