#!/bin/bash
# qwen-30b-rpi5.sh

export GGML_USE_CPU_REPACK=0
export GGML_USE_ASYNC_UPLOADS=0
export GGML_BACKEND_CPU_ONLY=1

/usr/local/bin/llama-server \
    -m /home/dietpi/llama.cpp/models/Qwen_Qwen3-30B-A3B-Q4_K_M.gguf \
    --host 0.0.0.0 \
    --temp 0.6 \
    --top-p 0.95 \
    --top-k 20 \
    --ctx-size 8192 \
    --port 8080 \
    --threads 4 \
    --batch-size 128 \
    --no-mmap \
    --timeout 1200
