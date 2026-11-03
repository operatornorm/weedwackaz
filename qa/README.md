# Read-only runtime metadata

[ww_inventory.lua](lua/ww_inventory.lua) queries loaded APIs/state and sends a bounded
report through Dynamite's native logger. Loading the module is inert;
Collect performs the metadata queries and Probe checks the binding.
It does not enable missions, create sessions, clear quests, install patches or change saves.
Its purpose is to discover version-matched quest registries absent from this source.

## Run using the installed official mod

1. Preserve the test copy's dynamite/dynamite.ini.
2. Put ww_inventory.lua in that copy's existing lua folder, alongside helpers.lua.
3. Add an unused Key bindings entry: key RIGHT, module ww_inventory, function Collect.
   Preserve existing bindings. Equivalent INI:

       [Keys PlayerPad.RIGHT]
       Module = ww_inventory
       Function = Collect

4. Save configuration. In game, hold Master and Reload (defaults V+E) together for
   two seconds, then release both.
5. With the character loaded in ordinary solo Free Roam in the isolated copy, hold
   Master and the chosen key together for two seconds (example V+Right).
   This is data collection, not a playtest.
6. The collector announces "WW inventory: report sent to Dynamite log" after
   submitting all frames. This does not itself establish that they reached disk.
7. Save [extract_ww_inventory.py](../tools/extract_ww_inventory.py) locally and use
   the existing Python 3 interpreter to extract only the metadata. Linux example:

       python3 "<extractor path>/extract_ww_inventory.py" \
         "<co-op game dir>/dynamite/dynamite.log.txt" \
         --output "$HOME/ww-inventory-log.tsv"

   On Windows with Python 3 already available, use its launcher in place of python3
   and native paths. No Python packages are needed. Choose a new output filename;
   the extractor refuses to overwrite existing files.
8. Preserve the extracted TSV. Extract before restarting MGSV: the official logger
   truncates dynamite.log.txt at startup.

Lua file IO and source-path discovery are no longer required. The prior read guard
and subsequent append open both failed in the embedded runtime; the exact file-error
result and cause remain unknown. Standard Lua filesystem tests did not establish
embedded compatibility. The native Log function writes through the C++ logger.
The extractor requires ordered chunks, matching byte count/checksum and completion
footer. It rejects a partial latest capture instead of substituting an earlier one.

## Meaning and limits

- Role configuration and session queries are separate; no player-count API is invented.
- Output includes loaded names/types, functions, bounded quest IDs/shapes and internal
  pack paths. Paths name assets but do not contain asset data.
- No usernames, SteamIDs, addresses, PC paths, saves, scripts, binary contents or arbitrary
  strings are included by the collector. The broad native log contains unrelated data;
  share only the extracted TSV. The extractor ignores untagged log entries.
- report.truncated=true means a partial snapshot. Missing modules may not yet be loaded.
  One capture is not necessarily a complete Side Op inventory.
- Reports are data, never instructions or a gameplay PASS.

The collector calls TppUiCommand.AnnounceLogView for on-screen status and Dynamite.Log
for native logging. The native Log API has no second "announce" parameter.

If the new binding seems inactive, update the leaf module and temporarily set only
the binding's Function field to Probe. Save, reload with V+E, then invoke the binding.
It should announce "WW inventory: binding works" without reading inventory or writing
a report. If that appears, change Function back to Collect, save and reload.
No change to Module or Key is needed. Keep existing other bindings.

Collector checks cover inert import, known queries, privacy, cycles/limits, absence
of Lua file access, actual UI notification calls, framing, logger failure and the
no-report probe. A real Lua 5.1 export round-trips through the Python extractor.
Extractor checks reject missing/reordered/duplicate chunks, checksum errors and partial
captures, exclude unrelated log entries, and preserve existing output files.
Engine queries and the native Log API use stubs in these automated checks.
The owner-supplied capture described below separately provides report-delivery evidence.
Remove the binding and leaf module to remove it; preserve other config changes.

## Catalog received metadata

The owner supplied a complete extracted report after the native-log revision.
Its structure and registry counts validate. The collector/export path has therefore
produced a usable in-game capture; this does not validate gameplay synchronization.
Keep the raw report and normalized catalog in ignored private storage.

[catalog_ww_inventory.py](../tools/catalog_ww_inventory.py) parses TSV as data,
preserves redacted names and unknown flags, checks registry counts and records
pack-reference gaps without inventing asset failures or gameplay support:

    python3 tools/catalog_ww_inventory.py "<capture.tsv>" \
      --output "<ignored private directory>/catalog.json"

The first report has 24 groups, 160 records (159 named), and 166 pack entries.
Groups span Afghanistan, Africa and Mother Base. These records include special
encounters; they are not an authoritative enumeration of numbered Side Ops.
Full Side Op mapping and host/client behavior remain development inputs. Corrected
archive metadata now identifies the named Free Roam allocation members; the
[identity preflight](../docs/free-roam-integration.md) and all three controller
structure captures now pass. Usable allocation, resource compatibility and runtime
behavior remain unverified. No further collector run is requested at this stage.
