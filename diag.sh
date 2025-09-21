#!/bin/bash
# diagnose_model.sh

echo "=== Diagnostic du modèle ==="

MODEL_PATH="/home/dietpi/llama.cpp/models/Qwen_Qwen3-30B-A3B-Q4_K_M.gguf"

# Informations sur le modèle
echo "Taille du fichier:"
ls -lh "$MODEL_PATH"

echo -e "\nInformations modèle:"
/home/dietpi/llama.cpp/build/bin/llama-cli --model "$MODEL_PATH" --help 2>&1 | head -10

echo -e "\nTest de chargement simple:"
#timeout 60 
time /home/dietpi/llama.cpp/build/bin/llama-cli \
    --model "$MODEL_PATH" \
    --ctx-size 512 \
    --threads 1 \
    --prompt "Test" \
    --n-predict 1 \
    --no-display-prompt 2>&1 
#| grep -E "(load_|error|failed)"
