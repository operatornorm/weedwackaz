#!/usr/bin/env bash
# Cloud-only build. Run from an approved managed environment with Docker available.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$(realpath -- "${1:?Usage: build.sh /path/to/patched-dynamite}")"
artifact_dir="$project_dir/build-artifacts/experimental-core-fixes"
trust_dir="$project_dir/build-cache"
mkdir -p -- "$artifact_dir" "$trust_dir"
cat /etc/ssl/certs/ca-certificates.crt > "$trust_dir/ca.pem"
if [[ -n "${CODEX_PROXY_CERT:-}" ]]; then
    cat -- "$CODEX_PROXY_CERT" >> "$trust_dir/ca.pem"
fi

docker_local() {
    env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS \
        -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
        docker --host=unix:///var/run/docker.sock "$@"
}
docker_local build --platform linux/amd64 \
    --secret "id=proxy_ca,src=$trust_dir/ca.pem" \
    --tag mgsv-coop-builder:local "$project_dir/build-support"

run_builder() {
    docker_local run --rm --user "$(id -u):$(id -g)" \
        --mount "type=bind,src=$source_dir,dst=/src" \
        --mount "type=bind,src=$project_dir/build-support,dst=/build-support,readonly" \
        --mount "type=bind,src=$artifact_dir,dst=/out" \
        --mount "type=bind,src=$trust_dir/ca.pem,dst=/run/codex-ca.pem,readonly" \
        --env SSL_CERT_FILE=/run/codex-ca.pem --env GIT_SSL_CAINFO=/run/codex-ca.pem \
        --env GOCACHE=/src/cache/go-build --env GOMODCACHE=/src/cache/go-mod \
        --env GOPATH=/src/cache/gopath --env GOMAXPROCS=4 \
        mgsv-coop-builder:local "$@"
}

# Always run CMake; upstream's file-only Make target can retain an old DLL.
run_builder sh -c '
cmake --fresh -S hook -B hook/cmake-build-release-docker-mingw15 -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE=/build-support/mingw.cmake -DCMAKE_BUILD_TYPE=Release \
    -DFLATBUFFERS_BUILD_TESTS=OFF -DFLATBUFFERS_BUILD_FLATC=OFF \
    -DFLATBUFFERS_BUILD_FLATHASH=OFF -DFLATBUFFERS_BUILD_SHAREDLIB=OFF &&
cmake --build hook/cmake-build-release-docker-mingw15 --target dinput8 --parallel 4 &&
cp hook/cmake-build-release-docker-mingw15/dinput8.dll /out/dinput8.dll'

run_builder sh -c '
go generate -v -x &&
go mod verify &&
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -buildvcs=true \
    -ldflags="-w -s" -o /out/dynamite-windows-amd64.exe . &&
GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -buildvcs=true \
    -ldflags="-w -s" -o /out/dynamite-linux-amd64 .'
