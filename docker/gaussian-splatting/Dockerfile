FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CUDA_HOME=/usr/local/cuda \
    FORCE_CUDA=1 \
    TORCH_CUDA_ARCH_LIST=8.9

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ffmpeg \
    git \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ninja-build \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

WORKDIR /opt
RUN git clone --recursive https://github.com/graphdeco-inria/gaussian-splatting.git /opt/gaussian-splatting
WORKDIR /opt/gaussian-splatting

RUN python -m pip install --upgrade pip setuptools wheel
RUN python -m pip install --extra-index-url https://download.pytorch.org/whl/cu118 \
    torch==2.0.1 torchvision==0.15.2
RUN python -m pip install \
    "numpy<2" \
    joblib \
    opencv-python \
    plyfile \
    tqdm
RUN python -m pip install --no-build-isolation ./submodules/diff-gaussian-rasterization
RUN python -m pip install --no-build-isolation ./submodules/simple-knn
RUN python -m pip install --no-build-isolation ./submodules/fused-ssim

CMD ["python", "train.py", "--help"]
