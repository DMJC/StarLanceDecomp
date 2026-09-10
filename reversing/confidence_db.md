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
| 12 | `RunNewGameSetupScreen` (0x430490) | 5 (corrected in Pass 62) | Campaign setup: **pilot gender toggle** (was mislabeled "difficulty toggle" here -- the real 3-tier difficulty picker is a separate modal, `RunDifficultySelectDialog`/was `FUN_00430300`), an inline pilot-name text editor (indexes a per-character-class string table at `DAT_005d5e8c`), routes to the save browser (screen 13) or starts the campaign (`RunDifficultySelectDialog` -> `LoadPlayerProfile`, returns 1 to signal "profile loaded, begin game"). |
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

- ~~`FUN_00463d30`, `FUN_00463ee0`, `FUN_004645c0`~~ — **all three resolved next session, see below.**
- "Ulysses" as a probable in-universe capital ship class name — worth checking the string table for siblings (other ship class names) if ship/fleet naming becomes a focus.
- The full component/subsystem damage model — only the existence and rough shape (per-component hit test, independent destruction, distinct effects) is confirmed; the component list's own structure isn't decoded.
- `UpdateShieldPowerAndComponents`/`HandleComponentDestroyedEvent` deserve a full pass if the shield/subsystem-damage system becomes a focus — both still Confidence 1, only skimmed this session.

## `ApplyShieldDamage` / `ApplyComponentDamage` / `GetShieldFacingIndex` (2026-09-08, thirteenth session)

Resolved the 3 remaining follow-up functions from `ProcessProjectileImpact`.
Between `ApplyShieldDamage` and `ApplyComponentDamage`, this reveals the
complete two-stage damage model: shields absorb per-facing damage with
hull spillover, and SEPARATELY, individually-targetable components use
their own grouped-hitbox health pools with armor thresholds.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `GetShieldFacingIndex` (0x463d30, was `FUN_00463d30`) | 1 | A thin wrapper — sets up a transform context from a sub-object pointer (`object+0x30`→`+0x70`, an unidentified turret/hardpoint-position reference) then delegates the actual facing computation to `FUN_00463ca0` (not decompiled). The real "which of the 4 quadrants was hit" logic lives in that unopened call, not here. |
| `ApplyShieldDamage` (0x463ee0, was `FUN_00463ee0`) | 2 | Confirmed as the real damage-application function: `(object, quadrantIndex, damageAmount, damageRatio, attackerSlot, damageTypeCode)`. Early-exits on an invulnerability flag (`object+8 & 0x200000`) or a "special/scripted" class-def state (`+0x28==6`). Computes overflow (`max(0, damage - currentShieldValue)`) for hull spillover, applies a difficulty-scaling pass (`FUN_00463d70`, not decompiled — "AdjustDamageForDifficulty"), triggers scoring/kill-credit (`FUN_00474c80`) and camera-shake/audio feedback (`FUN_00456dd0`/`FUN_00463e10`) when the LOCAL PLAYER is attacker or target respectively, checks multiplayer damage-authority (`FUN_004b5590` — "should this client actually apply this damage") and deathmatch team/friendly-fire rules (`DAT_0050c2f8` FF-enabled flag, per-slot team-ID array `DAT_005dae30`) before committing the shield decrement, spills excess damage to hull via `FUN_004641f0` ("ApplyHullDamage", not decompiled) when the quadrant goes negative, and finally updates several "recently hit" UI-flash flags (`DAT_005635d4`/`DAT_00563160`) and plays an impact sound (`FUN_0045a9e0`). A complete, coherent shield-then-hull damage pipeline. |
| `ApplyComponentDamage` (0x4645c0, was `FUN_004645c0`) | 2 | The real subsystem/component damage function: `(object, componentInstance, damageAmount, attackerSlot, damageTypeCode)`. Validates `attackerSlot` via `ReportAssertionFailureEx` (bounds-checked against the active-object count, or `-1` for "no attacker") — confirms `ReportAssertionFailureEx` is genuinely used as a general-purpose runtime assert throughout the codebase, not just in bootstrap code. Reveals a **grouped-hitbox component model**: components sharing a group ID (`+0xd4`) pool their health across multiple physical hit-collision pieces — the function walks the object's child list to find a group's "representative" member with remaining health (`+0x104>0`) before applying damage to it, meaning one logical subsystem (e.g. "engine cluster") can be modeled as several separate targetable meshes that share one HP pool. Also implements an **armor/threshold system**: components with health above `0x9c3` (2499) are immune to small hits (<500 damage) unless a "penetrating" damage type (3/4) or a specific target flag is set — i.e. some subsystems need a proportionally big hit to scratch. A **shielded-component damage reduction** (0.25× for hits under 1000 when a `0x4000` flag is set) suggests some components have their own point-defense-resistant armor. On destruction (health `<0`), sets a "destroyed" flag bit (`0x40`) and — for the LOCAL PLAYER's own ship, outside deathmatch — triggers a distinct reaction (`FUN_00474e00`). Also triggers wingman/comm chatter (`FUN_00415270`) when a friendly AI's assigned escort-target component is hit. Ends by resolving ANOTHER "representative component" lookup (two variants depending on a `+0x108` grouping field) and playing an impact sound (`FUN_0045a9e0`/`FUN_0045ade0`). |

### Open follow-ups

- ~~`FUN_00463ca0`, `FUN_00463d70`, `FUN_004641f0`, `FUN_004b5590`~~ — **all four resolved immediately next, see below.**
- The component group-ID fields (`+0xd4`, `+0x108`) and the armor-threshold constant (`0x9c3`=2499) — real, load-bearing balance numbers, not yet cross-referenced against any other data source (e.g. a ship-stats file) to see if they're tunable per-ship-class or hardcoded globally.
- `DAT_004f7478` — the assertion message string for the `attackerSlot` bounds check in `ApplyComponentDamage`, not read.

## Difficulty curve, multiplayer authority, hull damage, hit geometry, and ship destruction (2026-09-08, fourteenth session)

Resolved all 4 remaining follow-ups plus one more (`SetShipDestroyedState`,
found by following the hull-damage-depleted path). This is the richest
single round of confirmed gameplay-balance numbers and mechanisms in
the whole investigation, and includes an important **correction** to
several earlier sessions' interpretation of the `+0x684` field.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `ScaleDamageForDifficulty` (0x463d70, was `FUN_00463d70`) | 3 | The exact difficulty curve, read directly (not inferred): deathmatch/PvP damage is NEVER difficulty-scaled (`DAT_00582e8c` check, returns unchanged). Outgoing damage (local player as attacker, hitting a non-teammate): easy=**1.5×**, normal=**1.0×**, hard=**0.75×**. Incoming damage (local player as target) has a baseline **0.5× reduction applied on top of** a further difficulty modifier: easy=0.75×0.5=**0.375×**, normal=1.0×0.5=**0.5×**, hard=1.5×0.5=**0.75×** (the hard-mode branch returns early, skipping the extra 0.5× the other two paths fall through to). A genuinely well-formed, deliberate difficulty curve — not just a flat multiplier. |
| `HasDamageAuthority` (0x4b5590, was `FUN_004b5590`) | 3 | Multiplayer damage-application authority check. For actual player-controlled ships (`slot < DAT_0058832c`, the player count): only the OWNING client has authority (`slot == localPlayerSlot`). For non-player (NPC/AI) objects: in deathmatch, only the HOST applies damage (`DAT_005dc1e8==1`); in co-op/campaign multiplayer, ownership of NPCs is **distributed round-robin across clients** via a modulo scheme (`(objectSlot - perClientBaseOffset[localSlot]) % objectsPerClient == 0`) — each client is authoritative for a distinct subset of NPCs rather than the host simulating everything. A genuinely interesting distributed-simulation architecture choice for a 1999 co-op game. |
| `ApplyHullDamage` (0x4641f0, was `FUN_004641f0`) | 2 | **A third defense tier, distinct from shields.** Near-identical structure to `ApplyShieldDamage` but operates on a SEPARATE float array (`object+0x600 + sectionIndex*4`, vs. shields' `+0x5f0`) — confirms the damage model is Shields → Hull/Armor sections → Components, not just shields-then-components as assumed after the previous session. A ship in "disabled/docked" mode (`+0xb95=='\x04'`) takes zero hull damage (fully absorbed). When a hull section depletes below zero, calls `SetShipDestroyedState` with a "big hit" flag (`damage > 1000.0`) — **this is the ship-destruction trigger**, confirmed by tracing into it (below). |
| `ComputeHitQuadrant` (0x463ca0, was `FUN_00463ca0`) | 3 | The real shield/hull-facing geometry `GetShieldFacingIndex` wraps. Takes a local-space impact point, divides X and Z(or Y) coordinates by the ship's own bounding-box extents on each axis, compares which axis dominates (via an `fabs`-shaped call), and returns a quadrant index 0-3 based on dominant axis + sign — i.e. a real front/back/left/right (or similar 2-axis) facing computation from actual hit-point geometry. Directly confirms the "4 shield quadrants" structural model at the highest confidence yet (3): this is genuine geometric facing detection, not just 4 independently-tracked values. |
| `SetShipDestroyedState` (0x401f30, was `FUN_00401f30`) | 2 | Source-tagged `C:\lancer\game\Ai.cpp` (two allocations, lines `0x5d9`/`0x5da`) — confirms ship AI/behavior state lives in a dedicated `Ai.cpp`. Reveals `object+0x684` is a pointer to an **AI command/state structure** (allocated 0x208 bytes on first use), NOT the "current target" reference assumed in earlier sessions — see the correction below. Pushes a command onto this structure: type `0xb` (11) for "destroyed" (skipped if the ship is already in that state), or type `0x6c` (108) under specific NPC conditions (non-player slot, a specific counter `<0x28`, or a "special mode 3" state) — a distinct pre-destruction state, plausibly "critically damaged/bailing out" for NPCs, not confirmed. The passed-in "big hit" bool is stored directly into the queued command's own data. |

### Correction: `object+0x684` is an AI command/state pointer, not a "current target"

Three earlier sessions (`GetOwningShip`, `ProcessMissionSimulationTick`,
`SpawnProjectile`'s aim-assist logic) described `+0x684` as pointing to
something read as "the ship's current target." `SetShipDestroyedState`
now shows this field is allocated as a 0x208-byte structure whose FIRST
field is a command-type SHORT (values seen: `0xb`=destroyed, `0x6c`=108,
and separately `100` checked elsewhere) — this is an **AI
command/state queue head**, not a target reference. The earlier
sessions' surrounding structural observations (the field's existence,
its role as something `GetOwningShip` resolves and `ProcessMissionSimulationTick`
polls) remain valid; only the semantic label "current target" is
wrong and should be read as "current AI command/state" instead.
Marked as an explicit correction, not silently edited, per METHODOLOGY.
This also means the "difficulty-scaled aim assist" mechanic documented
for `SpawnProjectile` (checking the target's `+0x684`) was actually
checking the target's current AI STATE (e.g. "is it currently evading")
to modulate aim correction, not looking up a target reference — the
aim-assist MECHANISM itself (that it exists, and is difficulty-gated)
is unaffected by this correction, only the specific "what is being
checked" detail.

### Open follow-ups

- ~~`FUN_0040ca50`~~ — **resolved immediately next, see below: a priority-gated AI state machine.**
- `object+0x600` hull-section array's own size/count (how many sections a ship has — the shield-quadrant array was 4; hull sections aren't confirmed to be the same count).
- Whether `Ai.cpp`'s command-queue system is the same one driving normal (non-destruction) ship behavior — **confirmed below**: `TrySetAiState` is a general priority-gated FSM transition function, not destruction-specific, so yes.

## `TrySetAiState` (2026-09-08, fifteenth session) — a priority-gated AI finite-state-machine

| Name (address) | Confidence | Notes |
|---|---:|---|
| `TrySetAiState` (0x40ca50, was `FUN_0040ca50`) | 3 | The general-purpose AI state-transition function `SetShipDestroyedState` (and presumably every other AI behavior change) calls. Reveals a genuine state-definition table (`PTR_DAT_004e06e0`, indexed `[commandID/100][commandID%100]`, 0x18=24 bytes/entry) with per-state fields: `+8` an OnExit callback (invoked when leaving a state), `+0xc` a flags byte (bit `0x20` = "always allow this transition unconditionally," bypassing the priority check entirely), `+0x10` a display-name string pointer (used directly in debug/assert messages — `"Cannot set ai '%s' on ship '%s'. Still ..."`/`"Cannot clear ai on ship '%s'. Still ..."`), `+0x14` a PRIORITY integer. **Transitions are only allowed if the new state's priority exceeds the current state's** — otherwise the request is rejected and logged via `ReportAssertionFailureEx`. Command `0xb` ("destroyed", from `SetShipDestroyedState`) and `-1` ("clear AI") get special handling, but ordinary commands go through the full priority gate. Early-exits: a ship not yet AI-initialized (`+0x680==0`) or mid-transition (`+0x688!=0`) trivially allows the request; a destroyed/inactive ship (`+8 & 0x10000840`) trivially rejects it. This is a well-designed, general priority-based FSM — confirms `Ai.cpp`'s command system drives ALL ship AI behavior changes, not just destruction. |

### Open follow-ups

- The full contents of the `PTR_DAT_004e06e0` state-definition table — only its per-entry LAYOUT is confirmed, not its actual list of states/priorities/names (would require reading the table's static data directly).
- Whether state priority values are fixed constants or vary per ship class.

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

## Single-player campaign structure (2026-09-08, twenty-fifth session)

First dedicated pass at the campaign layer, building on the mission
load/run/unload chain documented several sessions ago.

### `mission.cpp` — the real subsystem name and API, confirmed

String-table sweep for "Mission" turned up direct source evidence:
`"C:\lancer\game\mission.cpp"`, `"!mission_initialised"`,
`"init_mission: A mission is already initialised"`,
`"destroy_mission: No mission to destroy!"`,
`"process_mission: No mission initialised"`, `"Mission_TriggerCount <
MAX_TRIGGERLIST"`, and `"gMissionBuffer"` (the real name of the buffer
`LoadMissionFile` allocates). Confirms the real API shape:
`init_mission`/`process_mission`/`destroy_mission`, matching
`LoadMissionFile`/`RunMissionGameplay`/`UnloadMission`'s roles
one-to-one, plus a real trigger-list system (`Mission_TriggerCount`,
`MAX_TRIGGERLIST`) not yet located in code.

### Campaign outcome branching, in `InitializeMissionGameplay`

Re-examined the "previous mission result code → next mission-select
code" branch table flagged as unopened when `InitializeMissionGameplay`
was first documented. It's a genuine two-tier campaign narrative
branch:

- Reads a per-player "last mission outcome" code (`DAT_0050c2e8` in
  single-player, or `DAT_00588400 + playerSlot*0x54` — the same
  per-player-record stride seen in multiplayer contexts elsewhere).
- **Codes 0-11**: a `switch` maps most of them through to a shared
  fallback, with only a few (values not individually distinguished
  from the decompile — the switch mostly falls through to one path)
  taking distinct routes.
- **Codes `0xf4`-`0xff`** (244-255 — reads as a small SIGNED byte range,
  -12 to -1, cast to int): a SECOND switch maps each to a distinct
  target value stored in `DAT_005883c0` — `0x10e`, `0x108`, `0x107`,
  `0x106`, `0x10b`, `0x11b`, `0x10f`, `0x11e`, `0x117`, `0x11a`, `0x112`
  — 11 distinct values in the `0x106`-`0x11e` range. `DAT_005883c0` is
  then used to select a resource via `FUN_004a44d0` (not decompiled).
  This reads as a genuine **branching debrief/intro-cutscene selector**:
  how the PREVIOUS mission ended (11 distinct special outcome codes —
  plausibly things like "died," "captured," "objective failed,"
  "retreated," etc., though the exact code-to-meaning mapping isn't
  determined) determines which of 11 different follow-up
  cutscenes/screens plays before the next mission. This is the
  campaign's actual narrative-branching mechanism.
- A completely separate, later switch in the same function (on the
  local player's own SHIP CLASS ID, not mission outcome) sets
  `DAT_00566f8c`/`DAT_00579990` — flags already seen referenced in
  `RunMissionBriefingScreen`/`RunMissionSelectMapScreen` — gating
  whether a specific ship class is eligible for some later behavior
  (plausibly eject-pod/escape-craft eligibility, given the context of
  those two callers).

### A mission-scripting command catalog exists (found, not yet fully mapped)

Following up on two command-description strings noticed during the
string sweep (`"TerminateMission"` → `"End the mission, and drop to
death sequence"`; `"Sets a Mission Objective's status"`), located both
as DATA in a real table via `search_byte_patterns` (`0x4f323c` and
`0x4f3298` respectively) — a fixed-stride record table, each entry
holding a description-string pointer, a handler FUNCTION pointer
(real code addresses, e.g. `0x459bb0`, `0x459bd0`, `0x459c90`), and
further name/parameter string fields in a sparse, mostly-zero-padded
layout (consistent with per-command parameter slots, mostly unused for
simple 0-argument commands like `TerminateMission`). This is very
likely SHARED metadata between `Lancer.exe` and the `SLEdit.exe`
mission editor also present in `gamedata/StarLancer/` — a
scripting-command catalog for the `.dte` mission format's script
opcodes, analogous in spirit to the AI state table and DirectPlay
message catalog found in earlier sessions, but NOT fully read or
mapped this session (only 2-3 entries examined, exact struct layout
not resolved, no xrefs found from executable CODE to
`"TerminateMission"` specifically — meaning the STRING itself might be
editor-only tooltip text not touched by the runtime, even though the
adjacent HANDLER FUNCTION POINTERS presumably are real runtime script
opcodes).

### Known campaign mission numbers (consolidated from this and earlier sessions)

- Normal numbered missions: `mission1.dte` through at least `mission32`
  (`.dte`), sequenced via `DAT_00562dc8`.
- `mission25` (`0x19`): repeatedly special-cased across many earlier
  sessions (`WinMain`, `RunMenuScreenLoop`, `RunMissionBriefingScreen`)
  — always paired with a `DAT_00587cdc` companion flag, suggesting a
  two-part or replayable mission.
- `mission29` (`0x1d`): special-cased with NO speech-tag lookup in
  `RunMissionBriefingScreen` — plausibly an epilogue, cutscene-only,
  or otherwise non-standard "mission."
- `mission251`, `mission311`: two additional specifically-named
  missions outside the normal low-number sequence — likely bonus,
  secret, or otherwise non-linear campaign content.

### Open follow-ups

- The exact meaning of each of the 11 outcome codes (`0xf4`-`0xff`)
  and their 11 corresponding `DAT_005883c0` cutscene/screen values —
  only the existence and count of branches confirmed, not their
  individual narrative meaning.
- `FUN_004a44d0` (resolves `DAT_005883c0`/`DAT_0057e048` into an
  actual resource) — not decompiled.
- The mission-scripting command table's full extent and exact struct
  layout — only 2-3 entries examined.
- The trigger-list system (`Mission_TriggerCount`/`MAX_TRIGGERLIST`)
  referenced in a debug string but not yet located in code — likely
  part of the same scripting subsystem.
- What `mission25`/`mission29`/`mission251`/`mission311` actually
  represent narratively — structural specialness confirmed across many
  sessions, in-universe meaning still unknown.

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

## The AI state catalog, read directly from memory (2026-09-08, sixteenth session)

`PTR_DAT_004e06e0` turned out to be a 3-entry array of pointers to
per-group state tables (`(&PTR_DAT_004e06e0)[stateId/100]` selects
group 0/1/2, matching the `/100`, `%100` indexing seen in `TrySetAiState`),
each entry 24 bytes as previously documented (`+0`/`+4` two callback
slots not read by `TrySetAiState` itself — plausibly OnEnter/OnUpdate
— `+8` OnExit callback, `+0xc` a flags byte, `+0x10` a display-name
string pointer, `+0x14` priority). Read the group-0 and group-1 tables
and their adjacent string pools directly via `read_memory` (Confidence
3 — this is raw data, not inferred).

**Group 0 states (partial, ~20 entries read):** Find Scoop Up, Jump
Out, Jump In, Slow Rotate, Ship Follow Curve, **Toggle Cloak**, Patrol
Route, Formation Regroup, Object Attack, "Ripper grabs target object",
Explode, Find New Target, Escort, Land, Run Away, Fly, Warp Out, Warp
In, Launch Missile, Fly Aimlessly, Do Nothing.

**Group 1 states (partial, ~20 entries read):** "...ght" (truncated,
plausibly "Fight"), "Make capship list left", Disrupted, "Eject
fighter attack", "Ripper attach cargo pod to Mammoth", "Ripper end
drop object", "Dark reign shoot", Dock, Eject Spin, Scoop Up, Fight,
Launch, Torpedo, Avoid Target, Multiplayer Control, Player Control,
"Fly ship backwards", "Immediately set ship to zero velocity and
rotation", "Huuuuuuuuge explosion" (verbatim — developer humor, not a
transcription artifact), "Turns object lights off", "Make ripper drop
what it's c[arrying]".

This confirms and substantially enriches several earlier findings and
open questions at once:

- **`Toggle Cloak` confirms a real stealth/cloaking mechanic** exists
  in the AI state system — corroborates `DAT_00595c64` cloak-related
  checks noticed but not investigated all the way back in the very
  first bootstrap session.
- **"Ripper" is a specific in-universe NPC/ship type** — a cargo-
  grabbing entity ("Ripper grabs target object", "Ripper attach cargo
  pod to Mammoth", "Ripper end drop object", "Make ripper drop what
  it's carrying") that attaches to and steals cargo, plausibly a
  pirate/salvage ship class. "Mammoth" is a second named ship/object
  type (the Ripper's cargo target).
- **"Dark reign shoot" — user's claim independently confirmed in code (Confidence 3), plus more found.** The user identified this as a superweapon-firing state. Located both occurrences precisely via `search_byte_patterns` (byte-exact pointer search, not guessed offsets): group0 entry 33 (state ID 33, string `"Dark Reign shoot"`, capital R) and group1 entry 10 (state ID 110, string `"Dark reign shoot"`, lowercase r). Decompiled their callbacks: `HandleDarkReignAttackState` (state 33's `+4` slot) initializes a target-search structure (`bestDistance = FLT_MAX` sentinel, `0x7f7fffff`), calls an unopened target-scan function, and on success rolls a `rand()`-based selection before calling `FUN_00402660` — a genuine find-target-then-fire sequence, gated by the same `HasDamageAuthority`/deathmatch-team-array checks documented for the shield/hull damage functions. `HandleDarkReignExitState` (state 110's OnExit) simply clears a 16-byte per-object field range (`+0x710..0x71f`) and calls an unopened cleanup function — consistent with post-fire state cleanup. **Also found the objective name this ties to**: a THIRD nearby string, `"Deathmatch Dark Reign target"` (at `0x4e06ec`, immediately adjacent to `PTR_DAT_004e06e0` itself) — confirms "Dark Reign" is specifically a **deathmatch-mode objective/superweapon** players fight over control of, not just a generic superweapon.
- **Multiplayer/Player Control states** confirm the AI system itself
  handles the handoff between AI-controlled and human-controlled
  piloting of a ship — i.e., "Player Control" is just another AI state
  in the same priority-gated FSM, not a separate code path.
- **Capital-ship/mission-scripting states** (Jump In/Out, Warp In/Out,
  Formation Regroup, Escort, Dock, Launch) match the kind of scripted
  large-scale behaviors a capital-ship-and-carrier-based campaign like
  Star Lancer's would need.
- The literal string `"Huuuuuuuuge explosion"` is a genuine piece of
  the shipped binary's data — developer humor preserved verbatim in
  the release build, not a decompilation artifact.

### Open follow-ups

- The exact numeric state ID for each name wasn't individually
  re-verified (the string pool was read as a contiguous block and the
  names listed in memory order, which should match table order, but
  the precise ID↔name pairing wasn't cross-checked entry-by-entry).
- Group 2's table (the third pointer in `PTR_DAT_004e06e0`) — not read
  yet.
- The remaining, un-read portions of groups 0 and 1's tables (each
  region read covered roughly 20 entries; the full catalog is likely
  larger).
- "Mammoth" and "Ripper" as confirmed in-universe names — worth a
  broader string-table sweep if ship/enemy taxonomy becomes a focus.

## Exact state-ID confirmations, Dark Reign verification, and Group 2 (2026-09-08, seventeenth session)

Followed up on the user's "Dark Reign shoot = superweapon firing"
claim by locating the exact table entries via `search_byte_patterns`
(searching for the literal 4-byte pointer value, not estimating offsets
by hand — avoids the manual-parsing errors flagged as a risk last
session) and decompiling their callbacks.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `HandleDarkReignAttackState` (0x40bad0, was `FUN_0040bad0`, group0 state 33's `+4` callback slot) | 2 | Confirms the user's claim directly: initializes a target-search context (`bestDistance` seeded to `FLT_MAX`/`0x7f7fffff`, matching a classic "find nearest/best candidate" scan pattern), calls an unopened scan function (`FUN_00401cb0`), and on finding a target rolls a `rand()`-based choice before calling `FUN_00402660` (the actual fire/effect trigger, not decompiled) — gated by `HasDamageAuthority` (multiplayer) and a deathmatch team-array check (`DAT_005db650`, same pattern as `ApplyShieldDamage`/`ApplyComponentDamage`). A genuine target-acquire-then-fire sequence. |
| `HandleDarkReignExitState` (0x40d1e0, was `FUN_0040d1e0`, group1 state 110's OnExit slot) | 2 | Clears a 16-byte per-object field range (`object+0x710`..`+0x71f`) and calls an unopened cleanup function (`FUN_0040e8a0`) — consistent with post-attack state cleanup, not the firing logic itself. |

**The objective name**: a third nearby string, `"Deathmatch Dark Reign
target"` (`0x4e06ec`, positioned immediately adjacent to
`PTR_DAT_004e06e0` itself), confirms "Dark Reign" is specifically a
**deathmatch-mode objective** — likely a capturable/interactive
superweapon on certain deathmatch maps that players fight over control
of, matching the target-acquisition-then-fire mechanic found in its
handler. This is a genre-appropriate design (deathmatch maps with a
neutral superweapon objective are a known FPS/arena-shooter pattern,
here adapted to a space-combat deathmatch mode).

**Exact state-ID confirmations** (via byte-pattern search, not manual
offset arithmetic): state `33` = "Dark Reign shoot" (group 0), state
`110` = "dark reign shoot" (group 1) — two distinct states despite the
near-identical names (capitalization differs), consistent with
attack-state (33) and exit/cleanup-state (110) being separate FSM
nodes for the same overall mechanic. Also re-confirms state `11`
(`0xb`) = "Explode" in group 0, matching `SetShipDestroyedState`'s use
of literal `0xb` for the destroyed transition — the state CATALOG and
the EARLIER-decompiled `SetShipDestroyedState`/`TrySetAiState` code
now cross-verify each other exactly.

**Group 2's table** (`PTR_DAT_004e06e0`'s third pointer, `0x4e06c8`):
turns out to be essentially empty — a single all-zero-except-name
entry whose name field points to `DAT_00515d70`, a global already
identified in an earlier session as a shared "empty string" constant
(used elsewhere as a default value for `GetPrivateProfileStringA`
calls). This reads as an unused/placeholder/reserved state (ID 200),
not a populated third group. No state IDs observed anywhere in this
investigation have fallen in the 200+ range, consistent with group 2
being effectively vestigial in the shipped game.

### Open follow-ups

- ~~`FUN_00401cb0`, `FUN_00402660`~~ — **both resolved next, see below: a target-scan dispatcher and a second, previously-unknown AI subsystem (the perception/event queue).**
- `FUN_0040e8a0` (exit-state cleanup detail) — not decompiled.
- Whether group 2 is truly entirely unused, or has real entries beyond
  the single placeholder read this session (only the first 24 bytes of
  its table were examined).

## `ScanForTargetCandidate` and `QueueAiEvent` — a second AI subsystem (2026-09-08, eighteenth session)

Resolved `HandleDarkReignAttackState`'s two remaining calls. `QueueAiEvent`
in particular turned out to be a significant find: a whole second AI
subsystem — a per-object **perception/event queue** — distinct from
the state-machine (`TrySetAiState`) documented two sessions ago.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `ScanForTargetCandidate` (0x401cb0, was `FUN_00401cb0`) | 2 | A generic, 3-mode target-search dispatcher: `(shipSlot, testCallback)`. Reads a mode selector from the ship's AI command structure (`object+0x684 → +2`). Mode 0: calls the test callback exactly once (immediate/no-search). Mode 1: iterates a MISSION-SCRIPTED candidate list — `DAT_005267cc` (stride `0x14`=20 bytes), one of the 27 mission-directory tables `LoadMissionFile` populates (documented 6 sessions ago) — calling the test callback on each candidate (via a helper, `thunk_FUN_004531c0`, not decompiled) until it returns success or the list is exhausted. Mode 2: delegates entirely to `FUN_00401d80` (not decompiled). Directly connects the AI targeting system to mission-authored data — a real mission file can apparently script a specific candidate-target list for certain AI searches, not just "nearest enemy." |
| `QueueAiEvent` (0x402660, was `FUN_00402660`) | 2 | **A second, previously undocumented AI subsystem**: a per-object perception/event queue, source-tagged `C:\lancer\game\Ai.cpp` line `0x752` (lazily allocates a 720-byte, ~19-slot buffer at `object+0xb90`, count at `object+0xb8c`). Guards against overflow with a real named assertion (`"DPStack Overflow on %s"` — "DP" plausibly "Decision Process," suggesting this queue feeds AI decision-making) via `ReportAssertionFailureEx`. Implements DEDUPLICATION: pushing an event matching an already-queued one (compared by a 4-`short` key) either no-ops if the existing entry hasn't expired yet, or replaces it if it has. Each event carries a payload (~13 shorts), a flags byte, and an expiry timestamp (`DAT_005883b0 + duration`). In multiplayer, authoritative pushes are broadcast to other clients via `FUN_004ba560` (not decompiled). This is a distinct mechanism from the `TrySetAiState` FSM: state = "what is this ship currently doing," event queue = "what has this ship perceived/been told, with a time-to-live" — presumably state transitions are triggered by processing this queue, though that link isn't directly traced. |

### Open follow-ups

- ~~`FUN_00401d80`, `thunk_FUN_004531c0`, `FUN_004ba560`~~ — **all three resolved next, see below.**
- Whether/how the event queue (`QueueAiEvent`) actually drives state transitions (`TrySetAiState`) — the two systems' relationship is inferred from their shared domain (`Ai.cpp`, per-object AI data) but not directly traced through code.
- `DAT_005267cc`'s own record layout (20 bytes/entry, `+9`=count/flag byte observed) — only partially decoded via this one consumer.

## The mission navigation graph, and AI-event network serialization (2026-09-08, nineteenth session)

Resolved `ScanForTargetCandidate` mode 2's delegate plus its own helper,
and the multiplayer broadcast call from `QueueAiEvent`. The first of
these ties together several previously-separate mission-directory
globals (from `LoadMissionFile`'s 27-table `.dte` format, documented 6
sessions ago) into one coherent structure.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `ScanNavigationGraphTarget` (0x401d80, was `FUN_00401d80`) | 2 | **Reveals a mission-scripted navigation/waypoint GRAPH**, not just flat candidate lists. Walks nodes (12-byte stride) starting from an index resolved via `DAT_005294fc`, bounded by `DAT_00529520` (a count) against a base `DAT_00529500` — all three previously catalogued only as "one of `LoadMissionFile`'s 27 directory tables" with no known relationship to each other; this function shows they're parts of ONE graph structure. Each node has a type byte (from a further table, `DAT_005267c0`) selecting behavior: type 0 calls the test callback once (a plain waypoint); type 1 iterates a THIRD table (`DAT_00538c90`, pointer+count-byte-at-`+9` shape, matching `ScanForTargetCandidate` mode 1's pattern exactly) — a node that expands into a sub-list of candidates; type 2 recurses into another graph node (`FUN_00453070` then this function again) — genuine graph traversal, not just a flat list. This is very likely the same navigation-node system backing the `"Patrol Route"`/`"Jump In"`/`"Jump Out"`/`"Formation Regroup"` AI states catalogued last session — a mission author can apparently script a whole waypoint/patrol graph, not just point-to-point destinations. |
| `GetObjectIndexFromPointer` (0x4531c0, was `thunk_FUN_004531c0`, formerly a thunk) | 2 | A small utility: converts a raw pointer/offset into an object-table array INDEX by subtracting a base (`DAT_0052951c`) and dividing by `0x4c`=76 (the per-object record stride) — with sentinel values `0`, `-1`, `0xffff` all normalized to `0xffff` ("no object"). Confirms `DAT_0052951c` is the base of a 76-byte-stride array of mission-instantiated objects (consistent with earlier sessions' scattered references to `DAT_0052951c`-relative offsets). |
| `BroadcastAiEventPacket` (0x4ba560, was `FUN_004ba560`) | 2 | Confirms `QueueAiEvent`'s multiplayer sync is real network packet serialization: begins a packet (`FUN_004b9920(2)`, presumably "packet type 2"), writes 4 fields unconditionally (`FUN_004b9830`, called repeatedly — a per-field network-write primitive, not decompiled), then branches on the event's own type key (`*param_2`): type `0x69` (105) writes 4 MORE fields (a richer payload for that specific event type) before one final write; every other type just writes one final field and returns. Confirms different AI event types carry genuinely different amounts of network-synced data. |

### Open follow-ups

- ~~`FUN_00453070`, `FUN_0045a440`, `FUN_004b9920`, `FUN_004b9830`~~ — **all four resolved next, see below: confirms "DP" = DirectPlay and reveals a genuine bit-packed network serialization layer.**
- What event type `0x69` (105) specifically represents, and why it alone carries extra data.
- The full node-type enum for the navigation graph (only 0/1/2 observed; a `default` fallback exists implying more types may be possible even if unused).

## DirectPlay confirmed, bit-packed networking, and the emergency crash handler (2026-09-08, twentieth session)

| Name (address) | Confidence | Notes |
|---|---:|---|
| `GetNavGraphNodeIndexFromPointer` (0x453070, was `FUN_00453070`) | 2 | Sibling utility to `GetObjectIndexFromPointer`, same shape: converts a raw pointer into a navigation-graph node array index by subtracting `DAT_005294fc` and dividing by `0xc`(12) — the exact node stride confirmed in `ScanNavigationGraphTarget` last session. Cross-confirms `DAT_005294fc` as that array's base a second, independent way. |
| `HandleFatalMissionError` (0x45a440, was `FUN_0045a440`) | 3 | The navigation graph's invalid-node-type fallback is a genuine CRASH HANDLER: formats `"** IT'S A DISASTER! ** Emergency file saved to 'fatal.dte'"` (the exact string found in the very first bootstrap session but never traced to its user), calls `FUN_0045a460` (presumably the actual emergency-state-dump writer, not decompiled) to save an emergency `fatal.dte`, then calls the CRT `exit()` (`FUN_004d04ed`, identified in `mainCRTStartup` in session 1) with code `-1`. A real developer safety net: on unrecoverable mission-data corruption, dump an emergency save file before terminating, rather than crashing uncontrolled. |
| `BeginNetworkMessage` (0x4b9920, was `FUN_004b9920`) | 2 | Selects a per-player message buffer (`DAT_005dcd1c` = buffer pointer, `DAT_005dd528` = bit-offset cursor pointer) from one of TWO parallel buffer sets based on a flags bit (`param_3 & 1`) — plausibly reliable-vs-unreliable channel selection, a standard networking pattern. Another flag bit (`& 2`) overrides the target player with the local player slot. If given a message-type ID, logs it via `DebugLog_Stub(3, "Sending: %s", ...)` looking up a name from a table anchored near `PTR_s_DPMESSAGE_END_0050ca94` — **confirms a real "DPMessage" enum with debug names exists.** |
| `WriteMessageBits` (0x4b9830, was `FUN_004b9830`) | 3 | **A genuine bit-packed network serialization primitive** — not byte-aligned. Writes an arbitrary number of BITS (not bytes) from a source buffer into the current player's message buffer at the current bit-offset, handling both the byte-aligned fast path and the general unaligned case (shifting/merging bits across a byte boundary), masking trailing partial-byte bits via a lookup table (`DAT_0050ca88`), and bounds-checking against a 16KB (`0x4000`) max message size. This is genuine bit-level compression — exactly the kind of bandwidth-conscious serialization a 1999 dial-up-era multiplayer game would need. |

**"DP" = DirectPlay, confirmed.** A second string, `"Bad DPMessage number %d"` (alongside `"DPMESSAGE_END"`), settles the "DP" prefix seen in `QueueAiEvent`'s `"DPStack Overflow"` assertion and this message-table naming: Star Lancer's multiplayer layer is built on **Microsoft DirectPlay**, the standard Windows multiplayer networking API of 1996-2002 — a natural, expected choice for a game of this era, now confirmed directly from the binary's own debug strings rather than assumed. This slightly revises the earlier "DPStack ... 'DP' plausibly Decision Process" guess from two sessions ago: "DP" is DirectPlay-related throughout, though `QueueAiEvent`'s own queue might still be an AI-side structure that merely reuses the "DP" naming convention (a per-object stack of pending DirectPlay messages related to AI events) rather than literally being a decision-process queue — the exact relationship isn't fully pinned down, but the acronym source is now clear.

### Open follow-ups

- ~~The `DPMessage` name table~~ — **read in full next session, see below: the single richest find of the investigation.**
- `FUN_0045a460` (the actual emergency-mission-state-dump writer).
- The two parallel per-player buffer sets in `BeginNetworkMessage` (`DAT_005db674`/`DAT_005db678` vs `DAT_005db67c`/`DAT_005db680`) — reliable/unreliable channel guess not confirmed.
- `DAT_0050ca88`'s trailing-bit-mask table contents (8 bytes expected for a per-bit-count mask table).

## The full DirectPlay message catalog (2026-09-08, twenty-first session)

Read `PTR_s_DPMESSAGE_END_0050ca94`'s pointer array and its entire
backing string pool directly (Confidence 3 — raw string data, not
inferred). ~100 pointers resolve to ~80 real message names before the
`DPMESSAGE_END` sentinel, split into two prefix families: `DPGMESSAGE_*`
("Game" messages — in-mission gameplay sync) and `DPIMESSAGE_*`
("Interface" messages — lobby/matchmaking/session setup). This is
easily the richest single data find of the whole investigation —
essentially a table of contents for the entire multiplayer game,
revealing several mechanics never seen in any prior session.

### `DPGMESSAGE_*` — gameplay sync (~52 entries)

`DROPPICKUP`, `NOVACANNONFIRED`, `PLAYERTARGET`, `PLAYERGONE`,
`PROXMINE`, `RIPPERSYNC`, `FRIENDLYFIRE`, `SCRIPTSYNCRESTART`,
`SCRIPTSYNCREADY`, `LAUNCHMISSILE`, `PLAYEREJECTED`, `CLOAKACTIVE`,
`SPECTRALSHIELDSACTIVE`, `ECMACTIVE`, `HELPMEOUT`, `BACKOFF`,
`ATTACKMYTARGET`, `RESPAWN_PICKUP`, `POWERUP_TRIGGERED`,
`PICKEDUP_OBJECT`, `KILLS`, `HOJ`, `AI_DECISION`, `SYNC_SCRIPT_START`,
`cSCRIPTSYNC`, `TRIGGERNUKE`, `DROPPEDCOMMSRELAY`,
`DEATHSPEWBEACONS`, `KILLEDBYSHADOW`, `SETSHADOW`, `DISEASED`,
`IONCANNONSTATE`, `IONCANNONROTATION`, `TAGBOMBEXPLODES`,
`TAGBOMBOWNER`, `DM_SEND_RESYNC`, `DM_REQUEST_RESYNC`,
`RESYNC_DMSCENARIO`, `SPAWNPOSITION`, `ACT_SPHERE_HIT`, `APP_PAUSE`,
`WARPOUT_REQ`, `JUMPOUT_REQ`, `MISSILEPOSITION`, `SHIELDSTRENGTH`,
`SHIELDHIT`, `SUBOBJSTRENGTH`, `SUBOBJHIT`, `CHAFF`, `CREATEBULLET`,
`POSITION`, `LANDING`.

### `DPIMESSAGE_*` — lobby/session (~28 entries)

`SETINMAINGAME`, `REQINMAINGAME`, `SETTEAMCOLOUR`, `REQTEAMCOLOUR`,
`IAMDEAD`, `KICKOUT`, `AREYOUREADY`, `WHOISHOST`, `SENDPLAYERSHIP`,
`REQPLAYERSHIP`, `SENDMYINDEX`, `NEWHOST`, `SENDLOADOUT`,
`SYNC_START`, `cPing`, `sPing`, `SENDWORLDSTATE`, `REQWORLDSTATE`,
`SENDEXTRAMISSSPEC`, `SENDMISSSPEC`, `REQMISSPEC`, `REQGAMEINDEX`,
`GAMEINDEX`, `UNREADY_TO_START`, `READY_TO_START`, `SETPLAYER`,
`START`.

(Sentinel: `DPMESSAGE_END`. An adjacent, related string: `"DP Unknown
error"`.)

### What this reveals

- **Confirms `SUBOBJHIT`/`SUBOBJSTRENGTH`** as the literal network
  names for the subsystem/component damage model documented several
  sessions ago (`ApplyComponentDamage`) — direct terminology
  confirmation from the game's own protocol naming, not inference.
- **`PROXMINE` is a real, separate mechanic** — genuine proximity
  mines exist as their own message type, independent from the
  "huge gun" weapon types 0xd/0xe (corrected from an earlier session's
  mine guess for those IDs — this is the ACTUAL mine mechanic).
- **New weapon/gadget types found for the first time**: an **Ion
  Cannon** (`IONCANNONSTATE`/`IONCANNONROTATION` — a rotating/aimable
  capital weapon, distinct from the "Huge Gun" superweapons and
  "Dark Reign"), **Tag Bombs** (`TAGBOMBEXPLODES`/`TAGBOMBOWNER` — a
  planted/thrown explosive with an owner-tracking mechanic), and a
  **Nuke** (`TRIGGERNUKE`).
- **A "Spectral Shields" mechanic** (`SPECTRALSHIELDSACTIVE`) distinct
  from the regular directional shield-quadrant system documented
  earlier — plausibly a special ability, pickup, or ship-class
  feature, not yet connected to any other finding.
- **ECM and Chaff confirmed as real, separate countermeasure systems**
  (`ECMACTIVE`, `CHAFF` — the latter also matches the `"chaff exit"`
  debug-log tag noticed in `RunMissionGameplay`'s teardown sequence
  several sessions ago, now with a real network message to match).
- **A "Shadow" mechanic** (`KILLEDBYSHADOW`, `SETSHADOW`) — unclear
  meaning; possibly a stealth/decoy/AI-difficulty feature, or an
  in-universe named threat. Not connected to any other finding yet.
- **Death/loot mechanics**: `DEATHSPEWBEACONS` (ships eject beacons on
  death — plausibly a cargo/salvage or distress-signal mechanic),
  `DROPPEDCOMMSRELAY` (a droppable communications item), `DROPPICKUP`/
  `PICKEDUP_OBJECT`/`RESPAWN_PICKUP`/`POWERUP_TRIGGERED` (a genuine
  pickup/powerup system in multiplayer).
- **`DPGMESSAGE_DISEASED`** — an unusual, unexplained message name;
  could be a status-effect mechanic or, less likely, developer humor
  similar to `"Huuuuuuuuge explosion"` from the AI state table.
- **Deathmatch-specific resync machinery** (`DM_SEND_RESYNC`,
  `DM_REQUEST_RESYNC`, `RESYNC_DMSCENARIO`) — a dedicated
  desync-recovery protocol specific to deathmatch mode.
- **The full lobby protocol** is present: host migration
  (`WHOISHOST`/`NEWHOST`), ready-check (`AREYOUREADY`/
  `READY_TO_START`/`UNREADY_TO_START`), team color assignment
  (`SETTEAMCOLOUR`/`REQTEAMCOLOUR`), world-state and mission-spec sync
  for late joiners (`SENDWORLDSTATE`/`SENDMISSSPEC`/
  `SENDEXTRAMISSSPEC`), and even a custom ping mechanism (`cPing`/
  `sPing`, plausibly client-ping/server-ping).

### Open follow-ups

- Individual handlers for any of these ~80 message types — none
  traced; this session read only the NAME table, not the dispatch/
  handling code.
- "HOJ" (`DPGMESSAGE_HOJ`) — an unexplained 3-letter acronym, meaning
  not determined.
- ~~The "Shadow" mechanic~~ — **resolved next session, see below: a spectator/follow-cam system.**
- "Spectral Shields" — still unconnected to any other finding.
- Whether `DPGMESSAGE_DISEASED` is a real mechanic or developer humor.

## The "Shadow" mechanic resolved: multiplayer spectating (2026-09-08, twenty-second session)

Located `DPGMESSAGE_SETSHADOW` (message ID **50**) and
`DPGMESSAGE_KILLEDBYSHADOW` (message ID **51**) precisely by
byte-pattern-searching for their string pointers within the message
table (found at table slots `0x50cb5c`/`0x50cb60`), then located their
SEND functions by searching for the exact `mov edx, 50`/`mov edx, 51`
immediate-load instructions preceding calls to `BeginNetworkMessage` —
found at `0x4bb030`/`0x4bb060`, which trace back to two handler
functions.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `HandleSetShadowMessage` (0x4b49f0, was `FUN_004b49f0`) | 2 | **This is a multiplayer spectator/"follow-cam" system.** Manages a global "currently-shadowed player" slot (`DAT_005db538`). Takes a new shadow-target slot (`-1` = none). Builds a chat/notification-style message using a 60-byte-per-player name array (`&DAT_005db654 + slot*0x3c`), substituting a `"you"`-style string when the local player is involved instead of their own name (`FUN_00491030`, the same resource-string lookup used throughout the UI). When the LOCAL PLAYER becomes the shadow (spectator), zeroes their own shield-quadrant array (`object+0x5f0`..`+0x600`) — consistent with a spectator having no combat state to track. Updates `DAT_005db538` to the new shadow target and, if requested, broadcasts the change via `SendSetShadowMessage`. |
| `HandleKilledByShadowMessage` (0x4b4b30, was `FUN_004b4b30`) | 1-2 | Sets the target object's `+0x694` field (documented several sessions ago as the "last attacker slot" written by `ApplyShieldDamage`/`ApplyComponentDamage`) to the sentinel value `0xfffffffe` (-2) — a special "not killed by a normal attacker" marker, plausibly meaning "eliminated/ended while in a shadow/spectate-related state" rather than a literal in-combat elimination. Builds a similar name-substituted notification message. The exact triggering circumstance (does this fire when the player BEING shadowed disconnects/dies, ending the spectate session? Or something else?) isn't fully pinned down — Confidence 2 for the mechanism (writes a special sentinel + notification), Confidence 1 for the precise semantic trigger. |
| `SendSetShadowMessage` (0x4bb030) / `SendKilledByShadowMessage` (0x4bb060) | 2 | Thin `BeginNetworkMessage`/`WriteMessageBits` wrappers confirmed via exact message-ID immediate-value search (`mov edx, 50`/`51`) — the network-send side of the above handlers. |

This also explains the `"shadow = %d"` debug string found alongside
the message names: a straightforward debug print of the current
`DAT_005db538` value.

### Open follow-ups

- The exact trigger for `HandleKilledByShadowMessage` — what specific
  game event calls it, and what the `-2` sentinel is checked against
  downstream (e.g. does HUD/scoring code special-case it as "no kill
  credit"?).
- `FUN_00491030`'s own resource-string-lookup mechanism — used
  pervasively across many sessions now (menus, this shadow system,
  etc.) but never itself decompiled.
- Whether "shadowing" is available to any disconnected/eliminated
  player at any time, or gated to specific game modes (deathmatch was
  assumed given `DAT_005db538`'s neighborhood of other deathmatch-
  specific globals, not independently confirmed).

## "Spectral Shields" resolved: a real temporary-invulnerability ability (2026-09-08, twenty-third session)

The user supplied external knowledge (game documentation): Spectral
Shields grants near-temporary invulnerability. Verified directly
against the binary using the same precise tracing method as the
"Shadow" investigation: located `DPGMESSAGE_SPECTRALSHIELDSACTIVE`'s
table slot (`0x50cba0`) via byte-pattern search on its string address,
computed message ID **67** (`0x43`), found the sender via `mov edx,
0x43` (`ba 43 00 00 00`) immediately preceding a `BeginNetworkMessage`
call (`SendSpectralShieldsMessage`, `0x4babc0`), and traced its one
caller to the real toggle function.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `SetSpectralShieldsActive` (0x415430, was `FUN_00415430`) | 3 | **Confirms the user's claim directly.** Gated by an availability flag (`DAT_0057bf20 != -1`, presumably set based on difficulty or whether the ability is unlocked/available this mission — not independently confirmed). Deactivating (`param_1==0`) clears bit `0x8000000` on the LOCAL PLAYER's own ship flags (`object+8`) — the SAME flags dword checked throughout the combat system for state like "destroyed," "docked," etc. Activating sets that exact bit. This is a genuine, dedicated flag bit for a temporary defensive state — consistent with "near invulnerability" as documented. Broadcasts the change over the network (`SendSpectralShieldsMessage`) when in multiplayer, either direction. |
| | | **Also performs a threat-analysis pass on activation**: scans every nearby enemy ship (proximity-radius-gated, team check `+0x644==1`) and tallies which weapon TYPES their hardpoints are using into a 15-slot accumulator (indexed via the same weapon-type-definition `+0x64` field documented many sessions ago in `FireWeapon`), then weights each tally by a per-type "threat" value read from a previously-undocumented field in the SAME 11-int-stride weapon-type table already partly catalogued (`DAT_00500cec` — a sibling of `DAT_00500ce0`/`ce4`/`ce8`), and stores the single most-weighted-threatening weapon type (excluding the two Huge Gun superweapon types, `0xd`/`0xe`) into a NEW ship-object field, `object+0x670`. Purpose of this analysis isn't fully confirmed — plausibly selects a matching visual/audio cue for the shield effect, or feeds into some other reactive system, but the mechanism itself (tally→weight→pick-max) is directly read from the decompiled code, not guessed. |
| `SendSpectralShieldsMessage` (0x4babc0, was `FUN_004babc0`) | 3 | Confirmed network-send counterpart via the exact message-ID immediate-value search described above — not inferred from naming. |

### Open follow-ups (updated below)

- ~~What `object+0x670` is used for downstream~~ — **the network-sync side is now confirmed (see next session below); the actual damage-blocking READ site is still not located.**
- `DAT_0057bf20`'s exact semantics (availability flag vs. cooldown timer vs. something else) — only its `!=-1`/`==0`/`==1` states observed, not a full value range.
- Whether bit `0x8000000` on the ship-flags dword is checked by name anywhere else (e.g. in `ApplyShieldDamage`/`ApplyComponentDamage`'s own invulnerability checks, which so far only documented bit `0x200000`) — worth a targeted re-check of those functions' flag masks now that this specific bit's meaning is known.
- The `"SPECTRAL SHIELDS"` UI-display string (`0x4e37a0`) — found but not traced to its own usage (likely a HUD/pickup-notification label), separate from the message-name string.

## `object+0x670` is network-synced as the blocked weapon type (2026-09-08, twenty-fourth session)

The user supplied a further, specific claim: Spectral Shields blocks
the single most dangerous nearby NON-superweapon (the exact value
`SetSpectralShieldsActive` computes). Searched for other references to
struct offset `0x670` via `search_byte_patterns` on the raw
displacement bytes (`70 06 00 00`) to find where else this field is
touched, beyond the write already documented in
`SetSpectralShieldsActive` itself.

Found a SECOND write site, at `0x4b90f5`, inside a large (~9.5KB)
function spanning `0x4b6f80`-`0x4b9511` — renamed `ProcessNetworkMessage`,
the master incoming-DirectPlay-message dispatcher (the receive-side
counterpart to the ~44 individual `Send*Message` functions documented
across earlier sessions). Disassembled the instructions around
`0x4b90b0` directly (rather than decompiling the whole giant function)
and found, for the `DPGMESSAGE_SPECTRALSHIELDSACTIVE` case specifically:

```
if (receivedValue == 0) {
    targetShip->flags &= ~0x8000000;      // deactivate
} else {
    ReadMessageBits(...);                  // read the extra field
    targetShip->flags |= 0x8000000;        // activate
    targetShip->field_0x670 = receivedValue;  // <-- the blocked weapon type
}
```

This exactly matches `SendSpectralShieldsMessage`'s own send-side
shape (`WriteMessageBits` called unconditionally once, then a SECOND
time only `if (activate != 0)` — the conditional second write is
precisely this weapon-type value, sent only on activation). **This
confirms the "most threatening weapon type" computed locally is
transmitted over the network specifically so other clients know which
weapon type THIS ship's Spectral Shields currently blocks** — strong,
direct architectural support for the user's claim about the ability's
actual defensive behavior, even though the specific code that CHECKS
`object+0x670` during hit resolution (to actually negate/block a
matching incoming shot) was not located this session — only the
computation (`SetSpectralShieldsActive`) and the two-directional
network sync (`SendSpectralShieldsMessage`/`ProcessNetworkMessage`)
were found. Recorded as Confidence 2: the SYNC mechanism is directly
confirmed in code; the actual ENFORCEMENT (the hit-blocking check
itself) remains inferred from context, not yet independently located.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `ProcessNetworkMessage` (0x4b6f80, was `FUN_004b6f80`) | 2 | The master incoming-DirectPlay-message dispatcher — a single large function handling all ~80 cataloged `DPGMESSAGE_*`/`DPIMESSAGE_*` types (receive-side counterpart to the many individual `Send*Message` functions found across several sessions). Only the `DPGMESSAGE_SPECTRALSHIELDSACTIVE` case (`0x4b90b0`-`0x4b9113`) has been examined in detail. |
| `ReadMessageBits` (0x4b6e50, was `FUN_004b6e50`) | 3 | The receive-side counterpart to `WriteMessageBits`, confirmed structurally symmetric: reads an arbitrary bit count from the current incoming-message buffer (`DAT_005dcce8`/`DAT_005dcc9c`), handling byte-aligned and unaligned cases and trailing-bit masking via the same lookup tables (`DAT_0050ca88`, plus a sibling `DAT_0050ca7c` used only on the read side). |

### Open follow-ups

- The actual hit-resolution code that reads `object+0x670` and blocks/negates damage from a matching weapon type — not located. Likely somewhere in or near `FireWeapon`/`ProcessProjectileImpact`/`ApplyShieldDamage`, but a direct search for the `0x670` displacement found only the two WRITE sites (computation + network sync), no read.
- The rest of `ProcessNetworkMessage`'s ~9.5KB body — only the one message case was examined; this function is a rich target for confirming/correcting many other message-name-only findings from the DirectPlay catalog session.
- `DAT_0050ca7c` (the second trailing-bit-mask-adjacent table used only in `ReadMessageBits`, not `WriteMessageBits`).

## Mission-scripting command handlers decompiled (2026-09-08, twenty-sixth session)

Direct follow-up to the previous session's open item: decompiled the
handler function pointers referenced by the mission-scripting command
table, confirming the dispatch-table theory behaviorally.

| Name (address) | Confidence | Notes |
|---|---|---|
| `MissionScript_WaitForKey` (0x459ae0) | 4 | Script-VM wait-opcode handler: `(scriptCursor*, argList*) -> bool done`. Indexes a 0x4e-stride condition table by the arg[0] key index; rewinds the script cursor by 4 bytes to retry if not yet satisfied. Behavior matches the table's own description string for `WaitForKey` ("Stops script until key pressed") exactly. |
| `MissionScript_TerminateMission` (0x459bb0) | 3 | Trivial no-arg handler: increments global `DAT_00588338` and always returns done=1. Table association with the name "TerminateMission" is solid; whether it's *also* responsible for "drop to death sequence" is now doubted (see layout ambiguity below) — that behavior looks like it actually belongs to the neighboring handler. |
| `MissionScript_EndMissionDeathSequence` (0x459bd0) | 3 | Calls `FUN_0045d460(&LAB_00459bf0)`, which resets two globals and calls `FUN_0045d480(label, 0)` — shape strongly consistent with scheduling a jump to a death-sequence label/state. Likely the real handler behind "drop to death sequence" text, but exact command-name association is uncertain pending the table-layout ambiguity below. |
| Mission-scripting command table layout (~0x4f31a8+) | 2 | Confirmed real (name/handler/description/per-arg-metadata), but per-command record is almost certainly NOT fixed-stride — the 116-byte gap seen between 3 sampled entries is likely coincidental (their argument counts happened to size them equally), not a structural constant. **Downgraded from an implicit "fixed stride" assumption in the previous session** — corrected here explicitly rather than silently. |

### Open follow-ups

- Walk further table entries correlating argument count against
  inter-entry byte distance to resolve the true variable-length record
  layout.
- Decompile `FUN_0045d480` to confirm the death-sequence-jump
  hypothesis.
- Decompile the `TurretSetTarget` handler (strings already located) to
  grow the confirmed-handler sample size.
- Characterize `DAT_00588338`.

## TurretSetTarget investigation: table pattern confirmed, one contradiction found (2026-09-08, twenty-seventh session)

Direct follow-up on "continue with TurretSetTarget." Re-derived the
mission-scripting command table's field layout byte-precisely and
decompiled two more handlers.

| Name (address) | Confidence | Notes |
|---|---|---|
| Command-table description-string lag pattern (each slot's desc field describes the *previous* slot's command) | 4 | Confirmed 3-for-3 across WaitForKey/TerminateMission/TurretSetTarget by directly reading and matching string content. Up from 2 (open ambiguity) in the previous session. |
| `MissionScript_SetAnyTriggerState` (0x45d3a0) | 4 | Decompiled: walks a per-entity trigger array at `DAT_005267c0`, finds the Nth trigger of a given type, writes a new enable/disable state, calls `FUN_0045b2d0` to apply. Clean match to its 4 catalogued arguments. Second independent confirmation of the table's `(cursor, argListPtr)` handler calling convention. |
| `MissionScript_0x459bd0_ResetAndScan` (0x459bd0) | 3 (own behavior) / 1 (command association) | Traced its full call chain (`ResetTriggerGlobalsAndResolveTarget` -> `ResolveObjectRangeAndInvokeCallback` -> `InvokeTargetMatchCallback`). Confirmed effect as called from this table slot: resets 2 globals (`DAT_00537418`/`DAT_00537575`), then hits a provable no-op because the range-checked argument it's hardcoded to pass (`&LAB_00459bf0`, a code address) can never match any of the checked data-segment collections, and its callback argument is NULL. ~~Previously named `MissionScript_EndMissionDeathSequence` (Pass 26), implying it schedules a jump to a death-sequence label~~ **-- corrected this session: that interpretation is not supported by the full call-chain trace and has been removed from the function's name.** |
| `ResolveObjectRangeAndInvokeCallback` (0x45d480, was FUN_0045d480) | 3 | Range-checks an object pointer against 3 known live-collection ranges (nav-graph nodes, a trigger table, the previously-documented navigation/waypoint graph), and for a match, iterates candidates invoking a callback via `InvokeTargetMatchCallback`. Distinct from, but closely related to (shares globals with), the already-documented `ScanNavigationGraphTarget` (0x401d80). |
| `InvokeTargetMatchCallback` (0x45d700, was FUN_0045d700) | 4 | Trivial: calls `FUN_0045d720()` then invokes its function-pointer argument directly, `(*param_1)()`. Confirms the callback-function-pointer-as-argument pattern already seen elsewhere in this codebase (`PropagateAlertToChildren`/`InvokeEffectAnchorCallback`). |
| `TurretSetTarget`'s true handler | 0 (unresolved) | The table-slot-implied handler (`0x459bd0`) does not touch the command's own Turret/Entity-to-target arguments and is provably inert as called. Genuinely open -- not guessed at further this session. |

### Open follow-ups

- Locate the actual `.dte` mission-script interpreter/dispatcher that
  reads this table -- no xrefs found to any table row or handler
  address, so the exact field-offset convention can't be independently
  confirmed against real dispatch code, only inferred from 3-for-4
  consistent behavioral matches.
- Reconcile the two different trigger-table access shapes seen
  (`ResolveObjectRangeAndInvokeCallback`'s `DAT_005267c0`-stride-8 range
  check vs. `MissionScript_SetAnyTriggerState`'s
  `DAT_005267c0`-stride-8-then-inner-stride-0x30 walk) into one struct.
- `FUN_0045b2d0`, `FUN_0045d720`, `FUN_0045d8b0`, `FUN_0045d8e0`,
  `FUN_0045d910` -- not decompiled.

## Resource file / BigFile TOC loader (2026-09-08, twenty-eighth session)

Direct investigation of the ".hog"/BigFile archive subsystem. Confirmed
real source files `bigfile.cpp` and `hog_file.cpp`, and the `HOG_`
public-API naming convention.

| Name (address) | Confidence | Notes |
|---|---|---|
| BigFile archive header format (magic 0x42494746="BIGF" @0x00, tocEntryCount @0x04, tocSizeBytes @0x08, 4 bytes unused @0x0c) | 4 | Directly read from `OpenBigFile`'s decompile; magic check is unconditional and fails cleanly. |
| BigFile TOC entry format `{uint32BE fileOffset; uint32BE fileSize; char name[];}`, packed/variable-length | 4 | Derived from `FindBigFileTocEntry`'s exact field-access offsets (name compared at cursor+8; offset/size re-read from cursor+0/+4 on match; non-match advance = 8 + strlen(name) + 1). Internally consistent, no contradictions found. |
| `OpenBigFile` (0x4c7e20) | 4 | Reads header, allocates+rewinds+bulk-reads the TOC (TOC buffer includes a copy of the header at its front, offset by `FindBigFileTocEntry`'s `+0x10` search start). |
| `CloseBigFile` (0x4c7f20) | 3 | Frees TOC buffer, closes file handle, frees the struct -- straightforward, not deeply re-examined this session. |
| `HOG_BigRead` a.k.a. `HOG_bigread` (0x4c7f60) | 4 | Confirmed real name via debug strings. Strips a trailing "ut"-prefixed 2-char extension and leading directory, looks up via `FindBigFileTocEntry`, checks a `0x10fb` compression marker, dispatches to `DecompressBigFileEntry` or a direct read, and falls back to `HOG_file_read` (loose file) on TOC miss. |
| `FindBigFileTocEntry` (0x4c8370, was FUN_004c8370) | 4 | TOC linear-scan-by-name; case-insensitive compare via `FUN_004dae20` (confirmed CRT-style `_stricmp` shape); seeks the archive FILE* to the resolved offset and returns size on match. |
| `DecompressBigFileEntry` (0x4c8480, was FUN_004c8480) | 3 | Reads a 5-byte true-size header after the compression marker, allocates size+0x2800 slack, reads compressed payload into the buffer's tail, calls `FUN_004cc350` (not decompiled) to expand in place, copies to a right-sized final buffer. |
| `HOG_bigsize` (0x4c81f0, was FUN_004c81f0) | 3 | Compression-aware logical-size lookup, mirrors `HOG_BigRead`'s marker check without doing the actual read. |
| `GetBigFileEntrySize` (0x4c5b80, was FUN_004c5b80) | 2 | Thin wrapper around `HOG_bigsize`; exact distinct purpose from calling `HOG_bigsize` directly not determined. |
| `HOG_file_read` (0x4c5be0, was FUN_004c5be0) | 4 | Confirmed real name via debug string + `hog_file.cpp` source path. Loose-file (non-archive) loader: size via `HOG_file_size`, allocate, open+fread+close. |
| `HOG_file_size` (0x4c5b90, was FUN_004c5b90) | 4 | `fseek(END)`+`ftell()`-equivalent size lookup for a loose file. |
| `FileExistsOnDisk` (0x4ad6e0, was FUN_004ad6e0) | 4 | Plain `GetFileAttributesA(path) != INVALID_FILE_ATTRIBUTES`. Used by `LoadResourceFileBuffer` as a mod/dev-override check -- a loose file on disk with the expected name silently pre-empts the packed archive. |
| `ReadLooseResourceFile` (0x45a3e0, was FUN_0045a3e0) | 3 | Loose-file reader used by `LoadResourceFileBuffer`'s override path; calls `HandleFatalMissionError()` on failure under specific caller flags, tying into the mission-loading fatal-error path documented in an earlier pass. |

### Open follow-ups

- `FUN_004cc350` (the actual decompressor) -- not decompiled; likely LZ/RLE given the `0x10fb` marker.
- The stripped `.ut` trailing-extension behavior in `HOG_BigRead` -- purpose unknown.
- The BigFile header's unused 4th 16-byte-header word.
- Whether `HOG_bigsize`/`GetBigFileEntrySize` are called from any currently-documented higher-level resource manager -- not traced.

## BigFile decompressor identified as RefPack; .ut suffix explained (2026-09-08, twenty-ninth session)

| Name (address) | Confidence | Notes |
|---|---|---|
| `DecompressRefPackBlock` (0x4cc350, was FUN_004cc350) = EA "RefPack"/"QFS" LZ77 codec | 4 | Control-byte decode shape (3-tier match-token width, literal counts in low 2 bits, 0xFC-0xFF terminal range) structurally matches the publicly-documented RefPack scheme; the `0x10FB` marker checked before calling it is RefPack's known 2-byte magic. Not verified against a live compressed sample -- pattern-match confidence, not a tested re-implementation. |
| `.ut` = speech/dialogue "utterance" tag file | 3 (abbreviation reading) / 4 (file class) | 383 matching strings, all pilot-chatter/briefing/taunt/pickup-line names; confirmed via `get_xrefs_to` that `"ms_speech\enrbr_tag%02d.ut"` is referenced only from `RunMissionBriefingScreen`, tying directly to the already-documented "speech-tag lookup" mechanism from an earlier pass. |
| `HOG_BigRead`'s extension-stripping rule | 3 | Generic (`strncmp(ext,"ut",2)==0`), not `.ut`-literal-specific; most likely reconciles a hardcoded `.ut` suffix used by callers against bare-basename entries in the BigFile TOC. Plausible, not directly confirmed against real TOC contents. |
| `SR_CCB_load` (0x4cb9d0, was FUN_004cb9d0) | 3 | Confirmed real SurrenderLib name via its own debug strings + source path. Loads `.ccb` files (format/semantics not investigated). Incidental finding while chasing `HOG_BigRead` callers. |

### Open follow-ups

- `.ccb` file format -- not investigated, out of scope for this pass.
- RefPack identification not verified against an actual live compressed sample from the game's data.

## The .ccb loader: a master-palette resource format (2026-09-08, thirtieth session)

Direct follow-up on the incidental `SR_CCB_load` find from Pass 29.

| Name (address) | Confidence | Notes |
|---|---|---|
| `.ccb` = global master-palette resource type | 4 | Only 3 exist in the whole game (`palette.ccb`, `palette3.ccb`, `softpal.ccb` -- "softpal" implying a software-rendering-path palette), unlike per-mission/`.dte` or per-line/`.ut` resources. |
| `CcbResource` struct layout (0x30 bytes: payload ptr, unused, scalarC ptr, blockA ptr [0x300B], blockB ptr [0xc00B], 6 scalars, 1 size scalar) | 4 | Directly derived from `SR_CCB_load`'s field-by-field construction; internally consistent (payload copy length matches the last scalar field exactly). |
| ~~Block A (0x300/768 bytes) = 256-entry raw RGB palette, sourced from the `.ccb` file~~ | ~~4~~ **0, CORRECTED in Pass 61** | **Wrong attribution.** The RGB-triple packing loop's source data (`renderState+0x1602`) is populated by a SEPARATE call, `SR_TGA_allocate_palette("softpal.tga"/"palette.tga")`, not by `SR_CCB_load`'s result (`+0x1606`). The `.ccb` file and the master RGB palette are two independent resources loaded side-by-side from same-named `.ccb`/`.tga` file pairs -- see Pass 61 in `reverse_engineered_functions.md` for the full correction, directly confirmed via the loader's own self-naming assertion strings. |
| Block B (0xc00/3072 bytes) = possible 12-shade-per-color lighting ramp | 2 | Size (256x12) fits a common paletted-rendering shading-ramp technique, but not observed being consumed by either traced caller -- flagged as unconfirmed hypothesis, not a traced finding. |
| `FUN_004cb540` = native-endian (non-swapped) uint32 cursor read | 3 | Same hidden-fastcall-cursor-advance pattern as `ReadSwappedUint32`, but without the byte-swap -- `.ccb` files are native x86 byte order, unlike the BigFile archive's big-endian header/TOC. |
| "CCB" acronym meaning | 0 | No textual confirmation found. Content (global palettes) does not support a "Cel Control Block" (3DO) reading -- explicitly not adopted as a guess. |

### Open follow-ups

- Trace consumers of `CcbResource.blockB` and the 7 scalar fields.
- `FUN_00441aa0`/`FUN_004acbe0` are large graphics-init functions, only their CCB-relevant slices examined.

## Mission trigger-type catalog discovered (2026-09-08, thirty-first session)

Continued mission-scripting investigation. Interpreter/dispatcher still
not located (one large candidate, the HUD renderer at 0x4843a4, was
checked and ruled out), but found the complete trigger-type catalog.

| Name (address) | Confidence | Notes |
|---|---|---|
| `DumpMissionTriggerListOverflow` (0x45b330, was FUN_0045b330) | 4 | Diagnostic dump + fatal assert when live trigger count exceeds 999; confirms `DAT_005373e4` = real `Mission_TriggerCount`. |
| `MAX_TRIGGERLIST` = 1000 | 3 | Inferred from the `999 < count` guard value, not a literal constant read. |
| 32-entry mission trigger-type catalog (TT_SHOTAT, TT_DESTROYED, TT_CLOAKED, TT_DOCKED, TT_GAME_TIMER_EXPIRED, controller-doubletap types, etc.) | 4 | Read directly from `DumpMissionTriggerListOverflow`'s local string-pointer table, indexed by each trigger record's byte 0. Real, complete event vocabulary for the mission-script trigger mechanism -- distinct from the previously-documented AI perception/event queue (`QueueAiEvent`). |
| Trigger record struct: 0x30 (48) bytes, byte 0x00 = trigger type code | 3 | Directly confirmed for byte 0 only; rest of the 48-byte record not mapped. Array base `DAT_0052abe0` here. |
| `DAT_0052abe0` and `DAT_005294e0` (from `MissionScript_SetAnyTriggerState`, Pass 27) may be the same trigger-instance array | 2 | Matching 0x30-byte stride and matching subject matter, but not directly cross-referenced -- circumstantial, not proven. |
| `FUN_004843a4` = HUD per-frame render function (not the script interpreter) | 3 | Ruled out as an interpreter candidate; its `DAT_005799bc` usage draws the on-screen "press key to continue" prompt. Not renamed -- large, mostly unexplored otherwise. |

### Open follow-ups

- Locate the `.dte` script interpreter/dispatcher itself -- still open.
- Map the full 0x30-byte trigger record beyond byte 0.
- Confirm/refute `DAT_0052abe0` == `DAT_005294e0`.
- `FUN_004024e0` (object display-name resolver) -- not decompiled.

## THE MISSION SCRIPT INTERPRETER FOUND: a stack-based bytecode VM (2026-09-08, thirty-second session)

Found by following the trigger-processing data flow from `UpdateMissionFrame` rather than searching from the command-table side.

| Name (address) | Confidence | Notes |
|---|---|---|
| `RunMissionScriptVM` (0x45c980, was FUN_0045c980) = the interpreter's fetch-decode-execute loop | 5 | Unambiguous: fetches an opcode byte from a per-thread cursor, indexes a jump table by raw byte value, calls the handler, loops until a handler signals stop. |
| `DAT_004f6350` = opcode jump table (~84 populated entries) | 5 | Directly read and parsed; immediately followed in memory by the START of the Pass 25-27 named-command metadata table -- the two are adjacent, structurally DISTINCT tables, not the same data read two ways. |
| Stack-based VM execution model (`DAT_00537570` = eval stack pointer) | 5 | Confirmed via 2 fully decompiled opcodes (`MissionVM_OpEquals`/`MissionVM_OpNotEquals`, opcodes 2/3): classic pop-pop-push comparison primitives on a 4-byte-word stack. |
| `ResumeMissionScriptThread` (0x45ba30, was FUN_0045ba30) = cooperative script-thread scheduler | 4 | Restores/saves VM stack pointer + instruction cursor per thread; yields (state saved) vs. finishes (thread torn down, active-count decremented). |
| `PTR_DAT_004f6348` = head of a linked list of active mission-script thread instances (0xB8-byte records) | 4 | Confirmed via `FindMissionScriptThreadSlot`'s list-walk shape (next-pointer at +0xc8, 0x2e-dword/0xB8-byte stride). |
| `ProcessMissionTriggerQueue` (0x45b840) / `DispatchMissionTriggerMatch` (0x45ce70) / `MatchTriggerAgainstWaitingScripts` (0x45cea0) | 4 | Per-frame trigger-consumption pipeline, called from `UpdateMissionFrame`; confirms `DAT_005294e0`+index*0x30 (from `MissionScript_SetAnyTriggerState`, Pass 27) and `DAT_0052abe0` (trigger record array, Pass 31) are traversed together here, up-confirming Pass 31's "possibly the same array" hypothesis to confidence 4. |
| `AddMissionTriggerVariantA`/`B` (0x45b690/0x45b7c0, was FUN_0045b690/FUN_0045b7c0) | 3 | Two similarly-shaped trigger-registration functions (dedup check, then append to the 0x30-byte trigger array); exact distinction between the two variants not determined. |
| Relationship between this stack VM and the Pass 25-27 named-command table | 0 (open) | Two plausible hypotheses (independent condition/action layers vs. one opcode bridges to the other) -- neither confirmed. Leaning toward "independent systems" given WaitForKey's handler uses an entirely different data structure than this VM's stack, but not settled. |

### Open follow-ups

- Decompile more opcode handlers to build a fuller ISA (branches/jumps, arithmetic, the trigger-wait opcode).
- Confirm whether this VM's bytecode is literally what `.dte` files store on disk.
- Resolve the VM-vs-named-command-table relationship.
- Map the full 0xB8-byte script-thread struct.

## VR ship-interior system: closing open questions (2026-09-08, thirty-third session)

Follow-up on the already-complete 145-node graph walk (Passes 4-5); the
12-screen menu system (Pass 6) had no new leads this round.

| Name (address) | Confidence | Notes |
|---|---|---|
| `RunShipInteriorVRLoop` caller = `WinMain` only | 4 | Confirmed via `get_function_callers`; also confirmed `RunShipInteriorVRLoop` itself calls `RunMenuScreenLoop` directly on the roomType==1 exit transition. |
| `roomType` 3/4 = mouse-hover interactive-prop triggers, NOT room transitions | 3 | Both gated on a FIXED screen rect (x:0x43-0x87, y:0x83-0xfb) + held mouse button, independent of the node's own hotspot data; type 3 plays a literal `"move_a.bik"` overlay, type 4 loads a resource via `LoadNamedResource`. Reframes Pass 5's vaguer "replay movie" guess. |
| `pMoviePathAlt` = one-time entry/arrival transition clip (vs. `pMoviePath`'s idle loop) | 2 | Refined from Pass 4's "not determined" -- when set, plays once on arrival and suppresses the roomType 3/4 hover-prop check for that visit. |
| `unk10` (+0x10) unused by `RunShipInteriorVRLoop` | 3 | Confirmed by exhaustive read of the struct-typed decompile -- every other field is exercised, this one is not. Narrows (doesn't resolve) the open question. |
| Hotspot hit-test mechanics (target's own leading 4 int16 = clickable rect vs. tracked mouse pos) | 4 | Up from 3 (structural inference) to 4 (behavior-confirmed) via the actual comparison code. |

### Open follow-ups

- `unk10`'s consumer elsewhere in the binary, if any.
- Whether the roomType 3/4 interactive-prop content varies by room or is a single shared asset.
- Mission-select cheat code's exact key sequence (needs `FUN_004bd570` internals or live debugging).
- `DAT_0051dab4`'s display-mode-dependent Bink playback selection.

## `CheckKeyEdgeState` decoded; the "CTRL+POTATO" cheat code confirmed (2026-09-08, thirty-fourth session)

Direct request: decode `FUN_004bd570`. Setting its function prototype
explicitly made Ghidra reveal hidden `__fastcall` arguments across
EVERY caller project-wide, immediately unlocking `RunMainMenuScreen`'s
previously-opaque input chain.

| Name (address) | Confidence | Notes |
|---|---|---|
| `CheckKeyEdgeState` (0x4bd570, was FUN_004bd570) = edge-triggered key+modifier poll `(keyIndex, modifierMode, pressOrRelease) -> bool` | 5 | Fully mechanical once hidden args exposed. Shares `DAT_00595c68` (raw key state) with `MissionScript_WaitForKey` (Pass 26). |
| modifierMode 0/1/2/3 = none/Shift/Ctrl/Alt | 4 (Shift/Ctrl) / 3 (Alt) | Shift/Ctrl cross-confirmed via Pass 31's HUD `local_160[]` display-string array (`["","SHIFT","CONTROL"]`) using the same index; Alt inferred from parallel structure only, no display-string confirmation seen. |
| Mission-select cheat code = **Ctrl+P-O-T-A-T-O** (scancodes 0x19,0x18,0x14,0x1e,0x14,0x18, each with Ctrl held, in sequence) | 5 | Read directly from `RunMainMenuScreen`'s now-visible `local_c[]` array and matched against standard PC Set-1 scancodes. Resolves the "not recoverable from static analysis" caveat from Pass 6. |
| Post-cheat debug menu (Shift+F1-F12, Ctrl+Enter, Shift+Enter each set a distinct `_DAT_00588400` code 0-11) | 3 | Structure and trigger keys confirmed; the 12 destination codes' actual meanings not traced. |
| Post-cheat digit-entry mission-select (plain '1'-'9'/'0', 2-digit accumulation into `DAT_00562dc8`) | 4 | Mechanically confirmed, matches Pass 6's structural guess exactly. |

### Open follow-ups

- Trace `_DAT_00588400`'s consumer to decode the 12 debug destinations.
- Re-decompile other heavy `CheckKeyEdgeState` callers (VR loop, other menu screens) now that its prototype is set -- likely reveals more hidden key bindings.

## `_DAT_00588400`'s consumer traced: 12 debug codes = 12 real squadron-roster files (2026-09-08, thirty-fifth session)

Direct follow-up on Pass 34's open item. Traced the consumer through
`InitializeMissionGameplay`'s outcome-code switch (Pass 25) into a
newly-identified squadron-roster file loader, `LoadSquadronRoster`.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `LoadSquadronRoster` (0x4a44d0, was FUN_004a44d0) | 4 | Confirmed via own error string + `srofiles.cpp` source tag as a `.sro` squadron/wing roster file parser (600-byte-stride records, sub-tables for wings/hardpoints). NOT a cutscene/debrief resolver as Pass 25 speculatively guessed. |
| The 12 Ctrl+Potato debug codes = direct aliases of 11 of Pass 25's `0xf4`-`0xff` outcome codes + one unique 12th | 4 | Confirmed via shared `goto` case labels in `InitializeMissionGameplay`'s decompile -- not inferred. |
| 12 real roster filenames revealed (`kamg_frm_shp`, `preg_frm_shp`, `nagg_frm_shp`, `gre2_frm_shp`, `cru3_frm_shp`, `coyg_frm_shp`, `mirg_frm_shp`, `temg_frm_shp`, `pat2_frm_shp`, `wolv_frm_shp`, `rea2_frm_shp`, `shr2_frm_shp`, `phe2_frm_shp`) | 4 | Directly read from the decompile after applying `set_function_prototype` to `LoadSquadronRoster` -- the same hidden-argument-exposure technique from Pass 34, reused successfully. |
| Campaign-outcome branching's real effect = loading a different ship/squadron formation roster for the next mission | 2 | Plausible narrative interpretation of the mechanism; not confirmed against `.sro` file contents or in-game observation. |
| **Correction to Pass 25** (not silent): `DAT_0050c2e8` vs `DAT_00588400[slot]`'s single-player/multiplayer assignment was stated backwards | 2 (corrected assignment) / 4 (that the original was wrong) | `DAT_00588400[slot]` is used when `DAT_00582e8c == 0` (no active network session), not the other way around as Pass 25 said. |

### Open follow-ups

- Confirm ship-class-abbreviation readings (`wolv`=Wolverine, `phe2`=Phoenix, etc.) against an authoritative source.
- Map the `.sro` roster format itself -- out of scope for this pass.
- Verify `DAT_00582e8c`'s corrected SP/MP semantics against a live multiplayer session.

## More hidden key bindings revealed via CheckKeyEdgeState's prototype (2026-09-08, thirty-sixth session)

Continuation of Pass 34's flagged follow-up.

| Name (address) | Confidence | Notes |
|---|---:|---|
| Esc (scancode 1) = universal exit, confirmed in both `RunShipInteriorVRLoop` and `UpdateMissionFrame` | 5 | Directly read from decompiles. |
| Space bar (scancode 0x39) = keyboard equivalent of clicking a VR hotspot | 4 | Confirmed via identical boolean condition alongside the tracked mouse-button state. |
| `SaveScreenshotTga` (0x4adc20, was FUN_004adc20), bound to '0' key (scancode 0xb) in `UpdateMissionFrame` | 4 | Confirmed via its own literal `"screenshot_%04d.tga"` format string. |
| `DAT_004e5cd0` = control-descriptor table (stride 0x24, ~51 entries, display names at `DAT_004e5cd4+idx*0x24`) | 3 | Structurally confirmed in `RunControlsOptionsScreen`'s rebind-conflict-detection logic; entries not individually read yet. |
| `DAT_004e2380` confirmed as the live runtime key-binding table (not just a mission-script artifact) | 4 | Directly read/written throughout `RunControlsOptionsScreen`; matches the same global `MissionScript_WaitForKey` (Pass 26) consumes. |

### Open follow-ups

- Read `DAT_004e5cd0`'s ~51 entries to produce a real default-flight-control-scheme table.
- `DAT_004e23cc`'s exact per-control meaning.
- ~40 remaining `CheckKeyEdgeState` callers not yet re-examined.

## .bik loading/playback pipeline decoded; DAT_004e5cd0 corrected (2026-09-08, thirty-seventh session)

| Name (address) | Confidence | Notes |
|---|---:|---|
| `FindBinkMovieInArchive` (0x4c83f0, was FUN_004c83f0) | 4 | Structurally identical to `FindBigFileTocEntry` (Pass 28), operating on the same `OpenBigFile`-returned struct via its raw Win32 `HANDLE` field (+4) instead of the CRT `FILE*` (+0). Resolves why `OpenBigFile` opens the file twice. |
| `DAT_005202d4` = the currently-mounted BigFile archive handle, shared between resource loads and Bink movie streaming | 3 | Written once in `WinMain`, rewritten per disc-swap in `EnsureCorrectCDMounted`; read constantly by VR/briefing screen code. |
| Generic Bink 1.x SDK playback pattern (Open/SetFrameRate/SetSoundSystem/DoFrame/CopyToBuffer/Wait/Goto/Close) | 5 | Public, well-documented third-party library semantics -- not itself a StarLancer-specific finding, just confirmed as the consistent pattern used throughout. |
| `GetLanguageString` (0x491030, was FUN_00491030) | 5 | Confirmed via own `"invalid language string %d"` assert string. Central localized-text accessor, 1-based index into a runtime-loaded string-pointer array (`DAT_0057dbbc`/`DAT_0057dbc0`). |
| **Correction to Pass 36** (not silent): `DAT_004e5cd0` is a table of 89 candidate REBINDABLE SCANCODES (`{scancode, tag}`, 0x24-byte stride), NOT a table of named flight controls with inline display names as previously assumed | 4 | Directly confirmed by raw memory read (scancodes match real A/B/C/D/E key values) + re-decompiled `RunControlsOptionsScreen` with `GetLanguageString`'s prototype set. |
| Real per-control data lives in `DAT_004e2380`'s existing runtime binding table (`DAT_004e23ac`=name string index, `DAT_004e23ae`=device-name string) | 3 | Confirmed via the `GetLanguageString(*(short*)(&DAT_004e23ac+idx*0x4e))` call chain; not yet read out to produce an actual control-name list. |

### Open follow-ups

- Read `DAT_004e2380`'s full range to produce the real control list + default bindings (the corrected version of Pass 36's original goal).
- `FUN_0042c5f0` (rebind-conflict check) -- not decompiled.
- Language string table content is runtime-only, unrecoverable from the static image.

## THE COMPLETE DEFAULT FLIGHT CONTROL SCHEME (2026-09-09, thirty-eighth session)

Direct continuation of Pass 37. Read `DAT_004e2380` in full (74 entries x 78 bytes, exact clean boundary) and created a real Ghidra struct.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `ControlBinding` struct (78 bytes: scancode, modifierMode, debugName[40], langStringIndex, keyLabelText[30], actionSlot) applied as `ControlBinding[74]` at `DAT_004e2380` | 5 | Directly read from the shipped binary's static `.data` image -- not inferred, not runtime-dependent. Table boundary confirmed exactly (74*78=5772 bytes, immediately followed by the unrelated Pass-29 `.ut` string-pointer table). |
| All 74 scancode/modifier/debugName/keyLabelText values (full default keyboard control scheme: cameras, targeting, flight, weapons, ship-systems windows, special abilities incl. Spectral Shields=`;`, wingman commands, menu) | 5 | Literal data, directly read. |
| A genuine shipped developer typo preserved in the binary: "CURSOR DIWN" (entry 31, Nose Up) | 5 | Directly read, verbatim. |
| `actionSlot` field = plausibly a persistent/continuously-polled action index (7 entries have one: Fire Lasers=0, Launch Missile=1, Afterburners=2, Target Nearest Enemy=3, Strafe Right=4, Next Friendly Target=5, Strafe Left=7 -- note 6 is missing) | 2 | Hypothesis based on which controls have a value vs. -1; not traced to a consumer. |
| `langStringIndex` values are real but their localized text is unrecoverable | N/A | `DAT_0057dbbc` (the loaded string table) is runtime-only, confirmed all-zero in the static image (Pass 37). |

### Open follow-ups

- Trace `ControlBinding.actionSlot`'s consumer.
- Localized string text remains unrecoverable without a live session or extracted language resource.

## .fnt/.spr assets identified as WinVFX resource formats (2026-09-09, thirty-ninth session)

| Name (address) | Confidence | Notes |
|---|---:|---|
| `.fnt`/`.spr` are native resource formats of a third external library, WinVFX (`winvfx8.dll`/`winvfx16.dll`) | 5 | Directly confirmed: dynamic `LoadLibraryA` + ~27 `GetProcAddress` calls for real `VFX_*` export names (`VFX_shape_draw`, `VFX_string_draw`, `VFX_character_width`, etc.), read unambiguously from the decompile. |
| `InitializeWinVfxLibrary` (0x4a26d0, was FUN_004a26d0) | 5 | Loads winvfx8.dll (8-bit palette mode) or winvfx16.dll (16-bit true color), resolves the whole VFX_* API table, initializes the shared global palette. |
| `.fnt`/`.spr` binary layouts are NOT parsed anywhere in Lancer.exe -- genuinely external to this project's scope | 5 | Same category of finding as Bink (`.bik`) and Miles Sound System -- a real, well-defined third-party middleware boundary, not a gap requiring further static analysis. |
| The `.ccb` master palette (Pass 30) is shared between SurrenderLib (3D) and WinVFX (2D) | 4 | Confirmed via near-identical RGB-triple-to-native-format conversion code in `InitializeWinVfxLibrary`, using the same source data and bit-shift constants as the earlier-documented SurrenderLib palette loop. |
| `DrawShapeJittered` (0x48c6e0, was FUN_0048c6e0) | 3 | A `VFX_shape_*` consumer implementing a per-scanline random-offset screen-distortion blit, plausibly a damage/hit-shake visual effect; not cross-checked against a specific damage-event caller. |

### Open follow-ups

- `DAT_00588700`/`DAT_00588724` (jitter intensity globals) -- not independently confirmed as damage-flash state.
- `FUN_00480a40` (true-color-mode palette-skip alternative) -- not decompiled.
- `DrawShapeJittered`'s callers -- not traced to confirm the trigger event.

## WINVFX8.DLL present in gamedata: the real .spr/.fnt formats decoded (2026-09-09, fortieth session)

**Correction to Pass 39** (not silent): Pass 39 claimed `winvfx8.dll`/`winvfx16.dll` were "not present in this project" -- wrong. `WINVFX8.DLL` is present at `gamedata/StarLancer/WINVFX8.DLL` and was loaded and decompiled directly this session.

| Name (address, in WINVFX8.DLL) | Confidence | Notes |
|---|---:|---|
| `ShapeSet`/`ShapeRecord`/`shapes[]` layout for `.spr` files (unknown0, shapeCount @+4, then 8-byte {recordOffset,paletteOffset} pairs; ShapeRecord holds a bbox + RLE pixel data) | 4 | Directly read from `VFX_shape_count`/`VFX_shape_list`/`VFX_shape_bounds`/`VFX_shape_draw`, mutually consistent across all four. |
| Row-oriented, back-reference-free RLE pixel encoding (distinct from the RefPack/QFS codec used by the BigFile archive, Pass 29) | 3 | Control flow fully decoded from `VFX_shape_draw`/`VFX_shape_blit_unclipped` (was `FUN_100035fc`); not independently verified against a real `.spr` file's actual bytes. |
| `FontResource`/`GlyphRecord` layout for `.fnt` files (lineHeight @+8, glyphOffset[256] @+0x10, each glyph = {width, raw uncompressed pixel bytes}) | 4 | Directly read from `VFX_font_height`/`VFX_character_width`/`VFX_character_draw`, mutually consistent. |
| `VFX_character_draw`'s two blit modes: direct paletted copy vs. 256-entry remap table (short table w/ 0xfffe transparent sentinel for 16-bit color, byte table w/ 0xff sentinel for 8-bit) | 4 | Directly read; explains the many differently-named/colored `.fnt` files found in Pass 39. |
| `PaletteOverrideRecord` format (entryCount, then {index, r6,g6,b6} entries, 6-bit VGA-precision colors) | 3 | Directly read from `VFX_shape_palette`. |

### Open follow-ups

- `ShapeRecord.headerField0`/`headerField1` -- not decoded.
- `VFX_shape_colors`'s record format -- read but not fully explained.
- Byte-exact verification against a real loaded `.spr`/`.fnt` buffer -- not done.
- `WINVFX16.DLL` -- not examined.

## ShapeRecord.headerField1 resolved as origin point (2026-09-09, forty-first session)

| Name (address, WINVFX8.DLL) | Confidence | Notes |
|---|---:|---|
| `ShapeRecord+0x04` = origin/hotspot point, confirmed via `VFX_shape_origin` | 4 | Directly read; resolves a Pass-40 open item. |
| `VFX_shape_minxy`/`VFX_shape_resolution` confirm existing bbox field positions | 4 | No surprises, cross-confirms Pass 40's layout. |
| Real loose `.fnt`/`.spr` files are RefPack-compressed even outside the BigFile archive | 3 | Confirmed via `gamedata/StarLancer/RESOURCE/FONT.FNT`'s literal header bytes (`10 FB ...`, the Pass-29 RefPack magic). |
| No live Lancer.exe process attached this session | 4 | `read_memory` on runtime-only globals (`DAT_00520134`) reads zero, consistent with static-image-only access throughout this project. |

### Open follow-ups

- A carefully-tested RefPack decompressor to verify `FontResource`/`ShapeSet` against real file bytes -- deliberately not attempted by hand this session to avoid a false verification.
- `ShapeRecord.headerField0` still unresolved.
- `VFX_shape_colors` record format, `WINVFX16.DLL` -- still open.

## RefPack decoder built and verified byte-exact against real assets (2026-09-09, forty-second session)

Direct request. Hand-ported `DecompressRefPackBlock` (Pass 29, `0x4cc350`) to Python and verified against real `gamedata/` files.

| Name | Confidence | Notes |
|---|---:|---|
| RefPack header = 2-byte magic (0x10 0xFB) + 3-byte big-endian decompressed size, opcode stream starts at byte 5 | 5 | Empirically confirmed: only this offset decompresses `FONT.FNT` cleanly to a length matching its own size field exactly (13426 bytes). Corrects Pass 29/41 speculation about extra header-skip bytes. |
| RefPack opcode algorithm (4 back-reference forms + literal-run + end-marker, exact bit-packing per form) | 5 | Byte-exact verified against 2 independent real files (`FONT.FNT`, `YOVB.SPR`). |
| `FontResource`/`GlyphRecord` layout (Pass 40) | 5 (up from 4) | Verified: lineHeight=17, 250/256 glyphs present, character-appropriate widths (space narrower than letters). |
| `ShapeSet`/`ShapeRecord` layout (Pass 40) | 5 for shapes with sane data (up from 4); shape index 0 in the tested file decoded to garbage | Verified against `YOVB.SPR`: shapes 1-4 show a clean, sane multi-frame sprite-sheet pattern. Shape 0's anomaly flagged, not glossed over. |
| `reversing/tools/refpack_decompress.py` saved as a reusable project tool | -- | Standalone, dependency-free Python port. |

### Open follow-ups

- Why `YOVB.SPR` shape index 0 decodes to garbage while 1-4 are clean -- possible special/reserved first entry.
- `ShapeRecord.headerField0`'s semantic meaning still unresolved (now confirmed readable, not confirmed meaningful).
- The "large header" (4-byte size) RefPack variant not exercised by either test file.

## Mission briefing / weapons loadout / debriefing: the full flow (2026-09-09, forty-third session)

Direct research request. Full decompile of `RunMissionBriefingScreen` plus its two direct callees.

| Name (address) | Confidence | Notes |
|---|---:|---|
| `InitializeLoadoutScreen` (0x441aa0, was FUN_00441aa0) | 3 | Confirmed real via `loadout.cpp`/`loadout_load.cpp` source tags; builds fighter/missile/gunship model lists, backdrop, lighting rig. Called directly by `RunMissionBriefingScreen`, not reachable via `RunMenuScreenLoop`. |
| `UpdateLoadoutSelection` (0x443760, was FUN_00443760) | 3 | Confirmed as the per-frame loadout-UI-update loop body (toggles model visibility flags, rebuilds tooltip). Contains a mission-23-specific hidden-object rule. |
| The 5-stage briefing/loadout/debriefing sequence (loadout setup -> video/epilogue -> interactive loadout -> closing speech -> VR hand-off) | 4 | Directly read from `RunMissionBriefingScreen`'s full decompile. |
| Mission 29 (0x1d) = the campaign's final debriefing/epilogue, loading `enddebriefing.ut` instead of a normal briefing video | 4 | Confirmed via a real data xref from `enddebriefing.ut`'s address landing inside the mission-29 special-case block. Resolves the "mission 29 special-cased" observation scattered across Passes 4/6/25. |
| Speech narration (`ms_speech_enrbr_tag_%02d.ut`) plays AFTER loadout confirmation, not before | 3 | Directly read; corrects/refines the implicit ordering assumption from Pass 4. |
| Frame-0x11 animation trigger during closing speech = talking-head/portrait animation cue | 2 | Reasonable inference from established project patterns, not independently verified. |

### Open follow-ups

- `InitializeLoadoutScreen`'s per-mission available-loadout list -- not extracted.
- `UpdateLoadoutSelection`'s input/selection-change handling -- not traced.
- Mission 23's hidden loadout object -- not identified.
- `FUN_00446180` (tooltip/description builder) -- not decompiled; likely path to real weapon/ship names.

## VR ship interior: what happens when a .bik clip finishes (2026-09-09, forty-fourth session)

Direct research request. Decompiled `FUN_0043c1c0` (the per-frame VR-loop callback installed at `DAT_00588730+0x88`, previously only referenced by address).

| Name (address) | Confidence | Notes |
|---|---:|---|
| Ordinary steady-state room videos freeze on their last frame (no auto-loop) | 5 | `_BinkNextFrame_4` simply stops being called once `frame==totalFrames`; completion flag `DAT_00520298` set instead. |
| Special `roomType` (1/2/5/6/7/9) transitions are driven by this completion flag, not a separate timer | 4 | Confirmed via the outer loop's `if (DAT_00520298==0) break;` gate (Pass 33) combined with this session's finding of where the flag gets set. |
| `roomType==3`'s "fish tank" prop cycles through NEW `.bik` clips on completion, not a `.spr` file | 5 | Directly read: 14-entry weighted table resolving to 4 base names (`move_a_`/`move_b_`/`move_c_`/`move_d_`), own error strings confirm `fish_tank_resource`/`tv_in_loop.bik` theming. Real `fish.spr` file exists (Pass 39) but is not what's loaded here. |
| Non-type-3 arrival clips loop back to frame 2 via `_BinkGoto_12`, rather than freezing | 4 | Directly read; opposite behavior from the ordinary steady-state freeze case. |

### Open follow-ups

- Cross-reference the full 145-node VR graph (Pass 5) for other `roomType==3` fish-tank instances.
- Whether `fish.spr` serves as a hotspot cursor/icon for this prop -- not traced.
- Whether the table's uneven 7/3/1/2 weighting toward `move_a_` is deliberate.

## The briefing-hub "news report" TV, and tracing the path to mission briefing (2026-09-09, forty-fifth session)

| Name (address) | Confidence | Notes |
|---|---:|---|
| `RunBriefingHubNewsReport` (0x43ba40, was FUN_0043ba40) | 4 | Confirmed via own `"news_report_resource"` error strings; plays a mission-indexed news broadcast (table of ~27-28 short numeric strings) before the briefing-hub room settles into its own ambient video. |
| Mission 1 gets a distinct 3-state news cycle (idle loop <-> `tv_cald_.bik` calendar interstitial) vs. simple play-once for other missions | 3 | Directly read. |
| `RunShipInteriorVRLoop` never writes `DAT_0051dac4` -- roomType==7 alone does not launch the briefing screen | 4 | Confirmed via exhaustive `get_xrefs_to`. |
| `RunMissionBriefingScreen` is called directly by `WinMain` at two sites (0x4aa027, 0x4aa6f2), not just via `RunMenuScreenLoop` | 4 | Confirmed via `get_xrefs_to`. Exact triggering condition under investigation (forked). |

### Open follow-ups

- WinMain-level trigger investigation (forked, pending).
- Exact mission-number-to-news-clip-string mapping direction.
- Narrative significance of mission 1's distinct news cycle.

## THE MISSING LINK FOUND: roomType 1 leads to mission briefing, not the main menu (2026-09-09, forty-sixth session)

| Name (address) | Confidence | Notes |
|---|---:|---|
| `roomType==1` doors call `RunMenuScreenLoop(7)` (literal argument), i.e. lead to `RunMissionBriefingScreen`, NOT the main menu | 5 | Directly read after exposing the hidden argument via `set_function_prototype` on `RunMenuScreenLoop`. **Corrects Passes 4/5**, which described roomType==1 as "exit to front-end menu" based only on the function name, not its argument. Flagged, not silently fixed. |
| `WinMain`'s two direct `RunMissionBriefingScreen` calls (0x4aa027, 0x4aa6f2) are mission-29-epilogue-only short-circuits | 4 | Confirmed via background investigation: both gated on `DAT_00562dc8==0x1d`, followed by an ending-cutscene call (`FUN_004ac620`) and campaign reset to mission 1. |
| `RunMissionSelectMapScreen` launches gameplay directly (`InitializeMissionGameplay`/`RunMissionGameplay`/`UnloadMission`), does NOT route through briefing | 4 | Full decompile this session; no call to `RunMissionBriefingScreen` or write to `DAT_0051dac4` anywhere in it. |
| The complete closed-loop picture: briefing-hub (roomType 7) <-> briefing screen (roomType 1) <-> star map (roomType 5) -> gameplay | 4 | Synthesized directly from this session's findings plus Passes 4/5/7/33/43/45. |

### Open follow-ups

- Exact disambiguation of `DAT_0051d4b4` values 0 vs. 2 (both exit paths, distinct narrative meaning not confirmed).
- Systematic sweep of other `RunMenuScreenLoop(N)` call sites for further mislabeled transitions.
- `FUN_004ac620` (mission-29 ending cutscene/credits function) -- not decompiled.

## Menu asset position data decoded: the mission-select star map's hotspot table (2026-09-09, forty-seventh session)

| Name | Confidence | Notes |
|---|---:|---|
| `MenuHotspotRect` struct `{x,y,w,h}` (8 bytes, int16 each) | 5 | Byte-exact match against `RunMissionSelectMapScreen`'s own hit-test code. Created as a real Ghidra struct, applied to state 0's array at `0x4ebaf8`. |
| `MapScreenState` record: `{hotspotCount:2, pad:2, rects*:4, ...}`, stride 0x58 (88) bytes | 4 | First 8 bytes confirmed via two independently cross-checked states (0 and 1); tail fields (+0x08 onward) not mapped. |
| State 0 (3 hotspots) / State 1 (5 hotspots) real coordinates | 5 | Directly read from the shipped binary's static image. |
| State 1 = state 0 + a 3rd mission-choice button + a 2nd small button (plausibly mission29 + confirm/cancel) | 2 | Reasonable inference from position/size/count, not independently confirmed. |
| Transition table at `0x4ebb60` (`[state][hotspotIndex] -> nextState`, 22 dwords/state) | 3 | Structurally located and characterized, not mapped entry-by-entry. |

### Open follow-ups

- `MapScreenState`'s fields beyond +0x08.
- Full entry-by-entry mapping of the `0x4ebb60` transition table.
- State 5 (referenced in code, not read).
- The other 11 menu screens' position tables are mostly one-off stack locals, not global struct arrays -- this table was an atypically clean target.

## Hotspot layouts documented for all 12 menu screens (2026-09-09, forty-eighth session)

Combined direct investigation + 4 parallel forks. Key infrastructure finding: `HitTestRectArray` (0x43eb30, was FUN_0043eb30), a shared hit-test utility whose hidden arguments (rectArray pointer + count) were exposed project-wide via `set_function_prototype` (same technique as Passes 34/35/37) -- this is now the standard tool for any further menu/UI position-data archaeology.

| Screen | Confidence | Notes |
|---|---:|---|
| 0 `RunMainMenuScreen` | 4 (coords) / 1 (target mapping) | Inline hit-test, own 12-byte-stride table, 5 entries. Target-field attribution needs a second pass. |
| 1 `RunOptionsMenuScreen` | 5 | 6-entry table, fully read, exact switch destinations. |
| 3 `RunSoundOptionsScreen` | 5 | 10-entry contiguous global table (6 buttons + 4 sliders), fully read and cross-confirmed against ini-key sequence. |
| 8 `RunNetworkDisconnectScreen` | 5 | Confirmed zero hotspots -- non-interactive pass-through. |
| 10/11 `RunSaveLoadScreen` | 4 (actions) / 2 (positions) | Actions confirmed by switch-case; coordinates not cleanly isolated. |
| 12 `RunNewGameSetupScreen` | 4 (10-entry list) / -- (8-entry row not extracted) | Name/callsign-picker list read directly; main button row's raw coordinates not obtained this pass. |
| 13 `RunSaveGameBrowserScreen` | 4 (list rows) / 2 (action buttons) | Clean 10-row, 17px-pitch save-slot list; action-button positions not confidently isolated. |
| 14 `RunMultiplayerSetupScreen` | 5 (actions) / 2 (one partial cluster) | ~30-chained-pointer-alias layout; fork correctly declined to force a full mapping. Confirms Zone.com finding from Pass 6. |
| 15 `RunVideoOptionsScreen` | 5 | Clean 17-entry global array + independently cross-confirmed gamma-slider rect. |
| 16 `RunControlsOptionsScreen` | 5 (raw values) / 3-4 (attribution) | Extends Pass 37; checkboxes + 12-row scrollable key-rebind list, clean pitch values. |
| 0x11/0x12 `RunMultiplayerLobbyScreen` | 5 (roster stride) / 3-4 (button rects) | Player-roster layout confirmed; 8-button descriptor shape clean, underlying rects partially decoded. |

### Open follow-ups

- `RunMainMenuScreen` target-field attribution.
- `RunSaveLoadScreen`/`RunSaveGameBrowserScreen` action-button coordinates.
- `RunNewGameSetupScreen`'s 8-entry main button row coordinates.
- `RunMultiplayerSetupScreen`'s full ~30-alias layout mapping.
- `RunMultiplayerLobbyScreen`'s remaining unattributed rects; button label text blocked on runtime-only string table.

## Pass 49/50 -- `RunNewGameSetupScreen`'s 8-entry button row: investigated, root-caused, not resolved (2026-09-09)

**Correction**: Pass 49's initial claim of entry 0 = `(239,151,102,275)`
at confidence 4 is **retracted** (downgraded to 0 / not asserted). It
was derived from manual ESP-offset bookkeeping across the function's 4
`PUSH` instructions and did not correctly account for cumulative
push/pop effects. A follow-up raw-P-code cross-check (see Pass 50 in
`reverse_engineered_functions.md`) contradicts it directly: no
instruction anywhere in the function's control-flow path writes to the
stack region the manual reading pointed at.

| Name | Confidence | Notes |
|---|---:|---|
| 10-entry name-picker list array, base = canonical stack offset -100 | 5 | Cross-confirmed via P-code `PTRSUB(ESP,-0x64)` matching the literal `0x8a` write and Pass 48's independent read. Unaffected by this correction. |
| 8-entry main-button-row array, base = literal `PTRSUB(ESP,-0xa4)` (-164) as decompiled | 0 | Decompiler-emitted offset has zero corresponding writes anywhere in the function; diagnosed as a probable Ghidra stack-tracking precision failure on this one `PTRSUB`, not a real, reliable frame location. Not usable as-is. |
| `FUN_004aada0` (called at 0x430712) | 5 | Confirmed NOT an array-filler -- two-line function (`DAT_00595d70 = 0; return;`), no arguments. |
| "8-entry and 10-entry tables are one contiguous stack block" hypothesis | 0 | Retracted -- contradicted by the write-search above. |

### Open follow-ups

- `RunNewGameSetupScreen`'s 8-entry button row real coordinates: still unresolved. Needs either dynamic analysis (live memory read) or a much more careful manual re-derivation, independently cross-checked before being trusted.
- Methodological note for future passes: don't trust a `PTRSUB`-derived stack constant on its own -- cross-check it against a second, nearby literal-offset write before relying on it (see Pass 50 writeup).

## Pass 51 -- `RunMainMenuScreen` target-field attribution + `RunSaveLoadScreen`/`RunSaveGameBrowserScreen` action-button coordinates (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| `RunMainMenuScreen` `DAT_004e5b90` target-field semantics | 5 | Not a destination ID -- a loop-continue gate (`target==3` = absorbed by frame loop, else breaks to action switch, which dispatches on hotspot index). |
| `RunMainMenuScreen` index 0/1/2 -> New Game/Multiplayer/Options | 5 | Direct switch on `DAT_0051d544`. |
| `RunMainMenuScreen` index 4 -> mission 0x1d ("watch ending") trigger | 4 | Same `DAT_0057e044`+mission-29 signature as the documented campaign epilogue path; button's exact label not confirmed. |
| `RunMainMenuScreen` index 3 -> inert (target field blocks dispatch) | 3 | Mechanism confirmed; exact UI purpose (hover region? disabled slot?) not resolved. |
| Mission-select cheat code = "POTATO" (scancodes `0x19,0x18,0x14,0x1e,0x14,0x18`) | 5 | Independently re-derived this pass, but **not new** -- already confirmed at confidence 5 in Pass 34 ("CTRL+POTATO"). Used to fix a stale, contradictory "not recoverable" claim left in an earlier (pre-Pass-34) doc entry that was never updated. |
| `RunSaveLoadScreen` 19-record contiguous stack table, load=records[1:6], save=records[6:19] | 5 | Base-pointer arithmetic directly confirmed (40-byte/5-record offset between the two `HitTestRectArray` base args), not inferred. |
| `RunSaveLoadScreen` load-mode (5) and save-mode (13) coordinates | 5 | Directly read, all 18 entries. |
| `RunSaveGameBrowserScreen` 17-record table (10 slots + 4 actions via one window, 2 scroll arrows + 1 confirm-dialog rect via two more) | 5 | Directly read. Corrects Pass 48's x/h field transposition on the slot-list row, and its "cancel/delete" action-label guess (real actions: Back/Confirm/Exit-to-main-menu/Options). |

### Open follow-ups

- `RunSaveLoadScreen` record 0 `(201,217,84,21)` -- referenced only via a button-descriptor pointer, not hit-tested; role unclear.
- `RunNewGameSetupScreen`'s 8-entry row remains unresolved (Pass 50).
- `RunMultiplayerSetupScreen`/`RunMultiplayerLobbyScreen` remaining items untouched this pass.

## Pass 52 -- `RunMultiplayerSetupScreen` and `RunMultiplayerLobbyScreen`: full hotspot layouts (2026-09-09)

Both screens' previously-flagged "chained pointer alias" layouts
resolved using the same technique validated in Pass 51 (reconstruct
the contiguous stack table from all literal-assignment offsets, then
slice per `HitTestRectArray` window; adjacency confirmed via matching
base-pointer arithmetic, not inferred).

| Name | Confidence | Notes |
|---|---:|---|
| `RunMultiplayerSetupScreen` 38-record contiguous table, 5 `HitTestRectArray` windows | 5 | Directly read: main row+session list (16), connecting panel (4), host-setup dialog (4), difficulty row (8), join dialog (6). |
| `RunMultiplayerSetupScreen` main-row index 7 = Options dialog | 5 | Corrects Pass 48's "Cancel-confirm" guess. |
| `RunMultiplayerLobbyScreen` 3-entry exit cluster + 40-entry (`0x28`) main table | 5 | Directly read: Ready/Start, Cancel, page-scroll x2, mission-list (6), roster-slot toggles (8, one literally zeroed), 2 dropdown toggles + item lists (4+12), reserved tail. |
| `RunMultiplayerLobbyScreen` host-mode 3-entry checkbox row (`&pcStack_258`) | 0 | Unresolved -- stack slot reused for SEH bookkeeping, no literal assignments visible in the decompile. Same limitation class as Pass 50. |

### Open follow-ups

- `RunMultiplayerLobbyScreen`'s 3-entry host-mode checkbox row coordinates -- would need the Pass 50-style P-code cross-check if pursued further.
- Button-label text for both screens remains blocked on the runtime-only string table (Pass 37).

All twelve menu screens' hotspot layouts are now at confidence 5 except: `RunNewGameSetupScreen`'s 8-entry row (Pass 50, root-caused decompiler limitation) and this pass's one 3-entry checkbox row -- both are the same class of gap (a stack region the decompiler didn't expose as literal assignments).

## Pass 53 -- Palette-to-image mapping investigated (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| No shipped `.spr` shape uses a per-shape `PaletteOverrideRecord` | 5 | Exhaustive: 8583 shapes across all 337 `.spr` files in `gamedata/`, `paletteOffset` is 0 in every single one, script-verified. |
| Palette selection is per render-context (screen), not per image | 4 | `InitializeLoadoutScreen` loads its own `.ccb` via `SR_CCB_load()` for 3D content, then restores and re-packs the PRE-EXISTING (pre-screen) palette for the final WinVFX global-palette conversion. |
| `.SHP` (438 files, ship/turret/pod 3D object descriptions) carries no palette reference | 4 | `LoadSquadronRoster`'s full decompile (the generic parser `.SHP` files are loaded through) has no CCB/RGB/palette-related code anywhere. |
| `LoadSquadronRoster` is a generic structured-text object parser, not `.sro`-specific | 3 | Reused verbatim for single-`.SHP` ship/missile/gun model loads in `InitializeLoadoutScreen`; name kept (still accurate for primary use) but scope corrected. |
| `gamedata/`'s `extracted`/`out_palettes`/`out_softpal` dumps correspond to a real per-image code mechanism | 0 | No such mechanism exists (see above). Sampled data across all 3 folders shows only index 0 looks like genuine varied palette data; N>0 mostly degrades into flat gray R=G=B noise runs -- consistent with a heuristic byte-scanner producing false positives, not a principled per-asset extraction. |

### Open follow-ups

- `.tga` files (142, not examined) may carry their own embedded palettes independent of the `.ccb`/WinVFX system -- a plausible next target if 3D ship texture palettes specifically are wanted.
- `FUN_004a3040`/`FUN_004a3cb0` (per-wing post-processing inside `LoadSquadronRoster`) not decompiled.
- The third-party tool that produced the `gamedata/` extraction dumps is unidentified; its real logic is out of scope for static analysis of `Lancer.exe`.

## Pass 54 -- Which palette is used for the menus (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| Menus use the startup-loaded global palette (`softpal.ccb` or `palette.ccb`, chosen by `rendererState+0x1ac`), never their own | 5 | `SR_CCB_load` has exactly 2 call sites total (revealed via `set_function_prototype`); neither is in any menu screen. `InitializeGraphicsDevice` (was `FUN_004acbe0`) loads the startup one once; `InitializeLoadoutScreen` loads `palette3.ccb` separately and restores the original before returning to the menu (Pass 53). |
| `InitializeGraphicsDevice` (0x4acbe0) | 5 | Renamed from `FUN_004acbe0`. Runs the softpal.ccb/palette.ccb selection; called 4x from a device try/fallback loop (`FUN_004a8600`), once at startup. |

### Open follow-ups

- The exact condition setting `rendererState+0x1ac` (hardware vs. software renderer selection) -- not traced.
- Byte-level comparison of `palette.ccb` vs `palette3.ccb` content -- not done.

## Pass 55 -- The `.SHP`/`.sro` 3D object format: a generic tagged-chunk container (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| `ReadTaggedChunk` (0x4a2eb0, was `FUN_004a2eb0`) -- `{tag:u16,stride:u16,count:u16}` chunk scanner | 5 | Directly decompiled; independently confirmed via a Python chunk-walker against a real `.SHP` file, exactly reproducing the framing. |
| `SR_FileAlloc` (0x4cb420, was `FUN_004cb420`) -- loads a named resource whole into memory (cache-or-disk) | 5 | Directly decompiled; matches its own `"SR_falloc: error loading %s"` string. |
| Tag 1 = named parts array, tag 0xf = renderable polygon/face list | 5 | Tag 1: part names directly visible in raw decompressed bytes. Tag 0xf: consumer computes a real cross-product face normal from 3 referenced vertex positions, with a triangle/quad flag -- unambiguous 3D mesh geometry. |
| Tag 0xa = hardpoint/socket records w/ embedded keyword strings | 4 | Embedded string at +6 matched against `"startup"`/`"deploy"`, directly read. |
| Tags 2/3/4/6/7/8/9/0xb/0xc/0xd/0xe -- structurally located (offset, stride, nesting) | 2-3 | Exact field semantics not decoded. |
| Tag 0x10 (file-scope, read once after all parts, natural home for a materials/textures table) | 0 | Present in the reader code but absent from the one sample file checked (`gren_frm.SHP`) -- no semantic content confirmed. |
| `.SHP` texture/material assignment mechanism | 0 | No texture/material filename found embedded anywhere in a fully-decompressed sample file; not resolved whether it's a numeric-index lookup (candidate: unresolved per-part `+0x138` field) or an external naming convention. |

### Open follow-ups

- Field semantics for tags 3/4/6/8/9/0xb/0xc/0xe.
- The per-part `+0x138` field's source (candidate material/texture index).
- Find a `.SHP`/`.sro` sample that actually contains a tag-0x10 chunk.
- `FUN_004a3040`/`FUN_004a3cb0` (per-hardpoint post-processing) and `FUN_004c14f0`/`FUN_004c1370`/`FUN_004c11c0` (vertex fetch/normalize/length helpers) not decompiled.
- `.tga` (142 files, unexamined) association with ships via naming convention.

## Pass 56 -- `.SHP` tags decoded further; tag 0x10 "materials table" hypothesis corrected (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| Tag 4 = per-vertex `{position:float3, normal:float3, 2 trailing int32}` | 5 | Every sampled normal has magnitude 1.0; positions match real ship-scale coordinate ranges. |
| Tag 6 = named socket/hardpoint string label (e.g. `"cpit0"`) | 5 | Direct literal string read; resolves Pass 55's stray `"cpit0"` string-scan fragment. |
| Tag 0xf on-disk = `{v0,v1,v2,v3}` int32 vertex-index quad/triangle | 5 | Confirmed against 2 real populated instances (`stalag.SHP`) -- both clean, small, plausible indices. |
| Tag 0xf is essentially unused in the shipped game | 4 | Across all 438 `.SHP` files, only 2 chunks total have `count>0`. |
| Tag 0x10 = collision/bounding-plane table (unit normal + adjacency bitmask), NOT a materials/textures table | 2 (hypothesis) / 5 (NOT textures) | 73 files sampled: leading float3 always unit-length; trailing 16 int32 fields are bitmask-shaped (varied set-bit patterns) or uniform `0xFFFFFFFF`, never strings or small sequential indices. Explicitly corrects Pass 55. |
| Tag 3 = per-triangle-fan record (fan/strip vertex indices + UV/shading floats) | 3 | Sliding-window index pattern across consecutive records is strong, well-evidenced structural signal; header/trailing field semantics inferred. |
| Tag 9 = hardpoint attach transform (position + orientation + range scalars) | 3 | Plausible reading of one real 124-byte record; not confirmed against a consumer. |
| Tag 0xa numeric field = range/distance value | 2 | One data point (`16000`) in the 8-byte on-disk variant. |
| Ship textures assigned by a mechanism entirely outside `.SHP`'s own chunk data | 3 | Every tag in the catalog has now been checked; none carries a texture filename or a clean index-into-materials pattern. Strengthened from Pass 55's confidence 0 now that the tag-0x10 candidate is ruled out. |

### Open follow-ups

- `FUN_004a3040`/`FUN_004a3cb0` (per-hardpoint post-processing in `LoadSquadronRoster`) -- now the most promising lead for texture assignment.
- Tags 8/0xb/0xc/0xd/0xe still undecoded with real sample data.
- Tag 0x10's bitmask fields -- would need to find its consumer to confirm the collision/visibility-table hypothesis.

## Pass 57 -- Combat engine: Spectral Shields enforcement exhaustively searched (not found); 3 helpers decoded, one correction (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| Spectral Shields' `object+0x670`/flag `0x8000000` -- never read anywhere for damage-blocking | 5 (negative finding) | Full-binary displacement scan (2 hits, both known writes) + restricted flag-constant scan + direct inspection of `ApplyShieldDamage`/`ApplyComponentDamage`/`ProcessProjectileImpact` -- no read found anywhere. |
| `TrackFriendlyFireWarning` (0x474c80, was `FUN_00474c80`) -- friendly-fire voice-warning escalation, NOT scoring | 5 | Corrects a prior guess. String-table-confirmed (`"ff_001/005/009.ut"`), call-site-confirmed (attacker==local player, target's team flag==0). |
| `SetComponentDestroyedNotification` (0x474e00) | 4 | Sets `object+0x678` notification flag; consumer not traced. |
| `QueueCommChatterEvent` (0x415270) | 2 | Queues a 2-field event + triggers processing/network broadcast; exact field semantics and queue identity vs. `QueueAiEvent` unconfirmed. |

### Open follow-ups

- `FUN_00402860` (event-slot allocator) -- settle whether it's the same queue as `QueueAiEvent`.
- `FUN_0048c580`/`FUN_004bb980`/`FUN_004bb920` not decompiled.
- `object+0x678`'s UI/HUD consumer not traced.
- Spectral Shields enforcement: a live-debugging pass is the recommended next step per METHODOLOGY, since static search is now exhausted.

## Pass 58 -- Do `.bik` files contain/set a palette? No (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| `.bik` videos do not contain or set a palette | 5 | Full import table has no `BinkGetPalette`/`BinkSetPalette`-shaped entry (12 real Bink imports catalogued, none palette-related). `_BinkCopyToBuffer`'s only variable flags argument (`DAT_0051dab4`) decoded as an RGB555-vs-RGB565 output-surface-format selector, not a palette mode. |
| `DAT_0051dab4` = 16-bit RGB555/RGB565 selector for Bink's blit target | 5 | All 4 write sites compute it identically: `(rendererState+0x162e != 0x03E0) ? 4 : 3` -- `0x03E0` is RGB555's green-channel bitmask, and `+0x162e` sits directly among the already-documented pixel-format bit-shift constants (Pass 25/30). |

## Pass 59 -- `.spr` RLE format fully decoded and verified; medal sprites decoded and visually confirmed (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| `.spr` RLE opcode format: `CB=0x00`=end-of-row, even `CB`+count>0=repeat-fill, odd `CB`+count>0=literal copy, `CB=0x01`+skip-byte=transparent skip | 5 | Upgraded from Pass 41's confidence 3. Decoded directly from `VFX_shape_blit_unclipped` (WINVFX8.DLL 0x100035fc); implemented in `reversing/tools/decode_spr.py`; verified by reproducing a real screenshot exactly across 6 independent files. |
| Whole-file embedded palette stored as a fake "shape 0" (768 bytes, 256 x {R,G,B} at 6-bit VGA precision) | 5 | Directly read; distinct from the confirmed-unused per-shape `PaletteOverrideRecord` (Pass 39/41/53). Explains per-file distinct color schemes without needing the unused per-shape mechanism. |
| `MEDAL1-6.SPR` = the 6 medal-case UI images, each a 7-9 frame hover/select-highlight animation | 5 | Visually confirmed against a real user-supplied screenshot -- exact match across all 6. |

### Open follow-ups

- The 5 ribbon-bar icons in the screenshot -- no matching filename found in `gamedata/`.
- `ShapeRecord.headerField0`/`headerField1` still unresolved.
- Whether the "fake shape 0 = palette" convention applies outside the medal-case files.

## Pass 60 -- `INTERFACE\*.bik` menu-transition videos: full call map (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| 18 of 26 requested `.bik` filenames mapped to their exact calling menu screen | 5 | Every entry from direct `get_xrefs_to`/`get_bulk_xrefs` results, not filename inference. |
| 8 of 26 requested filenames unused (`FADIGOPT`, `IGOPTFAD.bik`, `MUL2OPT`, `MULFA2OPT`, `MULTI2MM`, `OLDOPFAD2MM`, `SIN2OPT`, `SINFA2OP`) | 5 | Not present anywhere in the string table under multiple independent searches. `OLDOPFAD2MM`'s name is self-explanatory (deprecated leftover). |
| `RunInGameOptionsScreen` (0x4394d0, was `FUN_004394d0`) -- mid-mission pause-menu options screen | 5 | Called from `RunMissionBriefingScreen`/`RunShipInteriorVRLoop`; reuses `RunSaveGameBrowserScreen`/`RunSoundOptionsScreen`/`RunControlsOptionsScreen`/`RunVideoOptionsScreen`. |
| `RunMultiplayerDebriefScreen` (0x4296a0, was `FUN_004296a0`) -- post-mission MP results/ready-check screen | 4 | Called 3x from `WinMain`; loads `mpdebr.spr`, tracks per-player ready state. |
| Shared sub-screens get two parallel fade-clip sets depending on which parent invoked them (main-menu-Options path vs. in-game-pause path) | 5 | Directly observed across `RunControlsOptionsScreen`/`RunSoundOptionsScreen`/`RunVideoOptionsScreen`/`RunSaveGameBrowserScreen`'s call sites. |

### Open follow-ups

- `RunMultiplayerDebriefScreen`'s relationship to the main mission-completion flow -- not traced.
- Whether `WinMain`'s 3 call sites for `RunMultiplayerDebriefScreen` have their own surrounding `.bik` transitions.

## Pass 62 -- Campaign pilot setup decoded; corrects Pass 46's "difficulty A/B" mislabel (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| `RunNewGameSetupScreen` cases 0/1 = pilot gender (male/female), NOT difficulty | 5 | Corrects Pass 46. Directly confirmed: `g_wPilotGenderIsFemale` (was `DAT_00562f16`) selects `"mp%s"`/`"fp%s"` format strings and gates the in-game pilot-record screen setup and the setup screen's own portrait preview. |
| `RunDifficultySelectDialog` (0x430300, was `FUN_00430300`) = the real 3-tier Easy/Normal/Hard picker | 5 | `g_wCampaignDifficulty` (was `DAT_00562f14`), cycled 0-2 by this dialog, read directly by `ScaleDamageForDifficulty`. |
| `LoadPlayerProfile` loads an existing `profile.bin` or silently creates a new one with defaults (mission 1, zeroed stats) | 4 | Directly read: tries `fopen`-style read first, falls to write-fresh-defaults on failure. |
| `profile.bin`'s field layout beyond mission-index/name | 1 | Only 2 of ~208 bytes' worth of fields identified. |

### Open follow-ups

- `profile.bin`'s remaining fields (stats, unlocks, per-wingman roster status) not mapped.
- Case 5 ("Reset")'s exact semantic meaning -- mechanism read, not confirmed.
- Whether gender selection affects anything beyond the `mp`/`fp` asset prefix and kills-screen display field.

## Pass 63 -- `profile.bin`'s field layout decoded and verified against a real save (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| `PlayerProfile` struct (208 bytes, base `DAT_00562cf8`): mission index, callsign, rank/score fields, 2 reserved blocks, 2x 28-entry per-mission arrays | 5 (boundaries/sizes) | Directly read from `AdvanceCampaignMissionAndSaveProfile`'s field-by-field save copy, cross-checked byte-for-byte against a real 208-byte sample file (`gamedata/StarLancer/profile.bin`, callsign "DMJC"). |
| `highestRankTierReached`/`cumulativeScore` semantic labels | 3 | Well-supported by a real 9-tier threshold-table lookup mechanic, directly read; "rank" terminology itself not independently confirmed (localized strings are runtime-only). |
| `perMissionSpecialFlag`, 2x 6-dword reserved blocks | 1 | Structurally located only. |
| Real sample profile.bin's `callsign` field has genuine uninitialized-memory leftover bytes past the name terminator | 5 | Directly observed in the shipped file (`0x1b` stray byte after `"DMJC\0"`), confirms `LoadPlayerProfile`'s variable-length (not fixed-fill) name copy. |
| `AdvanceCampaignMissionAndSaveProfile` (0x475a90, was `FUN_00475a90`) -- end-of-mission profile save + mission-index advance, with special-case mission jumps (0xb/0xc->0xe, 0x10->0x12, 0x15->0x17, 0x1c->0x1d) | 4 | Directly read; the 0x1c->0x1d jump matches the already-documented mission-29 campaign-epilogue special case. |
| `RefreshActiveCallsignFromProfile` (0x475390, was `FUN_00475390`) -- only refreshes the active callsign global, doesn't unpack other fields | 5 | Directly read; short function. |

### Open follow-ups

- `perMissionSpecialFlag` and the two reserved blocks -- not identified.
- Whether the 9-tier rank table maps to real named ranks anywhere -- blocked on runtime-only localized strings.
- `DAT_0050099f`/`DAT_005009d7`/`DAT_005009bb` (small per-mission tables feeding the advance logic) not mapped.

## Pass 64 -- `profile.bin`'s remaining fields resolved (2026-09-09)

| Name | Confidence | Notes |
|---|---:|---|
| `reserved1[6]`/`reserved2[6]` (`PlayerProfile+0x30`/`+0x48`) = hub-room hotspot/prop enabled-flags | 4 (role) / 2 (individual mapping) | Read by `RenderBriefingHubFrame` (0x436b20, was `FUN_00436b20`) as two parallel 6-entry boolean arrays gating interactive hub-room hotspots; switches between early/late-campaign table sets via `DAT_00562dc8 < 0x13`. |
| `perMissionSpecialFlag` and the 3 small per-outcome tables (`DAT_0050099f`/`DAT_005009d7`/`DAT_005009bb`) = debrief-narrative paragraph gates | 3 | Read by `BuildMissionDebriefText` (0x424cf0, was `FUN_00424cf0`). One gate is ANDed with `perMissionRankSnapshot==4`, independently supporting Pass 63's "rank" interpretation of that array. |

### Open follow-ups

- Map the 12 hub-room flag bit-positions to named VR ship-interior room-graph objects.
- Debrief narrative text content itself -- runtime-only, not recoverable statically.
- `DAT_0052a460` (a plausible "first-time debrief" flag) not traced further.

## Pass 65 -- CONFIRMED: mission-19 threshold = ANS Reliant -> ANS Yamato transfer (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `DAT_00562dc8 < 0x13` (mission 19) = the Reliant->Yamato ship-transfer boundary | 5 | Directly read from `WinMain`'s cutscene-selection logic (`new_reliant_transfer.bik` vs `new_a_y_trans.bik`, gated by session flag `DAT_0052a470`); independently corroborated by a second site picking `new_rel_exec.bik`/`new_y_exec.bik` on the same comparison. |
| `reliant.shp`/`yamato.shp`/`reliant_hang.shp`/`reliant_destback.shp`/`Yamato DestBack.shp` = the two carriers' 3D models + destruction-backdrop variants | 5 | Direct string confirmation. |
| The "two parallel ship-layout graphs" note (circa Pass 33) = literally Reliant-interior vs. Yamato-interior | 5 (raised from "plausible") | Grounded by user-supplied narrative context + the string/threshold evidence above. |
| `RenderBriefingHubFrame`'s (Pass 64) early/late hub-room table switch = the hub room physically changing ships | 5 (raised from 4) | Same mission-19 boundary, now understood as a real ship change, not a cosmetic variant. |

### Open follow-ups

- `DAT_0052a470`'s write site (confirms "transfer cutscene already shown" semantics) -- not located.
- The Reliant "induction" sequence's role -- only its existence confirmed.
- Other mission-index thresholds possibly corresponding to further story beats -- not surveyed beyond mission 19.

## Pass 66 -- The missing AI link found: `UpdateShipAiTick` + the real AI state stack (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `UpdateShipAiTick` (0x40c5f0, was `FUN_0040c5f0`) -- per-object AI tick, called from `ProcessMissionSimulationTick` | 5 | Drains the `QueueAiEvent` perception queue (Pass 20) using the exact same priority-gate `TrySetAiState` uses, then runs the top-of-stack state's OnEnter(once)/OnUpdate(every tick) callbacks. This is the missing link flagged unresolved since Pass 20. |
| `PushAiState` (0x40cc10, was `FUN_0040cc10`) -- `object+0x684`/`+0x680` is a real 20-entry pushdown STACK, not a single "current command" | 5 | Corrects/completes Pass 17's "AI command/state structure" language. Move-to-front deduplication against the existing stack, priority-gated via `TrySetAiState`, lazy-allocates a 520-byte stack + 144-byte scratch buffer (source-tagged `aigeneric.cpp`). |
| State catalog's leading two callback slots = OnEnter/OnUpdate | 5 | Confirms Pass 18's "plausibly OnEnter/OnUpdate" guess -- directly read in `UpdateShipAiTick`. |
| `FUN_0040ca00` (PushAiState's first gate check) | 1 | Mechanism read, exact semantics (which ships/states it blocks) not confidently determined. |

### Open follow-ups

- `FUN_0040ca00`'s exact semantics.
- `FUN_0040ce70`/`FUN_0040c520` not decompiled.
- The generation-ID mechanism (`DAT_005185a8`/`DAT_005185b1`) -- purpose not traced.

## Pass 67 -- 14 specific `.tga` images mapped to their exact call sites (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| All 14 requested `.tga` files' calling function(s) | 5 | Every mapping is a direct `get_bulk_xrefs` result resolved to its containing function, not inferred from filenames. |
| `briefdoor` texture selected by the exact Reliant/Yamato mission-19 threshold | 5 | `DAT_00562dc8 > 0x12`, the same boundary confirmed in Pass 65 via 2 independent sites; this is now a third. |
| `LoadGenericSplashBackdrop`/`LoadStartupSplashBackdrop`/`ShowMissionLoadingScreen` (0x4ab3f0/0x4ab4b0/0x4ad0a0, were `FUN_004ab3f0`/`FUN_004ab4b0`/`FUN_004ad0a0`) | 4 | Directly read; the startup one's resolution-tiered `sl_splash*` selection sits behind a jump table Ghidra couldn't recover, so the exact resolution-to-file mapping is not confirmed. |
| Requested `igoptfade.tga` doesn't exist under that spelling -- real file is `igoptfad.tga` | 5 | Confirmed absent via string search; mapped under its real name instead. |

| Each menu screen's `.tga` is its real, persistent background (not a poster-frame placeholder); the matching `.bik` is the click-triggered transition animation FROM the departing screen TO that background | 5 | User-supplied correction, directly verified against `RunOptionsMenuScreen`'s real disassembly: `main2opt.tga` loads once at screen entry, before the per-frame render callback is installed -- the shape of a persistent backdrop, not a transient placeholder. Ties directly into Pass 60's per-button `.bik` trigger table -- each menu click's transition target is a `(video, destination background)` pair. |

### Open follow-ups

- The `sl_splash*.tga` jump table's resolution-to-file mapping -- not recovered.
- `FUN_0043eaf0` (shared `briefdoor` loader) not decompiled.
- Whether every `.bik`/`.tga` pair follows the same click-triggered-transition shape confirmed for `main2opt` -- only that one pair was checked at the disassembly level.

## Pass 68 -- CONFIRMED: shipboard VR interfaces use the identical background system (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `SetActiveBackgroundImage` (0x494b50, was `FUN_00494b50`) is the ONE shared function behind every background swap, menu or shipboard | 5 | Directly read; no-ops if the requested filename matches the already-active one, else updates and calls the real loader (`FUN_00494a70`, not opened). |
| `RunCdPlayerPropScreen` (0x437fc0) sets its room's background via this function, picking between `rel_bunk2cd.tga`/`brd2cd.tga` on the exact Reliant/Yamato mission-19 threshold | 5 | 4th independent site confirmed using that boundary (after `RenderBriefingHubFrame`, `WinMain`'s cutscene selection, `RunMissionBriefingScreen`'s `briefdoor`). |

### Open follow-ups

- `FUN_00494a70` (the real image display routine) not decompiled.
- Other VR room-graph nodes' own background-image pairs not swept.
- Whether `RunShipInteriorVRLoop`'s main per-room dispatch calls `SetActiveBackgroundImage` directly for each room.

## Pass 69 -- `DisplayActiveBackgroundImage` decoded: the real TGA display pipeline (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `DisplayActiveBackgroundImage` (0x494a70, was `FUN_00494a70`) | 5 | Two paths: a callback override (`DAT_00588740`) bypassing the image pipeline entirely, or the real static-image load/decode/blit sequence. |
| `SR_TGA_rle_uncompress` (0x4cad60, was `FUN_004cad60`) -- complete, correct TGA RLE decoder | 5 | Self-identified via its own 3 assertion strings; correctly handles both TGA orientation flags and the real RLE packet format. |
| `ComputePixelFormatFromMasks` (0x4c3430, was `FUN_004c3430`) -- channel-mask-to-bpp helper | 4 | Every observed call site uses the same fixed ARGB8888 masks; general-case behavior for other masks not independently re-verified. |
| `SetActiveBackgroundCallback` (0x494bb0, was `FUN_00494bb0`) -- dynamic-background sibling to `SetActiveBackgroundImage` | 4 | Directly read; no caller located yet to show a concrete dynamic-background example. |

### Open follow-ups

- No `SetActiveBackgroundCallback` caller located.
- `rendererState+0x50`'s actual blit target not traced.

## Pass 70 -- The renderer `+0x50` blit target: searched exhaustively, genuinely not found (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `rendererState+0x50`/`+0x40` write sites -- not found anywhere in the binary | 5 (negative finding) | `search_instructions` checked every store to `+0x50`/`+0x40` program-wide and every plausible graphics/device init function individually; all came up empty. `+0x50` is confirmed heavily reused by unrelated structs elsewhere (a genuine DirectX COM vtable call in `DetectDirectXVersion`, gameplay object fields in `FUN_00404040`/`FUN_00412390`) -- not unique to the renderer state. |
| `SR_init` (0x4c3830, was `FUN_004c3830`) | 5 | Self-named via its own assertion string; zeroes a ~6KB renderer struct and returns it -- `+0x50` is in the zeroed range but never individually set anywhere found. |
| `InitializeWinVfxLibrary` resolves ~28 `VFX_*` exports into separate named globals, none into `DAT_00588730` | 5 | Rules out the "sequential WinVFX export table" hypothesis for `+0x50`. |

### Open follow-ups

- Live-debugging (hardware write-breakpoint) is the recommended next step; static search is exhausted for this specific field.
- Check the remaining renderer callback slots (`+0x78`/`+0x7c`/`+0x80`/`+0x88`/`+0x8c`/`+0x90`) the same way to see if they show findable write sites while `+0x40`/`+0x50` don't.

## Pass 71 -- The ITAC interface decoded (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `RunItacScreen` (0x43efc0, was `FUN_0043efc0`) -- main ITAC screen loop | 5 | Directly read in full: setup, 9-category state machine, eye-recog gate, room-transition-out mechanism. |
| `DAT_00523088`'s eye-recognition gate is a 5th confirmed Reliant/Yamato mission-19 threshold site | 5 | `DAT_00562dc8 < 0x13` picks `PlayBinkMovieFromArchiveByName` (Reliant); otherwise `PlayBinkMovieFromHandle` (Yamato). Joins `RenderBriefingHubFrame`, `WinMain`'s cutscene selection, `RunMissionBriefingScreen`'s `briefdoor`, `RunCdPlayerPropScreen`'s room background. |
| `PlayBinkMovieFromArchiveByName`/`PlayBinkMovieFromHandle` (0x4ab9d0/0x4ab6e0, was `FUN_004ab9d0`/`FUN_004ab6e0`) -- generic Bink player utilities, NOT ITAC-specific | 5 | Reused by ITAC's eye-recog gate and exit sequence with different arguments; one looks a clip up by name in a packed archive, the other opens a direct handle. |
| The 9-category catalog (Debrief/News/Video Reports/Fighters/CapShips/Squadrons/Personnel/Kills/Exit) | 5 | All 9 `ItacEnter*Category` enter callbacks identified and renamed by decompiling their `LoadNamedResource` calls; cross-checked against three parallel 9-entry tables (`0x4e9288` callbacks, `0x4e9340` hotspot rects, `0x4e9418` bik/tga string names), all read directly. |
| **CORRECTION**: bik `f`-suffix means exit-line, not gender | 5 | First-impression hypothesis (by analogy with the confirmed `g_wPilotGenderIsFemale` "mp"/"fp" system, Pass 62) was that `itacdebf.bik` was a female voice variant. Reading the actual code disproved this before it was written anywhere: non-suffixed = enter-category line, `f`-suffixed = exit-category line. Confirmed for all 9 categories via the `0x4e9418` string table. |
| `ItacShowCategoryTransitionAndEnter` (0x43fca0, was `FUN_0043fca0`) | 5 | Loads `inter\itac\itactrans_NNNNN.tga`, decodes via `SR_TGA_rle_uncompress`, `memcpy`s directly into `*DAT_00520314` -- a working blit path that bypasses the still-unresolved `rendererState+0x50` vtable call from Pass 70 entirely. |
| Table field 2 ("content setup") callbacks: shared no-op stub vs. per-category ones | 4 | Shared stub (`0x44de90`) resets a 4-entry list-selection state, used by the 4 plain list-browser categories. Debrief/Squadrons/Personnel have their own. Kills' (`0x4411c0`) renders a live 3D scene via the renderer's `+0x78`/`+0x7c` frame callbacks -- qualitatively different from the list categories. |
| Category 3/6 bik-name fragments ("ss"=Fighters, "pil"=Personnel) don't match their `.spr` names | 1 | Fact of the mapping is confidence 5 (directly read); any semantic explanation for the fragment choice is confidence 1 speculation, kept explicitly separate per methodology. |

### Open follow-ups

- Table fields 3/4 (called from undecompiled `FUN_004404a0`) -- likely per-frame update / record-selection.
- ITAC's room-graph exits (the `rel_itac2X.bik`/`itac2X.bik` clips) not mapped to hotspots/destinations.

## Pass 72 -- Room-transition-out internals and the remaining itac.cpp functions (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `PlayBinkMovieFromArchiveWithVolume` (0x4abb80, was `FUN_004abb80`) -- a 3rd generic Bink-player variant | 5 | Confirmed generic via `get_xrefs_to`: 11 `WinMain` sites, `AdvanceCampaignMissionAndSaveProfile`, 4 other VR-room helpers, plus exactly 1 call from `RunItacScreen`'s room-transition-out. Differs from the Pass 71 pair by explicit `_BinkSetVolume_8` and a `+0x1ac` render-mode check instead of `+0x15f8`. |
| `ItacRoomTransitionFrameCallback` (0x4403f0, was `FUN_004403f0`/`LAB_004403f0`) -- fade+cursor per-frame overlay hook | 4 | Installed at `DAT_00588730+0x88` during transition-out; chains any prior `+0x80` callback, drives the fade via `FUN_0043fe90(DAT_0052082c)`, draws the mouse cursor when not in the `DAT_0052308c` waiting state. |
| `ActivateItacTransitionBackground` (0x43eaf0, was `FUN_0043eaf0`) | 4 | Formats `%s.tga`, triggers renderer `+0x78` begin-frame, calls `SetActiveBackgroundImage` -- the final step that actually swaps in the destination room's background. |
| `DynamicList_GetByIndex` (0x4406a0, was `FUN_004406a0`) -- core record-list traversal primitive | 5 | Self-identified via its own `DynamicList::GetByIndex` assertion string. Confirmed via `get_xrefs_to` as the single shared list-walker used by every ITAC record-browser category (Kills, Capital Ships, Fighters, Personnel, Squadrons) -- structurally generic, but this binary only exercises it from itac.cpp. |
| `InitializeItacLanguageStrings` (0x440770, was `FUN_00440770`) -- ITAC's own localized string-table loader | 5 | Directly read in full: loads `itaclang.dll`, two-pass `LoadStringA` walk (count+size, then copy+index) into a flat buffer + pointer table. Behind the already-known `"language_init: Can't find ITACLANG.DLL"` assertion. |
| `RegisterItacTooltip` (0x440bd0, was `FUN_00440bd0`) | 5 | Bounded (30-slot) tooltip-string registration list; asserts `"Too many tooltips"` past slot 29. |

### Open follow-ups

- `DAT_00588730+0x1ac`'s render-mode values not independently mapped.

## Pass 73 -- `UpdateMouseCursorState`, `g_dwItacSkipEyeRecognition`'s set-site, and ITAC's room-graph exits (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| **CORRECTION**: `UpdateMouseCursorState` (0x4404a0, was `FUN_004404a0`) is a generic mouse-input helper, NOT a category-table dispatcher | 5 | Pass 71/72 speculated it called table fields 3/4; disproved by reading it. Confirmed generic via `get_xrefs_to`: also called from `RunMissionSelectMapScreen`. |
| Table field 3 = per-category per-frame update; field 4 (at least for Video Reports) = click-confirm handler | 5 | `ItacDebriefPerFrameUpdate` (0x4247c0) and `ItacVideoReportsPerFrameUpdate` (0x450630) decompiled directly; `ItacSelectVideoReportRecord` (0x450cc0, field 4) fetches the selected `DynamicList` node on click-release. |
| **CORRECTION**: `DAT_005251dc` is ITAC's "play the selected Video Report record" trigger, not a room-exit mechanism | 5 | Traced its only non-`RunItacScreen` write site to `ItacSelectVideoReportRecord`. It reuses the room-transition bink-playing plumbing because playing a clip needs the same background-hide/CD-check/chdir sequence a real room change does -- but it is NOT a room exit. Corrects the Pass 71 framing. |
| `g_dwItacSkipEyeRecognition` (0x523088, was `DAT_00523088`) -- both write sites traced | 5 | Set to 1 in `WinMain` immediately before the post-mission-debrief `RunItacScreen()` call; cleared to 0 by `ItacDebriefPerFrameUpdate` on the first per-frame tick after landing on Debrief. One-shot "skip eye-recognition for this specific post-mission entry" flag. |
| ITAC has no internal room-exit hotspot table -- exits are driven entirely by `RunShipInteriorVRLoop`'s `VRRoomNode.nRoomType == 2` dispatch | 5 | Directly read in `RunShipInteriorVRLoop` (0x439fb0). |
| Reliant's ITAC `VRRoomNode` (0x506c50) and its single exit target, the bunkroom (0x506c80) | 5 | Hotspot rect (150,100,150,300); entry clip `bunk2itac_no_eye_recog.bik`; exit clip `rel_itac2bunk.bik`. `nNumTargets == 1` confirms exactly one way out. |
| Reliant's pre-ITAC corridor-junction waypoint (0x506b30) and its 3 fan-out targets | 4 | Explains 3 of the 4 confirmed Reliant `X2itac`/`itac2X` clip names from Pass 71's string search (`rel_t2itac.bik`, `rel_itac2t.bik`, `rel_itac2pod.bik`). |
| Yamato's fixed post-ITAC room (0x50aec8, movie `itac2rot.bik`) confirmed different from Reliant's (bunk vs. "rot") | 5 | Confirms the two ships' VR room graphs are laid out differently, matching the asymmetric bik-name sets already noted in Pass 71. |
| Yamato's exact ITAC room node (`nRoomType==2` counterpart to 0x506c50) | 0 (not located) | Traced 3 hops from the post-ITAC node without finding it; `get_xrefs_to` on the `pod2itac.bik`/`lock2itac.bik` string addresses returned no data references. |

### Open follow-ups

- `DAT_00588730+0x1ac`'s render-mode values not independently mapped.

## Pass 74 -- Remaining clip names/nodes resolved; every category's fields 3/4 decoded (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `rel_cap2itac.bik`'s `VRRoomNode` (0x506f50) -- a true terminal/scripted node | 4 | Zero hotspot size, zero targets, and nothing else points to it (`search_byte_patterns` on its own address found no hits). Consistent with the one-time capital-ship-transfer cutscene context (Pass 65), not the interactive room graph. |
| `itac2pod_hud.bik`'s `VRRoomNode` (0x50acb8) -- `nRoomType==5`, launches `RunMissionSelectMapScreen` | 5 | Its `pTarget0` (0x50b678) matches exactly the hardcoded "next room after the mission map" in `RunShipInteriorVRLoop`, confirming the link. |
| `itac2dor.bik`'s `VRRoomNode` (0x50ab08) -- ordinary room, 3 targets | 4 | The "door" room from Pass 71's name-fragment list. |
| **Yamato's ITAC room node located**: `VRRoomNode` at 0x50ada8 (movie `itac2itac.bik`), `nRoomType==2` | 5 | The counterpart to Reliant's 0x506c50 that Pass 73 failed to find via graph traversal; found instead via `search_byte_patterns` on the string address. Has 2 confirmed incoming edges: junction nodes at 0x50ab68 (`ir_l2i.bik`, lock room) and 0x50ae34 (`ir_f2i.bik`). |
| Every category's field 3 (per-frame update) and field 4 (hover-preview render) now decoded | 5 | All 14 remaining functions decompiled and renamed: `ItacDebriefRenderTransferSummary`, `ItacNewsReportsPerFrameUpdate`/`RenderPreview`, `ItacVideoReportsRenderPreview`, `ItacFightersPerFrameUpdate`/`RenderPreview`, `ItacCapShipsPerFrameUpdate`/`RenderPreview`, `ItacSquadronsPerFrameUpdate`/`RenderPreview`, `ItacPersonnelPerFrameUpdate`/`RenderPreview`, `ItacKillsPerFrameUpdate`/`RenderPreview`. |
| **New**: 4 of 9 categories (Fighters, Capital Ships, Squadrons, Personnel) have their own internal sub-tabs | 3 | Poll a second hotspot row (shared table ~`0x4e96c4`-`0x4e96d0`, indexed by shared global `DAT_00523058`) presumably filtering the roster by class/rank. News Reports/Video Reports/Debrief/Kills don't have this. Exact table size/semantics not mapped. |
| The 4 shared per-frame primitives: `FindHotspotIndexAtCursor`, `IsClickConfirmEdge`, `DrawFadingTextCaptions`, `UpdateHoverAnimationWidget` (0x43fe40/0x441060/0x43ff50/0x4409f0) | 5 | Generic hit-test, click-debounce, floating-caption-fade renderer, and hover-animation updater used across every category and the main tab bar. |

### Open follow-ups

- `rel_cap2itac.bik`/`itac2pod_hud.bik`/`itac2dor.bik` fully placed structurally but not connected to a specific gameplay trigger (e.g. what puts the player at 0x506f50).

## Pass 75 -- All 4 remaining open items resolved (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| Sub-tab table fully resolved: exactly 2 sub-tabs | 5 | 4 parallel 2-entry `short` arrays at `0x4e96c4`/`c8`/`cc`/`d0`: icon index (25/24), hotspot->subtab-ID mapping (0/1, identity), draw X (551/478), draw Y (59/59). Semantic meaning of the 2 tabs (confidence 1) and their click-rects (not located) remain open. |
| `ItacCapShipsRenderPreview`'s 19-case switch -- **CONFIRMED real**, not a decompilation artifact | 5 | Verified via `disassemble_function`: a genuine jump table plus a 56-byte class-ID-to-tint-group lookup at `0x423c74` (pattern `groupN,groupN,default` repeating for 19 groups). Selects a color/tint group before drawing the raw class icon. |
| `UpdateHoverAnimationWidget`'s widget struct -- partially identified | 4 | Confirmed generic (also used at `0x42a4f2` outside ITAC). Each ITAC call site passes a hardcoded literal address, one static instance per category (e.g. `0x51d2e8` for Debrief). Traced Debrief's instance init (`FUN_00424730`): `+0x00` = a `RunItacScreen` setup sprite-surface handle, `+0x20` = redraw callback `&LAB_00425220` (not decompiled). Used alongside a category-specific secondary hotspot table (e.g. Debrief's prev/next-mission buttons at `0x4e4928`, count 2) -- likely animates hover feedback for small nav buttons. |
| `DAT_00588730+0x1ac` -- resolved: first field of a bulk-copied 1299-dword video-mode record, not a scalar flag | 5 | `InitializeGraphicsDevice` copies `(&DAT_00595da0)[param_4]` (from `EnumDisplayCardsFromDriver`'s mode table) into `+0x1ac` onward -- the same 1299-dword copy Pass 70 found but couldn't place. Its first field (0/1/2) selects a renderer-backend-driver-DLL load via `LoadRendererBackendDriver` (0x4cc470, was `FUN_004cc470`, self-identified via its `"SR_driver_init"` string); other values skip that load (true hardware acceleration). The 47 program-wide `+0x1ac` hits from `search_instructions` were a red herring -- almost all belong to unrelated structs at the same coincidental offset, same lesson as Pass 70's `+0x50`. |

### Open follow-ups

- `rel_cap2itac.bik`/`itac2pod_hud.bik`/`itac2dor.bik` fully placed structurally but not connected to a specific gameplay trigger.

## Pass 76 -- Sub-tab click-rects, hover-widget callback, tint-group semantics investigated (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| Sub-tab click-rects located: `0x4e5460`, 2 entries | 5 | Found via `disassemble_function` on `ItacFightersPerFrameUpdate` (literal args don't survive decompilation): entry 0 = (551,59,64,41), entry 1 = (478,59,64,61) -- X/Y match Pass 75's confirmed draw-position table exactly. |
| **CORRECTION**: `UpdateHoverAnimationWidget`'s Debrief callback is `BuildDebriefSummaryText`, not a wiggle-redraw | 5 | `LAB_00425220` -> `RefreshDebriefSummaryText` (0x425220) -> `BuildDebriefSummaryText` (0x425240) -- a large function assembling the mission-debrief narrative paragraph from per-mission outcome-flag arrays and template/language-string fragments. The generic hover-animation mechanism is reused here as a periodic text-refresh trigger, not an actual button wiggle. |
| CapShips' 2 sub-tabs correspond to 2 distinct roster tables (21 vs. 27 ships) | 4 | `PopulateCapShipsRosterForSubTab` (0x424410, was `FUN_00424410`, called from `ItacEnterCapShipsCategory`) walks `0x4e42c0` (21 records) or `0x4e4560` (27 records) depending on sub-tab index, inserting each into the category's `DynamicList`. Each 32-byte record holds ~7-8 consecutive `GetLanguageString` IDs plus small numeric fields -- consistent with a name/description/stat card per ship class. |
| Tint-group (Pass 75's 19-group lookup) semantic meaning | 1 | NOT resolved -- the localized string text those `GetLanguageString` IDs resolve to isn't available in this Ghidra project (separate language resource, not open in this session). Structural link to the roster tables confirmed; which classes fall in which group, and what unifies each group, remains unknown. |

### Open follow-ups

- `UpdateHoverAnimationWidget`'s other call site (`0x42a4f2`, outside ITAC) not traced -- unclear if it's a genuine wiggle-animation user there.
- The per-mode-value driver DLL name passed to `LoadRendererBackendDriver` not traced (implicit register argument).
- `rel_cap2itac.bik`/`itac2pod_hud.bik`/`itac2dor.bik` fully placed structurally but not connected to a specific gameplay trigger.

## Pass 77 -- Tint-group semantics unblocked via direct LANGUAGE.DLL string extraction (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `LANGUAGE.DLL` exists on disk and its `RT_STRING` table is directly extractable | 5 | Pass 76 wrongly treated the localized text as unreachable. New tool `reversing/tools/extract_language_strings.py` parses the PE resource directory in Python (no Ghidra needed) -- generic Win32 STRINGTABLE reader, also works on `ITACLANG.DLL`. |
| **CORRECTION**: Capital Ships' 32-byte records hold 8 PERSON names/callsigns each, not ship-class name/stat data | 5 | IDs 1262+ resolve to real names ("General Makin", "Sean Oliver"...) and callsigns ("Jester", "Zero", "Ace"...). Corrects Pass 74-76's assumption of a "name/description/stat card per ship class." IDs 1200-1244 are the game's own end credits; 1245-1261 are mission-specific objective text and NPC names for a specific mission -- confirming this is the shared campaign/credits/NPC text pool, not a dedicated ship-class table. |
| Tint groups -- classIDs used strictly in pairs, one pair per group, across all 48 records on both sub-tabs | 4 | Decoded all 21+27 records; `FUN_00440710` links records into the `DynamicList` by reference (no copy), so `record+0x1e` is each record's own trailing field. Every classID actually used (36 distinct values, e.g. 1,2,4,5,7,8...56) lands on a "group" slot; the "default" slot (3,6,9,...,57) is never assigned to any real record on either sub-tab. Several classIDs repeat across multiple distinct records, confirming it's a shared category value, not a unique ID. |
| Ultimate real-world label of each tint group (hull class? faction?) | 1 | Not determined -- would need `capships.spr`'s icon art decoded and compared; the record text is person-names, not a self-describing class label. |

### Open follow-ups

- `UpdateHoverAnimationWidget`'s other call site (`0x42a4f2`, outside ITAC) not traced.
- The per-mode-value driver DLL name passed to `LoadRendererBackendDriver` not traced.
- `rel_cap2itac.bik`/`itac2pod_hud.bik`/`itac2dor.bik` fully placed structurally but not connected to a specific gameplay trigger.

## Pass 78 -- `capships.spr` decoded: tint groups are per-class-pair palettes (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `shapeCount==57` explains Pass 77's "default slot never used" pattern: 19 groups x (1 palette + 2 ships) | 5 | Decoded the real `CAPSHIPS.SPR` (RefPack-compressed). Shape indices 0,3,6,...,54 (exactly the never-assigned "default" classIDs) are each a dedicated 768-byte palette block sitting immediately before that group's 2 ship images -- not unused/reserved ship slots. `19*3=57`. |
| **Bug fix**: `decode_spr.py` only used the first palette block for every shape | 5 | Correct for single-palette files (medal-case sprites -- re-verified unaffected), wrong for multi-palette files like `CAPSHIPS.SPR` (produced color-scrambled but geometrically-correct "static" images for every shape after the first pair). Fixed to track the nearest-preceding palette block per shape. |
| Tint groups = per-group faction/national color schemes, not "2 marks of one hull" | 4 | Visual comparison after the fix: group 1's 2 ships are entirely different hull designs (not variants); group 6 shows a US-style star-and-stripes roundel, group 18 shows a Soviet-style red star -- opposing national insignia between groups, confirming the palette encodes a faction color scheme. |
| `GetShapeRecordPointer`/`ActivateShapePalette` (0x480c40/0x428410, was `FUN_00480c40`/`FUN_00428410`) decoded | 5 | `GetShapeRecordPointer` = `ShapeSet.shapes[i].recordOffset` lookup (matches `decode_spr.py`'s own Pass 39/41 documented format, now confirmed against the game's own code). `ActivateShapePalette` converts a 6-bit-VGA palette block to native pixel format (via `ComputePixelFormatFromMasks`-style shift/mask fields) and uploads it, with a brightness scalar for fades. Together they explain `ItacCapShipsRenderPreview`'s `group*3` computation: it's the palette block's shape index, selected and activated before the icon draw. |

### Open follow-ups

- The real-world label for each of the 19 groups (which hull class/faction) -- needs matching against official reference art.
- Whether the other ITAC `.spr` files use the same multi-palette-per-group layout -- not checked.
- `UpdateHoverAnimationWidget`'s other call site (`0x42a4f2`, outside ITAC) not traced.
- The per-mode-value driver DLL name passed to `LoadRendererBackendDriver` not traced.
- `rel_cap2itac.bik`/`itac2pod_hud.bik`/`itac2dor.bik` fully placed structurally but not connected to a specific gameplay trigger.

## Pass 79 -- Player creation / campaign start documented end-to-end (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| Full New Game -> pilot creation -> campaign start flow documented | 5 | Main Menu -> `RunNewGameSetupScreen` -> `RunDifficultySelectDialog` -> `LoadPlayerProfile` (Pass 62) -> `FUN_0049cd20` -> `WinMain`'s `DAT_00562dc8==1` gate -> `new_intro.bik` -> `RunReliantInductionTour` -> `RunShipInteriorVRLoop`. Each link directly read, not inferred. |
| `RunReliantInductionTour` (0x438d50, was `FUN_00438d50`) -- new-pilot 5-stage orientation tour | 5 | Gated in `WinMain` on `DAT_00562dc8 == 1` exactly (brand-new pilot's first session only). 5 stages (locker/sim pod/cargo deck/ITAC/outro), each an ambient loop + narrated intro clip; returns which stage the player exited from. |
| `FUN_0049cd20` -- resets transient per-campaign session state | 3 | Called only on new-pilot confirmation (not Load Existing). Fills a 260-byte array with value 2 + resets a small struct; not persisted in `profile.bin`; consumer/role not traced. |
| `RunNewGameSetupScreen` case 5 clarified: "cancel callsign edit," not a field-clear | 4 | Up from Pass 62's unconfirmed rating. Resets the callsign-edit-mode flag (`DAT_0052019c`) and re-runs a trivial init call; typed characters aren't observed to be erased. |

### Open follow-ups

- `FUN_0049cd20`'s 260-byte array/struct -- role not traced to a consumer.
- Whether `RunReliantInductionTour` can be aborted entirely vs. just exited early at a given stage.
- The post-tour per-stage transition-clip jump table in `WinMain` -- only partially read.

## Pass 80 -- The post-tour transition-clip jump table, fully mapped (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| Post-`RunReliantInductionTour` jump table (`0x4aa8c8`, 6 entries indexed by exit stage 0-5) fully decoded | 5 | Every case sets a `VRRoomNode` pointer (after 0-2 supplementary `PlayBinkMovieFromArchiveByName` clips) and falls into a shared `RunShipInteriorVRLoop(ECX)` tail at `0x4aa2b0`. All 6 cases traced: stages 0/1/5 play 2 clips then land at the pod bay (`0x506cb0`); stage 2 plays 1 clip then lands at the pod bay; stages 3/4 play no extra clip and land at `0x506bf0`/`0x506cb0` directly (relying on the target node's own built-in arrival clip). |
| `0x506bf0`/`0x506cb0` are the same physical room (pod bay), two arrival-direction node copies | 5 | Identical 3 outgoing targets and `pMoviePathAlt`; differ only in hotspot rect and arrival clip (`rel_cd2pod.bik` vs `rel_itac2pod.bik`) -- same pattern as Pass 73's corridor-junction node pair. |
| Some clip names don't literally match the exit stage that selects them (case 1's "locker to corridor" clip plays for a sim-pod-stage exit; case 2's "pod to ITAC" clip routes the player *to* the pod bay) | 2 | Plausible economical reuse of a small set of generic hallway-walk clips rather than one bespoke clip per exit stage -- not independently confirmed. |

### Open follow-ups

- What the pod bay's 3 shared outgoing targets (`0x506d40`/`0x506c20`/`0x506ce0`) lead to -- not traced.
- Whether the clip-name/stage mismatches reflect deliberate asset reuse or a wrong stage-index assumption -- not resolved.

## Pass 81 -- The pod bay's 3 exits mapped: CD Player room, ITAC, and Mission Select Map (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| Pod bay is a 3-way hub: `0x506c20` (ITAC vestibule), `0x506d40` (CD Player room), `0x506ce0` (Mission Select Map launcher) | 5 | All 3 targets read directly and traced one hop further. |
| `0x506c20` -- a 3rd copy of the ITAC vestibule junction (pod-bay-arrival variant) | 5 | Identical hotspot rect and 3 outgoing targets to Pass 73's corridor-arrival copy (`0x506b30`); differs only in arrival clip. |
| **CORRECTION**: "cd" = the CD Player room, not "cargo deck" | 5 | `0x506d40`'s `pMoviePathAlt` is `rel_cdloop.bik`, the same ambient loop `RunReliantInductionTour`'s stage 2 used (Pass 79); cross-confirmed via `RunCdPlayerPropScreen` (Pass 68) and a dedicated `nRoomType==9` trigger node found inside this room's own branching. |
| `nRoomType == 9` = launch `RunCdPlayerPropScreen` | 5 | Confirmed via disassembly at `RunShipInteriorVRLoop`'s room-dispatch (`0x43ad91`: `CMP AX,0x9; JNZ <skip>; CALL RunCdPlayerPropScreen`). 7th confirmed `nRoomType` value. |
| `0x506ce0`'s single target (`0x506d10`) is a 3rd bunkroom-arrival-variant copy | 5 | Shares the exact same 3 outgoing targets as Pass 73's bunkroom node; also matches Pass 73's already-confirmed "next room after mission map" hardcode. |

### Open follow-ups

- `nRoomType == 8` -- not seen/confirmed in any node read so far.
- The CD room's further 4-way branching (`0x506d70`'s targets) -- not traced.
- `nRoomType` 1/3/6's exact semantics -- still only structurally sketched.

## Pass 82 -- `nRoomType == 6` identified: `RunMedalCaseScreen`, correcting Pass 64's `PlayerProfile` fields (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `RunMedalCaseScreen` (0x4362f0, was `FUN_004362f0`) -- the player's medal locker display, `nRoomType==6` | 5 | Self-identified via its own "MedalDisplay resource" assertion strings. Locker-open animation -> loads up to 6 medal + 6 bar sprites -> per-slot hotspot poll (supports screenshot save) -> locker-close animation. Shares `RenderBriefingHubFrame` as its per-frame callback with the briefing hub room. |
| **CORRECTION** (sharpened, not reversed): `PlayerProfile.reserved1[6]`/`reserved2[6]` = medal-earned / bar-earned flags | 5 | Up from Pass 64's confidence-2 "which hub objects" mapping. Directly gates which `rmedal_N.spr`/`rbar_N.spr` sprite loads in `RunMedalCaseScreen`. |
| Ties Pass 59's early `.spr` RLE-format decode (verified against `SL_Medal_Case.webp`) to the actual in-game render function | 5 | Closes the loop between early asset-level work and the later room-graph/`profile.bin` work. |

### Open follow-ups

- Which VR room node(s) have `nRoomType==6` -- not traced from the room-graph side.
- The 6-vs-11-hotspot Reliant/Yamato medal-case layout difference -- not mapped slot-by-slot.
- `nRoomType` 1/3's exact semantics -- still open.

## Pass 83 -- The `nRoomType == 6` (locker/medal case) room nodes traced (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| Two Reliant `VRRoomNode`s carry `nRoomType==6` directly: `0x506e90` (corridor entry) and `0x506ec0` (lock-lid-up entry) | 5 | Unlike the CD room (Pass 81), the locker room node itself IS the trigger -- no separate sub-node needed. Found via `search_byte_patterns` on the arrival clip's string address. |
| `0x506e90` sits between the CD room and the bunkroom in the Reliant graph | 5 | Confirmed reachable from `0x506d70`'s (CD room) own targets, one of which (`0x506e90`) was left untraced in Pass 81. |
| Post-medal-case hardcoded destination confirmed via disassembly | 5 | `RunShipInteriorVRLoop`'s `nRoomType==6` branch (`0x43ac8a`) hardcodes `0x506f20` (Reliant) / `0x50b3a8` (Yamato), matching Pass 73's earlier note. `0x506f20` is a 4th confirmed bunkroom arrival-variant copy. |

### Open follow-ups

- `0x506ec0`'s predecessor (which hotspot leads to the lock-lid-up entry variant) -- not traced.
- `0x506ef0` (target of the lock-lid-up entry copy) -- not read.
- The Yamato's `0x50b3a8` locker-room equivalent -- not read.

## Pass 84 -- Campaign-outcome branch table's filenames resolved (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| Campaign-outcome -> filename table fully resolved (13 entries, `InitializeMissionGameplay`) | 5 | Applied `LoadSquadronRoster`'s prototype (already set from a prior session) and re-decompiled the consumer -- all 13 filenames now directly visible, each independently verified via `read_memory`. Yes/no `LoadSquadronRoster`-call pattern matches Pass 35's independently-derived table exactly. |
| **Refinement (not a hard correction)**: these are `X_frm.shp` files, not `.sro` files | 3 | Pass 35 called `FUN_004a44d0` an `.sro`-format parser (confidence 3, filename unconfirmed). Every resolved filename actually uses `.shp`. Two open readings: `_frm` = formation data sharing the generic tagged-chunk container with mesh `.shp` files, or "roster" and "formation" describing the same data from two angles. Not resolved definitively; no rename applied. |
| Attempted to re-open the `.dte` interpreter/named-command-table relationship (open since Pass 32) | 0 (still unresolved) | Byte-pattern and instruction-operand searches for the command table's base address found zero references, consistent with 3 prior dedicated passes (27-32). Likely needs live debugging, same conclusion as the Pass 70 renderer `+0x50` mystery. |

### Open follow-ups

- Whether `_frm.shp` files share the exact tagged-chunk format with regular mesh `.shp` files (Pass 55/56) -- not compared.
- The `.dte` interpreter/named-command relationship -- still open, likely needs live debugging.

## Pass 85 -- Real `.dte` mission files decoded against ground truth (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `LoadMissionFile`'s directory format fully validated against 4 real mission files | 5 | Applied `set_function_prototype` to `ReadMissionDirectoryEntry` to expose all 4 hidden args at its call sites -- confirms constant buffer base across all 27 calls, matching the Pass 7 format exactly. |
| **CORRECTION**: the directory entry's low-16-bit field is NOT a stable type/record-ID | 4 | Varies unpredictably per file for the same table slot across 4 real missions (entry 0: `0x2380`/`0x3d50`/`0x3666`/`0x14d6`) -- a real type tag would stay constant. More likely a per-file checksum/version stamp; not resolved. |
| **New structural finding**: `.dte` is a fixed-size-per-table template, not densely packed | 5 | Every directory entry's resolved offset and the total decompressed size (850919 bytes) are byte-identical across all 4 real mission files checked. |
| Entry 0 (`DAT_00525fa8`) identified: the mission's object/name string table | 5 | Real content verified across 3 mission files: ship classes, named capital ships, named trigger instances, patrol routes, navpoints, wreckage markers, AI pilot-behavior file refs, speech-cue file refs. |

### Open follow-ups

- The other 26 tables' internal record layouts -- only locations confirmed, contents not decoded.
- Whether entry 0's strings are indexed by the other 26 tables -- not cross-referenced.
- The directory header's low-16-bit field's real meaning -- not resolved.
- Whether the 4 per-entry flag bits ever vary (all observed as `0xf` so far) -- not checked widely.

## Pass 86 -- Entry 3 decoded: the mission's object spawn table (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| `SpawnObjectRecord` layout (76 bytes, entry 3 / `DAT_0052951c`, 512-slot fixed array) | 5 | Stride confirmed independently via `GetObjectIndexFromPointer`'s `(ptr-base)/0x4c` in real game code. Fields: `objectID` (i32), `nameIndex` (i32, into entry 0's string table), `position[3]` (f32 world XYZ), `position2[3]` (duplicate of position), `tail[10]` (i16, partially understood). |
| Real content decoded: mission1.dte's full 118-object layout | 5 | Every name resolves to sensible, legible mission content (enemy squadron with flight-position callsigns, capital-ship convoy, Soviet strike group, camera rigs, patrol routes, snap-points) -- zero garbage across all 118 real records. |
| `tail[10]` sub-fields | 2 | Loose patterns only: `tail[2]/[3]` often equal (heading?), `tail[4..7]` always `-1` (sentinel), `tail[8]/[9]` always equal to each other and vary per record (group/squadron ID?). Not fully mapped. |

### Open follow-ups

- `position2`'s purpose (identical to `position` in every record checked).
- `tail[10]`'s remaining fields.
- Whether an explicit per-mission object count field exists elsewhere in the directory.
- Entries 1, 2, 4-26 remain undecoded.

## Pass 87 -- CORRECTION: entry 3's directory tag is the object count, not a checksum (2026-09-10)

| Name | Confidence | Notes |
|---|---:|---|
| **CORRECTION**: entry 3's header tag (`DAT_00529504`) is the authoritative populated-object COUNT | 5 | Found via `FUN_0045cbc0` (one of `LoadMissionFile`'s finalization passes): its object-table walk uses `DAT_00529504` directly as the loop bound. Confirmed across 4 real files (118/299/279/23), all sensible small counts. |
| **CORRECTION**: Pass 86's zero-padding-scan heuristic for the object count was wrong | 5 | `mission30.dte` proves it: tag=23, but non-zero *stale editor garbage* (truncated fragments of earlier real names) continues for ~300+ more slots. The zero-scan coincidentally matched for missions 1/2/5 only. The directory tag is the only reliable source. |
| `mission30.dte` identified as a flight-training tutorial mission | 4 | Real objects: `training_hoop 1-9`, `Fly to Point`, `Bug Out Point`, `Enemy Drone`, `Back to Yamato` -- confirms this mission takes place aboard the Yamato. |

### Open follow-ups

- Whether the header-tag-as-count role applies to any of the other 26 tables, or is unique to entry 3.
- Entry 2's role (unconfirmed).
- Entries 1, 4-26 remain undecoded.
