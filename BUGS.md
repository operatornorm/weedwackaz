# Full-coverage tracker

Baseline: Dynamite v0.6.0, regular Steam game 1.0.15.3. No additional content is proven.

| State | Item | Evidence / limits |
|---|---|---|
| Fixed in source | Conditional OnTerminate shadowing | Actual module tests; package/game validation pending. |
| Fixed in source | Payload limit and verifier length | Portable helper tests, Windows DLL build; decoder/game traffic untested. |
| Fixed for build | Optional CRT diagnostic import | Link probe and DLL build; no game logic change. |
| Fixed in source | Empty/stale initial sync status | Actual lifecycle methods and required-key tracker tested, including two mutation checks; not world readiness. |
| Open | Variant IDs overwritten by base loaders | Source/Lua reproduction; runtime effect unknown. |
| Open | Free Roam and Side Op startup/allocation/authority | Missing integrations, not a list toggle. |
| Open | Prologue/tutorials/remaining story/boss/variant support | Content-specific work and real-client QA. |
| Open | Mission 46 policy/assets contradiction | Whitelisted, documented disabled, missing pack integration. |
| Open | Quest/world authority, join baseline, checkpoint/travel and dual-save rewards | Partial synchronization and local progression paths. |
| Open | Streaming/AI ownership and native handler lengths | Outside the narrow preliminary fixes. |
| Open | Restart hang, vehicles, buddies and bosses | Upstream reports; no claimed live fix. |
| Build passed | Windows/Linux installer packaging | Download blocker resolved; Windows runtime and both installs untested. |
| Metadata received | Loaded quest/API registry | Validated private catalog; one name redacted, numbered Side Op mapping pending. |
| Fixed in tool | Compressed archive metadata checksum rejection | Reporter v2 validates both independently demonstrated digest stages; decompression/integrity checks remain mandatory. |
| Identity and structure confirmed | Stock Free Roam controllers | Three Afghanistan/Africa captures pass exact identity and one-slot graph/profile checks. Runtime two-player behavior remains unknown. |
| Implemented, disabled | Free Roam loader/lifecycle adapter | Actual callbacks and three staged aliases wired; 22 Lua regressions pass. No production verifier or playable startup caller, staged installer or real-client validation. |
| Open | Native preflight/runtime proof producer | Lua test receipts do not verify resource compatibility, save isolation, wire epochs, peer liveness or actual engine realization. |
| Implemented, unvalidated in game | Passive native/Lua observations | Explicit missing-query states, atomic bookkeeping reads and locked handler counts; actual binding tested with Lua5.1 and engine stubs. Not a readiness provider or remote test transport. |
| Implemented, test-only | Local status-file bridge and smoke scorer | Compile-time default OFF plus fresh request; atomic bounded snapshots, caller affinity, restart fencing and stale-data rejection. Windows runtime behavior unvalidated. |
| Open, required | Steam invitations as the sole normal join flow | Standalone real-Steam binding/registration passed; borrowed game context, delivery, admission, automatic FOX load and cold-launch/sidecar handling remain. Existing MGO invitation routing must be preserved. |
| Open, blocks runtime deployment | Save isolation | AccountDir prepares backup/conversion output but does not redirect runtime saves. Existing DYNAMITE namespaces can reuse owner co-op progress. |
| Implemented, inactive | Steam invite binding/protocol/callback components | Exact flat exports/pinned SDK ABI verified from metadata/source; fake API tests pass. No real Steam delivery, friend picker or automatic game joining yet. |
| Synthetic Windows check passed | Our cross-DLL binder/callback fixture | Owner supplied PASS for our fake DLL; real_steam_used/game_launched/co_op_verified are false. |
| Real standalone Windows check passed | Steam binding/callback registration | Owner supplied PASS: initialized, interfaces bound, callback registered/unregistered, own shutdown called. No invitation, game launch or co-op verification. |
| Implemented, inactive | Invite session controller | Deferred warm/cold intent, in-memory role/target and context-owned cleanup tested offline. No production instance, engine action adapter, legacy hook migration or peer handshake. |
| Open, blocks invite activation | MGO invitation coexistence | A second Steam listener does not consume the event. Mod-prefix parsing alone cannot prevent the game's existing handlers entering MGO. |
| Prototype tested | Profile-preserving two-slot expansion and support split | Five-field delta and append preservation pass on Normal/scarf synthetic packages with native SDK validation. No installation path. |
| Open | Two-player resource/profile compatibility | NormalScarf support and effective object/motion dependency resolution remain unverified. |
| QA not run | Windows host/client and secondary Proton | Two Windows PCs available; remote access/deployment not implied. |

Portable tests do not close gameplay bugs or promote content coverage.
