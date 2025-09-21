#!/bin/bash
/home/dietpi/llama.cpp/bin/llama-server -m /home/dietpi/llama.cpp/models/Qwen_Qwen3-30B-A3B-Q4_K_M.gguf --host 0.0.0.0 --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0 --ctx-size 4096 --port 8080 &
