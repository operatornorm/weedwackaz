# Official linux/amd64 manifests resolved 2026-10-31. Package signatures stay enabled.
FROM docker.io/library/golang:1.24.5@sha256:9aba206b3974f93f7056304c991c9cc1f843c939159d9305571ab9766c9ccdf6 AS go
FROM docker.io/library/debian:trixie-slim@sha256:1e1a22175fbf1b32157ddaf0219e1db4e5401fab2b94ed285add64d18587cd2d

RUN --mount=type=secret,id=proxy_ca,required=true \
    apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca update \
    && DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::https::CaInfo=/run/secrets/proxy_ca \
       install -y --no-install-recommends ca-certificates git make cmake ninja-build \
       g++ g++-mingw-w64-x86-64-posix binutils-mingw-w64-x86-64 \
       python3 lua5.1 liblua5.1-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=go /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}" GOTOOLCHAIN=local
WORKDIR /src
