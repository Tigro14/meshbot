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

Verifiez que vous obtenez plus de 500MB/s en lecture sur le NVMe

```
apt install fio
fio --filename=/dev/nvme0n1 --direct=1 --rw=read --bs=1M --ioengine=libaio --iodepth=32 --runtime=20 --numjobs=1 --name=test --readonly
```

Vous devriez obtenir un maximumen théorique entre 800 et 900MB/s compte tenu de l'utilisation d'une line PCIe3.0 à 1GB/s



dernieres recos (Nov 2025) pour llama.cpp sur Raspi5:

```
Meilleure ultra light (<Pi5-16Go ou téléphone):
....../llama.cpp/build/bin/llama-server \
 -m ....../mradermacher/OLMoE-1B-7B-0125-Instruct-i1-GGUF/OLMoE-1B-7B-0125-Instruct.i1-Q6_K.gguf \
 -ctk q8_0 -ctv q8_0 -fa on \
 --jinja --ctx-size 8192 --mlock --port 8081

Absolue meilleure possible sur Pi5-16Go
....../llama.cpp/build/bin/llama-server \
 -m ....../mradermacher/Qwen3-30B-A3B-Instruct-2507-i1-GGUF/Qwen3-30B-A3B-Instruct-2507.i1-Q4_K_M.gguf \
 --temp 0.7 --top-p 0.8 --top-k 20 --min-p 0 \
 -ctk q8_0 -ctv q8_0 -fa on \
 --jinja --ctx-size 4096 --port 8081
```

## Compilation spécialisé RPi5 de llama.cpp (sur les conseils de serveurperso.com)

```
apt install open blas libopenblas-dev:arm64 pkg-config cmake
cd /home/dietpi/
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake clean
cmake --fresh . -DBUILD_SHARED_LIBS=OFF -DGGML_LTO=ON -DGGML_STATIC=OFF -DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS -DLLAMA_CURL=ON
```

J'ai fait un script pratique qui effectue tout cela: https://github.com/Tigro14/meshbot/blob/main/llama.cpp-integration/llama_compile_rpi5.sh

Puis on récupère le dernier modèle adapté à 15GB de RAM testé/validé sur RPi5:
```
wget https://huggingface.co/unsloth/Qwen3-30B-A3B-Instruct-2507-GGUF/resolve/main/Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf

ou

wget https://huggingface.co/mradermacher/OLMoE-1B-7B-0125-Instruct-i1-GGUF/resolve/main/OLMoE-1B-7B-0125-Instruct.i1-Q6_K.gguf
```


## Démarrer llama.cpp comme un service:

Copier le fichier https://github.com/Tigro14/meshbot/blob/main/llama.cpp-integration/llamacpp.service
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


