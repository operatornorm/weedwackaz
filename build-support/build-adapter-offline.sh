#!/usr/bin/env bash
# Package the dormant adapter using the already approved, cached build image.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$(realpath -- "${1:?Usage: build-adapter-offline.sh /path/to/patched-dynamite}")"
artifact_dir="$project_dir/build-artifacts/experimental-free-roam-adapter"
mkdir -p -- "$artifact_dir"

env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
docker --host=unix:///var/run/docker.sock run --rm --network none \
    --user "$(id -u):$(id -g)" \
    --mount "type=bind,src=$source_dir,dst=/src" \
    --mount "type=bind,src=$project_dir,dst=/project" \
    --mount "type=bind,src=$artifact_dir,dst=/out" \
    --workdir /src \
    --env GOPROXY=off --env GOCACHE=/src/cache/go-build \
    --env GOMODCACHE=/src/cache/go-mod --env GOPATH=/src/cache/gopath --env GOMAXPROCS=4 \
    mgsv-coop-builder:local sh -eu -c '
        go generate -v -x
        python3 /project/build-support/generate_free_roam_manifest.py --source /src
        go mod verify
        gofmt -d moddata/free_roam_test.go
        go test -count=1 -v ./moddata
        test "$(sha256sum hook/cmake-build-release-docker-mingw15/dinput8.dll | cut -d " " -f1)" = ba9c77e6dfa818b01845e41f8cc96015c4dcf30877716a778ab2d73c1491d35f
        cp hook/cmake-build-release-docker-mingw15/dinput8.dll /out/dinput8.dll
        GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -buildvcs=true -ldflags="-w -s" -o /out/dynamite-windows-amd64.exe .
        GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -buildvcs=true -ldflags="-w -s" -o /out/dynamite-linux-amd64 .
        go mod verify
        python3 /project/build-support/verify_adapter_artifacts.py --source /src --artifacts /out
        /out/dynamite-linux-amd64 -h
        x86_64-w64-mingw32-objdump -f /out/dynamite-windows-amd64.exe /out/dinput8.dll
        readelf -h /out/dynamite-linux-amd64
        x86_64-w64-mingw32-objdump -p /out/dinput8.dll
        cd /out
        sha256sum dinput8.dll dynamite-windows-amd64.exe dynamite-linux-amd64 > SHA256SUMS
    '
