#!/bin/bash

export seed=3407
export top_p=0.8
export top_k=20
export temperature=0.7
export repetition_penalty=1.0
export presence_penalty=1.5
export max_model_len=32768
export llm_seed=42
export max_new_tokens=4096
export CUDA_VISIBLE_DEVICES=0,1,5,6
export MODEL_PATH="/data/ZhouRongzhi/.cache/huggingface/hub/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b/"
python images_infer.py