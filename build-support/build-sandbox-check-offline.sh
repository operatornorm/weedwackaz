#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
artifact_dir="$project_dir/build-artifacts/windows-sandbox-check"
mkdir -p -- "$artifact_dir"
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
docker --host=unix:///var/run/docker.sock run --rm --network none --user "$(id -u):$(id -g)" \
    --mount "type=bind,src=$project_dir,dst=/project,readonly" \
    --mount "type=bind,src=$artifact_dir,dst=/out" --workdir /project mgsv-coop-builder:local sh -eu -c '
        python3 -B -m unittest discover -s tests -p test_sandbox_plan.py -v
        x86_64-w64-mingw32-g++ -std=c++23 -O2 -s -static -Wall -Wextra -Werror -Wno-cast-function-type \
            -municode -mwindows -I tools/windows-sandbox-check tools/windows-sandbox-check/main.cpp \
            -lbcrypt -ld3d11 -ldxgi -ldxguid -luuid -liphlpapi -lws2_32 -ladvapi32 -lshell32 -o /out/ww-sandbox-check.exe
        x86_64-w64-mingw32-objdump -p /out/ww-sandbox-check.exe
        cd /out
        sha256sum ww-sandbox-check.exe > SHA256SUMS
    '
