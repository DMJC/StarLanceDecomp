# Confidence database

Structured index of what's known about `Lancer.exe`'s functions/structs/
globals, at what confidence, per `METHODOLOGY.md`'s scale. See that file
before adding entries.

**Status**: this database was created 2026-09-07 (first RE session on this
project). `reversing/reverse_engineered_functions.md` did not previously
exist for StarLancer — the mention of an "827-entry" pre-existing file in
`CLAUDE.md` refers to the sibling `wc3remake` project's template and does
not apply here. Both files are being built from scratch, entry by entry,
starting from the program entry point downward. Treat anything not listed
below as Confidence 0 (undetermined) — there is no legacy corpus to
inherit unrated claims from in this project.

Confidence levels: **5** exact compiler match · **4** assembly-equivalent ·
**3** differential-tested · **2** static-analysis-supported · **1** plausible
guess · **0** unknown.

Ghidra project: `Starlancer` (instance already open via ghidra-mcp bridge),
2434 functions total, essentially all still at default `FUN_`/`LAB_` names
as of session start — this is a from-scratch pass.

## Functions

| Name (address) | Confidence | Notes |
|---|---:|---|
| `mainCRTStartup` (0x4d1210, was `entry`) | 2 | Standard MSVC CRT startup boilerplate (`GetVersion`, heap/io init, argv/environ setup, then dispatches to `WinMain`). Recognized by shape against the well-known MSVC CRT0 pattern, not individually decompiled field-by-field — low investigative value, CRT internals are not game logic. |
| `WinMain` (0x4a8b10, was `FUN_004a8b10`) | 2 | Confirmed as WinMain by CRT calling convention (`hInstance,hPrevInstance,cmdLine,showCmd`) AND by an embedded string literal `C:\lancer\game\winmain.cpp` used as a memory-allocation tag inside the function body. This single ~700-line function is the ENTIRE top-level game state machine: single-instance mutex check, DirectX version gate, `-`-prefixed command-line arg parsing, `starlancer.ini` config load (Device/Multiplayer/Sound sections via `GetPrivateProfileIntA`), then a large state loop covering menu/mission-select/loadout/mission-play/multiplayer-sync flow. Only the bootstrap prologue (through INI load) has been read closely this session; the deep state-loop body (mission index dispatch, multiplayer zone-check state machine, ~400 remaining lines) is NOT yet understood beyond a skim — flagged as follow-up work, not silently claimed as covered. |
| `RegisterGameWindowClass` (0x4aa8e0, was `FUN_004aa8e0`) | 3 | Clean, unambiguous: builds a `WNDCLASSA` (class name `"WARTHOG_STARLANCER"`, icon resource 0x6f, `WindowProc` as `lpfnWndProc`) and calls `RegisterClassA`. No ambiguity in a function this short and this canonically-shaped. |
| `WindowProc` (0x4a8300, was `FUN_004a8300`, previously not a defined function — created this session) | 3 | Main window procedure. Handles `WM_DESTROY`(2)/`WM_ACTIVATE`(6)/`WM_PAINT`(0xf)/`WM_SETCURSOR`(0x20)/`WM_CHAR`(0x102, feeds a keystroke ring buffer at `DAT_005d547c`)/`WM_SYSCOMMAND`(0x112, SC_CLOSE=0xf060 sets a shutdown flag, SC_RESTORE=0xf120 re-registers/un-minimizes)/`WM_ENTERSIZEMOVE`/`WM_EXITSIZEMOVE`(0x231/0x232)/`WM_ENTERMENULOOP`/`WM_EXITMENULOOP`(0x211/0x212)/a self-posted `WM_USER`(0x400) used to poll window-active state (`DAT_005ddd28`). Individual branch targets (`FUN_004bd780`, `FUN_004a8110`, `FUN_004a8260`) not yet decompiled. |
| `GetVersionInfoAndInstanceTitle` (0x4a8160, was `FUN_004a8160`) | 2 | Reads the EXE's own `VS_VERSION_INFO` (`GetFileVersionInfoA`/`VerQueryValueA`) to populate build-version globals (`DAT_005d5638` etc.), then UNCONDITIONALLY overwrites its output parameter with the literal string `"Microsoft StarLancer"` — the version-info formatting result is computed but never actually used by the output buffer that `WinMain` passes to `FindWindowA` for its single-instance check. This looks like a real quirk in the original binary (dead code path), not a decompiler artifact — worth double-checking if it ever becomes load-bearing, but low priority. |
| `SafeFormatString` (0x4cf4f6, was `FUN_004cf4f6`) | 1 | CRT-level "format into buffer, guarantee null-termination" wrapper around `FUN_004d234c` (unidentified, likely the real `vsnprintf`-family internal) and an overflow handler `FUN_004d2234`. Not investigated further — CRT internals, not game logic; used pervasively for building file paths (`%sships\`, `%sstarlancer.ini`, etc.) throughout `WinMain`. |
| `DebugLog_Stub` (0x4bff10, was `FUN_004bff10`) | 5 | Decompiles to a bare `return;` — an empty function. This is the release build's compiled-out debug/telemetry logger; `WinMain` calls it ~30 times with `(level, format, ...)`-shaped arguments that are all discarded. Confidence 5 because the emptiness itself is directly, unambiguously observed (not inferred) — the *original* meaning (what it logged in debug builds) remains unknown and unrecoverable from this binary. |
| Display-mode/device-cache loader (0x4a89c0, was `FUN_004a89c0`, NOT YET RENAMED) | 2 | Loads `dmodes.bin` (present in `gamedata/StarLancer/`) via a `fopen`/`fread`/`fclose`-wrapper trio (`FUN_004d02ef`/`FUN_004cfeec`/`FUN_004d013c`). File format cross-checked directly against the real file's first bytes (see Data formats below): magic `u32=0x102` at offset 0 confirmed byte-for-byte. Returns 0 (cache reused), 1 (file missing/bad magic → full redetect needed), or 2 (cached mode list doesn't match the live enumerated display modes → stale cache). Not yet renamed pending understanding the second, larger record block it loads into `DAT_00595da0` (0x144c bytes/record — likely full 3D device capability records, not just display modes). |

## Data formats

| File | Confidence | Notes |
|---|---:|---|
| `dmodes.bin` (`gamedata/StarLancer/dmodes.bin`) | 2 | Cached display-mode/device-capability list, read by 0x4a89c0. Layout (from code + direct hex inspection of the real 16-byte file header): `u32 magic` (=`0x00000102`, confirmed), `u32 mode_count` (=1 in the sample file), then `mode_count × 16-byte` records whose individual field semantics are NOT yet determined (values in the sample — `0x00001002, 0x000068d8, 0, 0` — don't obviously read as a width/height/bpp/refresh tuple, so no field-name guess is recorded). A second, larger table (`0x144c` bytes/record, count at a separate offset) is also loaded from the same file and is completely unexamined. |

## SurrenderLib engine core (diagnostics/assertion cluster)

**Major structural finding this session**: the engine's real internal name is
**SurrenderLib** (`SR_` prefix), confirmed directly from two independent
embedded source-path strings: `C:\lancer\surrender\surrenderlib\...` (in
`ReportAssertionFailure`/`ReportAssertionFailureEx`) and the self-referential
diagnostic string `"SR_printf: Null format string pa[ssed]"` inside
`SR_printf` itself. This explains the `SR_MEM_*` import cluster and the
`SR_driver_enumcards` export name found earlier — they're all one library.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `SR_printf` (0x4c3640, was `FUN_004c3640`) | 4 | Real engine name, taken directly from its own embedded self-referential error string. Formats via `FUN_004d05e0` (vsprintf-shaped, not itself investigated), always logs through `DebugLog_Stub` (a no-op in this release build — see above), then either calls an installable output-redirect callback (`DAT_005e82e4`) or falls back to `OutputDebugStringA`. Returns the formatted string's length. |
| `ReportAssertionFailure` (0x4c37b0, was `FUN_004c37b0`, 3-arg) / `ReportAssertionFailureEx` (0x4c3710, was `FUN_004c3710`, 4-arg) | 3 | SurrenderLib's fatal-error/assert handler pair. Both: build a `"Debug assertion in module %s line %d ..."`-shaped message via `SafeFormatString`, route it through `SR_printf`, show a `MessageBoxA` titled `"FATAL: SR Assertion Failed"`, then execute `swi(3)` (x86 `INT 3` — `__debugbreak`) to trap into a debugger/crash. The Ex variant takes an extra code parameter and invokes a different callback slot before the message box. Confidence 3 (not 4) because the exact parameter semantics — which of module/line/code map to which literal call-site argument — are inferred from the format string's argument order, not independently cross-checked against a call site with unambiguous values. |
| `SetAssertionCallback` (0x4c3620, was `FUN_004c3620`, sets `DAT_005e82e8`) / `SetAssertionCallbackEx` (0x4c3630, was `FUN_004c3630`, sets `DAT_005e82ec`) | 3 | Trivial one-line setters, confirmed by direct xref: each writes exactly the global that its corresponding `ReportAssertionFailure(Ex)` reads and conditionally calls as a pre-crash cleanup hook. Neither setter's own CALLER has been traced yet (who installs these hooks, and when, is unknown). |
| `DAT_005e82e4` (SR_printf output-redirect callback) | 1 | Read once (inside `SR_printf`), no writer found yet in functions examined so far — likely set by a not-yet-decompiled init routine (possibly a debug-console or network-log redirect). Genuinely open, not guessed at. |

## Bootstrap cluster, continued (this session's second pass)

| Name (address) | Confidence | Notes |
|---|---:|---|
| `CreateGameWindow` (0x4a85a0, was `FUN_004a85a0`) | 3 | Builds the window title via `GetVersionInfoAndInstanceTitle`, then `CreateWindowExA` on class `"WARTHOG_STARLANCER"` at a fixed 640×480 (`0x280`×`0x1e0`) with style `0x800000`, then immediately zeroes `GWL_STYLE` — the real style is applied later once config (windowed/fullscreen) is known. |
| `LoadLanguageStrings` (0x490dc0, was `FUN_00490dc0`) | 2 | Loads `LANGUAGE.DLL` (present in `gamedata/StarLancer/`), enumerates ALL its string-table resources by calling `LoadStringA` with an incrementing ID until it fails, concatenates them into one `SR_MEM_allocate`'d block (tagged `C:\lancer\game\language.cpp`) with a parallel offset-index array. Also reads `LANGUAGE.DLL`'s own version resource and scans a version/language compatibility table at `DAT_0050318c` via `FUN_004daef0` (an unidentified 4-byte comparator) — this trailing scan's purpose (language-version compatibility gating?) is NOT understood, flagged Confidence 1 for that part specifically. |
| `DetectDirectXVersion` (0x4778c0, was `FUN_004778c0`) | 3 | The DirectX capability prober `WinMain` calls before its `"DirectX Version %03x" < 0x700` gate. Walks a full detection ladder: OS platform (`GetVersionExA`) → DirectDraw create+QI (0x100/0x200) → DirectInput availability via `LoadLibraryA("DINPUT.DLL")`+`GetProcAddress("DirectInputCreateA")` (0x300) → primary surface creation via `SetCooperativeLevel`+`CreateSurface`+QI to a surface interface (0x500/0x600) → `CoCreateInstance` of a DirectMusic CLSID (0x601) → `GetProcAddress("DirectDrawCreateEx")` success (0x700 = DirectX 7, the actual minimum). Confirmed by the output tier value matching `WinMain`'s own `0x700` threshold exactly. Individual DirectX interface vtable offsets (e.g. `+0x50`=`SetCooperativeLevel`, `+0x18`=`CreateSurface` on `IDirectDraw2`) inferred from well-known COM vtable layout, not independently verified against a header. |
| `OpenBigFile` (0x4c7e20, was `FUN_004c7e20`) / `CloseBigFile` (0x4c7f20, was `FUN_004c7f20`) | 3 | Confirmed real name: embedded debug-tag string `C:\lancer\game\bigfile.cpp`. Opens a `.HOG`-style archive: validates a `0x42494746` ("BIGF"/"FGIB" FourCC, byte order not fully pinned down) magic, reads two header ints (record counts/offsets), allocates and reads a directory/TOC block. Matches real files in the game directory (`RESOURCE.HOG`, `Resource.FAT`, `cd1.hog`/`cd2.hog`). Individual directory-entry field layout NOT yet decoded — only the container-level open/close lifecycle is understood. |
| `ShowEulaDialog` (0x4aacf0, was `FUN_004aacf0`) | 3 | Loads `EBUEULA.DLL` (present in game dir), calls its exported `EBUEula` function (name confirmed via literal `GetProcAddress` string) with a registry path and an app-name string loaded from resource ID 1. |
| `InitializeHighResTimer` (0x4a6e70, was `FUN_004a6e70`) | 3 | One-shot guarded init: zeroes an 80-byte global block, calls `timeBeginPeriod(1)`. Straightforward. |
| `LoadInstallPathsFromRegistry` (0x4ad480, was `FUN_004ad480`) | 2 | Reads `HKLM\Software\Microsoft\Microsoft Games\...` (Starlancer subkey name not extracted from the string table this pass), pulling `InstallType`, `CDPath`, `InstallationDirectory` values. If `InstallType=='3'`, additionally populates two more path globals (`DAT_005d6a28`/`DAT_005d6928`) — plausibly per-disc paths matching the real `cd1`/`cd2` directories seen in the game folder, but NOT confirmed (the `'3'` value's meaning is a guess). Falls back to `GetCurrentDirectoryA` if the registry key is entirely absent. |
| `LoadPlayerProfile` (0x4751b0, was `FUN_004751b0`) | 2 | Loads `profile.bin` (present in game dir). Sets numerous default globals first, including `DAT_00562dc8 = 1` — cross-confirms this global as "current mission index", corroborating `WinMain`'s heavy independent use of the same global (two unrelated functions treating it consistently raises this above a single-call-site guess, though no formal differential test was run, so held at 2 not 3). On file-open failure, falls back to a not-yet-decompiled `FUN_00475390()` (likely `CreateDefaultProfile`/`SaveProfile`). The actual 0xd0-byte profile record's field layout is NOT decoded. |
| `EnumDisplayCardsFromDriver` (0x4cc520, was `FUN_004cc520`) | 3 | Generic "load a display-driver DLL, call its exported `SR_driver_enumcards`, unload" wrapper — confirmed by the literal exported-function-name string. This is the display-mode/card enumerator that the `dmodes.bin` cache loader (0x4a89c0) cross-checks itself against; resolves that dependency-graph gap. |
| `FUN_004bcf70` (NOT renamed) | 1 | Walks two fixed memory ranges in fixed-size strides and mutates a literal charset string (`"abcdefghijklmnopqrstuvwxyz_0123..."`) via repeated calls to `FUN_004bcff0(0x1d)` and `FUN_004d10cb`. Shape strongly suggests a copy-protection/anti-tamper or resource-descrambling table init, but the decompile shows an uninitialized stack variable being passed by value where an address would be expected (`FUN_004d10cb((int)local_28)`), suggesting either self-modifying/hand-written-asm code the decompiler can't faithfully represent, or a genuinely obfuscated routine. Deliberately NOT further investigated or renamed this session — per METHODOLOGY, static reading stopped producing a confident hypothesis, and this doesn't gate any game-logic understanding (it runs once, unconditionally, early). Left as an honest gap rather than guessed at. |

## RunMenuScreenLoop's 12 screen handlers — COMPLETE (2026-09-08, third session)

All 12 screen IDs `RunMenuScreenLoop` dispatches to are now identified,
mostly at high confidence thanks to embedded `.ini`-key and URL strings
that make the purpose unambiguous even without full algorithmic detail.
Individually huge functions (100-700+ lines each, dominated by hardcoded
UI-widget-position tables) — documented at the structural/purpose level
(Tier 1-2 per METHODOLOGY), not decompiled field-by-field.

| Screen ID | Name (address) | Confidence | Purpose |
|---:|---|---:|---|
| 0 | `RunMainMenuScreen` (0x428b60) | 2 | Main title menu. Loads player profile, hit-tests 3 button rects (→ screens 12/14/1), and contains what looks like a hidden mission-select cheat code: 6 chained input checks arm a "type a 2-digit number" mode that directly overwrites `DAT_00562dc8` (current mission index) — the exact key values aren't identified (Confidence 1 for the "cheat code" interpretation specifically, 2 for the mechanism's shape). |
| 1 | `RunOptionsMenuScreen` (0x42a620) | 2 | Options hub — routes to Sound (screen 3), Video (0xf/15), Controls (0x10/16), or back to main menu (screen 0). |
| 3 | `RunSoundOptionsScreen` (0x42dab0) | 3 | Sound options. Confirmed unambiguously: writes `[Sound]` `3DProvider`/`Fxvolume`/`Musicvolume`/`Speechvolume`/`Mastervolume` directly to `starlancer.ini` via `WritePrivateProfileStringA`. Cycles 3D audio provider, adjusts 4 volume sliders. |
| 7 | `RunMissionBriefingScreen` (0x437010) | 3 | Documented in the previous session — mission briefing movie/speech, hands off to the ship-interior VR loop. |
| 8 | `RunNetworkDisconnectScreen` (0x43ca30) | 3 | Trivial: `Sleep(1000)` then a network-cleanup call (`FUN_004abde0`), returns to screen 3 (Options). A "disconnecting..." pause screen. |
| 10/11 | `RunSaveLoadScreen` (0x43ca50) | 2 | Shared Save/Load Game screen, mode selected by `DAT_0051d54c` (1=save, 0=load — same flag pattern as the 17/18 pair). Builds a save-slot grid from a large hardcoded UI-layout table; load path waits on network/deathmatch state (`DAT_005dccfc`/`DAT_00582e8c`) before proceeding, save path formats a save name via a resource string. |
| 12 | `RunNewGameSetupScreen` (0x430490) | 2 | Campaign setup: difficulty toggle, an inline pilot-name text editor (indexes a per-character-class string table at `DAT_005d5e8c`), routes to the save browser (screen 13) or starts the campaign (`FUN_00430300`, returns 1 to signal "profile loaded, begin game"). |
| 13 | `RunSaveGameBrowserScreen` (0x431730) | 3 | The actual save-file scanner/browser: builds `saves\<pilotname>GAME_%02d.IFF` paths, reads each slot's `SAVE`/`MISN` IFF chunks (FourCC `0x45564153`="SAVE", `0x5353494d`="MISS") for a thumbnail and timestamp (`GetFileTime`→`GetDateFormatA`, formatted as `"<hour>:<minute> <date>"`), lists up to 10 slots with scroll support. Shared/called directly by `RunSaveLoadScreen` mid-flow as well as being screen 13 itself. |
| 14 | `RunMultiplayerSetupScreen` (0x432fc0) | 3 | Multiplayer connection-type menu. Confirmed via a literal `ShellExecuteA(..., "http://www.zone.com/starlancer", ...)` call — Star Lancer used the **MSN Gaming Zone** for online matchmaking, a real, historically-accurate detail. Offers Direct-connect / Zone.com (launches the web browser) / Host / Join / other connection types, plus a scrollable found-session list connecting via `FUN_004bc720`. |
| 15 | `RunVideoOptionsScreen` (0x42e9b0) | 3 | Video/display options. Confirmed via `[Device]` `gamma`/`Transitions` ini keys. Directly manipulates the SAME device/mode table (`DAT_00595fe8`/`DAT_00595fec`/`DAT_00595ff0`) populated by the `dmodes.bin` loader documented in an earlier session — cross-confirms that table's role as the enumerated display-mode list. Also cycles texture/geometry detail levels, lightmap toggle, and 3D provider (all `starlancer.ini` `[Device]` settings read at bootstrap). |
| 16 | `RunControlsOptionsScreen` (0x42b690) | 3 | Controls/key-binding options. Confirmed via `[KeyConfig]` ini keys: `ForceFeedback`, `JoystickInvert`, `HatEnable`, `TwistEnable`, `controller` (0/1/2 selecting keyboard/joystick/other device). Contains a full key-rebind UI (click a control, press a new key, swaps binding table entries, detects and reports conflicts with other bound controls). |
| 17/18 | `RunMultiplayerLobbyScreen` (0x44b950) | 2 | Multiplayer game-setup lobby, mode via `DAT_0051d54c` (host=1/client=0 — matches the save/load pair's flag reuse pattern). Host picks a mission from a table (`DAT_0050c798`, cross-indexed against `DAT_00562dc8`), sees/toggles a player roster (`DAT_005db8f4`, same per-player stride seen in `WinMain`'s multiplayer section) with ready/team-type flags. |

### Coverage note

This closes `RunMenuScreenLoop`'s entire dispatch table — all 12 distinct
screen IDs (0,1,3,7,8,10,11,12,13,14,15,16,17,18 — 10 and 11 share a
handler, as do 17 and 18) now have identified, named handlers. None of
the sub-widget/UI-layout details (the hundreds of hardcoded pixel
coordinates in each function) were catalogued — those are presentation
data, not behavior, and low value to reverse further per METHODOLOGY's
"byte-level match is a confidence tool, not the goal" principle.

## Save-game IFF reader + resource-loading primitives (2026-09-08, fourth session)

| Name (address) | Confidence | Notes |
|---|---:|---|
| `IffFile_Open` (0x490930), `IffFile_FindFormChunk` (0x4909d0), `IffFile_FindChunk` (0x490c40), `IffFile_Read` (0x45e8d0), `IffFile_CloseChunkStack` (0x490980) | 3 | A real, generic C++ `__thiscall` IFF (InterChange File Format) reader class — not save-specific. Confirmed via: (1) the classic IFF container magic `0x4d524f46` decoding byte-for-byte to `"FORM"`; (2) `IffFile_Read`'s own embedded error strings (`"Attempted read from unopened file: %s"`, `"Attempt to read 0 bytes: %s"`, `"Read from NULL pointer: %s"`, `"Read failed on file: %s"`) which describe exactly the guard checks present in the decompile. `FindFormChunk` searches for a NESTED `FORM`-type container by 4-character type tag (correct IFF semantics — `FORM` chunks nest); `FindChunk` searches for a plain leaf data chunk by raw 4-character chunk ID (also correct — leaf chunks are NOT `FORM`-typed). This distinction is exactly how real IFF parsers work, strong evidence this is a faithful, standards-following implementation rather than an ad-hoc format. |
| `LoadGame` (0x475430) | 2 | Confirmed real save-file user: opens a save via `IffFile_Open`, finds the `FORM "SAVE"` container (`0x45564153`="SAVE"), then iterates a 5-entry field table (`PTR_DAT_00500a24`) calling `IffFile_FindChunk`+`IffFile_Read` per tagged field — a real "read N named fields from a form" pattern. Also restores a ~34-field campaign/difficulty-state block (`DAT_0052a3f0`..`DAT_0052a480`) from a parallel `DAT_00562f7x` staging area — this is the SAME state block `WinMain`'s bootstrap and `LoadPlayerProfile` both zero/default at startup, now cross-confirmed a third way (save-game restore). Individual field TAGS in the 5-entry table (`PTR_DAT_00500a24`) not yet read as strings — flagged as an easy follow-up (the table itself is right there, un-decoded). |

## Mission file format (`.dte`) and load chain (2026-09-08, fourth session)

**Major structural finding**: traced the complete chain from "player selects mission" to "mission data loaded and gameplay begins," and decoded the on-disk `.dte` mission file's top-level structure. Files live at `.\missions\mission<N>.dte` (confirmed via 3 embedded literal paths — `mission29.dte`, `mission251.dte`, `mission311.dte` — plus the general `mission%d.dte`/`%s.dte` format strings), and a file-open-dialog string `"StarLancer DTE Files (*.dte)"` confirms the extension's real name (though not what "DTE" stands for — not found in the string table this pass).

| Name (address) | Confidence | Notes |
|---|---:|---|
| `RunMissionSelectMapScreen` (0x44f3d0) | 2 | The in-universe "star map" screen reached from the ship-interior VR loop's `roomType=5` hub — lets the player pick between 3 mission branches (`mission30`/`mission31`/`mission32`, hotspot-selected) or a special `mission29` path, then triggers the load via `InitializeMissionGameplay`/`FUN_00494040`/`FUN_004942b0` with `DAT_00562dc8` temporarily set to the chosen mission number. Confirms `DAT_00562dc8`'s identity yet again (4th independent function now). |
| `InitializeMissionGameplay` (0x4934f0) | 2 | Sets up cockpit/HUD/radar rendering state, resolves difficulty/campaign-branch outcome codes (a large `switch` on a "previous mission result" value, 0-0xff, mapping to specific follow-on mission-select codes — an actual branching-campaign outcome table, not decoded field-by-field), and calls `LoadMissionFile`. Fatal-errors (`ReportAssertionFailureEx`, `"The mission number is invalid!!!!"`) if the load fails. |
| `LoadMissionFile` (0x451d90) | 3 | The real `.dte` parser entry point. Calls `LoadResourceFileBuffer` to get the whole mission file into memory as one buffer (~1,024,000 / `0xfa000` byte cap), then calls `ReadMissionDirectoryEntry` exactly **27 times** in a fixed sequence — each call reads one 8-byte directory entry from the buffer and resolves+stores an absolute pointer to a named global (a different `DAT_/PTR_DAT_` global per call, e.g. `DAT_00525fa8`, `DAT_00525f3c`, `DAT_005294f8`, `DAT_0052951c`, ... 23 more). Finishes with 5 not-yet-decompiled finalization calls (`FUN_0045cb40`, `FUN_00452010`, `FUN_00453050`, `FUN_00457c10`, `FUN_0045cbc0` — likely cross-reference resolution between the just-loaded tables, e.g. linking ship spawns to their AI scripts). Returns the loaded buffer pointer, or 0 on failure. |
| `.dte` directory-entry format (`ReadMissionDirectoryEntry`, 0x452a20) | 3 | Each entry is 8 bytes: a 32-bit header word whose low 16 bits are a type/ID field and whose top byte carries 4 individual capability flag bits (`0x1000000`/`0x2000000`/`0x4000000`/`0x8000000`, each setting a distinct global flag — meaning present elsewhere in the mission, e.g. "this mission uses feature X"), followed by a 32-bit `offset` that gets added to the buffer's base address to produce an absolute pointer into the mission blob. This is a flat, single-buffer format with an upfront table of contents — no filesystem-style nesting (unlike the save-game format, which reuses the general-purpose nested-IFF reader). Confidence 3: directly read from the decompiled bit-test/pointer-arithmetic code, not inferred. |
| `LoadResourceFileBuffer` (0x45a300) | 2 | Loads a named resource either from a loose file on disk (`FUN_0045a3e0`, only if `FUN_004ad6e0()` — an "is this a real installed copy with direct file access" check, not decompiled — returns true) or from the `RESOURCE.HOG` archive via `LoadNamedResource`, always copying the result into a freshly `malloc`'d buffer sized to the actual read length. Generic — used for `.dte` mission files here, but the mechanism itself isn't mission-specific. |
| `LoadNamedResource` (0x4c5bd0) / `HOG_BigRead` (0x4c7f60) | 3 | The engine's core "load a resource by name from the archive" primitive — **real name confirmed directly**: `HOG_BigRead`'s own embedded error strings are `"HOG bigread2: error loading '%s'"` and `"HOG bigread: error loading '%s'"`, i.e. the function names itself. Strips a 2-character extension suffix if present (likely a language/resolution variant suffix, not confirmed) and any directory path from the requested name, tries a loose-file-on-disk override first, then falls back to scanning the open `.HOG` archive's directory (via the `OpenBigFile`-opened handle) for a matching entry and reading it into an `SR_MEM_allocate`'d buffer (tagged `bigfile.cpp` again). `LoadNamedResource` is a one-line convenience wrapper around this. Called constantly across menu screens, the VR loop, and mission loading alike — this is THE central asset-loading choke point for the whole game, matching `OpenBigFile`/`CloseBigFile` as siblings in the same `bigfile.cpp` source file. |

### Open follow-ups from this session

- The 27 individual `.dte` directory-entry targets' semantics (ship
  placements? waypoints/spots? script commands? dialogue triggers?) —
  only their storage addresses are known, not their content layout.
  Given `dependency_graph.md`'s AREA/SPOT/PART-record precedent from the
  sibling `wc3remake` project (a structurally similar Digital
  Anvil/Origin-era engine), these are plausible candidates but NOT
  confirmed for StarLancer specifically.
- `LoadMissionFile`'s 5 finalization calls (`FUN_0045cb40`,
  `FUN_00452010`, `FUN_00453050`, `FUN_00457c10`, `FUN_0045cbc0`).
- `FUN_004ad6e0` ("has direct file access" check) and `FUN_0045a3e0`
  (raw loose-file reader) — the non-archive load path.
- `PTR_DAT_00500a24`'s 5 field tags in `LoadGame` — not read as strings
  yet, would fill in the save-file's actual field names.
- What "DTE" stands for — not found in the string table.

## Flight/combat gameplay core loop (2026-09-08, fifth session)

Completed the "load/run/unload mission" trio flagged as the highest-value
remaining target last session, and went one level deeper into the actual
per-frame gameplay loop.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `RunMissionGameplay` (0x494040) | 3 | Confirmed via a run of `DebugLog_Stub` teardown tags matching real subsystem names exactly (`"uncolour hud target"`, `"destroy lockring"`, `"dockring exit"`, `"chaff exit"`). This IS the flight/combat main loop. Structure: an outer `do` loop wrapping an inner `while(true)` that pumps input (`FUN_004aab20`, 0 = quit), computes elapsed simulation ticks since last frame, calls `UpdateMissionTick` once per elapsed tick (fixed-timestep sim) and a multiplayer network-tick function (`FUN_004776 70`, NOT YET IN DB) the same number of times if multiplayer, then calls `UpdateMissionFrame` once per rendered frame (variable-rate) — breaking out to call `CheckMissionExitState` instead when a pause/menu flag (`DAT_0057e04c`) is set. Exits the whole loop when `UpdateMissionFrame` or `CheckMissionExitState` signal completion. |
| `UnloadMission` (0x4942b0) | 3 | Confirmed the same way — teardown tags `"deathmatch exit"`, `"bmo destroy"`, `"radarmesh destroy"`, `"end samples"`, `"streamer stop"`, `"end 3d samples"`, `"speech free"`, `"samples free"`, `"mission destroy"` (the last one calling `FreeMissionFile`, `0x45a530` — the direct counterpart to `LoadMissionFile`, confirming the load/run/unload trio is symmetric). |
| `UpdateMissionTick` (0x477850) | 2 | Thin fixed-timestep dispatcher: increments a frame counter, every 100th tick decrements a difficulty-related countdown (`DAT_0052a474`), and calls `FUN_004774d0` (NOT YET IN DB — almost certainly the real physics/AI simulation step, given this wrapper does nothing else of substance). In multiplayer (`DAT_005dc1e8`), calls two different sub-steps (`FUN_0049ceb0`/`FUN_0049cf40`) instead of/around the single-player path. |
| `UpdateMissionFrame` (0x4924b0) | 1-2 | The big per-rendered-frame update — 400+ decompiled lines, NOT fully decoded, documented structurally only. Confirmed pieces: (1) a frame-rate-adaptive detail throttle keyed off graphics-detail setting (`DAT_005d54e0` 0/1/2 → different target-FPS bands 30-40/30-40/40-60, adjusting a global throttle value `_DAT_005e829a`); (2) a mission-timeout/cutscene state machine on `DAT_00539a34` (values 7/8/0x1a/0x1b/0x1c/0x1d, each computing a tick deadline relative to `DAT_00539aa4`/`DAT_005883b0`, auto-triggering mission exit when exceeded); (3) a per-object damage-severity visual-banding system — computes an armor-percentage-like ratio per ship object, buckets it into 4 severity levels (0-3) via 50%/70%/90% thresholds, and calls `FUN_00494400` (NOT YET IN DB) when a ship's severity level changes, presumably to swap damage-decal/smoke visual state; (4) random engine-smoke particle emission (`FUN_0046bd00`, `rand()%10==0`) for ships in a specific damage state; (5) end-of-mission polling across all player slots checking a "player status/flags" bitmask, logging via `DebugLog_Stub` when all players have exited. Individual object-type special cases (type IDs `0x6d`, `0xa8`, `0x44`, `0xd` compared against `piVar7[0]`/`*(int*)*puVar9` — almost certainly object-CLASS IDs, e.g. capital ship / weapon / other) are NOT decoded — this is the natural next layer if flight/combat is revisited. |
| `CheckMissionExitState` (0x491fc0) | 2 | Handles a small state code (`DAT_0057daa4`, values 5/6/7) controlling how the mission loop terminates: 5 → sets a "restart" flag (`DAT_005d60b9=1`) and returns "done"; 6 → returns "done" with no restart; 7 → sets `DAT_00588394=4` (an outcome code shared with other screens' dispatch, e.g. `RunMissionBriefingScreen`'s own `DAT_00588394` checks) and returns "done"; any other value → normal per-frame continuation (screen-shake/gamma-change handling, end-of-turn cleanup for a "current target" global `DAT_005027b8`). |

### Open follow-ups from this session

- `FUN_004774d0` — very likely the real physics/AI simulation step (called by `UpdateMissionTick`, itself otherwise trivial). Highest-value next target for understanding actual flight/combat mechanics.
- `UpdateMissionFrame`'s object-type-ID special cases (`0x6d`, `0xa8`, `0x44`, `0xd`) and the damage-severity visual system (`FUN_00494400`).
- `FUN_00477670` (multiplayer per-tick network update, called in lockstep with `UpdateMissionTick`).
- The ship/object struct itself — `UpdateMissionFrame` dereferences dozens of offsets into what's clearly a large per-object struct (`piVar7`, offsets up to `+0x198` and beyond) without any type recovered yet. Given the volume of code that touches this struct, recovering it properly would be a substantial, high-value subsystem in its own right (matches the "actor" struct pattern documented for the sibling `wc3remake` project).

## Physics/AI simulation step + ship-object struct (2026-09-08, sixth session)

Opened the function `UpdateMissionTick` calls (`FUN_004774d0`) — this
turned out to be the real per-object simulation dispatcher, run once
every 4 ticks (a rate-limiter), iterating the main object array
(`DAT_00587ce0`, count `DAT_00539aa0+1` — the SAME array `UpdateMissionFrame`
iterates) and calling 3 per-object functions on each active one.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `ProcessMissionSimulationTick` (0x4774d0, was `FUN_004774d0`) | 2 | Rate-limited to 1-in-4 calls from `UpdateMissionTick`. Iterates all active objects (flags at object`+8`, skipping any with bit `0x420` set — almost certainly "destroyed/inactive"), calling `UpdateObjectPhysicsAndTimers`/`UpdateShieldQuadrants`/`UpdateWeaponFiring` on each. Has a round-robin "one object gets extra processing this tick" mechanic (`DAT_00562ffc`, cycling through all objects over time) calling `FUN_004c2690` twice — plausibly a cost-spreading technique for an expensive per-object operation (LOD refresh, AI re-evaluation), not identified further. |
| `UpdateObjectPhysicsAndTimers` (0x476c90, was `FUN_00476c90`) | 2 | Per-object update with 3 distinct jobs: (1) **physics transform commit** — if flag bit 0 of `object+4` is set, copies a 72-byte (18-float) block from `object+0x5c` to `object+0x14`, then updates the flags; this pairing (`+0x14`=committed/current, `+0x5c`=pending) reads as a classic double-buffered physics-transform commit (position+orientation+velocity), though NOT verified against real data. (2) **Shield/weapon energy regeneration with 3 distinct curve modes** (`object+0xb4` = 1/2/3): mode 1 clamps to a capacity limit and zeroes on overflow, mode 2 wraps by repeated subtraction keeping remainder, mode 3 wraps differently — each followed by a threshold-crossing scan over a per-capacity-index sub-table (`object+0xa4` chain, stride `0x28`/`0xc`) that fires one of two events (`FUN_0047c7b0`/`FUN_0047c800`, NOT decompiled) when the regen value crosses into specific integer ranges. (3) **Recurses into attached child objects** (`object+0xf8`=count, `+0x100`=array) whose own flags satisfy `(flags & 0xa0)==0 && (flags & 0x800)!=0`, marking the parent with `0x800` — models attached sub-objects (turrets, docked craft) sharing the same per-tick update. |
| `UpdateShieldQuadrants` (0x476fc0, was `FUN_00476fc0`) | 1 | Tentative interpretation. Skips objects with flag bit 1 (`object+8 & 2`) set. If a mode byte (`object+0xb95`) equals 5, zeroes 4 floats at `object+0x5f0..+0x5fc` and returns — otherwise ramps those same 4 floats toward a capacity limit derived from the object's class-definition pointer (`object+0x10`), with special-cased extra logic for the LOCAL player's object (`object+4 == DAT_005883fa`) referencing what look like live control-input globals (`_DAT_0051cf34`/`_DAT_0051cf78`). 4 regenerating float values per ship, player-adjustable, is classically a **directional/quadrant shield strength** mechanic — Star Lancer is known to have directional shields — but this is a plausible-shape guess, NOT confirmed field-by-field. Confidence 2 for "4 regenerating capped floats with player-specific handling," Confidence 1 for "these are shield quadrants specifically." |
| `UpdateWeaponFiring` (0x4770e0, was `FUN_004770e0`) | 2 | The real weapon-firing/gunnery decision logic — shared by player auto-fire assist and AI-controlled ships (branches on `object+4 == DAT_005883fa`, the local-player check). Ramps a weapon-energy-pool float (`object+0x140`) toward a capacity limit, then iterates a hardpoint array (`object+0x130`=count, `+0x134`=array, stride `0x60`) — each hardpoint has a ready-tick field compared against the current tick (`DAT_005883b0`, the same global elsewhere confirmed as tick counter), a linked weapon-type-definition pointer (reload time, energy cost, ammo-per-shot fields), and calls `FUN_0047c5f0`("FireWeapon"?)/`FUN_0047c800` when ready AND enough energy/ammo is available — gated by a difficulty-scaled reload-time modifier (`object+0x674`, `*0x87/100` when set) and, for AI ships specifically, a `rand()%100 < <aggression-derived threshold>` chance-to-fire roll. Also toggles an "alternate fire group" bit (`object+0x14c`) — a classic dual/quad-mount alternating-barrel firing pattern. |

### Ship-object struct — partial, offset-confirmed fields only

**Deliberately NOT created as a formal Ghidra struct type this session** — unlike `VRRoomNode` (verified against real memory), every field below is inferred purely from code usage across `UpdateMissionFrame`/`UpdateObjectPhysicsAndTimers`/`UpdateShieldQuadrants`/`UpdateWeaponFiring`, with no independent data-level cross-check. Per METHODOLOGY, this stays Confidence 1-2 prose, not a committed type, until something more concrete (a real save/mission-file byte layout, or a differential test) confirms it.

| Offset | Size | Field (tentative) | Confidence | Evidence |
|---|---:|---|---:|---|
| `+0x00` | 4 | object class/type ID | 2 | Compared against literal type IDs (`0x6d`, `0xa8`, `0x44`, `0xd`, `0x1f`) in `UpdateMissionFrame` |
| `+0x04` | 4 | **UNRESOLVED — see caveat below** | 0-1 | See "Open question" below |
| `+0x08` | 4 (byte-tested) | status flags | 2 | Tested consistently as `&2` (destroyed?), `&0x420`/`&0x10000840`/`&0x200420` (various inactive/special states) across every function that touches objects in this session AND the previous session's `UpdateMissionFrame` work |
| `+0x14` | 72 (18 floats) | current/committed physics transform (pos+orient+velocity, unconfirmed subdivision) | 1 | Destination of the `+0x5c` copy in `UpdateObjectPhysicsAndTimers`, gated by a "commit" flag bit |
| `+0x5c` | 72 (18 floats) | pending physics transform | 1 | Source of the same copy |
| `+0xa4` | 4 | pointer to a weapon/shield-energy capacity-group structure | 1 | Dereferenced through 2 more levels (`+0x220`, stride `0x28`/`0xc`) to reach per-index capacity values and event-trigger sub-records |
| `+0xb4` | 4 | energy regen curve mode (1/2/3) | 1 | Selects between 3 distinct clamp/wrap formulas in `UpdateObjectPhysicsAndTimers` |
| `+0xb8` | 4 | index into the capacity-group array | 1 | |
| `+0xbc` | 4 | energy regen rate (float) | 1 | |
| `+0xc0` | 4 | energy current value (float) | 1 | |
| `+0xf8` | 4 | attached child-object count | 1 | |
| `+0x100` | 4 | pointer to child-object pointer array | 1 | |
| `+0x130` | 2 (short) | weapon hardpoint count | 1 | |
| `+0x134` | 4 | pointer to hardpoint array, stride `0x60` | 1 | |
| `+0x138` | 4 | pointer to a per-hardpoint alt-fire counter array | 1 | |
| `+0x13c` | 4 | ammo/charge count | 1 | |
| `+0x140` | 4 | weapon energy pool (float) | 1 | |
| `+0x144` | 2 (ushort) | weapon-related flags | 1 | |
| `+0x148` | 4 | weapon-energy-pool gate (float, zero-check) | 1 | |
| `+0x14c` | 4 | alternate-fire-group toggle | 1 | |
| `+0x5f0`-`+0x5fc` | 4×4 | 4 regenerating capped floats (tentatively shield quadrants) | 1 | See `UpdateShieldQuadrants` above |
| `+0x664`, `+0x66c` | 4 each | floats feeding the shield-quadrant and weapon-firing ramp formulas | 1 | |
| `+0x674` | 4 | difficulty-scaled reload-time flag | 1 | |
| `+0x734`, `+0x73c` | 4 each | more ramp-formula floats | 1 | |
| `+0x754` | 4 | AI/behavior state (compared against literal `8`) | 1 | |
| `+0xb95` | 1 | special mode byte (5 = disabled/docked, zeroes shield quadrants) | 1 | |

**Open question — offset `+0x4`, deliberately NOT resolved**: in
`UpdateShieldQuadrants`/`UpdateWeaponFiring`, `object+4` is compared for
exact EQUALITY against `DAT_005883fa` (the local player's slot index,
a small 0-7 value) — consistent with "owner/pilot slot index." In
`UpdateObjectPhysicsAndTimers`, `object+4` is read as a flags dword and
individually bit-tested/set (bits 0,1,2,3,5,7,11 all touched). Both
could be true simultaneously if the low bits hold a small owner-index
and specific higher bits are independent status flags that are usually
zero — a real, if slightly unusual, packed-field design — but this has
NOT been verified, and could equally mean these three functions don't
all receive the literal same struct base pointer (e.g. one might take
a sub-object pointer offset from the ship base). Flagged explicitly as
open rather than guessed at, per METHODOLOGY.

### Open follow-ups from this session

- ~~`FUN_0047c7b0`/`FUN_0047c800` (energy-threshold-crossing events), `FUN_0047c5f0` (the actual "fire weapon" call)~~ — **resolved next session, see below.**
- `FUN_004c2690` (the round-robin per-tick extra work) — still not decompiled.
- Whether `+0x5f0..+0x5fc` really are shield quadrants (Confidence 1
  guess) — could be checked by finding where these 4 floats are
  rendered/read for HUD display, which would likely reveal a clearer
  UI-facing name.
- The full ship-object struct's total size is unknown — `+0xb95` is
  the highest confirmed offset this session, but nothing bounds the
  struct's actual end.

## `FireWeapon` and the weapon-instance/weapon-type struct split (2026-09-08, seventh session)

Followed the weapon-firing chain one layer deeper: `FireWeapon`
(`FUN_0047c5f0`) and its two siblings `FireChildTurrets`
(`FUN_0047c7b0`) and `SpawnWeaponVisualEffect` (`FUN_0047c800`), both
previously flagged as the energy-threshold-crossing event handlers in
`UpdateObjectPhysicsAndTimers`.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `FireWeapon` (0x47c5f0, was `FUN_0047c5f0`) | 2 | Confirmed as the real fire-a-shot function. Reads a sound/effect-variant index (0-14, clamped) from the weapon-type-definition (reached via the weapon instance's `+0xac` pointer, `+0x64` field), allocates a free slot from a 200-entry global projectile/tracer pool (`DAT_00563148`, stride `0x31`=49 dwords — searched linearly for a `-1` sentinel, so a flat free-list scan rather than an explicit freelist), spawns the projectile (`FUN_0047bdb0`), optionally plays a positional sound effect from a 15-entry×11-variant sound table (`DAT_00500ce0`, indexed by the effect-variant index — the 11 variants per entry plausibly are different listener-distance/perspective mixes), links the new projectile into a global active-projectile doubly-linked list (`DAT_00563144`= head), and sets a cooldown-until-tick value on the weapon instance (`+0xbc`, float) from a matching 15-entry duration table (`DAT_00500f64`) added to the current tick (`DAT_005883b0`). |
| `FireChildTurrets` (0x47c7b0, was `FUN_0047c7b0`) | 2 | Iterates the SAME child-object list (`+0xf8`=count, `+0x100`=array) documented on the ship-object struct last session — cross-confirms those offsets a second, independent way. For every child whose type ID (`child+0`) equals `4`, calls `FireWeapon` on it. This means: when a capital ship's turret-group energy (tracked via `UpdateObjectPhysicsAndTimers`'s regen-curve/threshold-crossing mechanism) crosses a threshold, it AUTOMATICALLY fires every attached type-4 (turret) child — a complete, closed explanation for how capital-ship turret arrays autofire in this engine. Type `4` is now a reasonably confident guess for "turret" in the object-class-ID enum (alongside `0x6d`/`0xa8`/`0x44`/`0xd`/`0x1f` seen in earlier sessions, still unidentified). |
| `SpawnWeaponVisualEffect` (0x47c800, was `FUN_0047c800`) | 2 | A DIFFERENT function from `FireChildTurrets` despite both being reached from threshold-crossing dispatch — takes a weapon-instance-like pointer, scans an effect-anchor sub-table (`+0xa4` → count `+0x214`/array `+0x218`, stride `0x7c`) for entries of type `7`, and for matches randomizes a UV sub-tile offset (quarter-texture-atlas selection: U from a 4-way random pick, V from a 2-way pick) on a global active-effect object (`DAT_005636dc`) — a classic "pick a random frame from a muzzle-flash sprite sheet" technique. This is the muzzle-flash/impact-spark visual trigger, not a turret-fire trigger — the two functions happen to share the "triggered by an energy/anchor-type-tagged sub-list" shape but serve different purposes. |

### Weapon-instance and weapon-type-definition structs (partial)

Two distinct, chained structs sit behind each hardpoint entry
(`shipObject+0x134[i]`, previously documented, stride `0x60`):
`hardpoint[2]` → **weapon instance** (per-mount runtime state) →
`weaponInstance+0xac` → **weapon type definition** (shared, read-only
data for all mounts of the same weapon).

| Struct | Offset | Field (tentative) | Confidence |
|---|---|---|---:|
| weapon instance | `+0x24` | reload time | 1 (carried over) |
| weapon instance | `+0x28` (int index `[10]`) | energy/ammo cost per shot | 2 — cross-confirmed: `UpdateWeaponFiring` reads it as `((int*)piVar8[2])[10]`, i.e. exactly `+0x28` |
| weapon instance | `+0xa4` | pointer to an effect-anchor sub-table (count `+0x214`, array `+0x218`, stride `0x7c`, type tag at each entry's offset 0) | 2 |
| weapon instance | `+0xac` | pointer to the shared weapon-type definition | 2 |
| weapon instance | `+0xbc` | cooldown-until-tick (float, set by `FireWeapon`) | 2 |
| weapon type definition | `+0x64` (100 decimal) | sound/visual-variant index source (int, clamped 0-14) | 2 |

Two 15-entry global tables indexed by that variant index:
`DAT_00500ce0` (sound IDs, stride `0xb`=11 — plausibly per
listener-distance/perspective sound variants) and `DAT_00500f64`
(per-type cooldown duration, single value per entry). A special case
exists for variant index `0xb`: a 2-in-5 random roll bumps it to `0xc`
(a visual/audio variant swap, purpose not determined — possibly a
"charged shot" or upgraded-weapon audio variant).

### Open follow-ups

- ~~`FUN_0047bdb0` (the actual projectile-spawn call), `FUN_00499f20`~~ — **resolved next session, see below.**
- Object-class ID `4` = turret is now a reasonable working hypothesis,
  not yet cross-checked against the other known IDs (`0x6d`, `0xa8`,
  `0x44`, `0xd`, `0x1f`) to see if a coherent enum can be assembled.
- Why variant index `0xb` has a 40% chance to become `0xc` — **partially
  answered below**: type `0xb` also gets extra random direction jitter
  in `SpawnProjectile`, consistent with `0xb`/`0xc` being a
  spread-weapon pair (e.g. a "tight" and "wide" spread variant).

## `SpawnProjectile` and `GetOwningShip` (2026-09-08, eighth session)

Resolved `FireWeapon`'s two remaining unknowns: `FUN_0047bdb0` (the
actual per-shot spawn/physics/effects function) and `FUN_00499f20`
(an owner-resolution helper). Between them these reveal several
concrete, previously-unknown weapon-type semantics.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `GetOwningShip` (0x499f20, was `FUN_00499f20`) | 2 | Walks a parent-link chain (`+0xec`, followed until it's `0` i.e. root) from a weapon/mount object up to its ROOT attachment, then returns that root's `+0xa8` field — the pointer to the ship that ultimately owns this weapon/mount/turret, regardless of how deep the mount is attached (turret-on-turret, weapon-on-turret-on-ship, etc.). The returned pointer's own fields (`+4`=owner/player-slot index, `+0x644`, `+0x684`=current-target-like pointer) match ship-object fields already documented — cross-confirms the ship struct rather than introducing a new one. |
| `SpawnProjectile` (0x47bdb0, was `FUN_0047bdb0`) | 2 | The real per-shot spawn function, filling in the projectile-pool slot `FireWeapon` just allocated. Confirmed pieces below. |

### New weapon-type semantics confirmed via `SpawnProjectile`

- **`DAT_00500ce0` is a full projectile-type-definition table, not just sounds.** Its 11-int stride holds at least: `+0`=sound-ish ID (as previously documented), `+4`=lifetime/duration (int, used as the pool slot's expiry-tick delta), `+8`=scale/radius (float, `fVar1`, used throughout for visual size AND a `1/(scale²)` proximity-detection radius factor). Corrects last session's "sound table" label — it's broader than that.
- **Force-feedback weapon rumble**: if the shot is the LOCAL player's own and force feedback is enabled (`DAT_0050e1a4`), triggers a DirectInput effect (`vtable+0x1c`, the `IDirectInputEffect::Start(self, 1, 0)` COM call shape) selected from a per-projectile-type array of pre-created effect handles (`DAT_005ddc58` family, one slot per type 0-10).
- **Instant-hit beam-weapon rendering path**: if a global rendering-feature flag (`DAT_00588730+0x1ac`) is set, creates a separate "beam" visual effect object (`FUN_004c4f30`) with color/alpha/width parameters, and recycles a small 2-slot ring buffer of recent beam effects PER SIDE (player beams vs. enemy beams, `DAT_0056317x`/`DAT_0056316x`) — fading out the oldest beam when a new one is fired. This is a genre-typical "instant hitscan laser" rendering path, distinct from the physical/travel-time projectile the rest of the function sets up — meaning at least some weapon types in this engine are hitscan, not simulated projectiles, though which specific type IDs use this path isn't determined (gated by a global flag, not a per-type check in the code seen so far).
- **Type `0xb` = a spread/shotgun-style weapon**: gets BOTH randomized effect-variant selection (documented last session, in `FireWeapon`) AND randomized shot-direction jitter (±0.06 radians-ish per axis, `FUN_004c2410`) — two independent pieces of evidence now pointing the same direction.
- **Types `0xa`-`0xe` are a coherent "special weapons" cluster**, exempted from the difficulty-scaled aim-assist system (below): plausibly mines, countermeasures, and spread weapons, as opposed to standard forward-firing guns (types `0`-`9`).
- **Difficulty-scaled aim assist**: if the owning ship's difficulty flag (`+0x674` — the SAME field flagged last session as a "difficulty-scaled reload-time modifier," now confirmed to gate a SECOND difficulty-related behavior too) is set, and the weapon type isn't in the `0xa`-`0xe` special cluster, applies an aim-correction adjustment toward the current target (the ship's `+0x684` field, matching `GetOwningShip`'s return value's own `+0x684`) — a simpler correction for the player's own shots, a target-flag-gated correction for AI shots. A concrete, previously-unknown difficulty-assist mechanic.
- **Types `0xd`/`0xe` get a much larger proximity-detonation radius** (+1200/+3000 added to the base detection-distance check, versus 0 for other types) — **CORRECTED next session (see below): these are capital-ship "Huge Gun" superweapons, not mines** — the larger radius is a bigger hit-detection allowance for a massive shot, not a mine blast radius. Marked down rather than silently dropped, per METHODOLOGY.
- **Proximity/homing reaction system**: scans every active object each spawn, and for anything within the scaled detection radius, either queues a "nearby object" record (a small max-20-entry per-projectile array) if the target isn't yet "active/awake," or immediately calls `FUN_0049bef0` (not decompiled — plausibly "alert this object to an incoming threat," triggering evasive AI) if it already is.

### Open follow-ups

- `FUN_0047d9a0` (projectile transform/velocity init), `FUN_004c4f30`
  (beam-effect object creation), `FUN_0049bef0` (proximity-alert
  reaction, not decompiled).
- The `&DAT_00500cd0+type*0x2c` per-type table (44 bytes/entry,
  referenced but not opened) — likely mesh/visual data for the
  projectile.
- Which specific weapon type IDs actually use the beam-rendering path
  vs. the physical-projectile path — the code gates this on a global
  flag, not a per-type field, so it may be more of a "beam rendering
  enabled at all" toggle than a per-weapon distinction; not confirmed.
- The owning-ship `+0x674` field is now confirmed to gate BOTH a
  reload-time modifier (previous session) AND aim-assist (this
  session) — worth checking whether it's a single "easy mode" flag
  rather than two separate difficulty settings.

## `CreateWeaponProjectileVisual` — the real weapon arsenal (2026-09-08, ninth session)

Decompiled the 3 remaining `SpawnProjectile` dependencies flagged last
session. One of them, `FUN_0047d9a0`, turned out to be a major find: a
per-weapon-type visual mesh builder whose `switch` cases embed the
game's **real weapon catalog** as literal mesh filenames — Confidence 3
for every name (directly read from the string table, not inferred).

| Type ID | Weapon name (from embedded mesh filename) | Notes |
|---:|---|---|
| 0 | LaserCannon | single mesh |
| 1 | PulseCannon | 2 meshes (BMO1/BMO2), random rotational jitter applied |
| 2 | MessonBlaster ("Meson Blaster") | 3-mesh radial cluster |
| 3 | ProtonCannon | single mesh |
| 4 | Gattlinglaser | 3-mesh cluster, 120° radial spacing |
| 5 | TachyonCannon | 2 meshes |
| 6 | Neutronparticle ("Neutron Particle Cannon") | single mesh |
| 7 | Collapsergun | 2 meshes (BMO1/BMO2) |
| 8 | Gattlingplasma | 4-mesh cluster |
| 9 | Vulcanbattery | 4-mesh square arrangement |
| 10 | Novacannon | single mesh, distinct rotation setup |
| 0xb | Turretflak ("Turret Flak") | matches the spread/shotgun-pattern finding from `SpawnProjectile` exactly — a flak weapon plausibly explains the shot-direction jitter |
| 0xc | TurretLaser | matches the `0xb`→`0xc` variant-swap finding — a turret-mounted laser, the "precision" sibling of the flak gun |
| 0xd | AlliedHugeGun ("Allied_big_gun") | capital-ship-scale weapon, faction-specific (Allied) |
| 0xe | AlliedHugeGun mesh + "Coal_big_gun" effect/glow | same base mesh as 0xd but a distinctly LARGER glow/burst effect scale (`0x45ea6000`≈7500 vs `0x459c4000`≈5000) — reads as the Coalition-faction equivalent of the same superweapon class, not a literally different mesh |
| default | gundefault | fallback mesh for unrecognized types |

**This directly corrects last session's guess** that types `0xd`/`0xe`
were proximity mines: they're capital-ship "Huge Gun" superweapons,
Allied and Coalition faction variants respectively — matching Star
Lancer's known two-faction setting (Alliance vs. Coalition). The larger
detonation-radius bonus documented last session now reads as a
bigger hit-detection allowance for a massive shot, not a mine blast
radius. Marked down rather than silently dropped, per METHODOLOGY.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `CreateWeaponProjectileVisual` (0x47d9a0, was `FUN_0047d9a0`) | 3 | The weapon-catalog function documented above. Takes a pointer to a weapon/projectile struct (`param_1[0]`=type ID, matching the type switch used throughout this whole subsystem) and a mode flag (`param_2`, 0/1, gates a "hero"/"friendly" color-tint pair — `local_40`/`local_44` — applied to some meshes' vertex-color-like fields). Stores created mesh handles back into the struct at several offsets (`+0x3c`, `+0x40`, `+0x44`, `+0x48`, `+0x5c`). For the huge-gun cases (`0xd`/`0xe`), also creates a `CreateEffectObject` glow effect and a second object via `FUN_0049c600` (not decompiled) — visibly richer VFX rigging for the two "hero" superweapons than any other type. |
| `CreateEffectObject` (0x4c4f30, was `FUN_004c4f30`) | 3 | A small (220-byte, `SR_MEM_allocate`-tagged `surrenderlib\...` line `0x2b5`), generic renderable-effect-object constructor: takes a type/owner tag plus a position triple and orientation triple, sets a default scale/alpha field (`+0x48=1.0`). Genuinely generic — used for the huge-gun glow effect here and the earlier-documented beam-weapon visual in `SpawnProjectile`. |
| `PropagateAlertToChildren` (0x49bef0, was `FUN_0049bef0`) | 1 | Simpler than expected: tests a predicate (`FUN_0049bd30`, not decompiled) on `param_2`, and if true, recurses into `param_1`'s child-object list (the SAME `+0xf8`/`+0x100` fields documented twice already — third independent confirmation) calling itself on each child not flagged `0xa0`. Contains NO other logic — the real "alert/react" behavior, if any, must live inside `FUN_0049bd30` itself, which is unopened. This function is purely a hierarchy-propagation wrapper. |

### Open follow-ups

- `FUN_0049bd30` — the actual predicate/reaction logic `PropagateAlertToChildren` wraps; still completely unknown.
- `FUN_0049c600` — the second special object created for huge-gun weapons.
- Exact meaning of the `param_2` mode flag (0/1) in `CreateWeaponProjectileVisual` — tentatively a friendly/hero color-tint selector.

## SurrenderLib scene-node primitives (2026-09-08, tenth session)

Opened the low-level draw/transform primitives called throughout the
whole weapon-visual investigation. All five are genuinely generic
SurrenderLib engine core (not game-specific), confirmed by the
recurring `SR_MEM_allocate` source-tag pattern (`surrenderlib\...`,
distinct line numbers per allocator call site).

| Name (address) | Confidence | Notes |
|---|---:|---|
| `SetPosition` (0x4c0e60, was `FUN_004c0e60`) | 3 | Trivial 3-float store (`this->x,y,z = params`) — exactly matches the "set position" guess from prior sessions, now confirmed directly. |
| `SetOrientationMatrix` (0x4c2410, was `FUN_004c2410`) | 3 | Builds a full 3×3 rotation matrix (9 floats) from 3 Euler-style angles, via `FUN_004c30e0`/`FUN_004c3100` (cos/sin, not individually confirmed but consistent with the call pattern — each angle gets exactly one of each). Standard yaw/pitch/roll → rotation-matrix construction for a 1999-era 3D engine using matrices rather than quaternions for orientation. |
| `CreateMeshInstance` (0x4c4bd0, was `FUN_004c4bd0`) | 2 | The core "instantiate a renderable mesh" factory. Takes an optional parent/group list (aggregates bounding info from sub-meshes if given), a mesh TEMPLATE pointer (face/vertex/radius fields), a flags word controlling optional per-instance override buffers (bits `0x200000`/`0x400000`, plausibly per-vertex color or UV override arrays), and an owner tag. Computes an exact allocation size depending on which optional buffers are requested — real, general-purpose engine infrastructure, used everywhere a 3D model is instantiated (weapons here, but not weapon-specific). |
| `CreateMultiPartMeshGroup` (0x4c4db0, was `FUN_004c4db0`) | 2 | A related but distinct factory: allocates a variable-sized struct holding N (a count, passed via the elided `ECX` register — NOT the string literal visible at `CreateWeaponProjectileVisual`'s call sites, which is actually the THIRD, stack-passed argument, a display-name tag) 100-byte sub-part records, each defaulted to unit scale. This is almost certainly the real constructor behind the "BMO" naming convention seen in weapon mesh filenames (`PulseCannon_BMO1`, `Collapsergun_bmo1`, etc.) — a multi-part object where each part can be independently transformed (e.g. a dual-barrel gun's two barrels animating separately). "BMO" itself is not spelled out anywhere in the string table found so far — its expansion remains unknown. |
| `CreateGroupNode` (0x4c51c0, was `FUN_004c51c0`) | 2 | A small (180-byte) generic scene-node constructor — position + orientation + owner tag, structurally almost identical to `CreateEffectObject` (220 bytes) but calling a different secondary init (`FUN_004c4190` vs. none) — likely the base "parent/group" node type used to hold multiple child mesh instances together (e.g. a multi-barrel weapon's group root, or a projectile's root transform separate from its visible mesh). |

### Open follow-ups

- `FUN_004c30e0`/`FUN_004c3100` (presumed cos/sin — not confirmed), `FUN_004c1be0`/`FUN_004c0e30` (called twice each in both mesh factories, likely default-initializing 2 sub-blocks — e.g. bounding box and transform), `FUN_004c4190` (`CreateGroupNode`'s extra init step).
- The exact meaning of `CreateMeshInstance`'s `0x200000`/`0x400000` flag bits.
- "BMO" itself — a real, load-bearing naming convention in this engine's asset pipeline, but its expansion (Bind Mesh Object? Bone Model Object? something else?) hasn't turned up in the string table.

## `InvokeEffectAnchorCallback` / `CreateParticleEmitter` (2026-09-08, eleventh session) — and a correction

| Name (address) | Confidence | Notes |
|---|---:|---|
| `CreateParticleEmitter` (0x49c600, was `FUN_0049c600`) | 3 | Real name confirmed directly: `SR_MEM_allocate` tags it `C:\lancer\game\particles.cpp` line `0x100`. Allocates a 252-byte, mostly-zeroed particle-emitter object, stamped with the creation tick (`DAT_005883b0`), default scale fields (`1.0`), and an owner tag. This is the second effect object the huge-gun weapons (`0xd`/`0xe`) attach — confirms those weapons get a genuine particle effect (charge-up glow or muzzle particles) in addition to the `CreateEffectObject` glow light documented last session. |
| `InvokeEffectAnchorCallback` (0x49bd30, was `FUN_0049bd30`) | 2 | **A generic callback-invoking tree walker, not a simple predicate as assumed last session.** Its second parameter is a genuine function pointer (confirmed by the decompiler's own `(*param_2)()` call syntax). Two modes, selected by whether `object+0xa8` is set: if unset, walks the object's effect-anchor sub-table (`+0xa4` → count `+0x20c` / array `+0x210` — a THIRD anchor-table shape seen this investigation, distinct from the `+0x214`/`+0x218` one documented for `SpawnWeaponVisualEffect` two sessions ago, meaning weapon/effect objects carry MULTIPLE independent anchor-point sub-tables, not just one) with a manual worklist stack, invoking the callback on each anchor node and recursing into two child-offset fields (`+0x50`/`+0x54`) when the callback returns nonzero on a non-leaf node (`+0x48==0`); if set, does a single simplified visual/transform pass and invokes the callback once, unconditionally. |

### Correction to `PropagateAlertToChildren` (documented two sessions ago)

That function's second parameter is this SAME kind of callback, not
"an alert source" as previously described — `PropagateAlertToChildren`
recurses through a ship's child-OBJECT hierarchy (`+0xf8`/`+0x100`)
passing the callback down unchanged, while `InvokeEffectAnchorCallback`
(called on each such object, per `SpawnProjectile`'s actual usage)
separately walks that SAME object's own internal effect-ANCHOR tree
invoking the callback there. Put together: `SpawnProjectile`'s
proximity-reaction scan installs a callback and runs it across both
axes — every object in a hierarchy, and every effect-anchor point on
each — rather than "checking a predicate then alerting children" as
the earlier session's more limited view suggested. The callback
function itself (passed at each real call site) has not been
identified, so what actually HAPPENS when it fires is still unknown —
only the traversal shape is now clear. Marked as a correction, not a
silent edit, per METHODOLOGY.

### Open follow-ups

- ~~The actual callback function(s) passed to `InvokeEffectAnchorCallback`/`PropagateAlertToChildren` at real call sites~~ — **found next session, see below: this is projectile hit/damage resolution.**
- The `+0x50`/`+0x54` "child" fields on effect-anchor nodes, and how the `+0xa4`/`+0x20c`/`+0x210` anchor-table shape relates to (or differs from) the `+0xa4`/`+0x214`/`+0x218` shape seen on `SpawnWeaponVisualEffect`'s target — possibly two different sub-object types sharing the `+0xa4` offset by coincidence, possibly a real structural relationship. Not resolved.

## `ProcessProjectileImpact` — hit detection, shield damage, and subsystem destruction (2026-09-08, twelfth session)

Checked `PropagateAlertToChildren`/`InvokeEffectAnchorCallback`'s
actual callers to find the real callback functions. This resolved the
whole "what does the traversal DO" question from last session in one
step — and turned out to be the actual combat-damage-resolution logic,
among the most gameplay-central code found in this entire investigation.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `ProcessProjectileImpact` (0x479b40, was `FUN_00479b40`) | 2 | The real projectile-vs-ship collision/damage function, processing the "nearby object" queue `SpawnProjectile` built (confirmed by matching field layout: a count field and a parallel array, matching pool-slot `+0x64`/`+0x68` from 3 sessions ago). For each queued nearby object: (1) re-derives the SAME type-`0xd`/`0xe` → `+1200`/`+3000` detection-radius bonus found independently in `SpawnProjectile`'s spawn-time scan — direct cross-confirmation from the damage-application side, not just the detection side; (2) solves a quadratic for closest-approach distance along the projectile's travel line, comparing against the target's radius plus the type bonus; (3) on a hit, resolves a shield-facing index (`FUN_00463d30`, not decompiled — "which quadrant did this hit") and applies damage directly to the shield-quadrant floats documented (as a guess) in the ship-object struct 4 sessions ago (`object+0x5f0+facing*4`) — **this promotes the "shield quadrants" interpretation from Confidence 1 to Confidence 2-3**: they are directly read/decremented here as damage-absorption values, and the SAME `_DAT_0051cf34`/`_DAT_0051cf78` globals `UpdateShieldQuadrants` referenced for live player input are used here too, as active "damage currently draining this quadrant" trackers; (4) gives flak/turret-laser weapons (types `0xb`/`0xc`) a **2.5× damage multiplier** specifically against non-player (larger/capital-ship) targets — a concrete anti-capital-ship point-defense role for those two weapon types; (5) calls `ApplyDamage`-shaped function `FUN_00463ee0` with the resolved amount; (6) invokes `InvokeEffectAnchorCallback` a SECOND time, recursively, against the hit ship's own subsystem/component list — resolving the callback mystery: **it's used here to detect whether the hit lands on a specific targetable SUBSYSTEM/COMPONENT of the ship** (an anchor-tree entry), and if so applies independent component-level damage/destruction, plays type-specific explosion effects (bigger for `0xd`/`0xe` huge guns), and triggers a distinct sound (`FUN_0049d360`, the same sound-trigger function documented in `FireWeapon` 4 sessions ago). This is genuine **subsystem/component-level ship damage** — individual turrets, engines, or other ship parts can apparently be independently targeted and destroyed, not just a single hit-point pool for the whole ship. |
| `UpdateShieldPowerAndComponents` (0x465380, was `FUN_00465380`) | 1 | A second `PropagateAlertToChildren` caller — appears to handle PLAYER-INITIATED shield power redistribution (decrementing `_DAT_0051cf34`/`_DAT_0051cf78` on player input, matching classic "redistribute shield power between quadrants" space-sim controls) combined with a named-component lookup (a literal string `"Ulysses Fin"` — very likely an in-game capital ship class name, "Ulysses," with a targetable "Fin" subsystem — consistent with the subsystem-damage system above). Not decoded in full detail — dense, entangled with several other systems (turret-target validation, `DAT_005883f8` combat-state flag). |
| `HandleComponentDestroyedEvent` (0x495ac0, was `FUN_00495ac0`) | 1 | A third, much smaller `PropagateAlertToChildren` caller — checks a component-state code (skips for codes `2`/`7`), then triggers an effect (`FUN_004645c0`, seen in multiple places this session as an effect/sound dispatcher taking an ID + owner + code) — plausibly fired specifically when a targeted subsystem/component is destroyed. Not decoded in full detail. |

### Open follow-ups

- `FUN_00463d30` ("which shield facing was hit" — resolves an index 0-3), `FUN_00463ee0` ("ApplyDamage"-shaped), `FUN_004645c0` (effect/sound dispatcher, called from at least 3 different functions this session with an ID+owner+code signature).
- "Ulysses" as a probable in-universe capital ship class name — worth checking the string table for siblings (other ship class names) if ship/fleet naming becomes a focus.
- The full component/subsystem damage model — only the existence and rough shape (per-component hit test, independent destruction, distinct effects) is confirmed; the component list's own structure isn't decoded.
- `UpdateShieldPowerAndComponents`/`HandleComponentDestroyedEvent` deserve a full pass if the shield/subsystem-damage system becomes a focus — both still Confidence 1, only skimmed this session.

## WinMain state-machine cluster (first dive, 2026-09-08)

| Name (address) | Confidence | Notes |
|---|---:|---|
| `RunMenuScreenLoop` (0x4289d0, was `FUN_004289d0`) | 2 | Top-level menu-system dispatcher: takes a starting screen ID (`DAT_0051dac4`), loops calling one of 12 screen-handler functions selected by a `switch` (IDs 0,1,3,7,8,10,11,12,13,14,15,16,0x11,0x12), continuing while the handler returns 0. Screen IDs 10/11 and 0x11/0x12 each toggle a shared flag (`DAT_0051d54c`) 1/0 before calling the SAME handler function for both IDs in each pair — strongly suggests each pair is a "save" vs "load" variant of one screen (e.g. save-game vs load-game, or save-pilot vs load-pilot). None of the 12 handler functions (`FUN_00428b60`, `FUN_0042a620`, `FUN_0042dab0`, `FUN_00437010`, `FUN_0043ca30`, `FUN_0043ca50`, `FUN_00430490`, `FUN_00431730`, `FUN_00432fc0`, `FUN_0042e9b0`, `FUN_0042b690`, `FUN_0044b950`) have been decompiled yet — this entry documents the DISPATCH shape only, not what any individual screen does. |
| `RunShipInteriorVRLoop` (0x439fb0, was `FUN_00439fb0`) | 3 | **Major find**: this is the carrier-interior FMV/hotspot-navigation system — the "walk around your ship between missions watching full-motion video" gameplay Star Lancer is known for. Source-tagged `C:\lancer\game\interface.cpp`. Room data model now CONFIRMED by direct memory inspection (see `VRRoomNode` struct entry below), promoted from Confidence 2 (code-usage inference only) to 3 (struct verified against 4 independent real instances with different branch counts). Clicking a hotspot loads and plays the next room's Bink movie. Confirmed by embedded strings: `"VR: %s"` (format for the movie path), `"VR movie resource: error searching/loading %s"`, and a literal comparison against `"rel_bunkroom2briefing_door.bik"` (a real room-transition movie name) to decide whether to play a door-open sound via the Miles Sound System (`_AIL_*` calls). "VR" here is the internal codename for this feature — not confirmed whether it stood for "Video Room" or something else, the string table doesn't spell it out. Room-type code semantics (0/1/2/3/4/5/6/7/9) are still NOT decoded. |
| `VRRoomNode` struct (44 bytes, created in Ghidra this session) | 3 | The room-graph node record used throughout `RunShipInteriorVRLoop` and `RunMissionBriefingScreen`. Verified by directly reading 4 real instances from memory (`0x50b2b8` numTargets=3, `0x50aef8` numTargets=1, `0x50b288` numTargets=3, `0x50b348` numTargets=4) and checking every field against the values the decompiled code actually reads. Layout: `int16 hotspotX,hotspotY,hotspotW,hotspotH` (+0x0, this node's own clickable rect as seen from a PARENT room — all-zero on root/entry nodes), `char *moviePath` (+0x8), `char *moviePathAlt` (+0xc, nullable — seen both matching `moviePath` and NULL), `int16 unk10` (+0x10, values ranging from ~195 up to 965 observed across ~85 samples read this session — too wide and non-repeating to be a small enum/ID; a per-node duration or frame-count is a plausible guess given the spread, NOT confirmed), `int16 numTargets` (+0x12, 0-4 observed), `VRRoomNode *target[5]` (+0x14..+0x24, a FIXED 5-slot array regardless of `numTargets` — trailing unused slots are NULL; this resolves an in-session confusion where a 4-target node initially looked like it overflowed a suspected 3-slot array), `int16 roomType` (+0x28), `int16 soundFlag` (+0x2a, `-1` in every sample seen so far). Applied as a real Ghidra struct type at all 15 known root-node addresses (see `RunShipInteriorVRLoop`'s 12 campaign-pair roots plus the 3 child nodes read directly this session). `unk10` and `roomType`'s value meanings remain open. |
| `RunMissionBriefingScreen` (0x437010, was `FUN_00437010`, `RunMenuScreenLoop` screen ID 7) | 3 | The mission-briefing screen: plays a per-mission briefing movie selected by `DAT_00562dc8` (current mission index) indexing a local array of filename pointers built from literal strings `"new_m01.bik"`...`"new_m28.bik"` (embedded, format `"%s.bik"` via `SafeFormatString`) — a THIRD independent confirmation of `DAT_00562dc8` = mission index. Internal name confirmed via its own error strings: `"InterfaceBriefing resource: error searching/loading %s"`. Also plays a speech/subtitle track (`"ms_speech_enrbr_tag_%02d_ut"` format — "enrbr" = enroute briefing) in parallel with the movie. Mission `0x1d` (29) gets a special-cased alternate path throughout (also seen in `WinMain` and `RunMenuScreenLoop`'s dispatch). On completion, hands off directly into the VR room system: sets `DAT_0051d478` to `&DAT_0050b2b8` (or `&DAT_00506ad0` if `DAT_00562dc8 < 0x13`) — this is the FIRST direct, concrete evidence connecting `RunMenuScreenLoop`/`RunMissionBriefingScreen` to `RunShipInteriorVRLoop`'s entry point, resolving what was an open "caller not yet traced" gap. Also calls `EnsureCorrectCDMounted` directly, confirming that function's real-world call site. |
| Ship-interior room GRAPH — COMPLETE walk (2026-09-08) | 3 | Walked the graph outward from all 6 hub pairs to full closure — every `target` pointer discovered resolves to an already-visited node, with no new leaves remaining after the final batch. Total: ~120 distinct `VRRoomNode` addresses in the late-campaign graph, ~24 in the early-campaign graph, all read directly from memory via `read_memory` (no scripting — `run_script_inline`/`run_ghidra_script` are disabled in this environment, `GHIDRA_MCP_ALLOW_SCRIPTS` not set, so this was ~120 individual manual reads across the session). Confirms three structural facts at Confidence 3 (directly observed, not inferred): **(1) doorway semantics** — every node with `roomType != 0` acts as a hard jump to that type's hub pair, and the door node's OWN `target[5]` array is irrelevant once this fires (often self-referential — pointing at the hub itself — or left entirely NULL despite `numTargets` claiming an entry, e.g. `0x50aa78` has `numTargets=1` but its one target slot is zero). Every `roomType` value seen (1,2,5,6,7,9) now has a confirmed concrete destination: 1→exit to `RunMenuScreenLoop` (no hub pair), 2→`0x50aec8`/`0x506c80`, 5→`0x50b678`/`0x506d10`, 6→`0x50b3a8`/`0x506f20`, 7→`0x50b318`/`0x506e30`, 9→`0x50b168`/`0x506dd0`. **(2) Twin-node redundancy** — the same logical "door" is frequently placed at multiple distinct addresses with identical target/roomType data (e.g. three separate `roomType=5` "go to pod bay" doors found at `0x50b378`, `0x50b6a8`, `0x50acb8`, all pointing at `0x50b678`) — consistent with several different corridors/rooms each having their own physical doorway into a shared destination, not a data-authoring bug. **(3) The graph is one connected whole, not six separate per-hub trees** — nodes discovered while walking one hub's subtree repeatedly turn out to be nodes already found walking a DIFFERENT hub's subtree (e.g. `0x50af28`, reached from the ITAC/ROT hub `0x50aec8`, points right back to `0x50aef8`/`0x50b288`/`0x50b348` — the entry room's own direct children). This matches "explore your whole ship freely," not a menu tree. |
| Early-vs-late-campaign ship access (structural asymmetry) | 3 | Directly observed, not inferred: for `DAT_00562dc8 < 0x13` (early campaign), the entry hub AND four of the five special-hub pairs (types 2/5/6/9, everything except the briefing room) all share the EXACT SAME 3 target pointers (`0x506b30`, `0x506b60`, `0x506b00`) and the same `moviePathAlt` (`0x507120`) — only each hub's own transition movie differs. `0x506b00` itself is a `roomType=1` node (direct exit to the front-end menu). One level deeper, `0x506b60` shares the identical 4-target set as the early briefing hub `0x506e30` itself. Net effect: the entire early-campaign "explorable ship" is a tiny ~7-8 node loop, functionally just "briefing room ⇄ a corridor with an exit door," while the late-campaign graph (Confidence 2-3 above) is a rich, multi-room, cross-linked structure. This is a clear, deliberate progression gate, not a coincidence of shared data. |
| Ship-interior room map (roomType → hub) | 1-2 | Cross-referencing `RunShipInteriorVRLoop`'s per-`roomType` branches against the 6 root-node pairs shows a clean 1:1 mapping (`roomType` 1 has no paired hub — it calls back into `RunMenuScreenLoop` directly, i.e. "exit to front-end menu"; types 2/5/6/7/9 each jump to one specific pair of `VRRoomNode` roots). Reading each hub's own `moviePath` string gives a strong naming signal (Confidence 2 for the byte-level fact of which string is where, Confidence 1 for the room-NAME interpretations below, which are abbreviation guesses): type 7 → `0x50b318`/`0x506e30`, movie `"tv2brd.bik"` (`BRD` = Briefing Room, consistent with `RunMissionBriefingScreen`'s own `brd_`-prefixed assets); type 2 → `0x50aec8`/`0x506c80`, movie `"itac2rot.bik"` (`ITAC`/`ROT` rooms, exact meaning unclear — possibly a tactical/intel room and a ready-room); type 5 → `0x50b678`/`0x506d10`, movie `"pod2rot2.bik"` (`POD` = escape-pod bay, plausible for a carrier); type 6 → `0x50b3a8`/`0x506f20`, movie `"lockzomo.bik"` (`LOCK` = locker room, where a pilot would suit up); type 9 → `0x50b168`/`0x506dd0`, movie `"cd_cd2d.bik"` (`CD` = corridor, connecting the named rooms). The entry pair itself (`0x50b2b8` late-campaign / `0x506ad0` early-campaign) has movies `"b2iloop.bik"` (bunkroom idle loop) and `"rel_ladd_bunk.bik"` (a ladder-to-bunkroom transition — a plausible campaign-opening scene of the player descending into their bunk). Overall picture: a hub-and-spoke ship interior — bunkroom, locker room, briefing room, a corridor, an escape-pod bay, and one more room (ITAC/ROT) — matching genre convention for a carrier-based flight sim. Room-name abbreviation guesses are NOT confirmed against any external source (manual, credits, etc.) — flagged accordingly. |
| `EnsureCorrectCDMounted` (0x42fe00, was `FUN_0042fe00`) | 3 | The 2-disc CD-swap-prompt system. Compares the currently-mounted CD number (`FUN_004ac6c0()`) against a required `param_1` (1 or 2); if they differ and the game isn't a full hard-drive install (`DAT_005d62c4==0`, set by `LoadInstallPathsFromRegistry`), loops showing a "please insert disc" state (via `FUN_0043eb30`) until the right disc is detected, then opens `"cd<N>.hog"` (`SafeFormatString` format string confirmed) via `OpenBigFile`/`CloseBigFile`, fatally erroring (`"Can't open HOG resource file: %s"` → `ReportAssertionFailureEx`) if it still can't open. Directly matches the real `cd1.hog`/`cd2.hog` files in the game directory and cross-confirms `DAT_005d62c4`'s "hard-drive install, no CD swapping needed" meaning from `LoadInstallPathsFromRegistry`. Confirmed called from `RunMissionBriefingScreen`. |

## Open follow-ups (not yet started)

- `WinMain`'s post-bootstrap state machine (mission select, loadout, multiplayer zone-check/deathmatch dispatch) — the largest remaining unknown reachable from the program entry point. Still untouched.
- `dmodes.bin`'s second, larger (`0x144c`-byte) record table — likely the real per-adapter/per-mode 3D capability structure; not examined.
- `OpenBigFile`'s directory/TOC entry format — container open/close is understood, individual entries are not.
- `FUN_004bcf70` — deliberately left unnamed/uninvestigated (see its own confidence_db.md entry); a live-debugging candidate per METHODOLOGY if it ever becomes load-bearing.
- `DAT_005e82e4`'s writer (SR_printf's output-redirect callback — who installs it, and when).
- `LoadLanguageStrings`'s trailing version/language-compatibility table scan (`DAT_0050318c`, via `FUN_004daef0`) — mechanism unclear.
- `FUN_00475390` (player-profile creation/save fallback, called from `LoadPlayerProfile` on file-open failure) — not decompiled.
- `FUN_004d05e0` (SR_printf's own formatter — likely the real vsnprintf-family core `SafeFormatString` also wraps) and `FUN_004daef0` — CRT/utility internals referenced but not opened.
- Import table groupings not yet cross-referenced to call sites: DirectInput (`DirectInputCreateEx`), Bink video (`_Bink*`), Miles Sound System (`_AIL_*`). The `SR_MEM_*` allocator and `SR_printf`/assertion diagnostics families are now reasonably well understood (see SurrenderLib section above) but their OWN internals (`FUN_004d05e0`, heap implementation details) are not.
- Registry key name for `LoadInstallPathsFromRegistry` (`HKLM\Software\Microsoft\Microsoft Games\...<subkey>`) — the exact subkey string wasn't extracted from the string table this pass.
- `RunMenuScreenLoop`'s 12 screen-handler functions (`FUN_00428b60`, `FUN_0042a620`, `FUN_0042dab0`, `FUN_00437010`, `FUN_0043ca30`, `FUN_0043ca50`, `FUN_00430490`, `FUN_00431730`, `FUN_00432fc0`, `FUN_0042e9b0`, `FUN_0042b690`, `FUN_0044b950`) — dispatch shape understood, individual screens not opened. High-value next target (this is the whole front-end menu system).
- `RunShipInteriorVRLoop`'s room-type codes (0/1/2/3/4/5/6/7/9 at `VRRoomNode.roomType`) — struct is now decoded, but what each type value actually triggers is not.
- `VRRoomNode.unk10`'s meaning (values 199-211 observed; too narrow a range sampled to guess a purpose yet).
- The full room graphs themselves — only 5 of the 15 known root/near-root nodes have been read from memory and struct-typed (`0x50b2b8`, `0x50aef8`, `0x50b288`, `0x50b348`, `0x506ad0`); the other 10 campaign-pair roots are typed but unread, and the graphs extend further via each node's `target[5]` pointers — a full graph walk/dump would be a good next step (could be scripted via `read_memory` + the now-known struct layout rather than manual decompiling).
- `RunMenuScreenLoop`'s other 11 screen handlers (ID 7 = `RunMissionBriefingScreen` is now done) — `FUN_00428b60`, `FUN_0042a620`, `FUN_0042dab0`, `FUN_0043ca30`, `FUN_0043ca50`, `FUN_00430490`, `FUN_00431730`, `FUN_00432fc0`, `FUN_0042e9b0`, `FUN_0042b690`, `FUN_0044b950`.
- Confirming the ship-interior room names (`ITAC`/`ROT` especially) against something more authoritative than filename-abbreviation guessing — e.g. finding an in-game UI string, a manual/readme reference, or the mission-briefing text that might name these rooms explicitly.
- `FUN_0043c1c0`, `FUN_00437df0`, `FUN_004394d0`, `FUN_00494b50` — the per-frame/per-transition callback functions `RunShipInteriorVRLoop` and `RunMissionBriefingScreen` both install/call repeatedly; likely rendering or input-mode setup, not decompiled.
- `VRRoomNode.unk10`'s real meaning — ranges from ~195 to 965 across the ~145 total nodes now read; a frame-count/duration hypothesis is plausible but unverified.
- `roomType == 3`'s exact behavior — found one real instance (`0x50ad48`) this pass. The dispatch code checks this value separately from the 1/2/5/6/7/9 hub-jump set (in two distinct places: a "replay without changing rooms" branch and a hover/idle-state branch) — mechanism sketched from the earlier full decompile but not re-verified against this concrete instance.
- Movie filenames for the ~145 nodes now catalogued by address/connectivity are mostly NOT individually read as strings — only a handful (the 6 hub roots + a few others) were resolved to actual `.bik` names. Reading the rest would let the abbreviation-based room names be checked against a much larger sample.
