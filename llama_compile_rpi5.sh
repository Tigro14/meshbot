#!/bin/bash
# Script complet d'installation llama.cpp pour Raspberry Pi 5
# Usage: ./setup_llama_rpi5.sh

set -e

INSTALL_DIR="/home/dietpi"
BUILD_DIR="build"
REPO_URL="https://github.com/ggerganov/llama.cpp.git"

echo "=== Installation complète de llama.cpp pour RPi5 ==="

# Vérification de l'espace disque
AVAILABLE_SPACE=$(df /home/dietpi --output=avail | tail -1)
if [ $AVAILABLE_SPACE -lt 5000000 ]; then  # 5GB en KB
    echo "ERREUR: Espace disque insuffisant (besoin de 5GB minimum)"
    exit 1
fi

# Navigation vers le répertoire de travail
cd "$INSTALL_DIR"

# Nettoyage préalable
if [ -d "llama.cpp" ]; then
    echo "Suppression de l'installation précédente..."
    rm -rf llama.cpp
fi

# Installation des dépendances
echo "Installation des dépendances..."
sudo apt update
sudo apt install -y \
    git \
    build-essential \
    cmake \
    pkg-config \
    libopenblas-dev \
    libgomp1

# Clonage du repository
echo "Clonage de llama.cpp..."
git clone "$REPO_URL"
cd llama.cpp

# Vérification que tout est en place
if [ ! -f "CMakeLists.txt" ]; then
    echo "ERREUR: CMakeLists.txt non trouvé après le clonage"
    exit 1
fi

echo "Repository cloné avec succès"
echo "Version: $(git describe --tags --abbrev=0 2>/dev/null || echo 'main branch')"
echo "Commit: $(git rev-parse --short HEAD)"

# Création du dossier de build
rm -rf "$BUILD_DIR"
mkdir "$BUILD_DIR"
cd "$BUILD_DIR"

echo "Configuration CMAKE..."

cmake .. \
    -DBUILD_SHARED_LIBS=OFF \
    -DGGML_LTO=ON -DGGML_STATIC=OFF \
    -DGGML_BLAS=ON \
    -DGGML_BLAS_VENDOR=OpenBLAS \
    -DLLAMA_CURL=ON \
    -DCMAKE_INSTALL_PREFIX="/home/dietpi/llama.cpp" \


# Compilation
echo "=== Début de la compilation ==="
echo "Utilisation de $(nproc) threads"
echo "RAM disponible: $(free -h | awk '/^Mem:/ {print $7}')"


# Compilation avec limitation pour éviter la surchauffe
time make -j$(nproc) --load-average=$(nproc)

echo "=== Compilation terminée ==="

# Vérification des binaires
echo "=== Vérification des binaires ==="
for binary in llama-cli llama-server llama-quantize; do
    if [ -f "$binary" ]; then
        echo "✓ $binary créé avec succès"
        ./"$binary" --version 2>/dev/null || echo "  (version non disponible)"
    else
        echo "✗ $binary non trouvé"
    fi
done

# Test rapide
echo "=== Test rapide ==="
./llama-server --help | head -5

# Taille des binaires
echo "=== Taille des binaires ==="
ls -lh llama-* | grep -v ".o$"

# Instructions finales
echo ""
echo "=== Installation terminée ==="
echo "Binaires disponibles dans: $(pwd)"
echo ""
echo "Pour installer système-wide:"
echo "sudo make install"
echo ""
echo "Pour tester:"
echo "cd $(pwd)"
echo "./llama-server --help"
echo ""
echo "Emplacement: $INSTALL_DIR/llama.cpp/$BUILD_DIR/"
