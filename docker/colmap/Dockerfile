FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    QT_QPA_PLATFORM=offscreen \
    CC=/usr/bin/gcc-10 \
    CXX=/usr/bin/g++-10 \
    CUDAHOSTCXX=/usr/bin/g++-10

ARG COLMAP_VERSION=4.0.3
ARG CMAKE_CUDA_ARCHITECTURES=89

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    ffmpeg \
    gcc-10 \
    g++-10 \
    git \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-program-options-dev \
    libboost-system-dev \
    libcgal-dev \
    libceres-dev \
    libeigen3-dev \
    libflann-dev \
    libfreeimage-dev \
    libglew-dev \
    libgl1 \
    libglib2.0-0 \
    libgoogle-glog-dev \
    libgmock-dev \
    libgtest-dev \
    libmetis-dev \
    libopenimageio-dev \
    openimageio-tools \
    libopenexr-dev \
    libopencv-dev \
    libqt5opengl5-dev \
    libsqlite3-dev \
    ninja-build \
    python3 \
    python3-pip \
    qtbase5-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --branch ${COLMAP_VERSION} --depth 1 https://github.com/colmap/colmap.git /opt/colmap
WORKDIR /opt/colmap
RUN cmake -S . -B build -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CUDA_ARCHITECTURES=${CMAKE_CUDA_ARCHITECTURES} \
    && cmake --build build --parallel \
    && cmake --install build \
    && rm -rf /opt/colmap/build /opt/colmap/.git

CMD ["colmap", "-h"]




