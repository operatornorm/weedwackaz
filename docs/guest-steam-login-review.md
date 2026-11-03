# Proposed guest Steam sign-in

The supplied prelogin report and run manifest were accepted by the bounded
validator. Their run/session fields match and their source tag matches the
published storage-check file. The observations cover the expected guest Steam
and profile paths, read-only Input and working report Output. They do not attest
executed source, verify offline licensing or authorize a game launch.

The proposed next action is deliberately limited:

1. Use Steam already open in the **same test Sandbox** that produced these files.
2. Sign into the owner's own licensed Steam account there, handling any Steam
   Guard prompt directly in the Steam client or official Steam mobile app.
3. Stop when the Library appears. Keep this guest open while continuing.

No credential, code, cookie, account file, screenshot or Steam log is requested
by the chat. This stage does not install/download/launch a game, send invitations,
alter Cloud preferences or change firewall/adapter settings. It uses the existing
guest Steam installation, so no further installation approval is needed.

The current Input contains only test instructions and its manifest. Existing
host Steam/userdata/game directories are not mapped. Output remains the narrow
writable per-run report folder. Closing this guest discards its private state;
an earlier receipt must not be reused for a replacement guest.

Before any game files are staged, the remaining work is a reviewed same-session
offline barrier with fresh host challenge/session binding, retiring the online
WSB and checking the local guest firewall/adapter state. Those steps remain
unimplemented and are not performed by signing in. MGSV's offline activation in
a fresh VM is unknown; failure must not lead to reconnecting a modified test
guest or bypassing activation. Live Steam invitations need a separate test plan.

The owner explicitly approved this guest sign-in step. Actual sign-in is pending
owner execution. The original reason for asking was
[AGENTS.md](https://github.com/cranebeaker/coop-anything/blob/main/AGENTS.md#ground-rules):
“Ask your owner before … using their accounts (Steam, Discord, GitHub).”
