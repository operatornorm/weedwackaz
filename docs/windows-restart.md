# Restart the closed Sandbox using the saved host cache

Prepared 7 November 2026 (Australia/Sydney). This is a baseline startup check,
not a mod installation or a multiplayer test.

The owner confirmed that the saved host game executable and copy manifest still
exist. Their current contents are not yet verified. The new host coordinator
hashes every one of the ten cached files against the accepted manifest before
opening another Sandbox. It refuses changed files and preserves the saved cache.

## What the packet does

The host creates a fresh run with only instruction files and a writable report
folder mapped initially. The guest's reviewed storage check runs before Steam
sign-in. The host validates that report locally and supplies the new session's
offline challenge. Owner sign-in/Steam Guard remain inside Steam itself.

After the owner disables Cloud, enters Offline Mode and exits guest Steam, the
guest applies the existing local firewall/adapter cutoff. Only matching fresh
offline and staging-ready reports allow host game staging. The online launcher
is retired first. On NTFS, staging uses hardlinks from this verified QA cache;
neither linked contents nor attributes are modified. Other supported filesystem
cases require a further host copy and sufficient space. The guest always makes
its own independent game copy and checks every size/hash.

The host then issues the already-approved startup request. The guest opens its
own Steam and asks the owner to confirm offline Library before launching the
copied game once for up to 120 seconds, followed by owned-process cleanup.
No original host Steam/userdata/game directories are mapped. No new runtime,
game download, mod installation, invitation or network reenabling is performed.
Guest Steam installation/self-updates are the same previously approved workflow.

## Owner procedure

1. Extract the newly supplied `MGSV-QA-restart.zip` on normal Windows.
2. Open normal Windows PowerShell and enter `powershell.exe -NoLogo -NoProfile`.
   Read `HOST-RESTART.txt` in the extracted package and paste its entire block.
   It checks the old cache first. When its picker opens, select `GUEST-SESSION.txt`
   from that same extracted package. The coordinator then opens a new Sandbox.
   Leave this host console open.
3. Inside the new Sandbox, open Windows PowerShell as administrator and enter
   `powershell.exe -NoLogo -NoProfile`. In guest File Explorer, open
   `C:\MGSVQA\Input\GUEST-SESSION.txt`. Read and paste its whole single block into
   that guest console once. Do not run the separate component text files.
4. Follow the guest's explicit prompts: official Steam installer download and
   verified normal installation, wait at sign-in for the storage check, then
   sign in, disable Cloud, Go Offline/restart if offered, and Exit Steam.
   The guest copy and request checks then proceed locally without chat handoffs.
5. At the startup prompt, use `READY` only once guest Steam Library is visible
   offline; use `STOP` if that is unavailable. No gameplay/mission selection is
   requested. Note any game error without installing or reconnecting.
6. Once both helpers finish and the HOST reports its final saved report, exit
   guest Steam. The Sandbox may then close; the host cache/reports remain.
   Upload only the new host Output folder's `restart-result.json` and any visible
   game-error wording. If a guard fails earlier, send its exact error instead.

The ZIP is specific to the accepted host cache, but every launch creates a new
run/session. Old closed-session requests are not reused. Do not start the retired
online launcher or run multiple coordinator copies. Abort/timeout does not retry,
restore networking or start another guest automatically.

## Validation and limits

Fifteen focused packager/cache/ordering/source-integrity checks passed. A read-only
subsystem review found and corrected installer process-tree waiting and found no
remaining concrete blocker. The final ZIP's members and hashes were checked.
Actual Windows PowerShell execution of this combined workflow remains pending.
The earlier 181-test native/collector checkpoint is unchanged and was not rerun
for this wrapper alone.

The final report records local observations. It does not attest executed source,
all network isolation, offline licensing, runtime save isolation, playable game
state or working co-op. A startup error is useful evidence, not permission to
reconnect the staged guest or bypass activation.

## Rebuilding the private packet

`tools/prepare_windows_restart.py` takes the previously accepted private
`game-stage-manifest.json`, its sibling `accepted.json`, the old host run ID and
the pinned manifest SHA256. It produces a deterministic ZIP under ignored
`build-artifacts/windows-qa-restart`. Those private inputs and generated
run-specific files stay off GitHub; generic source/templates/tests are tracked.
