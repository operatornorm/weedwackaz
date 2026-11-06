# Current Steam release compatibility: feasibility track

Status on 4 November 2026 (Australia/Sydney): requested secondary goal,
feasibility not yet established. This does not replace the complete-mission,
both-save-progression, Windows-first or no-port-forwarding requirements.

## Known build identities

The development baseline is the regular Steam 1.0.15.3 executable identified in
the existing QA pins. A separate 1.0.15.4 executable was previously reported from
the regular public installation. That report is historical identification, not
verification that 1.0.15.4 is today's latest public build. Fresh executable
version/hash, Steam build ID, region and original Steam DLL metadata must identify
the actual port target before work is applied to it. No newer game binary is in
this cloud workspace.

## Source-confirmed version dependencies

- The native constructor selects `mgsvtpp_adresses_1_0_15_3_en` explicitly.
  Its address table contains hundreds of named engine locations. Rebasing handles
  where that same executable is loaded; it does not locate functions in a
  differently compiled build. See the pinned upstream
  [constructor](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/hook/src/dynamite.cpp)
  and [address table](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/hook/src/mgsvtpp_addresses_1_0_15_3_en.h).
- Native gameplay changes include fixed-address expected-byte patches. Each
  destination and its intended behavior needs verification on another build;
  a single assumed address shift is insufficient. See the pinned
  [patch list](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/hook/src/dynamitePatches.cpp).
- Native hooks/getters also rely on calling conventions and object layouts,
  which must be checked even when a corresponding function is located.
- The [installer](https://github.com/unknown321/dynamite/blob/7fe74d31128ed8d3741b07181cb99e4adc1f57be/installer/installer.go)
  checks a particular stock `00.dat` MD5. The resource experiments use exact old
  archive/member/profile fingerprints. New-build data compatibility is unknown.
- Our invite protocol, Steam-module checks, resource plans and QA helpers pin
  executable/module hashes. They need verified per-build profiles, not a relaxed
  allowlist that treats an unknown build as compatible.

## Assessment

A port is plausible. The available evidence does not establish whether it is a
manageable mapping/resource update or a substantial engine port. It also does
not establish that changes outside the executable are necessary. Compare first.
There is no defensible time estimate yet.

Many Lua/gameplay/protocol ideas may be reusable, but their behavior must still be
tested on the new build. Existing 1.0.15.3 tests and captures do not certify it.

## Investigation and decision gate

1. Identify the current regular public Steam build through read-only metadata.
   Keep the known old copy intact and use separate test copies. Do not upload
   executables, game assets, saves or authentication files to the project.
2. Compare native hook/patch locations, object layouts, required Steam exports,
   stock archive identities, scripts and save behavior. Start with the functions
   needed for startup and passive observations before attempting a broad port.
3. Design explicit verified build profiles. Unknown builds must be refused before
   native hooks/patches run. Keep existing identity checks until replacements are
   independently validated; never run the old map blindly on a newer executable.
4. Bring up one isolated new-build client, verify real telemetry and save storage,
   then test two clients on the same exact new build. Mixed-build multiplayer is
   a separate interoperability question, not implied by supporting both builds.
5. Repeat the mission, progression, invitation and peer/relay regression matrix
   before claiming parity with the old-build implementation.

Perform low-cost identification/comparison early, alongside the baseline startup
work, so version assumptions do not become harder to separate later. If the port
looks manageable, propose moving primary development to the identified current
build before broad mission-by-mission QA. If it requires substantial research,
record the specific blockers and revisit priority with the owner. Compatibility
with every unknown future Steam update is not promised by this track.

No new-build hook execution, installation, game download or save modification has
been performed for this assessment. Immediate owner instructions remain the
read-only host-cache presence check in the restart roadmap.
