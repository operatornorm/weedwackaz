Use this with the SAME still-open test Sandbox where Steam Library is visible.
Do not close/reopen Sandbox, install MGSV, or add game files at this stage.

1. On your NORMAL Windows desktop, extract this ZIP into its own new folder.
   Open HOST-OFFLINE.txt in Notepad. Open normal Windows PowerShell and paste
   the WHOLE block, starting with & { and ending with the final }.
   A file picker appears: select GUEST-OFFLINE.txt in the folder you extracted.
   The block finds the existing QA workspace automatically, copies only the
   guest instructions, creates a fresh request, and renames MGSV-Test.wsb to
   MGSV-Test.online-retired. This leaves the current Sandbox open.
   It makes no host firewall/adapter/Steam changes. Do not reopen the retired file.

2. INSIDE Sandbox, in Steam: Settings > Cloud, turn off Enable Steam Cloud.
   Then Steam menu > Go Offline. Accept Restart in Offline Mode if offered.
   Once Steam is offline, choose Steam > Exit and wait for it to finish closing.
   The exact Steam labels can vary; stop and report the message if unavailable.

3. INSIDE Sandbox, open Start and type Windows PowerShell. Right-click it,
   choose Run as administrator. If prompted, accept for this guest shell.
   Type this command and press Enter to get a fresh shell:

   powershell.exe -NoLogo -NoProfile

   In File Explorer INSIDE Sandbox, type this path in its address bar:

   C:\MGSVQA\Input\GUEST-OFFLINE.txt

   It opens in Notepad. Select all and copy the WHOLE & { ... } block, paste
   into that guest PowerShell window, then press Enter if needed.
   Cross-boundary clipboard is disabled, but copying within Sandbox works.

4. Expected final line begins: Guest network cutoff recorded.
   This enables the guest firewall, blocks all guest outbound traffic, and
   disables its active network adapters. It does not change host networking.
   If it reports an error, leave everything as it is and send only that error.
   Partial network restrictions are deliberately left in place on errors.

5. On NORMAL Windows, open the existing MGSV-QA-... folder in Downloads.
   Upload only these two small files to the chat:

   Output\offline.gate
   Input\offline-request.json

Keep this Sandbox OPEN and OFFLINE. Do not copy game files yet.
This stage records local network-policy observations; it does not prove game
save isolation, offline game licensing, Steam invitations, or working co-op.
The offline guest is for local startup/observation work. Steam-invite testing
will need a separately prepared networked test setup later.
