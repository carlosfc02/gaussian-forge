FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

ARG APP_UID=1000
ARG APP_GID=1000

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CUDA_HOME=/usr/local/cuda \
    HOME=/home/appuser \
    XDG_CACHE_HOME=/home/appuser/.cache \
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
COPY docker/gaussian-splatting/patches/masked-rgb-loss.patch /tmp/masked-rgb-loss.patch
COPY docker/gaussian-splatting/patches/add-eval-ssim.py /tmp/add-eval-ssim.py
RUN git apply --recount --ignore-space-change --ignore-whitespace /tmp/masked-rgb-loss.patch
RUN python /tmp/add-eval-ssim.py

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

RUN groupadd --gid "${APP_GID}" appuser \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /bin/bash appuser \
    && mkdir -p /data /logs "${XDG_CACHE_HOME}" \
    && chown -R "${APP_UID}:${APP_GID}" \
        /opt/gaussian-splatting /data /logs /home/appuser

USER appuser

CMD ["python", "train.py", "--help"]
