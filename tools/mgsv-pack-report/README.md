# Read-only MGSV archive metadata reporter

Use reporter v2. Version1 could index valid archives but reject their compressed
containers because it checked only one producer's checksum convention.
If artifact downloads fail in chat, use the [text-only Python fallback](TEXT-TRANSFER.md).

This standalone tool reads an explicitly selected copied game directory and writes
one new JSON report outside it. It does not run MGSV, install Dynamite, extract
asset files, edit archives/configuration, read Steam userdata or change saves.

Use the regular Steam 1.0.15.3 co-op copy for this investigation. Close the game
and Dynamite installer first so archive files remain stable during inspection.

Windows PowerShell, using the compiled Windows reporter:

    & "$env:USERPROFILE\Downloads\mgsv-pack-report-v2-windows-amd64.exe" --game-dir "D:\path\to\copied-game" --output "$env:USERPROFILE\mgsv-pack-report-v2.json"

Linux, using the compiled Linux reporter directly:

    chmod +x "$HOME/Downloads/mgsv-pack-report-v2-linux-amd64"
    "$HOME/Downloads/mgsv-pack-report-v2-linux-amd64" \
      --game-dir "/path/to/copied-game" \
      --output "$HOME/mgsv-pack-report-v2.json"

Check the compiled download against the accompanying SHA256SUMS. Existing output
files are preserved: select another output filename to repeat a report.
Share only the resulting JSON, not game archives or extracted assets.

## What is collected

- SHA-256 of the selected mgsvtpp.exe (read only; no execution).
- Metadata from the pinned installer's known archive list, the active 00.dat and
  chunk0.dat. Missing/unreadable/invalid archives have explicit status codes.
- Exact hash matches for source-known Free Roam packs and bounded companion/variant
  probes. The hanger level range is unknown; 00..99 are probes rather than claims.
- Bounded selected-container decode and FPK/FPKD table inspection. Member names,
  offsets/sizes, external references and allocation-candidate fingerprints are metadata.
  Nested FPK tables and external references are followed to depth two.
- Duplicate occurrences in different archives are retained. No load precedence or
  successful allocation is inferred.

Names outside the expected internal /Assets namespace are omitted. No absolute PC
paths, raw operating-system errors, encryption keys, scripts, saves, account data or
member bodies are included. Names/hashes alone do not establish entity counts,
controller properties, complete dependency coverage or working multiplayer.
LimitSkips and ParseFailures remain visible in partial reports.
EnumerationFinished means the walk ended, including failed or skipped entries;
it does not mean all selected metadata was successfully inspected. Python v2
also exports containers_inspected, containers_failed, parse_failures and fixed
failure_code values without local OS error text.

## Checksum conventions

The pinned dependency's [independent compressed fixtures](https://github.com/unknown321/datfpk/tree/v0.3.0/qar/testdata)
store the MD5 of the decoded payload. Its [writer](https://github.com/unknown321/datfpk/blob/v0.3.0/qar/qarEntry.go#L295)
instead hashes the compressed/inner-encrypted representation before outer encryption.
The reader now completes bounded decoding and requires a full16-byte digest match
at one of these demonstrated stages. ChecksumStage/checksum_stage records which
matched. Neither match bypasses zlib checksum/EOF, exact decoded size, trailing-data
rejection or FPK table bounds. An unknown digest convention still fails closed.
No game-installer archive fingerprints or download checksums have been relaxed.

## Build and checks

Go 1.24.5, datfpk v0.3.0 and hashing's pinned commit are recorded in go.mod/go.sum.
Use the approved cloud build image; no Go installation is needed on the owner's PC.

    go mod verify
    python3 ../../build-support/check_pack_report.py
    GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -o mgsv-pack-report-v2-windows-amd64.exe .
    GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -o mgsv-pack-report-v2-linux-amd64 .

Fifteen Go checks, nine standalone Python safety checks and the member-bounds
mutation pass. Checks use synthetic archives, pinned independent QAR/FPK fixtures
and temporary files: QAR versions1/2, compression,
inner encryption, malformed bounds/counts, name redaction, metadata-only output,
duplicate archive occurrences, nested tables and output preservation. The member
bounds mutation must be rejected. Corrupt Adler32, truncated streams, trailing data,
wrong decoded lengths and both halves of a version2 digest must fail even when
another decoding check would pass. Both reporters cap hash inputs at128 bytes and
record longer references as skips. No owner game archives have been inspected in
the cloud, and the Windows reporter has only been cross-compiled.
