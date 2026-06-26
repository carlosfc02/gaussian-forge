FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

ARG APP_UID=1000
ARG APP_GID=1000

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/home/appuser

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    git \
    libassimp-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavformat-dev \
    libboost-all-dev \
    libembree-dev \
    libeigen3-dev \
    libglew-dev \
    libglfw3-dev \
    libgtk-3-dev \
    libopencv-dev \
    libswscale-dev \
    libx11-dev \
    libxxf86vm-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt
RUN git clone --recursive https://github.com/graphdeco-inria/gaussian-splatting.git /opt/gaussian-splatting

WORKDIR /opt/gaussian-splatting
RUN cmake -S SIBR_viewers -B build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --target install -j"$(nproc)"

RUN groupadd --gid "${APP_GID}" appuser \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" --create-home --shell /bin/bash appuser \
    && mkdir -p /data /logs /home/appuser \
    && chown -R "${APP_UID}:${APP_GID}" /data /logs /home/appuser

USER appuser
WORKDIR /opt/gaussian-splatting/SIBR_viewers/install

ENTRYPOINT ["/opt/gaussian-splatting/SIBR_viewers/install/bin/SIBR_gaussianViewer_app"]
CMD ["--help"]
