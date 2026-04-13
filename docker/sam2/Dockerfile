FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CUDA_HOME=/usr/local/cuda \
    SAM2_REPO_DIR=/opt/sam2 \
    SAM2_CHECKPOINT_DIR=/models/sam2

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    ffmpeg \
    git \
    libgl1 \
    libglib2.0-0 \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

WORKDIR /app

COPY docker/sam2/requirements.txt /tmp/requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel
RUN python -m pip install --extra-index-url https://download.pytorch.org/whl/cu124 \
    torch==2.5.1 torchvision==0.20.1
RUN python -m pip install -r /tmp/requirements.txt

RUN git clone --depth 1 https://github.com/facebookresearch/sam2.git "${SAM2_REPO_DIR}" && \
    python -m pip install -e "${SAM2_REPO_DIR}"

COPY scripts /app/scripts

RUN mkdir -p /data /jobs /logs /models/sam2

CMD ["python", "/app/scripts/segment_video.py", "--help"]
