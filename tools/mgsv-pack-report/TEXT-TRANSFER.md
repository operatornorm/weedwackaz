# Text-only transfer fallback

Use this fallback if your chat can preview source but its Save/download action
fails. A client with working file saving can also download the Python source;
no repository or release publication is needed.

Use ../mgsv_pack_report.py instead. It is a standalone standard-library Python 3
implementation that can be copied as text from the preview into a local editor.
Save it as mgsv_pack_report_v2.py in the home directory using the LOCAL editor.

    python3 "$HOME/mgsv_pack_report_v2.py" \
      --game-dir "/path/to/copied-game" \
      --output "$HOME/mgsv-pack-report-v2.json"

Close MGSV and Dynamite first. Only a new JSON outside the selected game directory
is written. Copying this source needs no Go installation or binary download.
Keep captures private and share only the JSON, not game assets.

Validation: 222 pack-probe hashes and CityHash inputs0..128 agree with the pinned Go
implementation. Eight version/compression/encryption combinations agree on decoded
synthetic containers; end-to-end duplicate-archive metadata and output preservation
pass. Four independent upstream QAR fixtures also agree on decoded contents and
checksum convention. Nine Python safety tests cover bounds, limits, redaction,
output guards and full digest/decompression validation. The full portable suite
now has91 checks; the Go suite has15 plus its bounds mutation.
No owner archives or real game clients have been tested in the cloud.

The Python hash implementation deliberately caps hash input names at128 bytes;
longer references are listed but not resolved and limits_hit is incremented.
The report's skips and errors must remain visible; no gameplay coverage is implied.
Version2 fixes compressed-container checksum interpretation while preserving
mandatory integrity checks. Enumeration_finished alone does not establish a
complete report; inspect parse_failures and limits_hit too.
