Installation sur DietPi RPI5

__Préambule: toute cette documentation n'aurait pas pu être rédigée sans les conseils bienveillants et le suppport de serveurperso.com__

## Prérequis NVMe sur Raspberry Pi5

Prérequis: un NVMe M.2 Pi Hat avec un SSD compatible PCIe 3.0 (pas la peine de pousser au PCIe 4, le RPi5 ne suivra pas)

ajouter dans le RPi5 dans /boot/config.txt:

```
# bloc de conf PCIe v3
# Configuration PCIe v3 (remplacer tout le bloc PCIe)
dtparam=pciex1_gen=3
dtparam=pcie_aspm=off

# Optionnel pour stabilité
over_voltage=2
arm_freq=2400
gpu_freq=800
gpu_mem=128
force_turbo=1
dtoverlay=disable-bt
```

Ce hack est nécessaire pour activer PCIe 3.0 dans le RPi5, il est par défaut en PCIe 2.0 préconisé par fiabilité par le constructeur, mais sérieusement bridé en performances.
Notez qu'ici, je désactive BlueTooth sur le RPi5 parceque je ne l'utilise pas.

## Compilation spécialisé RPi5 de llama.cpp (sur les conseils de serveurperso.com)

```
apt install open blas libopenblas-dev:arm64 pkg-config cmake
cd /home/dietpi/
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake clean
cmake --fresh . -DBUILD_SHARED_LIBS=OFF -DGGML_LTO=ON -DGGML_STATIC=OFF -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS -DLLAMA_CURL=ON
```

J'ai fait un script pratique qui effectue tout cela: https://github.com/Tigro14/meshbot/blob/main/llama_compile_rpi5.sh

Puis on récupère le dernier modèle adapté à 15GB de RAM testé/validé sur RPi5:
```
wget https://huggingface.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF/resolve/main/Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf
```


## Démarrer llama.cpp comme un service:

Copier le fichier https://github.com/Tigro14/meshbot/blob/main/llamacpp.service
dans /etc/systemd/system/llamacpp.service

# Recharger systemd
```
sudo systemctl daemon-reload
```

# Activer et démarrer le service
```
sudo systemctl enable llamacpp.service
sudo systemctl start llamacpp.service
```


