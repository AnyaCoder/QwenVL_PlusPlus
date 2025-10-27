#!/bin/bash
export OMP_NUM_THREADS=1
CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7 \
uvicorn server:app --host 0.0.0.0 --port 8000
