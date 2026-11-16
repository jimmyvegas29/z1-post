# Changelog

Z1 Post is based on the [Makera Community Fusion plugin](https://github.com/Carvera-Community/Carvera_Community_FusionPlugin)
by Moinois, version 0.9.1-RC1 (GPL v2). This file lists what Z1 Post changed, as the GPL asks. The original
project's history is kept in this repository's git log, up to tag `v0.9.1-RC1`.

## 0.2.0 (2026-11-16)

### Added
- **Z1 template.** Save one NC Program's machine, post processor and changed post settings (More tab); any
  document can then post by picking "Z1 template" in the NC Program list. Posting creates an NC Program named
  "Z1 Post" in the document and keeps it there. It's picked automatically in a document with no NC Program.
- After a posting error, the full traceback is saved as `last_error.txt` in the user data folder.

### Changed
- Send settings moved from the add-in folder to the user data folder (`%APPDATA%\Z1 Post` on Windows,
  `~/Library/Application Support/Z1 Post` on a Mac), so updating the add-in keeps them. 0.1.0's settings are
  read once from the old place.

## 0.1.0 (2026-11-16)

First Z1 Post release, by jimmyvegas29.

### Added
- **Send to the Z1.** After posting, each file is copied to the Makera Z1's SD card over Wi-Fi (the Z1's own
  file-transfer protocol on TCP port 2222, the same one Makera Studio uses). Progress dialog with Cancel, one
  summary message at the end. Won't send while the machine is running a job and never touches the file that
  is playing. If the Z1 is off or busy, the files are still saved on the computer.
- Files on the machine are always named `<File name>_<Setup>.cnc`, flat in the send folder (default
  `/sd/gcodes/`), whatever the grouping or folders on the computer.
- **Find the Z1 on the network.** Listens for the Z1's UDP announcements; if none arrive (Windows Firewall can
  block inbound traffic to Fusion), asks each address on the local /24 network over TCP instead.
- Send settings (on/off, machine address, folder) are kept per computer in `z1send/z1send.settings`.
- New icon, and new add-in and command IDs, so Z1 Post can be installed next to the original plugin.

### Changed
- The dialog is now four tabs, with everything a normal post needs on the first:
  - **Post:** NC program, one line naming the machine and post processor, setups table, Save to, File name,
    Files (grouping), Replace files that already exist, and the Send to the Z1 group.
  - **File names:** numeric names, numbering, combine same-tool operations, no subfolders, empty the output
    folder first.
  - **G-code:** rapid moves, then closed "4th axis" and "G-code blocks" groups.
  - **More:** language, rename setups, and one "Save all settings as my defaults" button (it was under every tab).
- The setups table has one **Check** column (reference / OK / the reason a setup can't be picked) instead of
  Origin / Parallel / Rotation.
- "Replace files that already exist" is remembered between sessions and on by default. "Empty the output
  folder first" is still off every time the dialog opens.
- The OK button reads "Post and send" when sending is on, "Post" when it's off (as of when the dialog opens).
- Settings added after a document saved its settings now fall back to the defaults.
- Renamed throughout (manifest, release archive `Z1-Post-v<version>.zip`, release workflow).

### Fixed
- Dialog event handlers piled up with every opening of the dialog (a button could act once per earlier
  opening); they are now cleared each time the dialog is built.
- The Misc tab's enable handler switched the Output tab instead of itself.
- The Misc tab and its Rename Setups group shared one input id.
- The Retract-Y save handler was registered twice.
- "Clear output folder" showed its raw tooltip keys.

### Files changed from the original
Every changed source file carries a notice on its first line. New files: `commands/postProcessor/z1send/`
(`send.py`, `naming.py`, `prefs.py`, `z1upload.py`), `dialog/layout/send_section.py`,
`dialog/layout/file_names_tab.py` (moved out of `output_tab.py`), `dialog/layout/template_section.py`,
`commands/postProcessor/z1template/`, `fusion_adapters/nc_program_template.py`, `z1send/userdata.py`,
`Tests/test_z1send_naming.py`, `Tests/test_z1template.py`, `LICENSE`,
this file. The icons (`Z1 Post.svg`, `dialog/resources/*.png`) are new artwork.
