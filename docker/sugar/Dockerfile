FROM nvidia/cuda:11.8.0-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CUDA_HOME=/usr/local/cuda \
    FORCE_CUDA=1 \
    TORCH_CUDA_ARCH_LIST=8.9 \
    CONDA_DIR=/opt/conda \
    PATH=/opt/conda/bin:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    bzip2 \
    ca-certificates \
    cmake \
    curl \
    ffmpeg \
    git \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-py39_24.3.0-0-Linux-x86_64.sh -o miniconda.sh \
    && bash miniconda.sh -b -p "$CONDA_DIR" \
    && rm miniconda.sh \
    && conda config --system --set auto_update_conda false \
    && conda config --system --set show_channel_urls true

RUN git clone --recursive https://github.com/Anttwo/SuGaR.git /opt/SuGaR
WORKDIR /opt/SuGaR

RUN conda env create -f environment.yml \
    && conda run -n sugar pip install -e ./gaussian_splatting/submodules/diff-gaussian-rasterization \
    && conda run -n sugar pip install -e ./gaussian_splatting/submodules/simple-knn \
    && git clone https://github.com/NVlabs/nvdiffrast /opt/nvdiffrast \
    && conda run -n sugar pip install --no-build-isolation /opt/nvdiffrast \
    && conda clean -afy

COPY docker/sugar/entrypoint.sh /usr/local/bin/sugar-entrypoint.sh
RUN chmod +x /usr/local/bin/sugar-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/sugar-entrypoint.sh"]
CMD ["conda", "run", "--no-capture-output", "-n", "sugar", "python", "train_full_pipeline.py", "--help"]
