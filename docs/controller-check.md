# Targeted controller structure check

The archive metadata capture identifies files by name/hash, but deliberately omits
their bodies and FOX2 properties. This narrower check reads the three pinned
Afghanistan/Africa controllers locally and exports selected structural metadata.
It is a development diagnostic; the final mod remains Windows primary, Proton secondary.

The single-file Python3 application needs no installation or extraction:

    python3 "<downloads>/mgsv-controller-check.pyz" \
      --game-dir "<copied game>" \
      --output "<new report outside the copy>/mgsv-controller-check.json"

Close MGSV and Dynamite first. Check the download against SHA256SUMS before running.
Existing output files are preserved. Share only the JSON, not game assets.

The tool verifies the executable, all nine known archive indexes, unique source
occurrences, six FPK/FPKD fingerprints and the three controller member fingerprints.
It exports approved entity-class names, relevant property types/counts and numeric
configuration values, instance-setting hashes, and canonical internal asset paths.
It omits raw member bodies, literal tables, scripts, PC paths, accounts and saves.
Unexpected class literals and malformed paths are redacted even when validation fails.

The received capture passes for all three targeted controllers, including their
graph and original one-slot configuration. The structural policy expects one
DataSet, one TppPlayer2BlockControllerData and one
TexturePackLoadConditioner, known property schemas, consistent non-null Address-based
links and one parts slot. This expectation comes from the existing mod model, not
an observation of the owner's controller contents. Parts slots do not establish
realized player count. The report always says `can_install=false`.

There is no transform/install option. The checker opens archives read-only and
creates only one new JSON outside the game copy. It never starts the game, calls
Steam or touches configuration/saves. Python3 on Linux has been tested; no Windows
game/runtime validation is implied.

## Development validation

Use the approved offline build image with the pinned Go module cache and Dynamite
source available. Prepare public reference fixtures and run the focused checks:

    python3 build-support/check_controller_preflight.py

This checks the parser against independent FoxTool fixtures and pinned Go decoding,
the four existing replacement FOX2 members, an explicitly synthetic single-slot
reference, malformed inputs, graph/ID distinctions, redaction, output guards and
the self-contained app. A pure table-removal prototype is checked with the native
pinned FPK reader and preservation assertions. No owner asset bodies are involved.

The complete portable suite passes91 checks. The standalone reporter's previous
15 Go checks and member-bounds mutation remain separate; its source is unchanged.

Build the deterministic app with:

    python3 build-support/package_controller_check.py

It bundles four source modules, the fingerprint manifest, entry point and notices.
It contains no game assets, test fixtures or third-party runtime binaries.

The capture is now sufficient for this structural gate. Current development uses
the [profile-preserving expansion prototype](free-roam-integration.md); it remains
unavailable for installation pending resource and runtime integration. The delivered
checker is kept unchanged; no repeat run is requested.
