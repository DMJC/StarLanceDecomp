# Star Lancer reverse-engineered functions

Implementation-oriented notes derived from `Lancer.exe` (loaded in Ghidra as
project `Starlancer`, 32-bit x86, MSVC-compiled, `x86:LE:32:default`).
Names are descriptive rather than recovered source symbols unless an
embedded string literal or debug path proves otherwise. Every entry here
should also have a row in `confidence_db.md` — that file is the index,
this one is the prose detail per METHODOLOGY.md.

This file starts from nothing as of 2026-09-07 (see `confidence_db.md`'s
status note for why — no pre-existing corpus for this project). Built
outward from the program entry point.

## `mainCRTStartup` (`0x004d1210`)

### Signature

```c
void mainCRTStartup(void);
```

### Behavior

Standard MSVC CRT process entry point. Recognized by shape (this exact
sequence appears in effectively every MSVC-linked Windows executable of
this era), not deeply investigated function-by-function:

1. Sets up an SEH exception frame.
2. Calls `GetVersion()` and stashes the packed OS version into globals
   (`_DAT_006235c8`/`_DAT_006235c4`/`_DAT_006235c0`/`_DAT_006235bc`).
3. Heap init (`FUN_004d51c8`) and low-I/O init (`FUN_004d2b56`), each
   aborting via `FUN_004d133d` (a CRT fatal-error/`_amsg_exit`-style
   routine) on failure.
4. argv/environ setup (`FUN_004d606a`, `GetCommandLineA`, `FUN_004d6ab0`,
   `FUN_004d6863`, `FUN_004d67aa`), global constructors (`FUN_004d04c0`,
   almost certainly `_initterm` over the `.CRT$XC*` table).
5. `GetStartupInfoA` to resolve the actual `nCmdShow`.
6. Calls `WinMain(GetModuleHandleA(NULL), NULL, cmdLine, nCmdShow)`.
7. Passes `WinMain`'s return value to `FUN_004d04ed` (CRT `exit()`), which
   does not return.

### Known use

Sole caller of `WinMain`. Nothing calls this except the OS loader (it's
the PE entry point).

## `WinMain` (`0x004a8b10`)

### Signature

```c
int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                    LPSTR lpCmdLine, int nCmdShow);
```
(third and fourth CRT-supplied parameters were optimized to a 3-arg
`__stdcall`-shaped decompile — `hPrevInstance` is read but never used, its
slot subsumed; treat the signature above as the semantic one.)

### Confirmation

Two independent pieces of evidence: (1) called from `mainCRTStartup` with
the CRT's canonical `(hInstance, hPrevInstance, cmdLine, showCmd)`
convention, immediately before an `exit()`-style tail call; (2) an embedded
string literal used purely as a memory-allocation debug tag,
`"C:\lancer\game\winmain.cpp"` (at the `SR_MEM_allocate(0x96000, ..., 0xc0b)`
call deep in the function body), which is the original source file's path —
about as strong a confirmation as static analysis gets without a symbol
table.

### Behavior — bootstrap prologue (well understood, this session)

1. **Single-instance check**: `CreateMutexA(NULL, TRUE, "StarlancerRunning")`
   (mutex name from `s_StarlancerRunning_00509a98`); if
   `GetLastError() == ERROR_ALREADY_EXISTS` (0xb7), finds the existing
   window (`FindWindowA` on class `"WARTHOG_STARLANCER"`, see
   `RegisterGameWindowClass`) and either brings it to the foreground
   (`SetForegroundWindow` + `PostMessageA(WM_SYSCOMMAND, SC_RESTORE)`) or,
   if no window is found, shows a "Game already running" `MessageBoxA`.
   Otherwise proceeds to full startup.
2. **Core init**: `SR_MEM_init()` (the game's own custom allocator —
   imported, not defined in this binary), a `DebugLog_Stub` call opening
   a `"c:\dbout.txt"`-named debug log (no-effect in this build), then
   `RegisterGameWindowClass()` (same address, 0x4aa8e0, as the function
   documented below — the decompiler doesn't surface the implicit
   `__fastcall` ECX argument at this call site) which gates almost the
   entire rest of the function behind `if (iVar5 != 0)`: the whole game
   bails out immediately if window-class registration fails.
3. **DirectX version gate**: `FUN_004bff10`-logged as `"DirectX Version
   %03x"`; if the detected version is below `0x700` (DirectX 7), shows an
   error message box and skips straight to cleanup — the game requires
   DirectX 7+.
4. **Command-line parsing**: manually scans `lpCmdLine` for `-`-prefixed
   switches. Recognized switches (by `_strncmp` against literal strings,
   exact text not yet extracted from the string table — only lengths seen:
   4, 4, 3, and a `-credits` (7 chars) and `-greyscale` (9 chars) both
   explicitly named): one sets a numeric value via `FUN_004cf460`
   (`atoi`-shaped) into `DAT_00509544` with a variable-width digit-count
   skip (looks like a `-mission<N>` or similar numeric-suffixed flag),
   `-credits` sets `DAT_00595d6c=1`, `-greyscale` sets two globals to
   `0x20000`.
5. **Path setup**: builds `ships\`, `missiles\`, `guns\`, `lights\`,
   `add_ons\`, and `starlancer.ini` paths relative to the executable's
   directory (via `SafeFormatString`), matching the directory listing seen
   directly in `gamedata/StarLancer/` (`SHIPS`, `MISSILES`, `GUNS`,
   `ADD_ONS`, `starlancer.ini` — case-insensitive match on a
   case-preserving filesystem, consistent).
6. **Resource load**: loads a resource file via `FUN_004c7e20` (fatal
   error `"main init: load failed on resource"` on failure, code `0x4fd`)
   — almost certainly `RESOURCE.HOG` (present in the game directory) but
   not yet directly confirmed by a path string read.
7. **INI config load**: reads `starlancer.ini`'s `[Device]` section
   (resolution width/height default `0x280`×`0x1e0` = 640×480, windowed
   flag, gamma default 100, texture/geometry detail defaults, lightmap
   toggle), `[Multiplayer]` section (protocol, IP address, modem number,
   comm port), and `[Sound]` section (3D provider, FX/music/speech/master
   volume defaults) via repeated `GetPrivateProfileIntA`/
   `GetPrivateProfileStringA` calls against the built INI path. Matches
   `starlancer.ini`'s presence in the game directory directly.
8. **Display-mode cache**: `FUN_004a89c0` loads `dmodes.bin` (see
   `confidence_db.md`'s Data formats section) to decide whether to trust a
   cached device-capability list or force a redetect.

### Behavior — post-bootstrap state machine (NOT yet understood)

Past the INI/display-mode load, `WinMain` becomes an enormous
(~400-line) `goto`-heavy state machine driven by globals like
`DAT_00562dc8` (looks like "current mission index" — compared against
literal mission numbers `0x19`=25, `3`, `0x1d`=29, `0xfb`=251 with a
matching `mission%d.dte`/`mission251.dte`/`mission311.dte` path pattern),
`DAT_005883fa`/`DAT_0058832c` (player slot / player count in a
multiplayer context — arrays indexed up to 8, matching an 8-player
multiplayer cap), `DAT_005d608c` ("zone check" result, branches on
values 1-4 doing `DAT_00582e8c`="deathmatch flag" setup), and
`DAT_005dc1e8` (looks like a host/client or single/multiplayer role flag
— gates very different code paths, e.g. only the `==1` path iterates
`DAT_005db83c` "number of players" doing per-player setup).

This is explicitly **not** understood yet — it was skimmed while tracing
the bootstrap sequence, not read line-by-line. It is the largest single
remaining unknown reachable directly from the program entry point and is
the natural next subsystem to tackle (see `dependency_graph.md`'s
coverage note and `confidence_db.md`'s open follow-ups).

## `RegisterGameWindowClass` (`0x004aa8e0`)

### Signature

```c
bool __fastcall RegisterGameWindowClass(HINSTANCE hInstance);
```

### Behavior

Builds and registers a `WNDCLASSA`: style `0xb`
(`CS_VREDRAW|CS_HREDRAW|CS_DBLCLKS`), `lpfnWndProc = WindowProc`,
`hIcon = LoadIconA(hInstance, MAKEINTRESOURCE(0x6f))`, default arrow
cursor, `hbrBackground = GetStockObject(BLACK_BRUSH)` (stock object 4),
class name `"WARTHOG_STARLANCER"`. Returns whether `RegisterClassA`
succeeded. Also stashes `hInstance` into `DAT_005d561c` as a global.

### Known use

Called once, early in `WinMain`'s success path (guarded behind the
DirectX version check having passed).

## `WindowProc` (`0x004a8300`)

### Signature

```c
LRESULT CALLBACK WindowProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);
```

Not previously a defined function in the Ghidra project (only reachable
via the `&LAB_004a8300` function-pointer literal in
`RegisterGameWindowClass`) — created as a function this session.

### Behavior

Standard game window procedure, dispatching on `msg`:

- `WM_DESTROY` (2): `ReleaseCapture()` + `PostQuitMessage(0)`.
- `WM_ACTIVATE` (6): if the window has a valid engine-side handle
  (`DAT_00588730`, checked against a `!=0` and a flag at `+0x15f8`) and
  the low word of `wParam` is `WA_INACTIVE` (0), sets
  `DAT_00595d74=1` and calls `FUN_004a8260` (deactivation hook, not yet
  decompiled); otherwise calls `FUN_004bd780` (activation hook, not yet
  decompiled).
- `WM_PAINT` (0xf): `BeginPaint`/`EndPaint` with no drawing (game renders
  via its own D3D/DirectDraw surface, not GDI).
- `WM_SETCURSOR` (0x20): calls `FUN_004a8110` unless a global flag
  `DAT_00509548` is set.
- `WM_CHAR` (0x102): feeds a 100-entry keystroke ring buffer at
  `DAT_005d547c`, indexed by `DAT_00595d70`, with an optional filter
  against a 9-byte exclusion list at `DAT_0050954c` once a mode flag
  (`DAT_005d6088`) is set.
- `WM_SYSCOMMAND` (0x112), masked to the low nibble-cleared command:
  - `SC_SIZE`-family (`0xf010`): swallowed (returns 0) unless
    `DAT_005e8148` is set.
  - `SC_CLOSE`-family? (`0xf060`): sets `DAT_005d60bc=1` (looks like a
    "close requested" flag) and swallows the message.
  - `SC_RESTORE` (`0xf120`): if the engine window handle
    `DAT_00588730` is non-null, clears a flag bit
    (`*(handle+0x34) &= ~0x40`); if not already restored
    (`DAT_005d60b8==0`), calls `SetWindowLongA(GWL_STYLE, DAT_00595d78)`
    + `OpenIcon` + `FUN_004a8110`, then falls through to
    `FUN_004bd780`.
- `WM_ENTERMENULOOP`/`WM_EXITMENULOOP`/`WM_ENTERSIZEMOVE`/
  `WM_EXITSIZEMOVE` (`0x211/0x212/0x231/0x232`): sets
  `DAT_005ddd28=1` and calls `FUN_004bd780`.
- Self-posted `WM_USER` (`0x400`, `pHVar3 == hWnd`-gated): recomputes
  `DAT_005ddd28` from `GetActiveWindow()`/`IsIconic()` and re-posts
  itself — this is a polling mechanism for window-active state, driven
  by the message loop rather than a timer.
- Everything else (including the fallthrough at the bottom of the
  `0x211..0x400` range) calls `DefWindowProcA`.

### Known use

Assigned as `WNDCLASSA.lpfnWndProc` in `RegisterGameWindowClass`; invoked
by the Windows message dispatcher, not called directly by game code.

## `GetVersionInfoAndInstanceTitle` (`0x004a8160`)

### Signature

```c
void __fastcall GetVersionInfoAndInstanceTitle(char *outBuffer);
```

### Behavior

Two unrelated things happen in sequence, and the second one clobbers any
effect of the first:

1. Reads the running EXE's own Win32 version resource
   (`GetFileVersionInfoSizeA`/`GetFileVersionInfoA` on the literal string
   `"lancer.exe"`, then `VerQueryValueA(..., "\\StringFileInfo\\")`) to
   extract an 8-byte language/codepage-ish value, builds a
   `"\StringFileInfo\<value>\FileVersion"` query string via
   `SafeFormatString`, queries that, and if successful formats
   `"StarLancer (BETA) Build <version>"` into `outBuffer` — this whole
   block is skipped if any `VerQueryValueA` call fails.
2. **Unconditionally**, regardless of step 1, copies the literal string
   `"Microsoft StarLancer"` into `outBuffer`, overwriting whatever step 1
   wrote.

### Known use

Called once in `WinMain`, immediately before
`FindWindowA("WARTHOG_STARLANCER", outBuffer)` for the single-instance
"already running" check — `outBuffer` (the caller's `local_88`) ends up
being window-title text for the `FindWindowA` lookup, meaning the
build-version formatting work in step 1 is currently provably dead code
in this binary. Flagged as a real quirk, not a decompiler artifact, since
both writes target the exact same output pointer with no intervening
branch that could explain it as reachable-but-conditional.

## Display-mode/device-cache loader (`0x004a89c0`)

### Signature

```c
int LoadDisplayModeCache(void);  // tentative name, not yet applied in Ghidra
```

### Behavior

Opens `dmodes.bin` (via `FUN_004d02ef`, an `fopen`-with-mode-`0x40`-ish
wrapper) relative to the current directory. Reads a `u32` magic and
checks it equals `0x102` (fails → return 1, "need full redetect"). Reads
a `u32` mode count into `DAT_005d5620`, then that many 16-byte records
into `DAT_005d5750`. If `DAT_005d60c4==0` (a "trust cache" flag,
presumably cleared by a prior `-` command-line switch or an earlier
session's redetect), cross-checks the cached mode count/records against
the live-enumerated display mode list (`FUN_004cc520` for the count,
comparing four `int`-sized fields per 16-byte record) — any mismatch
returns 2 ("cache stale"). On full success (or if the trust-cache flag
skipped the cross-check), reads a SECOND count field into
`DAT_005d5478` and a second, much larger table (0x144c bytes per record)
into `DAT_00595da0`, then returns 0.

### Data format cross-reference

Directly checked the real `gamedata/StarLancer/dmodes.bin`'s first 16
bytes: `02 01 00 00 01 00 00 00 02 10 00 00 d8 68 00 00`. This confirms
`magic=0x00000102` (matches the `!=0x102` failure check exactly) and
`mode_count=1`, followed by one 16-byte record
(`0x00001002, 0x000068d8, 0, 0`). The record's individual field meanings
are NOT determined — the values don't read naturally as a
width/height/bpp/refresh tuple, so no per-field names are recorded pending
further evidence (e.g. finding the code that WRITES this file during
detection, which would show field-by-field construction order).

### Known use

Called once from `WinMain`, gating a 3-way branch: 0 → proceed silently,
1 → run the "not enough… DirectX Version" error-and-fallback path (shares
a branch target with the earlier DirectX-version check), 2 → tear down
and exit (`CloseHandle`+`DestroyWindow`, then fall through to cleanup).

---

# Second pass (2026-09-08): SurrenderLib diagnostics + remaining bootstrap helpers

## `SR_printf` (`0x004c3640`)

### Signature

```c
int SR_printf(const char *format, ...);
```

Real name confirmed directly: the function's own null-format-string guard
clause passes the literal string `"SR_printf: Null format string
pa[ssed]"` to `ReportAssertionFailureEx` — a function naming itself in its
own error text, about as strong as static confirmation gets.

### Behavior

The engine's (SurrenderLib's) central logging primitive:

1. If `format` is NULL, calls `ReportAssertionFailureEx` (fatal).
2. Formats into a fixed global buffer (`DAT_005e6750`) via `FUN_004d05e0`
   (an unidentified vsprintf-shaped formatter — not itself decompiled).
3. Always forwards the formatted text to `DebugLog_Stub` — a no-op in
   this release build (see below), so this step has no observable effect
   in the shipped binary.
4. If an output-redirect callback is installed (`DAT_005e82e4`, function
   pointer), calls it with no visible arguments (likely takes the global
   buffer implicitly or via a fixed calling convention the decompiler
   didn't capture); otherwise falls back to `OutputDebugStringA`.
5. Returns the formatted string's length.

### Known use

Called by `ReportAssertionFailure`/`ReportAssertionFailureEx` to actually
emit their assembled fatal-error text before crashing. Given this is
described as "the" printf-equivalent for the whole engine, it is very
likely called from many more places across the 2434-function binary that
haven't been examined yet — worth re-checking its caller list as more of
the binary is covered.

## `ReportAssertionFailure` (`0x004c37b0`, 3-arg) / `ReportAssertionFailureEx` (`0x004c3710`, 4-arg)

### Behavior

SurrenderLib's fatal-error/assert-and-crash pair, confirmed by two
independent embedded source-path strings:
`C:\lancer\surrender\surrenderlib\...` (this is the engine's real
internal library name — "Surrender" — matching the `SR_` prefix seen on
imports like `SR_MEM_init`/`SR_MEM_allocate` and the
`SR_driver_enumcards` export).

Both functions:

1. Allocate a 1KB scratch buffer via `SR_MEM_allocate`.
2. If a corresponding callback is installed (`DAT_005e82e8` for the
   3-arg form, `DAT_005e82ec` for the 4-arg form), invoke it — this looks
   like a caller-installable "do cleanup before we crash" hook.
3. Format `"Debug assertion in module %s line %d ..."` (exact literal
   text and full argument list not extracted from the string table this
   pass) via `SafeFormatString`.
4. Route the message through `SR_printf`.
5. Show a `MessageBoxA` titled `"FATAL: SR Assertion Failed"` on the
   active window.
6. Free the scratch buffer.
7. Execute `swi(3)` — x86 `INT 3` (`__debugbreak`) — which does not
   return; this is a deliberate crash/debugger-trap, not a normal error
   return path.

### Known use

`ReportAssertionFailureEx` is called directly from `WinMain`'s resource
and MSSpeech load-failure paths (`"main init: load failed on resource"`,
code `0x4fd`; `"HudInit: load failed on msspeech"`, code `0x5f8`).
`ReportAssertionFailure` (3-arg) is also self-called by `SR_printf`'s
own null-format-string guard. Given the naming ("Debug assertion") this
is almost certainly SurrenderLib's general-purpose `assert()`-equivalent,
reached from many more call sites throughout the binary that haven't
been surveyed yet.

## `SetAssertionCallback` (`0x004c3620`) / `SetAssertionCallbackEx` (`0x004c3630`)

Trivial one-line setters (`DAT_005e82e8 = param; return;` and
`DAT_005e82ec = param; return;` respectively), confirmed by direct xref
to be exactly the globals `ReportAssertionFailure`/`ReportAssertionFailureEx`
conditionally invoke before crashing. Their own callers are not yet
traced — it's unknown who installs these hooks or when.

## `CreateGameWindow` (`0x004a85a0`)

```c
void CreateGameWindow(void);
```

Builds the window title via `GetVersionInfoAndInstanceTitle`, then calls
`CreateWindowExA(0, "WARTHOG_STARLANCER", title, 0x800000, 0, 0, 640, 480,
NULL, NULL, hInstance, NULL)`, storing the resulting `HWND` in
`DAT_005d60b0` (the same global `WinMain`'s single-instance check reads).
Immediately zeroes the window's `GWL_STYLE` afterward — the real
windowed/fullscreen style is applied later, once `starlancer.ini`'s
`[Device]` settings are known.

## `LoadLanguageStrings` (`0x00490dc0`)

```c
void LoadLanguageStrings(void);
```

Loads `LANGUAGE.DLL` (present in `gamedata/StarLancer/`) via
`LoadLibraryA`. Enumerates every string-table resource it contains by
calling `LoadStringA` with an incrementing resource ID starting at 1
until a call returns 0 (no more strings) — this is a full-enumeration
pattern, not a fixed known-ID list. Allocates one contiguous buffer
(`SR_MEM_allocate`, tagged `C:\lancer\game\language.cpp`) sized to hold
every string's bytes plus null terminators, copies them all in, and
builds a parallel `int[]` of offsets into that buffer (effectively a
`char*[]`-equivalent lookup table, one entry per string ID).

Separately, reads `LANGUAGE.DLL`'s own Win32 version resource (same
`GetFileVersionInfoA`/`VerQueryValueA` pattern as
`GetVersionInfoAndInstanceTitle`) and scans a table of 5-byte records at
`DAT_0050318c` (repeatedly incrementing a pointer by 5 and comparing 4
bytes via `FUN_004daef0` against the version string) up to some bound
(`0x5031a9`), storing a matching index into `DAT_00563a14`. **This
trailing scan's purpose is not understood** — plausibly a
language-DLL-version compatibility check, but not confirmed; flagged as
an open follow-up rather than guessed at further.

### Known use

Called once, early in `WinMain`'s success path (right after
`RegisterGameWindowClass`/`CreateGameWindow`, before the DirectX version
check completes). No other callers found yet.

## `DetectDirectXVersion` (`0x004778c0`)

```c
void __fastcall DetectDirectXVersion(int *pddVersionOut, int *pOsPlatformOut);
```

(Parameters are passed via the implicit `__fastcall` `ECX`/`EDX`
registers, which the decompiler doesn't surface at the `WinMain` call
site — inferred from the function's own parameter usage, not from a
visible argument list at the call.)

### Behavior

A capability-detection ladder that writes an increasing "tier" value
into `*pddVersionOut` as each successive DirectX feature check succeeds,
bailing early (leaving a lower tier value) the first time something
fails:

1. `GetVersionExA` — writes `*pOsPlatformOut` (1=NT, 2=9x) and rejects
   Windows 9x below version 4 outright (`*pddVersionOut = 0`). On NT4
   specifically (not later NT), caps out at DirectInput availability
   (tier `0x300`) without ever trying DirectDraw — presumably an
   NT4-specific compatibility carve-out.
2. `LoadLibraryA("DDRAW.DLL")` + `GetProcAddress("DirectDrawCreate")` +
   call it → tier `0x100`.
3. `QueryInterface` to a second DirectDraw interface (likely
   `IDirectDraw2`) → tier stays `0x100` on success (no tier bump coded
   for this specific step, just a capability gate).
4. `LoadLibraryA("DINPUT.DLL")` + `GetProcAddress("DirectInputCreateA")`
   → tier `0x300`.
5. Builds a `DDSURFACEDESC`-shaped structure (`dwSize=0x6c`, `dwFlags=1`
   i.e. `DDSD_CAPS`, caps `0x200` i.e. `DDSCAPS_PRIMARYSURFACE`), calls
   `SetCooperativeLevel` (vtable `+0x50`) then `CreateSurface` (vtable
   `+0x18`) → tier `0x500` on success.
6. `QueryInterface`s the created surface to a further interface → tier
   `0x600`.
7. `CoCreateInstance` of a DirectMusic CLSID → tier `0x601`.
8. `GetProcAddress(hDDrawDll, "DirectDrawCreateEx")` existing AND
   succeeding when called → tier `0x700` (DirectX 7 — the actual
   minimum `WinMain` requires; every step above 0x700 in the ladder is
   effectively just "DirectX 7 is present").

Every failure path calls `OutputDebugStringA` with a specific
`"Couldn't <thing>"` message (these are all present as string literals
and give a clean, readable trace of exactly which DirectX component was
missing) before returning the tier value reached so far.

### Known use

Called once from `WinMain`, immediately before the
`"DirectX Version %03x"` debug log line and the `< 0x700` fatal-error
branch. The returned tier's exact numeric thresholds (`0x700` = DX7)
match `WinMain`'s own check exactly, which is the strongest evidence this
function's return value IS the "DirectX version" `WinMain` logs.

## `OpenBigFile` (`0x004c7e20`) / `CloseBigFile` (`0x004c7f20`)

```c
BigFileHandle *OpenBigFile(const char *path);
void CloseBigFile(BigFileHandle *handle);
```

Real subsystem name confirmed: both allocate their handle struct
(`SR_MEM_allocate`) tagged with the embedded debug path
`C:\lancer\game\bigfile.cpp`.

### Behavior — `OpenBigFile`

1. Allocates a 0x24-byte handle struct.
2. Opens `path` via `FUN_004d02ef` (an `fopen`-with-mode wrapper already
   seen used by the `dmodes.bin` loader) — stores the `FILE*`-equivalent
   at handle offset 0.
3. ALSO opens the same path as a raw Win32 `HANDLE` via `CreateFileA`
   (offset 1) — the handle keeps both a buffered stream handle and a raw
   Win32 handle simultaneously; their respective roles (one likely for
   sequential reads via the CRT wrapper, the other perhaps for
   memory-mapping large assets later) aren't determined yet.
4. Reads a 16-byte block into handle offset 2 (fields not decoded).
5. Reads a 4-byte magic (`FUN_004c7df0`, a dedicated "read one int"
   helper) and checks it equals `0x42494946`/`0x42494746`-shaped FourCC
   spelling "BIGF" — fails (frees handle, returns NULL) if not.
6. Reads two more header ints (offsets 7 and 8) — the second is used as
   a byte count to allocate and read a directory/TOC block (offset 6).

### Behavior — `CloseBigFile`

Symmetric teardown: closes the buffered stream (`FUN_004d013c`, the
`fclose` wrapper), frees the TOC block if allocated, closes the raw
`HANDLE` if opened, frees the handle struct itself.

### Known use

`OpenBigFile` is called from `WinMain` on the main resource archive
(fatal error `"main init: load failed on resource"` on failure) and
again later for an MSSpeech-related resource (`"HudInit: load failed on
msspeech"`) — these are two SEPARATE archive files, not the same handle
reused. Matches real files present in the game directory: `RESOURCE.HOG`
/ `Resource.FAT` (and the CD-image containers `cd1.hog`/`cd2.hog`).
Individual TOC-entry layout is not yet decoded — this is purely the
container open/close lifecycle.

## `ShowEulaDialog` (`0x004aacf0`)

```c
int ShowEulaDialog(void *param);
```

Hides the cursor, loads `EBUEULA.DLL` (present in the game directory),
resolves and calls its exported `EBUEula` function (name confirmed
directly via the `GetProcAddress` literal string) with a registry-path
string, an app-name string loaded from string resource ID 1, a fixed 0,
and the caller's `param`. Restores the cursor and frees the library
before returning the EULA dialog's result.

## `InitializeHighResTimer` (`0x004a6e70`)

```c
void InitializeHighResTimer(void);
```

Guarded one-shot init (flag `DAT_00595c58`): zeroes an 80-byte global
block, then calls `timeBeginPeriod(1)` to request 1ms multimedia timer
resolution. Nothing more to it.

## `LoadInstallPathsFromRegistry` (`0x004ad480`)

```c
void LoadInstallPathsFromRegistry(void);
```

Opens `HKLM\Software\Microsoft\Microsoft Games\<subkey>` (exact subkey
name not extracted from the string table this pass — the visible string
fragment is `"Software\Microsoft\Microsoft Gam..."`, truncated in the
decompile output) and reads `InstallType`, `CDPath`, and
`InstallationDirectory` values, building two path globals
(`DAT_005d60ec` = CD path, `DAT_005d6b38` = install dir) each with a
trailing backslash appended via an inlined strcat-equivalent loop. If
`InstallType == '3'`, additionally populates two more path globals
(`DAT_005d6a28`, `DAT_005d6928`) from the install directory — plausibly
per-disc paths (the game directory does contain real `cd1`/`cd2`
subdirectories), but this specific mapping is NOT confirmed, just
plausible. If the registry key is missing entirely, falls back to
`GetCurrentDirectoryA` and populates all four path globals from that
single directory instead.

### Known use

Called once from `WinMain`'s bootstrap, before the resource/BigFile
load — the paths it resolves are presumably what later path-building
(`SafeFormatString`-based `%sships\` etc.) is relative to, though that
connection hasn't been traced with an xref yet.

## `LoadPlayerProfile` (`0x004751b0`)

```c
void LoadPlayerProfile(void);
```

Zeroes a large block of profile/campaign-progress globals and sets
several defaults, most notably **`DAT_00562dc8 = 1`** — this
independently corroborates `WinMain`'s own heavy use of the same global
as "current mission index" (two functions treating the same address the
same way, from different parts of the binary, without either one
calling the other — real corroborating evidence, not just a repeated
guess).

Attempts to open `profile.bin` (present in the game directory). On
success: copies the loaded data into the zeroed globals region and
reopens the file a second time (via a different global file-handle slot)
to read a 208-byte (`0xd0`) fixed record via `FUN_004d0003` (an `fread`
wrapper) into `DAT_00562cf8` — the record's own field layout is not
decoded. On failure to open at all: falls back to
`FUN_00475390()` (not decompiled yet — likely
`CreateDefaultProfile`/`SaveProfile`).

### Known use

Called once from `WinMain`'s bootstrap sequence.

## `EnumDisplayCardsFromDriver` (`0x004cc520`)

```c
int __fastcall EnumDisplayCardsFromDriver(const char *driverDllPath,
                                           void *param2, void *param3);
```

Generic "load a display-driver DLL, call one specific export, unload"
wrapper: `LoadLibraryA(driverDllPath)`, resolves and calls the export
named `"SR_driver_enumcards"` (name confirmed directly via the
`GetProcAddress` literal string — also confirms the engine's `SR_`
naming convention extends to driver-side exports, not just the main
EXE), then `FreeLibrary`s the DLL and returns the call's result.

### Known use

This is the "enumerate the live display modes" step the `dmodes.bin`
cache loader (documented above) calls to cross-check its cached mode
list for staleness — resolves a dependency-graph gap left open in the
first pass.

---

# Third pass (2026-09-08): first dive into `WinMain`'s state machine

## `RunMenuScreenLoop` (`0x004289d0`)

```c
void __fastcall RunMenuScreenLoop(int startingScreenId);
```

The front-end menu system's top-level dispatcher. Stores the starting
screen ID into `DAT_0051dac4`, then loops: each iteration resets a small
per-screen scratch block (`DAT_00588730+4..0x18`, zeroed, plus a default
per-frame callback installed at `+0x88`), then `switch`es on the current
screen ID to call exactly one of 12 handler functions, and continues
looping as long as the called handler returns 0.

Screen ID → handler table (none of these 12 handlers have been
decompiled yet — this is purely the dispatch shape):

| ID | Handler | Notes |
|---:|---|---|
| 0 | `FUN_00428b60` | |
| 1 | `FUN_0042a620` | |
| 3 | `FUN_0042dab0` | |
| 7 | `FUN_00437010` | Also called directly from `WinMain`'s own state machine when `DAT_00562dc8==0x1d` (29) — likely a specific unlockable screen (credits? epilogue?) tied to a specific mission number. |
| 8 | `FUN_0043ca30` | |
| 10 | `FUN_0043ca50` (sets `DAT_0051d54c=1` first) | |
| 11 | `FUN_0043ca50` (sets `DAT_0051d54c=0` first) | Same handler as ID 10 — the flag almost certainly selects a save-vs-load (or similar binary) mode for one shared screen. |
| 12 | `FUN_00430490` | |
| 13 | `FUN_00431730` (also zeroes `DAT_0051d5f4`/`DAT_005201a4` first) | |
| 14 | `FUN_00432fc0` | |
| 15 | `FUN_0042e9b0` | |
| 16 | `FUN_0042b690` | |
| 0x11 | `FUN_0044b950` (sets `DAT_0051d54c=1` first) | |
| 0x12 | `FUN_0044b950` (sets `DAT_0051d54c=0` first) | Same handler as ID 0x11 — same save/load-style pattern as the 10/11 pair. |
| other | (no-op, returns 3) | |

### Known use

Called from multiple points inside `WinMain`'s post-bootstrap state
machine with different starting screen IDs (0 appears to be the main
entry from mission-end/menu-return paths). The individual screen
handlers are the natural next layer to open — this is the entire
front-end/menu UI of the game and currently totally opaque past the
dispatch shape.

## `RunShipInteriorVRLoop` (`0x00439fb0`)

```c
void RunShipInteriorVRLoop(void *startingRoomNode);
```

**This is the carrier-interior full-motion-video navigation system** —
the "walk around your ship between missions, watch FMV, click hotspots
to move to the next room" sequence Star Lancer is well known for.
Source-tagged `C:\lancer\game\interface.cpp`.

### Data model (inferred from usage, NOT independently struct-typed yet)

Each "room" is represented by a node structure, pointed to by
`DAT_0051d478` (current room) and passed in as `param_1` (starting
room). Fields referenced by offset:

| Offset | Inferred meaning |
|---|---|
| `+8` | Pointer to the room's `.bik` movie filename (or 0 to signal "end of chain"/immediate menu return — checked before opening a movie) |
| `+0xc` | An alternate/secondary filename pointer, checked separately from `+8` in some paths (possibly a "with sound" vs "silent" variant, or an alternate resolution asset) |
| `+0x12` | `short` count of hotspot rectangles |
| `+0x14` | Array of pointers to `{x, y, w, h}` `int16` hotspot rectangles; each rectangle's own 4th `int16` (past x/y/w/h, i.e. `+8` within the rect) doubles as a "next room" pointer array parallel to it (`*(undefined **)(DAT_0051d478 + iStack_a8*4 + 0x14)` reassigns `DAT_0051d478` directly to the array entry — so the "hotspot array" is actually an array of pointers to NEXT-ROOM node structs, not raw rectangles; the rectangle is read through the first 4 shorts of whatever it points to) |
| `+0x28` | `short` "room type" code — observed values 0,1,2,3,4,5,6,7,9, each with distinct handling in the main loop (described below) |
| `+0x2a` | `short`, checked against `-1` to decide whether to play a UI sound on room transition |

### Behavior

Per-frame: polls input (`FUN_004aab20`, `FUN_004bd490`, `FUN_004bd3a0`,
`FUN_004bd570`), and hit-tests the current mouse position
(`DAT_0051db34`/`DAT_0051dacc`, updated from raw mouse delta each frame)
against every hotspot rectangle of the current room. On a click (mouse
button state tracked via `bStack_87`/`bStack_88` high bits) landing
inside a hotspot (or matching some other trigger conditions involving
`DAT_0051dab0`/`DAT_00520138`/`DAT_005d5e80`), transitions to that
hotspot's linked room: closes the current Bink video (`_BinkClose`),
compares the new room's movie filename against known special names
(e.g. the literal `"rel_bunkroom2briefing_door.bik"`) to decide whether
to trigger a door-open sound effect via the Miles Sound System
(`_AIL_init_sample`/`_AIL_set_named_sample_file`/`_AIL_start_sample`),
resolves and opens the new room's `.bik` file (`FUN_004c83f0` "find
resource" + `_BinkOpen`, fatal via `ReportAssertionFailureEx` if either
step fails), and continues.

The room-type code at `+0x28` selects special transition behavior in
several places (values 1, 2, 5, 6, 7, 9 each have distinct blocks in
`WinMain`-adjacent code — not further decoded this pass) — e.g. type 7
reloads a DIFFERENT pair of room-graph roots depending on
`DAT_00562dc8 < 0x13` (mission-index threshold, matching the "current
mission" global identified earlier), strongly suggesting two parallel
ship-layout graphs (an early-campaign carrier layout and a later one —
plausible given campaign narrative progression, not confirmed).

Also handles a "reverse" playback mode (`_BinkGoto` back to a movie's
start frame + `_BinkCopyToBuffer` with a flipped/reverse flag
`DAT_0051dab4 | 0x80000000`) for some transitions, and maintains a
mouse-idle/cursor-pulse animation state (`DAT_005d6c3c`/`DAT_0051d48c`/
`DAT_00520244`) independent of room navigation.

### Known use

Not yet traced to a specific caller — very likely invoked from
`WinMain`'s main state loop or from one of `RunMenuScreenLoop`'s 12
screen handlers when transitioning from "menu" to "walk around the
ship" mode. This is one of the richest, most gameplay-defining
subsystems found so far and a strong candidate for continued
investigation.

## `EnsureCorrectCDMounted` (`0x0042fe00`)

```c
void __fastcall EnsureCorrectCDMounted(int requiredCdNumber);
```

The 2-disc CD-swap-prompt system.

### Behavior

If the game is a full hard-drive install (`DAT_005d62c4 != 0`, set by
`LoadInstallPathsFromRegistry`), skips straight to opening the needed
archive from the single install directory. Otherwise:

1. Checks whether the currently-mounted disc (`FUN_004ac6c0()`, not
   decompiled — presumably reads a volume label or a marker file) already
   matches `requiredCdNumber`.
2. If not, enters a poll loop (input pump + `FUN_0043eb30`, presumably
   "is the right disc now present" combined with a "please insert disc"
   UI) until it detects the right disc or the user cancels
   (`FUN_004bd570(1)`).
3. Once the right disc is present, switches the working directory to
   that disc's path (`DAT_005d6a28` for disc 1, `DAT_005d6928` for disc
   2 — both set up by `LoadInstallPathsFromRegistry`), builds
   `"cd<N>.hog"` via `SafeFormatString` (format string confirmed
   directly), and opens it via `OpenBigFile` (closing any
   previously-open archive first via `CloseBigFile`).
4. Fatal errors (`"Can't open HOG resource file: %s"` →
   `ReportAssertionFailureEx`) if the archive still can't be opened
   after all that.

### Known use

Called directly from `WinMain`'s post-bootstrap state machine at
several points (visible in `WinMain`'s own decompile as
`FUN_0042fe00(...)` calls preceding mission loads) — matches the real
`cd1.hog`/`cd2.hog` files present in the game directory. Also called
directly from `RunMissionBriefingScreen` (see below).

---

# Fourth pass (2026-09-08): `VRRoomNode` struct confirmed, `RunMissionBriefingScreen`

## `VRRoomNode` struct (44 bytes)

Verified by directly reading four real instances from process memory via
`read_memory` and checking every field against how `RunShipInteriorVRLoop`
actually dereferences them — not inferred from code alone. Created as a
real struct type in the Ghidra project and applied at all 15 known
root-node addresses.

```c
struct VRRoomNode {
    int16_t hotspotX, hotspotY, hotspotW, hotspotH; // +0x00: this node's
        // own clickable rectangle, as read by its PARENT when hit-testing
        // the mouse against it as a destination. All-zero on entry/root
        // nodes (nothing points to them as a clickable hotspot).
    char *moviePath;      // +0x08: primary .bik filename for this room
    char *moviePathAlt;   // +0x0c: nullable; sometimes equals moviePath,
        // sometimes NULL — exact distinction not determined
    int16_t unk10;        // +0x10: values 199-211 observed; meaning unknown
    int16_t numTargets;   // +0x12: 0-4 observed (max possibly 5, matching
        // the fixed array size below, but never seen filled to 5)
    VRRoomNode *target[5]; // +0x14..+0x24: FIXED 5-slot array regardless
        // of numTargets — unused trailing slots are NULL. (This was
        // discovered by cross-checking a numTargets=1 node, which had
        // 4 trailing zero slots, against a numTargets=4 node, which had
        // only 1 trailing zero slot — 4+16 == 16+4 == 20 bytes either
        // way, confirming a constant 5*4-byte array rather than a
        // variable-length trailing array.)
    int16_t roomType;     // +0x28: values 0,1,2,3,4,5,6,7,9 observed in
        // RunShipInteriorVRLoop's dispatch — semantics not decoded
    int16_t soundFlag;    // +0x2a: -1 in every sample read so far
}; // sizeof == 44 (0x2c) bytes, ALWAYS — confirmed across all samples
   // regardless of numTargets, since the target array itself is fixed-size
```

### Verified instances (this session)

| Address | numTargets | moviePath | Notes |
|---|---:|---|---|
| `0x50b2b8` (early-campaign root, `DAT_0050b2b8`) | 3 | `"b2iloop.bik"` (bunkroom idle loop, plausible) | hotspot rect all-zero (it's a root) |
| `0x50aef8` | 1 | (not read) | moviePathAlt = NULL |
| `0x50b288` | 3 | (not read) | |
| `0x50b348` | 4 | (not read) | The node that forced correcting the 3-slot-array theory to 5-slot |
| `0x506ad0` (late-campaign root, `DAT_00506ad0`) | (typed, not read) | | |

### Known use

Used throughout `RunShipInteriorVRLoop`. 15 root/near-root addresses are
now struct-typed in Ghidra: the 12 campaign-pair roots referenced across
`RunShipInteriorVRLoop`/`RunMissionBriefingScreen`/`WinMain`
(`DAT_0050b2b8`/`DAT_00506ad0`, `DAT_0050b318`/`DAT_00506e30`,
`DAT_0050aec8`/`DAT_00506c80`, `DAT_0050b678`/`DAT_00506d10`,
`DAT_0050b3a8`/`DAT_00506f20`, `DAT_0050b168`/`DAT_00506dd0`) plus the 3
child nodes read directly this session. Only 5 of these 15 have actually
had their bytes read and manually verified — the rest are typed on the
assumption they share the same layout (a safe assumption given the
uniform access pattern in the code, but not independently confirmed
node-by-node).

## `RunMissionBriefingScreen` (`0x00437010`)

```c
int RunMissionBriefingScreen(void); // RunMenuScreenLoop dispatch, ID 7
```

Real internal name confirmed via its own error strings:
`"InterfaceBriefing resource: error searching/loading %s"`.

### Behavior

Plays the per-mission briefing video: builds an in-function array of
literal briefing filenames (`"new_m01.bik"`, `"new_m15.bik"`,
`"new_m16.bik"`, `"new_m18.bik"` through `"new_m28.bik"` — note the gap,
`new_m02`-`new_m14` and `new_m17` are NOT in this particular array,
meaning either they don't have distinct briefings or are handled by a
different path not seen here) and indexes it by `DAT_00562dc8` (current
mission index) via `SafeFormatString(..., "%s.bik", array[DAT_00562dc8])`
— this is the THIRD independent function found treating `DAT_00562dc8`
as the mission index (alongside `WinMain` and `LoadPlayerProfile`),
raising confidence in that identification further.

In parallel, plays a speech/subtitle track using the format string
`"ms_speech_enrbr_tag_%02d_ut"` (`DAT_00562dc8` again) — "enrbr" reads
naturally as "enroute briefing". Mission `0x1d` (29) is special-cased
throughout (a separate, simpler code path with no speech-tag lookup) —
this matches a special-case for mission `0x1d` also seen in `WinMain`
and `RunMenuScreenLoop`'s screen-ID dispatch, suggesting mission 29 is
some kind of non-standard mission (an epilogue, a cutscene-only
"mission", or similar — not confirmed).

Polls for "briefing skipped/finished" every frame; on completion, calls
`EnsureCorrectCDMounted` (confirming its real call site), then hands off
directly into the ship-interior VR system by setting the global
`DAT_0051d478` (the same global `RunShipInteriorVRLoop` reads as its
current-room pointer) to `&DAT_0050b2b8`, or `&DAT_00506ad0` if
`DAT_00562dc8 < 0x13` (19) — i.e. an early-campaign vs late-campaign
ship-interior layout, selected purely by mission number. This is the
first concrete, traced link between the menu/briefing system and the VR
room-navigation system.

### Known use

Called as `RunMenuScreenLoop`'s screen-ID-7 handler. Also referenced by
address directly elsewhere (mission `0x1d`'s special-case branches in
both `WinMain` and `RunMenuScreenLoop`'s own dispatch treat ID 7 /
this function specially).

## Ship-interior room map

Cross-referencing `RunShipInteriorVRLoop`'s `roomType`-keyed dispatch
branches (values 1, 2, 5, 6, 7, 9) against the six `VRRoomNode` root
pairs found so far, and reading each hub's own `moviePath` string,
produces a clean map:

| `roomType` | Hub node pair (late/early campaign) | `moviePath` | Guessed room |
|---:|---|---|---|
| 1 | *(none — calls back into `RunMenuScreenLoop` directly)* | — | Exit to front-end menu |
| 2 | `0x50aec8` / `0x506c80` | `"itac2rot.bik"` | "ITAC" / "ROT" room (exact identity unclear) |
| 5 | `0x50b678` / `0x506d10` | `"pod2rot2.bik"` | Escape-pod bay ("POD") |
| 6 | `0x50b3a8` / `0x506f20` | `"lockzomo.bik"` | Locker room ("LOCK") |
| 7 | `0x50b318` / `0x506e30` | `"tv2brd.bik"` | Briefing room ("BRD" — matches `RunMissionBriefingScreen`'s own `brd_`-prefixed assets) |
| 9 | `0x50b168` / `0x506dd0` | `"cd_cd2d.bik"` | Corridor ("CD") |
| *(entry)* | `0x50b2b8` / `0x506ad0` | `"b2iloop.bik"` / `"rel_ladd_bunk.bik"` | Bunkroom (idle loop / ladder-descent intro) |

This paints a coherent hub-and-spoke ship interior: bunkroom, locker
room, briefing room, a corridor, an escape-pod bay, and one more room
abbreviated `ITAC`/`ROT` — consistent with a carrier-based flight sim's
between-mission routine (wake up, suit up, get briefed, launch).

**Caveat**: the room-NAME interpretations (locker room, escape-pod bay,
etc.) are abbreviation guesses from the `.bik` filenames, not confirmed
against any authoritative source (in-game UI text, manual, credits).
The mapping of `roomType` → hub pair itself is a direct code fact
(Confidence 2); the English room names are Confidence 1.

---

# Fifth pass (2026-09-08, same day): full graph walk of the ship interior

Walked the `VRRoomNode` graph outward from all 6 hub pairs, ~2-3 levels
deep, reading ~85 distinct node addresses directly from process memory
(`read_memory`, one node at a time — Ghidra scripting is disabled in
this environment, `GHIDRA_MCP_ALLOW_SCRIPTS` is unset, so this was done
by hand rather than with a traversal script). Not exhaustive — roughly
20-25 further addresses were seen as targets but not yet read.

## Doorway (`roomType != 0`) nodes found

Every node below, once reached, unconditionally jumps to its `roomType`'s
hub pair — its own `target[]` array is not used for this (frequently
self-referential or left `NULL`/inconsistent with `numTargets`, since
it's dead data once the jump fires):

| Address | roomType | Jumps to | Own target[] (mostly vestigial) |
|---|---:|---|---|
| `0x506b00` | 1 | exit to `RunMenuScreenLoop` | `0x506f80` |
| `0x50b408` | 2 | `0x50aec8`/`0x506c80` (ITAC/ROT) | self (`0x50b408`) |
| `0x506c50` | 2 | (early variant) | self (`0x506c50`) |
| `0x50b378` | 5 | `0x50b678`/`0x506d10` (pod bay) | `0x50b678` (the hub itself) |
| `0x50b6a8` | 5 | (twin of above) | `0x50b678` |
| `0x50acb8` | 5 | (twin of above) | `0x50b678` |
| `0x50b0a8` | 5 | (twin of above) | `0x50b678` |
| `0x50b3d8` | 6 | `0x50b3a8`/`0x506f20` (locker room) | `0x50b3a8` (the hub itself) |
| `0x50b618` | 6 | (twin, no targets at all) | — |
| `0x50b2e8` | 7 | `0x50b318`/`0x506e30` (briefing) | `0x50a988` |
| `0x506e00` | 7 | (early variant) | self (`0x506e00`) |
| `0x50a958` | 1 | exit to menu (twin of `0x506b00`, late-campaign side) | `0x50bbe8`, `0x50bc18` |
| `0x50aa78` | 9 | `0x50b168`/`0x506dd0` (corridor) | *(numTargets=1 but the slot is NULL — an inconsistent/dead entry)* |
| `0x506da0` | 9 | (early variant) | *(NULL)* |
| `0x506e90` | 6 | (early variant) | `0x506f20` (the hub itself) |
| `0x506ec0` | 6 | (early variant, twin) | `0x506ef0` |

## Structural conclusions

1. **The graph is one connected whole**, not six separate per-hub
   trees. Nodes discovered while exploring one hub's subtree
   repeatedly turn out to already be known from a different hub's
   subtree — e.g. `0x50af28` (a child of the ITAC/ROT hub `0x50aec8`)
   points straight back to `0x50aef8`/`0x50b288`/`0x50b348`, which are
   the ENTRY room's own direct children. The whole ship is meant to be
   walked freely, not menu-tree-navigated.
2. **"Twin doors" are real and common**: the same logical destination
   is reachable from multiple distinct physical door nodes with
   identical `roomType`/target data (see the table above — 4 separate
   `roomType=5` doors alone). This models several different
   corridors/rooms each having their own doorway into a shared hub,
   not a data-authoring duplicate-bug.
3. **Early-campaign ship access is deliberately tiny**: for
   `DAT_00562dc8 < 0x13`, the entry hub and 4 of the 5 special hubs
   (everything except briefing) share the IDENTICAL 3-target set
   (`0x506b30`, `0x506b60`, `0x506b00`) and identical `moviePathAlt`
   (`0x507120`) — only the incoming transition movie differs per hub.
   One level deeper, `0x506b60` shares the exact same 4-target set as
   the early briefing hub itself. The entire early-campaign explorable
   ship is therefore a loop of roughly 7-8 nodes — briefing room, a
   shared corridor, and an exit door — while the late-campaign ship
   (documented above) is a much richer, cross-linked structure. This
   reads as a deliberate progression gate (you don't get full access to
   your ship until later in the campaign), not a coincidence.
4. **`unk10` is NOT a narrow ID field** as first suspected from a small
   sample — values observed this pass range from ~195 to 965. A
   per-node duration/frame-count is a plausible guess given that
   spread, but unverified.

## Coverage: COMPLETE

Finished the walk in a follow-up round: read the remaining ~45 queued
addresses in two more batches, down to zero new leaves — every `target`
pointer discovered now resolves to an already-visited node. Final
count: **~120 distinct `VRRoomNode` addresses in the late-campaign
graph, ~24 in the early-campaign graph** (~145 total), all read by hand
via `read_memory` (Ghidra scripting is disabled in this environment).

### New findings from finishing the walk

- **A genuine `roomType == 3` instance** found at `0x50ad48` — the
  earlier full decompile of `RunShipInteriorVRLoop` showed this value
  checked separately from the 1/2/5/6/7/9 hub-jump set (a "replay
  current movie without changing rooms" branch, and a distinct
  hover/idle-state check) but no concrete node with this value had been
  seen until now.
- **A third `roomType == 1` "exit to menu" door**, `0x50bbb8` — joining
  `0x506b00` (early-campaign) and `0x50a958` (late-campaign) already
  documented. Confirms multiple physical exit points exist, consistent
  with the "twin door" pattern seen for the other hub types.
- **Nodes with genuinely empty target arrays despite the field format
  implying entries**: `0x50ada8` (`roomType=2`, `numTargets=0`, all
  target slots zero) and `0x50ab98`/`0x50b1c8` (`roomType=6`,
  `numTargets=3` claimed but all three slots zero) — reinforcing that a
  door node's `target[]` data is genuinely dead/unreliable once
  `roomType` triggers a hub jump, not just "usually self-referential."
- **A door with no movie at all**: `0x50b7c8` (`roomType=6`) has both
  `moviePath` and `moviePathAlt` as NULL pointers — the transition into
  the locker-room hub from this specific spot plays no video, presumably
  an instant cut.
- No new areas, hub types, or major structural surprises — the last
  ~45 nodes were entirely corridor/connector nodes feeding back into the
  already-mapped 6-area structure, confirming the earlier structural
  conclusions rather than revising them.

---

# Sixth pass (2026-09-08, same day): the 12 menu-screen handlers

Completed `RunMenuScreenLoop`'s entire dispatch table (see
`confidence_db.md` for the full per-screen summary table). Each handler
is individually huge (100-700+ decompiled lines, dominated by hardcoded
pixel-position tables for UI widgets) — documented here at the
structural/purpose level per METHODOLOGY's tiered approach, not
field-by-field. Two finds are worth calling out in more detail:

## `RunMainMenuScreen` (`0x00428b60`) — a hidden mission-select cheat code

The main title screen, past its 3 straightforward menu-button hotspots
(→ New Game setup, Multiplayer setup, Options), contains an unusual
12-deep chain of nested `if`-checks against what looks like a keyboard
or input-queue poll function (`FUN_004bd570(1)`, called identically at
every step — no visible argument distinguishing *which* key). Failing
at any step sets a debug/status code (`_DAT_00588400 = 0..11`) and
aborts the sequence; succeeding all 12 arms a flag (`DAT_005d5641`)
that puts subsequent input into a different mode: the next several
inputs are accumulated (mod-10 arithmetic, combined with the CURRENT
mission index `DAT_00562dc8` if it's under 10) into a 2-digit number
that is then written directly into `DAT_00562dc8`.

This has every hallmark of a classic era-appropriate developer/QA
**mission-select cheat code** — type a specific sequence to unlock
direct entry to any mission number.

**Stale-entry correction (added Pass 51, 2026-09-09)**: the paragraph
above, as originally written, said the exact key sequence "isn't
recoverable from static analysis." That was superseded two passes
later, in Pass 34 (`CheckKeyEdgeState` decoded), which read the
literal scancode array directly and confirmed the sequence is
**Ctrl+P-O-T-A-T-O** ("Ctrl+Potato") at confidence 5 -- see that
section below for the full writeup. This entry was simply never
updated to point at the resolution, which left two contradictory
confidence claims about the same fact sitting in the same document.
Flagging and fixing that now per METHODOLOGY's non-silent-correction
rule, rather than leaving the stale "Confidence 1, not recoverable"
claim standing.

## `RunSaveGameBrowserScreen` (`0x00431730`) — save file format

Confirms the on-disk save format: files are named
`saves\<pilotname>GAME_<NN>.IFF` (matches the classic Origin/EA-era IFF
chunk convention also seen in the BigFile/.HOG format's own FourCC
magic-number style) and contain at least two identifiable chunks by
their FourCC magic: `0x45564153` = `"SAVE"` and `0x5353494d` = `"MISS"`
(read via `FUN_004909d0`/`FUN_00490c40`, an IFF-chunk-seeking helper
family not itself decompiled). Each slot's browser entry shows a
thumbnail (decoded via `FUN_0045e8d0`) and a formatted timestamp
(`"<hour>:<minute> <weekday, month day, year>"`, built from the file's
own last-write time via `GetFileTime`/`FileTimeToLocalFileTime`/
`FileTimeToSystemTime`/`GetDateFormatA` — the DISPLAYED date is the
file's filesystem timestamp, not something stored inside the save
data itself). Lists up to 10 slots with scrolling. Also directly
callable mid-flow from `RunSaveLoadScreen` (screens 10/11), not just
reachable as screen 13 on its own.

## `RunMultiplayerSetupScreen` (`0x00432fc0`) — Zone.com integration

Confirms Star Lancer's online multiplayer used the **MSN Gaming Zone**
matchmaking service: a `ShellExecuteA(NULL, "open",
"http://www.zone.com/starlancer", NULL, NULL, SW_MAXIMIZE)` call is
made directly when the player selects the "Zone.com" connection option,
launching the user's default web browser. A real, historically-grounded
detail rather than a guess — the URL string is embedded verbatim.
Alongside Zone.com, the screen offers Direct-connect, Host, Join, and a
scrollable list of discovered network sessions (a `0x14`-stride record
array) connected to via `FUN_004bc720`.

## `RunVideoOptionsScreen` (`0x0042e9b0`) — confirms the dmodes.bin table

Directly manipulates the SAME device/mode table
(`DAT_00595fe8`/`DAT_00595fec`/`DAT_00595ff0`) that the `dmodes.bin`
cache loader (documented two sessions ago, address `0x4a89c0`)
populates at startup — this screen is the UI for cycling through that
table's entries (device index / resolution mode index) and committing a
choice, which cross-confirms that table's role as "the enumerated list
of available display devices and modes" rather than something else.
Also writes `starlancer.ini`'s `[Device]` `gamma` and `Transitions`
keys directly, and cycles texture detail, geometry detail, lightmap,
and 3D-acceleration-provider settings (all of which `WinMain`'s
bootstrap reads back at next launch).

## `RunControlsOptionsScreen` (`0x0042b690`) — key/joystick binding

Confirms `starlancer.ini`'s `[KeyConfig]` section keys: `ForceFeedback`,
`JoystickInvert`, `HatEnable`, `TwistEnable`, `controller` (an integer
0/1/2, almost certainly keyboard/joystick/other-device selection given
the surrounding force-feedback and hat-switch context). Implements a
full interactive key-rebind flow: select a control, press a new
key/button, the binding table (`DAT_004e2380`, one entry per control)
is updated, with conflict detection against other already-bound
controls (prompting a confirm-overwrite dialog via `FUN_0042aa80` when
a collision is found).

## `RunMultiplayerLobbyScreen` (`0x0044b950`) — host/client game setup

The multiplayer pre-game lobby, shared between host and client via the
same `DAT_0051d54c` mode flag `RunSaveLoadScreen` also uses (1=host,
0=client — this flag-reuse-for-role/mode pattern is now confirmed
across two independent screen pairs). Host mode lets the player pick a
mission from a lookup table (`DAT_0050c798`, cross-indexed against the
now-familiar `DAT_00562dc8` mission-index global) and toggle game
options; both host and client see a player roster
(`DAT_005db8f4`, the same per-player array/stride already seen in
`WinMain`'s own multiplayer section) with ready-state and
team/ship-type flags, and a scrollable/paged player list (handles more
players than fit on screen at once via a scroll offset,
`DAT_00524a48`).

---

# Seventh pass (2026-09-08, same day): save-game IFF reader + mission file format

## The `IffFile` class (`0x0045e8d0`, `0x00490930`, `0x004909d0`, `0x00490c40`, `0x00490980`)

A generic, reusable `__thiscall` C++ class implementing the classic
**IFF (InterChange File Format)** container standard — confirmed two
independent ways: the magic constant `0x4d524f46` decodes byte-for-byte
to the ASCII string `"FORM"` (IFF's standard top-level container tag),
and `IffFile_Read`'s own guard-clause error strings describe exactly
the checks present in its decompile (`"Attempted read from unopened
file: %s"`, `"Attempt to read 0 bytes: %s"`, `"Read from NULL pointer:
%s"`, `"Read failed on file: %s"`).

### Methods

```c
bool  IffFile_Open(IffFile *this, const char *filename);
bool  IffFile_FindFormChunk(IffFile *this, uint32_t formType, int unused);
bool  IffFile_FindChunk(IffFile *this, uint32_t chunkId, int unused);
int   IffFile_Read(IffFile *this, void *dest, int numBytes);
void  IffFile_CloseChunkStack(IffFile *this);
```

`IffFile_FindFormChunk` searches forward from the current read position
for a nested `FORM`-type container whose 4-byte form-type tag matches
`formType` — correct IFF semantics, since `FORM` chunks are containers
that nest. `IffFile_FindChunk` searches for a plain LEAF data chunk
(explicitly requiring the chunk NOT be a `FORM`) whose raw chunk ID
matches `chunkId` — also correct, since leaf chunks hold data, not
sub-containers. This distinction being implemented correctly is good
evidence this is a faithful, standards-following IFF parser rather than
an ad-hoc reinvention.

### Known use

`LoadGame` (below) is the confirmed real-world user. The class is
generic enough that other callers likely exist elsewhere in the binary
(not traced this pass — `IffFile_Open`'s caller list showed one other
address, `FUN_004315c0`, not itself investigated).

## `LoadGame` (`0x00475430`)

```c
void LoadGame(const char *saveFilePath);
```

Opens a save file via `IffFile_Open`, locates its `FORM "SAVE"`
container (`0x45564153` decodes to `"SAVE"`), then iterates a 5-entry
field table (`PTR_DAT_00500a24`) calling `IffFile_FindChunk`+
`IffFile_Read` per tagged field — a standard "read N named fields out
of a form" IFF-consumer pattern. Afterward, restores a ~34-field
campaign/difficulty-state block (`DAT_0052a3f0` through `DAT_0052a480`)
from a parallel staging area (`DAT_00562f7x`) that was populated by the
field reads above.

This state block is the SAME one `WinMain`'s bootstrap zeroes to
defaults and `LoadPlayerProfile` also touches — three independent
functions now agree on its role as persistent
campaign/difficulty/settings state, reached via three different paths
(fresh boot defaults, profile load, save-game load).

### Known use

Called from `RunSaveGameBrowserScreen`'s "load selected slot" case.

## Mission file format (`.dte`) — the complete load chain

Traced end-to-end: player selects a mission on the in-universe star map
→ mission file is located and parsed → gameplay begins. Files live at
`.\missions\mission<N>.dte`, confirmed by three literal embedded paths
(`mission29.dte`, `mission251.dte`, `mission311.dte`) plus general
`mission%d.dte`/`%s.dte` format strings, and an Open-File-dialog filter
string `"StarLancer DTE Files (*.dte)"` confirms "DTE" as the real
extension name (though not what the acronym stands for — not found in
the string table).

### `RunMissionSelectMapScreen` (`0x0044f3d0`)

The in-universe "star map" screen — reached from the ship-interior VR
loop's `roomType=5` hub destination (previously identified only as
"pod bay", now clarified: the pod-bay area is apparently where the star
map/mission-select interface lives, e.g. a briefing table or holo-map
in that room). Offers 3 mission branches (`mission30`/`31`/`32`,
hotspot-selected against a small area-rect table) plus a special
`mission29` path, then hands off to `InitializeMissionGameplay` with
`DAT_00562dc8` set to the chosen mission number — the FOURTH
independent function now confirmed to treat this global as the mission
index.

### `InitializeMissionGameplay` (`0x004934f0`)

Sets up cockpit/HUD/radar rendering state (camera frustum corners,
crosshair layout, whiteout/damage-flash mesh) and resolves a large
"previous mission outcome code → next mission-select code" branch table
(a `switch` over values 0-0xff read from a per-player result field) —
this looks like the actual campaign branching logic (which mission
comes next depends on how the previous one ended), not decoded
field-by-field this pass. Calls `LoadMissionFile` and fatal-errors
(`"The mission number is invalid!!!!"`) if it returns 0.

Also confirmed as one leg of a recurring
`InitializeMissionGameplay`/`FUN_00494040`/`FUN_004942b0` trio — this
exact 3-call sequence appears repeatedly across `WinMain`'s own state
machine and inside `RunMainMenuScreen`'s idle/attract-mode loop, always
wrapped around a temporary `DAT_00562dc8` override. This trio is almost
certainly "load mission / run mission gameplay / unload mission" — the
real top-level entry into actual flying/combat gameplay, reached from
at least 3 independent call sites. `FUN_00494040` (run) and
`FUN_004942b0` (unload) are NOT yet decompiled — the single highest-value
remaining target if gameplay itself (as opposed to the menu/briefing
shell around it) becomes the next focus.

### `LoadMissionFile` (`0x00451d90`) — the real `.dte` parser

```c
void *LoadMissionFile(void);  // returns the loaded buffer, or NULL
```

1. Calls `LoadResourceFileBuffer` to load the entire `.dte` file into
   one memory buffer (capped at `0xfa000` = 1,024,000 bytes).
2. Calls `ReadMissionDirectoryEntry` exactly **27 times** in a fixed
   sequence, each call consuming one directory entry from the front of
   the buffer and storing a resolved pointer into a distinct global
   (`DAT_00525fa8`, `DAT_00525f3c`, `DAT_005294f8`, `DAT_0052951c`,
   `DAT_005267cc`, `DAT_005294e0`, `DAT_00525f88`, `DAT_005267c0`,
   `DAT_005267d0`, `DAT_005256c8`, `DAT_005294d8`, `PTR_DAT_004ef2fc`,
   `DAT_005294fc`, `DAT_00529500`, `DAT_00525f18`, `DAT_005256b8`,
   `DAT_00525fb0`, `DAT_005294ec`, `DAT_00525fb4`, `DAT_0052950c`,
   `DAT_00525fa0`, a local 6-byte buffer, `DAT_00525278`,
   `PTR_DAT_004ee7d8`, `DAT_00525f9c`, `DAT_00525f90`, `DAT_0052570c`
   — 27 in total). None of these tables' internal layouts are decoded
   this pass — only their existence and storage location.
3. Runs 5 finalization passes (`FUN_0045cb40`, `FUN_00452010`,
   `FUN_00453050`, `FUN_00457c10`, `FUN_0045cbc0`) — plausibly
   resolving cross-references between the just-loaded tables (e.g.
   linking a ship spawn record to its AI script), not investigated.

### `.dte` directory-entry format (confirmed via `ReadMissionDirectoryEntry`, `0x00452a20`)

Each directory entry is exactly 8 bytes:

```
offset 0 (4 bytes): header word
    bits 0-15  = type/ID (stored as the entry's "type" output)
    bit 24     = flag -> sets global DAT_00525f9a
    bit 25     = flag -> sets global DAT_00525fa4
    bit 26     = flag -> sets global DAT_005267c6
    bit 27     = flag -> sets global DAT_005294e8
offset 4 (4 bytes): relative offset, ADDED to the buffer's base address
    to produce an absolute pointer, written to the caller's output slot
```

A flat, single-buffer format with an upfront table of contents — no
filesystem-style nesting (unlike the save-game format, which reuses the
general-purpose `IffFile` class). The 4 header flag bits look like
mission-wide capability/feature flags (e.g. "this mission uses feature
X"), set globally rather than per-entry-type, but their specific
meanings aren't determined.

### `LoadResourceFileBuffer` (`0x0045a300`)

Loads a named resource either from a loose file directly on disk
(`FUN_0045a3e0`, only taken if `FUN_004ad6e0()` — an "is this a real
installed copy with direct file access" check, not decompiled — returns
true) or from the `RESOURCE.HOG` archive via `LoadNamedResource`,
always copying the result into a freshly `malloc`'d buffer sized to the
actual bytes read. Generic infrastructure, not mission-specific — used
here for `.dte` files but presumably for other resource types too.

### `LoadNamedResource` (`0x004c5bd0`) / `HOG_BigRead` (`0x004c7f60`)

The engine's central "load a named resource from the archive"
primitive. **Real name confirmed directly** — `HOG_BigRead` contains
its own embedded error strings `"HOG bigread2: error loading '%s'"` and
`"HOG bigread: error loading '%s'"`, the function naming itself exactly
as `bigfile.cpp`'s other functions (`OpenBigFile`/`CloseBigFile`) are
tagged with that same source file.

Behavior: strips a 2-character extension suffix if present (plausibly a
language or resolution variant tag, not confirmed) and any directory
path from the requested name, first tries a loose-file-on-disk override
(`FUN_004c8370`), then falls back to scanning the currently-open `.HOG`
archive's directory (via the handle `OpenBigFile` set up) for a
matching entry name and reading it into an `SR_MEM_allocate`'d buffer.
`LoadNamedResource` is a one-line convenience wrapper taking an
implicit-register filename argument.

This function is called constantly — from menu screens, the ship-interior
VR loop (loading `.bik` movies), and now mission loading — making it
THE central asset-loading choke point for the entire game. A natural
target for a future "enumerate every resource type the game loads"
pass if that's ever wanted (would mean surveying its many call sites
rather than the function itself, which is already well understood).

---

# Eighth pass (2026-09-08, same day): flight/combat gameplay core loop

Completed the "load/run/unload mission" trio identified last session as
the real top-level gameplay entry point, then went one level deeper
into the per-frame update structure. `UpdateMissionFrame` in particular
is large (400+ decompiled lines) and documented here structurally, not
field-by-field, per METHODOLOGY's tiered approach — full algorithmic
decoding of the per-object combat/damage logic would require first
recovering the ship/object struct itself, flagged as a substantial
follow-on subsystem.

## `RunMissionGameplay` (`0x00494040`) — confirmed as the flight/combat main loop

Confirmed unambiguously: a sequence of `DebugLog_Stub` calls at the
very end of the function use tags that read like real subsystem
shutdown labels — `"uncolour hud target"`, `"destroy lockring"`,
`"dockring exit"`, `"chaff exit"` — exactly the kind of per-system
teardown trace a game's main loop would emit in a debug build.

### Structure

```c
void RunMissionGameplay(void) {
    // one-time setup: HUD/cockpit modes, per-player-slot reset, etc.
    ...
    lastTick = currentTick;
    while (true) {
        while (true) {
            if (!PumpInput())          // FUN_004aab20, 0 = quit requested
                goto teardown;
            elapsed = currentTick - lastTick;
            for (i = 0; i < elapsed; i++)
                UpdateMissionTick();          // fixed-timestep sim
            if (multiplayer)
                for (i = 0; i < elapsed; i++)
                    NetworkTick();             // FUN_00477670, NOT YET IN DB
            lastTick = currentTick;
            if (paused) break;                // DAT_0057e04c
            if (UpdateMissionFrame() != 0 || DAT_00588338 != 0)
                goto teardown;
        }
        if (CheckMissionExitState() != 0)
            break;
    }
teardown:
    ... // the DebugLog_Stub-tagged cleanup sequence
}
```

This is a textbook fixed-timestep-simulation-plus-variable-rate-render
split: `UpdateMissionTick` runs at a fixed simulation rate (however many
ticks have actually elapsed, catching up if rendering fell behind),
while `UpdateMissionFrame` runs once per iteration of the render loop
regardless of how much sim time passed.

## `UnloadMission` (`0x004942b0`)

Confirmed the same way, via matching `DebugLog_Stub` tags:
`"deathmatch exit"`, `"bmo destroy"`, `"radarmesh destroy"`,
`"end samples"`, `"streamer stop"`, `"end 3d samples"`, `"speech free"`,
`"samples free"`, `"mission destroy"`. The last tag precedes a call to
`FreeMissionFile` (`0x45a530`) — confirming this is the direct
counterpart to `LoadMissionFile`, closing the "load/run/unload" trio as
a clean, symmetric triple.

## `UpdateMissionTick` (`0x00477850`) — fixed-timestep simulation step

A thin dispatcher, not the real physics: increments a frame counter,
every 100th tick decrements a difficulty-related countdown
(`DAT_0052a474`), then calls `FUN_004774d0` (not decompiled this pass —
given this wrapper does nothing else of substance, `FUN_004774d0` is
almost certainly where the actual per-tick physics/AI simulation lives,
making it the single highest-value remaining target for anyone wanting
real flight/combat mechanics rather than the surrounding structure).
In multiplayer, calls a different pair of sub-steps
(`FUN_0049ceb0`/`FUN_0049cf40`) instead.

## `UpdateMissionFrame` (`0x004924b0`) — per-rendered-frame gameplay update

The largest function opened this session. Confirmed structural pieces:

1. **Frame-rate-adaptive detail throttle**: keyed off the graphics
   detail setting (`DAT_005d54e0`, 0/1/2), picks a target FPS band
   (30-40 / 30-40 / 40-60) and adjusts a global throttle value
   (`_DAT_005e829a`) up or down to hit it — likely gates some
   per-frame-optional visual effect elsewhere.
2. **Mission-timeout/cutscene state machine**: a `switch` on
   `DAT_00539a34` (observed case values 7, 8, 0x1a, 0x1b, 0x1c, 0x1d),
   each computing a tick deadline relative to `DAT_00539aa4`/
   `DAT_005883b0` and auto-triggering a mission-exit flag
   (`DAT_0052a414` or a network-specific path via `FUN_004775d0`) once
   the deadline passes. This is plausibly the "mission ends N seconds
   after the last enemy is destroyed" kind of logic common to combat
   sims, but the specific state values' meanings aren't decoded.
3. **Per-object damage-severity visual banding**: for each active ship
   object, computes an armor-percentage-like ratio from several struct
   fields, buckets it into 4 severity levels via 50%/70%/90%
   thresholds, and — only on a level CHANGE — calls `FUN_00494400`
   (not decompiled; presumably swaps a damage-decal or smoke-emitter
   visual state).
4. **Random engine-smoke particles**: for ships already in a specific
   damage state, a `rand()%10==0` roll spawns a particle effect via
   `FUN_0046bd00` scaled by ship size (`piVar7[0x167]`).
5. **End-of-mission player-status polling**: iterates all active player
   slots checking a status/flags bitmask, and once every player has
   exited, logs the final state via several `DebugLog_Stub` calls
   (`"exiting mission: player strategy %d"`, `"...player status %d"`,
   `"...player flags %d %d"`) before allowing the mission to end.
6. **A handful of object-CLASS special cases**: object type IDs `0x6d`,
   `0xa8`, `0x44`, and `0xd` each get distinct handling (adjusting some
   kind of size/scale field for `0x6d`/`0xa8`, a target-lock/warning
   check for `0xd`) — these read like capital-ship, weapon-emplacement,
   or similarly distinguished object classes, but which is which is NOT
   determined.

None of this function's ~200 remaining sub-calls (`FUN_00474b40`,
`FUN_004c3570`, `FUN_0049b390`, etc.) were individually investigated —
this is a structural map of the function's shape, not a full behavioral
decode. The underlying per-object struct (`piVar7` in the decompile,
dereferenced at dozens of distinct offsets up to `+0x1a3` and beyond)
has no recovered type — recovering it properly is flagged as a
substantial follow-on subsystem in its own right, comparable to the
`Actor`/`FighterActor` struct-recovery work documented for the sibling
`wc3remake` project.

## `CheckMissionExitState` (`0x00491fc0`)

Handles a small state code (`DAT_0057daa4`) controlling how
`RunMissionGameplay`'s outer loop terminates when the pause flag is
set:

| Value | Behavior |
|---:|---|
| 5 | Sets a restart flag (`DAT_005d60b9=1`), signals loop-done |
| 6 | Signals loop-done, no restart |
| 7 | Sets `DAT_00588394=4` (an outcome code also checked by other screens, e.g. `RunMissionBriefingScreen`), signals loop-done |
| other | Normal per-frame housekeeping (screen-shake/gamma-change application, clearing a "current target" global `DAT_005027b8`) — loop continues |

---

# Ninth pass (2026-09-08, same day): physics/AI simulation step + ship-object struct

## `ProcessMissionSimulationTick` (`0x004774d0`) — the real per-tick simulation dispatcher

`UpdateMissionTick` (documented last session) turned out to be a thin
wrapper; this is where the actual per-tick work happens. Rate-limited
to run only once every 4 calls (a counter at `DAT_00588718`). When it
does run:

1. Re-polls input (`FUN_004bd490`/`FUN_004bd300`/`FUN_004bd3a0`).
2. Iterates every active object in the main object array
   (`DAT_00587ce0`, count `DAT_00539aa0+1` — the SAME array
   `UpdateMissionFrame` iterates, confirming this is the game's single
   flat list of live ships/objects), skipping any whose flags
   (`object+8`) have bit `0x420` set.
3. For each active object, calls `UpdateObjectPhysicsAndTimers`, then
   `UpdateShieldQuadrants`, then `UpdateWeaponFiring`.
4. A round-robin mechanic (`DAT_00562ffc`, advancing by one object
   per tick and wrapping) gives ONE object extra processing each tick
   — calls `FUN_004c2690` twice on it. Shape suggests a cost-spreading
   technique (e.g. refreshing an expensive per-object LOD or AI
   evaluation across many ticks instead of every ship every tick), not
   confirmed.
5. A small special case for the local player's active target
   (checking `**(short**)(object+0x684)==100`).

## `UpdateObjectPhysicsAndTimers` (`0x00476c90`)

Per-object update combining three distinct responsibilities:

**1. Physics transform commit.** If bit 0 of the flags dword at
`object+4` is set, copies a 72-byte (18-float) block from `object+0x5c`
to `object+0x14`, then updates the flags (clearing bits 0/1/3, setting
bits 1/2). Reads as a double-buffered "pending → current" physics
transform commit (position + orientation + velocity would be a natural
72-byte/18-float shape), though this is inferred from the copy/flag
pattern alone, not independently confirmed.

**2. Weapon/shield energy regeneration with 3 curve modes**, selected
by `object+0xb4`:
- Mode 1: clamp the accumulated value to a capacity limit; zero out on
  overflow or when it drops to/below zero.
- Mode 2: repeatedly subtract the capacity limit while the value
  exceeds it (a wrap/modulo-like reload cycle).
- Mode 3: a different wrap variant, feeding the wrapped remainder into
  `FUN_00499f40` (not decompiled).

After the regen step, scans a per-capacity-index sub-table (reached via
`object+0xa4` → `+0x220`, stride `0x28` outer / `0xc` inner) for
entries whose stored value falls into the specific integer range the
regen value just crossed, firing one of two events (`FUN_0047c7b0(0)`
or `FUN_0047c800()`, neither decompiled) based on an entry-type field.
This reads as a generic "fire an event when a regenerating value passes
a threshold" mechanism — plausibly used for weapon-ready or
shield-recharged notifications, not confirmed.

**3. Recurses into attached child objects** (`object+0xf8`=count,
`+0x100`=array of pointers), for any child whose own flags satisfy
`(flags & 0xa0)==0 && (flags & 0x800)!=0`, marking the PARENT with bit
`0x800` in the process. Models attached sub-objects (turrets, docked
craft) receiving the same physics/timer update as their parent, driven
by an explicit worklist/stack rather than recursion in the C sense
(the decompiled function uses a local 500-entry array as a manual
stack).

## `UpdateShieldQuadrants` (`0x00476fc0`) — tentative name

Skips objects with flag bit 1 (`object+8 & 2`) set. If a mode byte at
`object+0xb95` equals 5 (plausibly "docked" or "disabled"), zeroes 4
floats at `object+0x5f0` through `object+0x5fc` and returns
immediately. Otherwise, ramps those same 4 floats toward a capacity
limit derived from the object's class-definition pointer (`object+0x10`),
scaled by elapsed time and two more per-object floats
(`object+0x73c`/`object+0x664`). The LOCAL player's object
(`object+4 == DAT_005883fa`) gets extra handling for array indices 2
and 3 specifically, referencing what look like live control-input
globals (`_DAT_0051cf34`/`_DAT_0051cf78`).

Four independently-regenerating, capped float values per ship, with
special handling for the player's own input, strongly resembles a
**directional/quadrant shield-strength system** — genre-appropriate for
Star Lancer, which is known to feature manageable directional shields.
This interpretation is Confidence 1 (plausible, not confirmed); the
underlying structural fact (4 capped regenerating floats with
player-specific handling) is Confidence 2.

## `UpdateWeaponFiring` (`0x004770e0`) — the real gunnery/auto-fire logic

Skips objects with flag bit 1 set. Ramps a weapon-energy-pool float
(`object+0x140`) toward a capacity limit taken from the class-definition
pointer, then iterates a weapon-hardpoint array (`object+0x130`=short
count, `object+0x134`=array, stride `0x60` bytes per hardpoint). Each
hardpoint entry carries a ready-tick field (compared against
`DAT_005883b0`, the tick counter confirmed elsewhere), a pointer to a
weapon-type definition (reload time, energy cost, and an
ammo/heat-contribution field), and drives the actual fire decision:

- If the weapon type is "energy" (`*piVar8[2]==0`) and enough energy is
  pooled, or "ammo" (`==1`/`==2`) and ammo remains, AND (for
  AI-controlled ships specifically) a `rand()` roll against an
  aggression-like float (`object+0x66c`) succeeds, calls
  `FUN_0047c5f0(0, isLocalPlayer)` — almost certainly the actual
  "fire this weapon" call — then deducts energy or ammo accordingly.
- A difficulty-scaled reload-time modifier applies when
  `object+0x674` is set (`reloadTime * 0x87 / 100` — roughly a 35%
  reload-time reduction, i.e. faster firing on a harder difficulty
  setting, though which literal difficulty level this corresponds to
  isn't confirmed).
- Toggles an "alternate fire group" bit (`object+0x14c`) when a linked
  paired-mount condition is met — the classic alternating-barrel
  firing pattern seen in many space-combat games (fire left gun, then
  right gun, alternating).

Branches distinctly for the LOCAL player's ship vs. others (`object+4
== DAT_005883fa`), meaning this single function implements BOTH the
player's auto-fire-assist behavior and AI gunnery — a genuinely central
piece of the combat model.

## Ship-object struct — partial, confidence-graded field map

Every field below is inferred purely from how the three functions
above (plus `UpdateMissionFrame` from the previous session) dereference
their object pointer — there is no independent data-level
cross-check (unlike `VRRoomNode`, which was verified against real
memory). Deliberately left as prose, not a committed Ghidra struct
type, per METHODOLOGY's confidence discipline.

| Offset | Size | Field (tentative) | Confidence |
|---|---:|---|---:|
| `+0x00` | 4 | object class/type ID | 2 |
| `+0x04` | 4 | **unresolved — see caveat** | 0-1 |
| `+0x08` | 4 | status flags (bit 1 = destroyed?, others per mask) | 2 |
| `+0x14` | 72 | current/committed physics transform | 1 |
| `+0x5c` | 72 | pending physics transform | 1 |
| `+0xa4` | 4 | weapon/shield energy-capacity-group pointer | 1 |
| `+0xb4` | 4 | energy regen curve mode (1/2/3) | 1 |
| `+0xb8` | 4 | capacity-group array index | 1 |
| `+0xbc` | 4 | energy regen rate | 1 |
| `+0xc0` | 4 | energy current value | 1 |
| `+0xf8` | 4 | attached child-object count | 1 |
| `+0x100` | 4 | child-object pointer array | 1 |
| `+0x130` | 2 | weapon hardpoint count | 1 |
| `+0x134` | 4 | hardpoint array (stride `0x60`) | 1 |
| `+0x138` | 4 | per-hardpoint alt-fire counter array | 1 |
| `+0x13c` | 4 | ammo/charge count | 1 |
| `+0x140` | 4 | weapon energy pool | 1 |
| `+0x144` | 2 | weapon-related flags | 1 |
| `+0x148` | 4 | weapon-energy-pool gate | 1 |
| `+0x14c` | 4 | alternate-fire-group toggle | 1 |
| `+0x5f0`-`+0x5fc` | 4×4 | 4 capped regenerating floats (tentatively shield quadrants) | 1 |
| `+0x664`, `+0x66c` | 4 each | ramp-formula floats | 1 |
| `+0x674` | 4 | difficulty-scaled reload-time flag | 1 |
| `+0x734`, `+0x73c` | 4 each | more ramp-formula floats | 1 |
| `+0x754` | 4 | AI/behavior state | 1 |
| `+0xb95` | 1 | special mode byte (5 = disabled/docked) | 1 |

**Open question, deliberately unresolved**: `object+4` is read as an
exact-equality-comparable small integer (the local player's slot index)
in `UpdateShieldQuadrants`/`UpdateWeaponFiring`, but as a
multi-bit-tested flags dword in `UpdateObjectPhysicsAndTimers`. Both
could coexist (low bits = owner index, specific high bits = independent
flags, usually zero) but this is unverified — flagged honestly rather
than resolved by assumption, matching the precedent set by the sibling
`wc3remake` project's own unresolved-question entries.

### Open follow-ups

- `FUN_0047c7b0`/`FUN_0047c800` (energy-threshold events), `FUN_0047c5f0`
  (the actual fire-weapon call), `FUN_004c2690` (round-robin extra
  work) — none decompiled.
- The weapon-type-definition struct reached through each hardpoint
  entry — only scattered field offsets glimpsed.
- Whether the `+0x5f0..+0x5fc` floats really are shield quadrants —
  checking where they're read for HUD rendering would likely settle
  this.
- The ship-object struct's total size is unknown; `+0xb95` is just the
  highest offset touched by the functions opened this session.

---

# Tenth pass (2026-09-08, same day): `FireWeapon` and the weapon-instance/weapon-type structs

Resolved the two "energy-threshold-crossing event" functions flagged
last session as `FUN_0047c7b0`/`FUN_0047c800`, plus the actual
fire-a-shot call `FUN_0047c5f0`.

## `FireWeapon` (`0x0047c5f0`)

```c
void FireWeapon(void *unused, WeaponInstance *weapon, undefined4 unused2,
                 char playSound);
```

The real "fire one shot" function, called both directly (from
`UpdateWeaponFiring`'s player/AI fire decision) and indirectly (from
`FireChildTurrets`, below).

1. Reads a sound/visual variant index (0-14, clamped) from the weapon
   TYPE definition reached via `weapon->+0xac`, field `+0x64`.
2. Scans a 200-entry global projectile/tracer pool
   (`DAT_00563148`, each entry `0x31`=49 dwords) for a free slot
   (sentinel value `-1`) — a flat linear scan, not an explicit
   free-list.
3. Special-cases variant index `0xb`: a `rand()%5 < 2` (40%) roll
   bumps it to `0xc` — an audio/visual variant swap whose purpose
   isn't determined (a "charged" or upgraded-weapon variant is a
   plausible guess, not confirmed).
4. Spawns the projectile (`FUN_0047bdb0`, not decompiled) and sets its
   transform (`FUN_004c10d0`/`FUN_004c0e80`).
5. If `playSound` is set, plays a positional sound effect selected from
   a 15-entry × 11-variant global table (`DAT_00500ce0`, indexed by the
   variant index from step 1) — the 11 variants per entry plausibly
   correspond to different listener-distance/perspective mixes (e.g.
   own-ship-firing vs. another-ship-firing-nearby vs. far away), not
   confirmed field-by-field.
6. Links the new projectile into a global active-projectile
   doubly-linked list (head at `DAT_00563144`).
7. Sets the weapon instance's cooldown-until-tick value
   (`weapon+0xbc`, a float) to the current tick (`DAT_005883b0`) plus a
   per-variant duration from a second 15-entry table (`DAT_00500f64`).

## `FireChildTurrets` (`0x0047c7b0`)

```c
void __thiscall FireChildTurrets(ShipObject *this, undefined4 param);
```

Iterates `this`'s child-object list — the SAME `+0xf8` (count) /
`+0x100` (array) fields documented on the ship-object struct in the
previous session, now cross-confirmed by a second, independent
function using them the same way. For every child whose type ID
(`child+0`) equals `4`, calls `FireWeapon` on it.

This closes a satisfying loop: `UpdateObjectPhysicsAndTimers`'s
per-object energy-regeneration step (documented last session) scans a
capacity-group sub-table for threshold crossings and fires one of two
events — this is one of them. Put together: a capital ship accumulates
"turret energy" via the regen-curve mechanism, and each time it crosses
a threshold, EVERY attached type-4 child object (now a reasonably
confident working guess for "turret") automatically fires. This is a
complete, mechanistic explanation for capital-ship turret-array autofire
in this engine — no separate "turret AI" needed, just the same
generic energy-threshold system already documented, reused.

## `SpawnWeaponVisualEffect` (`0x0047c800`)

```c
void __fastcall SpawnWeaponVisualEffect(WeaponInstance *weapon);
```

The OTHER energy-threshold event handler — confirmed to be a genuinely
different function from `FireChildTurrets` despite both being reached
the same way from `UpdateObjectPhysicsAndTimers`. Scans an
effect-anchor sub-table on the weapon instance (`+0xa4` → count
`+0x214` / array `+0x218`, stride `0x7c`) for entries of type `7`, and
for each match randomizes a UV sub-tile offset on a global active-effect
object (`DAT_005636dc`) — picking a random quadrant from a 4-wide,
2-tall texture atlas (U from a 2-bit random value × 0.25, V from a
1-bit random value × 0.5). This is the classic "pick a random frame
from a muzzle-flash/spark sprite sheet" technique — a visual-only
effect trigger, not a fire-control decision.

## Weapon-instance and weapon-type-definition structs (partial)

Confirmed a two-level chain sitting behind each hardpoint entry
(`shipObject+0x134[i]`, stride `0x60`, documented previously):
`hardpoint[2]` → a **weapon instance** (per-mount runtime state) →
`weaponInstance+0xac` → a shared **weapon type definition** (constant
data reused by every mount of the same weapon).

| Struct | Offset | Field | Confidence |
|---|---|---|---:|
| weapon instance | `+0x24` | reload time | 1 |
| weapon instance | `+0x28` | energy/ammo cost per shot | 2 — `UpdateWeaponFiring` reads this exact offset via `((int*)piVar8[2])[10]` (index 10 × 4 bytes = `0x28`), a direct cross-check |
| weapon instance | `+0xa4` | effect-anchor sub-table pointer | 2 |
| weapon instance | `+0xac` | weapon-type-definition pointer | 2 |
| weapon instance | `+0xbc` | cooldown-until-tick (float) | 2 |
| weapon type definition | `+0x64` | sound/visual variant index (int, 0-14) | 2 |

Global tables keyed by the variant index (0-14): `DAT_00500ce0`
(sound IDs, 11 variants per entry) and `DAT_00500f64` (cooldown
duration per variant).

### Open follow-ups

- `FUN_0047bdb0` (actual projectile spawn) and `FUN_00499f20` (owner-info
  lookup feeding the new projectile's `+0xd` field).
- The 200-entry projectile pool's own layout — only 3 of its 49
  dword-fields glimpsed (`+0xd` owner info, `+0x2f`/`+0x30` linked-list
  prev/next).
- Whether object-class ID `4` really means "turret" — plausible from
  this session's evidence alone, not cross-checked against the other
  known class IDs (`0x6d`, `0xa8`, `0x44`, `0xd`, `0x1f`).
- The `0xb`→`0xc` variant-swap's purpose — **see next pass**: type
  `0xb` also gets independent random direction-jitter treatment in
  `SpawnProjectile`, consistent with a spread/shotgun weapon pair.

---

# Eleventh pass (2026-09-08, same day): `SpawnProjectile` and `GetOwningShip`

Resolved `FireWeapon`'s two remaining unknowns from last session. This
pass produced the richest set of concrete weapon-type semantics so far.

## `GetOwningShip` (`0x00499f20`)

```c
ShipObject *GetOwningShip(void *weaponOrMountObject);
```

Walks a parent-link chain (`+0xec` on each object, following until it
hits `0`, i.e. the root) starting from a weapon or mount object, then
returns the root object's `+0xa8` field — a pointer to the ship that
ultimately owns it, correctly handling arbitrarily deep attachment
(a weapon on a turret on a ship, for instance). The returned pointer's
own fields (`+4` = owner/player-slot index, `+0x644`, `+0x684` =
current-target-like pointer) all match ship-object fields already
documented from earlier sessions — this cross-confirms the existing
ship struct rather than requiring a new one.

## `SpawnProjectile` (`0x0047bdb0`)

```c
void __fastcall SpawnProjectile(int poolSlotIndex, int projectileType);
```

The real per-shot function — fills in the projectile-pool slot
`FireWeapon` already allocated. Dense and not fully decoded line by
line, but several concrete, previously-unknown pieces of weapon-type
behavior are now confirmed:

**The projectile-type table is broader than "sounds."** `DAT_00500ce0`
(11 ints per entry × 15 entries, previously documented only as a sound
table from `FireWeapon`) turns out to hold at least: `+0` sound-ish ID,
`+4` lifetime/duration (used directly as the new projectile's
expiry-tick delta), `+8` scale/radius (a float used both for visual
size and, squared and inverted, as a proximity-detection radius
factor later in the same function). This is really a general
projectile-type DEFINITION table, sound being only one field of it.

**Force-feedback weapon rumble.** If this is the LOCAL player's own
shot and force feedback is enabled (`DAT_0050e1a4`), triggers a
DirectInput force effect — the call shape (`vtable+0x1c`, args
`(self, 1, 0)`) matches `IDirectInputEffect::Start` exactly — selected
from a per-projectile-type array of pre-created effect handles
(`DAT_005ddc58` and 9 siblings, one slot per type 0-10).

**An instant-hit beam-weapon rendering path exists.** Gated by a global
rendering-feature flag (`*(int*)(DAT_00588730+0x1ac) != 0`), creates a
separate "beam" visual effect object (`FUN_004c4f30`) with explicit
color/alpha/width parameters, and recycles a small 2-slot-per-side ring
buffer of recent beam effects (one buffer for the player's beams,
another for everyone else's) — fading out the oldest when a new one
fires. This confirms at least some weapons in this engine render as
instant hitscan beams rather than physically-simulated travel-time
projectiles, though the code gates this on a global flag rather than a
clear per-type check, so which weapon TYPES actually use it isn't
determined from this function alone.

**Type `0xb` = a spread/shotgun-style weapon**, now confirmed two
independent ways: `FireWeapon` (documented last session) gives it a
40% chance to swap to a related variant `0xc`, and `SpawnProjectile`
independently gives it randomized shot-direction jitter (three
independent random offsets, each `(rand()/RAND_MAX - 0.5) * 0.12`
radians-ish, applied via `FUN_004c2410`). Both point the same direction
— `0xb`/`0xc` reads as a spread-weapon pair, plausibly "tight spread"
and "wide spread" variants of the same gun.

**A coherent "special weapons" cluster, types `0xa`-`0xe`.** These are
explicitly exempted from the aim-assist system below (`iVar6 != 0xa &&
iVar6 != 0xb && iVar6 != 0xc && iVar6 != 0xd && iVar6 != 0xe`) — as
opposed to standard forward guns (types `0`-`9`, going by the
force-feedback table's own 0-10 range). Plausibly mines,
countermeasures, and spread weapons as a group, distinct from regular
cannons.

**Difficulty-scaled aim assist — a new, concrete difficulty mechanic.**
If the owning ship's `+0x674` flag is set (the SAME field flagged last
session as a difficulty-scaled reload-time modifier — now confirmed to
gate a SECOND, independent difficulty behavior) and the weapon type
isn't in the special cluster above, applies an aim-correction
adjustment toward the ship's current target (`+0x684`, resolved via
`GetOwningShip`): a simpler correction path for the player's own shots,
a target-flag-gated correction path for AI-controlled shots (checking
`FUN_00401870`, not decompiled). This is a genuine, previously-unknown
"easy mode helps you aim" mechanic.

**Types `0xd`/`0xe` get a dramatically larger proximity-detonation
radius** — the base detection-distance check gets `+1200`/`+3000`
added respectively (versus `+0` for every other type). Combined with
being in the aim-assist-exempt cluster, this is strong evidence these
two types are proximity mines or other area-effect ordnance rather
than direct-fire weapons.

**A proximity/homing-reaction system runs on every shot fired.** Scans
every active object in the main array (`DAT_00587ce0`) each time a
projectile spawns; for any object within the scaled detection radius,
either queues a "nearby object" record (a small, max-20-entry
per-projectile array at pool-slot `+0x68`) if that object isn't yet
flagged "active/awake," or immediately calls `FUN_0049bef0` (not
decompiled — plausibly an AI-alert/evasive-reaction trigger) if it
already is. This reads as the mechanism by which nearby ships notice
and react to incoming fire, though `FUN_0049bef0`'s own behavior isn't
confirmed.

### Open follow-ups

- `FUN_0047d9a0` (projectile transform/velocity init), `FUN_004c4f30`
  (beam-effect creation), `FUN_0049bef0` (proximity-alert reaction) —
  none decompiled.
- The per-projectile-type mesh/visual table (`&DAT_00500cd0`, stride
  `0x2c`=44 bytes) — referenced but not opened.
- Whether the owning ship's `+0x674` flag is really one unified "easy
  mode" toggle (now confirmed to gate both reload speed and aim
  assist) or two coincidentally-related settings sharing a field.
- Which weapon type IDs specifically use the beam-rendering path — the
  code's gate is a global flag, not obviously per-type.

---

# Twelfth pass (2026-09-08, same day): the real weapon arsenal

Decompiled `SpawnProjectile`'s 3 remaining dependencies. One of them
turned out to be the best find of the whole weapon-system investigation
— a function whose `switch` cases are keyed by weapon type ID and whose
mesh-filename arguments are the game's actual weapon names, read
directly from the string table (Confidence 3, not inferred).

## `CreateWeaponProjectileVisual` (`0x0047d9a0`) — the weapon catalog

```c
void __fastcall CreateWeaponProjectileVisual(WeaponOrProjectile *obj, int mode);
```

`obj[0]` (the same "type" field used throughout this whole weapon
subsystem) selects one of 15 cases, each building a different mesh (or
cluster of meshes) and storing the resulting handles back into the
struct. The full arsenal, by type ID:

| Type | Weapon name | Mesh arrangement |
|---:|---|---|
| 0 | **LaserCannon** | single mesh |
| 1 | **PulseCannon** | 2 meshes (BMO1/BMO2), randomized rotation |
| 2 | **MessonBlaster** (Meson Blaster) | 3-mesh radial cluster |
| 3 | **ProtonCannon** | single mesh |
| 4 | **Gattlinglaser** | 3-mesh cluster, 120° spacing |
| 5 | **TachyonCannon** | 2 meshes |
| 6 | **Neutronparticle** (Neutron Particle Cannon) | single mesh |
| 7 | **Collapsergun** | 2 meshes (BMO1/BMO2) |
| 8 | **Gattlingplasma** | 4-mesh cluster |
| 9 | **Vulcanbattery** | 4-mesh square arrangement |
| 10 | **Novacannon** | single mesh, distinct rotation rigging |
| 0xb | **Turretflak** (Turret Flak) | matches the spread/shotgun jitter found in `SpawnProjectile` exactly |
| 0xc | **TurretLaser** | the `0xb`→`0xc` variant-swap partner — turret-mounted precision laser |
| 0xd | **AlliedHugeGun** ("Allied_big_gun") | capital-ship superweapon, Allied faction |
| 0xe | AlliedHugeGun mesh + "Coal_big_gun" effect | same base mesh as `0xd` but a visibly larger glow/burst scale — the Coalition-faction equivalent |
| default | **gundefault** | fallback mesh for any unrecognized type |

Each case also sets a small color/tint pair (`local_40`/`local_44`)
gated by the `mode` parameter and a deathmatch flag (`DAT_00582e8c`) —
plausibly a friendly/hero color distinction (e.g. tinting the local
player's own shots differently), not confirmed field-by-field. The two
"huge gun" cases (`0xd`/`0xe`) get visibly richer treatment than every
other type: a full 24-field transform block set to defaults, PLUS a
dedicated glow effect via `CreateEffectObject`, PLUS a second special
object via `FUN_0049c600` (not decompiled) — consistent with these
being the game's showcase capital-ship superweapons.

**This corrects last session's guess.** Types `0xd`/`0xe` were
tentatively called "proximity mines" based on their larger
detonation-radius bonus in `SpawnProjectile`. They're actually
**faction-specific capital-ship superweapons** (Allied vs. Coalition —
matching Star Lancer's known two-faction setting), and the larger
detection radius makes much more sense as generous hit-detection for a
massive shot than as a mine's blast radius. Marked down rather than
silently dropped, per METHODOLOGY's confidence discipline.

## `CreateEffectObject` (`0x004c4f30`)

```c
void *__thiscall CreateEffectObject(void *unused_this, int ownerTag,
                                     float x, float y, float z,
                                     float rx, float ry, float rz);
```

A small, genuinely generic renderable-effect-object constructor:
allocates 220 bytes (`SR_MEM_allocate`, tagged `surrenderlib\...` line
`0x2b5` — confirming this lives in the SurrenderLib engine core, not
game-specific code), sets position and orientation, stores an owner tag
at `+4`, and defaults a scale/alpha-like field (`+0x48`) to `1.0`. Used
by two independent callers now — the beam-weapon visual in
`SpawnProjectile` and the huge-gun glow effect here — confirming it's
real shared infrastructure, not a one-off.

## `PropagateAlertToChildren` (`0x0049bef0`)

```c
void __thiscall PropagateAlertToChildren(GameObject *obj, void *alertSource);
```

Simpler than its name (and its role in `SpawnProjectile`'s
proximity-detection scan) suggested: tests a predicate
(`FUN_0049bd30(alertSource)`, not decompiled) and, if true, recurses
into `obj`'s child-object list — the SAME `+0xf8`(count)/`+0x100`(array)
fields documented in two earlier sessions, now confirmed a THIRD
independent way — calling itself on every child not flagged `0xa0`.
There is no other logic in this function: whatever "alert" or
"reaction" actually happens must live inside `FUN_0049bd30` itself,
which remains completely unopened. This function is purely a
hierarchy-propagation wrapper, not the reaction logic itself as
originally assumed.

### Open follow-ups

- `FUN_0049bd30` — the real predicate/reaction logic behind
  `PropagateAlertToChildren`. Now the clearest single next step if the
  "how do nearby ships react to incoming fire" question matters.
- `FUN_0049c600` — the second special object attached to huge-gun
  weapons only.
- The `mode` parameter's exact meaning in `CreateWeaponProjectileVisual`
  (tentatively a friendly/hero color-tint selector).
- ~~The low-level draw primitives called throughout this whole session~~ — **resolved next session, see below.**

---

# Thirteenth pass (2026-09-08, same day): SurrenderLib scene-node primitives

Opened the 5 low-level draw/transform primitives flagged last session.
All are genuinely generic SurrenderLib engine core — confirmed by the
same recurring `SR_MEM_allocate` source-tag pattern
(`C:\lancer\surrender\surrenderlib\...`) seen for `SR_printf` and the
assertion functions back in the second session, at distinct line
numbers per call site — not game- or weapon-specific despite being
found via the weapon-rendering trace.

## `SetPosition` (`0x004c0e60`)

```c
void __thiscall SetPosition(Transform *this, float x, float y, float z);
```

Exactly what it looks like: `this->x, this->y, this->z = x, y, z`. No
surprises — confirms the "set position" guess carried since the
weapon-firing investigation began.

## `SetOrientationMatrix` (`0x004c2410`)

```c
void __thiscall SetOrientationMatrix(float matrix[9], float angle1,
                                      float angle2, float angle3);
```

Builds a full 3×3 rotation matrix (9 floats, `matrix[0]` through
`matrix[8]`) from 3 Euler-style angles, computing sine and cosine of
each (`FUN_004c30e0`/`FUN_004c3100`, one call of each per angle — not
individually confirmed as cos/sin, but the pattern is consistent with
it) and combining them with the standard rotation-matrix-composition
arithmetic. Confirms this engine represents orientation as a 3×3
matrix rather than a quaternion, typical for its era (1999).

## `CreateMeshInstance` (`0x004c4bd0`)

```c
void *__fastcall CreateMeshInstance(void *parentGroup, MeshTemplate *tmpl,
                                     uint flags, void *ownerTag);
```

The core "instantiate a renderable mesh" factory. If `parentGroup` is
given, aggregates bounding-box/radius info across its list of
sub-templates; otherwise reads the bounding info directly from `tmpl`.
Computes an exact allocation size that grows if `flags` requests
optional per-instance override buffers (bits `0x200000`/`0x400000`,
each adding a buffer sized `faceCount*8` bytes — plausibly per-vertex
color or per-face UV override arrays, not confirmed). This is
real, general-purpose SurrenderLib rendering infrastructure — used for
weapon meshes in the functions traced this session, but with no
weapon-specific logic of its own; it's presumably the same factory
used to instantiate every renderable mesh in the game (ships, ship
interior VR-room props, etc.), though this session's trace only
reached it via the weapon system.

## `CreateMultiPartMeshGroup` (`0x004c4db0`)

```c
void *__fastcall CreateMultiPartMeshGroup(int partCount, void *parentRef,
                                           const char *name);
```

A related but distinct factory: allocates a variable-sized structure
holding `partCount` 100-byte sub-part records (each defaulted to unit
scale), with a name/tag stored separately. Note: at
`CreateWeaponProjectileVisual`'s call sites, the visible argument
(e.g. `"PulseCannon_BMO1"`) is the STACK-passed third parameter
(`name`), not `partCount` — `partCount`/`parentRef` are passed via the
implicit `ECX`/`EDX` fastcall registers the decompiler doesn't surface
at those call sites, consistent with the recurring pattern seen all
session for `__fastcall`/`__thiscall` functions. This is almost
certainly the real constructor behind the "BMO" naming convention seen
throughout the weapon mesh catalog (`PulseCannon_BMO1`/`BMO2`,
`Collapsergun_bmo1`/`bmo2`, the huge guns' bmo effects) — a multi-part
object whose parts can be transformed independently (e.g. a
dual-barrel weapon's two barrels animating on separate recoil cycles).
"BMO" itself doesn't appear spelled out anywhere in the string table
found so far.

## `CreateGroupNode` (`0x004c51c0`)

```c
void *__thiscall CreateGroupNode(void *ownerTag, float x, float y, float z,
                                  float rx, float ry, float rz);
```

A small (180-byte) generic scene-node constructor: position +
orientation (via `SetPosition`/`SetOrientationMatrix`) + owner tag.
Structurally almost identical to `CreateEffectObject` (220 bytes,
documented last session) but calls a different secondary
initialization step (`FUN_004c4190`, not decompiled, vs. none for
`CreateEffectObject`). Likely the base "parent/group" node type used to
hold multiple child mesh instances together under one transform — e.g.
a multi-barrel weapon's group root, or a projectile's root transform
kept separate from its visible mesh instance(s).

### Open follow-ups

- `FUN_004c30e0`/`FUN_004c3100` (presumed cos/sin, not confirmed).
- `FUN_004c1be0`/`FUN_004c0e30` (each called twice in both
  `CreateMeshInstance` and `CreateMultiPartMeshGroup` — likely
  default-initializing two sub-blocks such as a bounding box and a
  local transform).
- `FUN_004c4190` (`CreateGroupNode`'s extra init step).
- The exact meaning of `CreateMeshInstance`'s `0x200000`/`0x400000`
  flag bits.
- What "BMO" actually stands for.

---

# Fourteenth pass (2026-09-08, same day): the effect-anchor callback system, and a correction

## `CreateParticleEmitter` (`0x0049c600`)

```c
ParticleEmitter *__fastcall CreateParticleEmitter(void *ownerTag);
```

Real name confirmed directly — `SR_MEM_allocate` tags this allocation
`C:\lancer\game\particles.cpp` line `0x100`. Allocates a 252-byte,
mostly-zeroed particle-emitter object: creation timestamp
(`DAT_005883b0`, the tick counter), a few default-scale fields (`1.0`),
and an owner tag. This is the second special effect object
`CreateWeaponProjectileVisual` attaches to the two huge-gun weapon
types (`0xd`/`0xe`) — confirms they get both a glow light
(`CreateEffectObject`, documented previously) AND a genuine particle
effect, consistent with these being the game's flagship capital-ship
superweapons.

## `InvokeEffectAnchorCallback` (`0x0049bd30`) — and a correction to last session's write-up

```c
undefined4 __fastcall InvokeEffectAnchorCallback(void *object,
                                                   char (*callback)(void));
```

Turns out to be more general than assumed: this is a **generic
callback-invoking tree walker**, not a simple true/false predicate.
The second parameter is a genuine function pointer — confirmed
directly by the decompiler's own `(*param_2)()` call syntax, not
inferred.

Two modes, selected by whether `object+0xa8` is set:

- **Unset** (`+0xa8==0`): walks the object's own effect-anchor
  sub-table (`+0xa4` → count at `+0x20c`, array at `+0x210`) using a
  manual worklist stack (the same "local array as an explicit stack"
  idiom seen in `UpdateObjectPhysicsAndTimers` two sessions ago).
  For each anchor node, applies a visual/transform setup, then:
  if the node is a "leaf" (`+0x48==0`)... actually the logic is
  inverted from what that reads like — when `+0x48==0` the callback is
  invoked and, if it returns nonzero, the node's own two child-offset
  fields (`+0x50`/`+0x54`) get pushed onto the worklist for further
  descent; when `+0x48!=0` the callback is invoked unconditionally
  with no further recursion. Either way, the callback decides whether
  traversal continues past a given node.
- **Set** (`+0xa8!=0`): skips the anchor-table walk entirely, does one
  simplified visual/transform pass targeting `object+0xa8`'s own
  `+0x5a0` sub-field, and invokes the callback exactly once.

This is a THIRD distinct effect-anchor table shape found in this
investigation — `+0xa4 → +0x20c/+0x210` here, versus `+0xa4 →
+0x214/+0x218` on the object `SpawnWeaponVisualEffect` operates on.
Whether these are the same conceptual table with different exact
offsets on different sub-object types, or genuinely unrelated
tables that happen to share the `+0xa4` base offset, is NOT resolved.

### Correction: `PropagateAlertToChildren`'s second parameter is a callback, not an "alert source"

Last session's write-up described `PropagateAlertToChildren`'s
`param_2` as "an alert source" being propagated to child objects. With
`InvokeEffectAnchorCallback` now decompiled, it's clear `param_2` in
BOTH functions is the same kind of value: a callback function pointer.
`PropagateAlertToChildren` recurses through a ship's child-OBJECT
hierarchy (`+0xf8`/`+0x100`) passing the callback down unchanged at
each level; `InvokeEffectAnchorCallback`, called once per such object
by `SpawnProjectile`'s actual usage, separately walks that SAME
object's own internal effect-ANCHOR tree, invoking the callback there
too. Put together, `SpawnProjectile`'s proximity-reaction scan installs
one callback and runs it across BOTH axes — every object in a
hierarchy, and every effect-anchor point on each object — rather than
the simpler "check a predicate, then alert children" picture the
previous session's more limited view suggested.

**What the callback actually DOES on each invocation remains unknown**
— the traversal SHAPE is now clear, but the real function pointer(s)
passed in at actual call sites haven't been identified. This is an
explicit correction, not a silent edit, per METHODOLOGY's confidence
discipline: the earlier "proximity-alert reaction" framing is
downgraded from an implied-confirmed mechanism to "traversal shape
confirmed, purpose still open."

### Open follow-ups

- ~~The real callback function(s) passed to `InvokeEffectAnchorCallback`/`PropagateAlertToChildren`~~ — **found immediately next, see below.**
- Whether the `+0xa4→+0x20c/+0x210` anchor-table shape here and the `+0xa4→+0x214/+0x218` shape on `SpawnWeaponVisualEffect`'s target object are related or coincidental.
- The anchor-node `+0x50`/`+0x54` child-offset fields' own structure.

---

# Fifteenth pass (2026-09-08, same day): `ProcessProjectileImpact` — hit detection, shields, and subsystem destruction

Checked every real caller of `PropagateAlertToChildren`/
`InvokeEffectAnchorCallback` to find the actual callback functions.
This single check resolved last session's open question completely —
and turned out to be the game's actual combat-damage-resolution logic,
arguably the most gameplay-central function found in this whole
investigation.

## `ProcessProjectileImpact` (`0x00479b40`)

```c
void __fastcall ProcessProjectileImpact(ProjectilePoolSlot *slot);
```

Processes the "nearby object" queue `SpawnProjectile` builds during its
proximity scan (confirmed by matching field shape: a count and a
parallel array, matching pool-slot `+0x64`/`+0x68` documented several
sessions ago). For each queued nearby object:

1. **Re-derives the exact same type-`0xd`/`0xe` detection-radius bonus**
   (`+1200`/`+3000`) found independently in `SpawnProjectile`'s
   spawn-time scan — direct cross-confirmation from the
   damage-application side of that earlier finding, not just a repeat
   guess.
2. **Solves a quadratic** for the projectile's closest approach to the
   target along its travel line, comparing the result against the
   target's own radius plus the type-based bonus, to determine an
   actual hit.
3. **On a hit, resolves a shield-facing index** (`FUN_00463d30`, not
   decompiled — "which of the 4 quadrants got hit") and applies damage
   directly to the shield-quadrant floats first documented (as a
   plausible guess) on the ship-object struct four sessions ago
   (`shipObject+0x5f0 + facing*4`). **This promotes that struct
   interpretation from Confidence 1 to Confidence 2-3**: the floats
   are directly read and decremented here as real damage-absorption
   values, not just ramped toward a cap as `UpdateShieldQuadrants`
   alone suggested. The same `_DAT_0051cf34`/`_DAT_0051cf78` globals
   `UpdateShieldQuadrants` referenced for live player redistribution
   input turn out to be active "damage currently draining this
   quadrant" trackers, used by both functions.
4. **Gives flak and turret-laser weapons (types `0xb`/`0xc`) a 2.5×
   damage multiplier** specifically against non-player (larger,
   presumably capital-ship-scale) targets — a concrete confirmation
   that these two weapon types have an anti-capital-ship point-defense
   role, beyond just being a "spread weapon pair" as documented three
   sessions ago.
5. Applies the resolved damage via an `ApplyDamage`-shaped function
   (`FUN_00463ee0`, not decompiled).
6. **Invokes `InvokeEffectAnchorCallback` a second time, recursively,
   against the HIT SHIP's own subsystem/component list.** This is the
   resolution of the whole callback investigation: the traversal is
   used here to check whether the impact lands on a specific
   independently-targetable SUBSYSTEM or COMPONENT of the ship (an
   entry in its own effect-anchor tree), and if so applies separate
   component-level damage/destruction, plays a type-specific explosion
   effect (visibly bigger for the `0xd`/`0xe` huge guns), and triggers
   a distinct impact sound via `FUN_0049d360` — the SAME sound-trigger
   function documented inside `FireWeapon` four sessions ago, now seen
   used for impacts as well as shots fired.

**This confirms genuine subsystem/component-level ship damage** —
individual ship parts (turrets, engines, fins, or similar) can
apparently be independently targeted, damaged, and destroyed, rather
than the whole ship sharing one undifferentiated hit-point pool. This
is a significant, previously-unconfirmed piece of the combat model.

## `UpdateShieldPowerAndComponents` (`0x00465380`) and `HandleComponentDestroyedEvent` (`0x00495ac0`)

Two more `PropagateAlertToChildren` callers, both only skimmed this
session (Confidence 1, real follow-up candidates):

- `UpdateShieldPowerAndComponents` appears to handle PLAYER-INITIATED
  shield power redistribution — decrementing the same
  `_DAT_0051cf34`/`_DAT_0051cf78` quadrant-drain trackers on player
  input, matching the classic "redistribute shield power between
  facings" control scheme common to space combat sims — entangled with
  a named-component lookup against a literal string `"Ulysses Fin"`,
  very likely referencing an in-universe capital ship class ("Ulysses")
  and one of its targetable subsystems ("Fin"), consistent with the
  component-damage system `ProcessProjectileImpact` revealed.
- `HandleComponentDestroyedEvent` is smaller: checks a component-state
  code (skipping for values `2`/`7`) and triggers an effect via
  `FUN_004645c0` — plausibly fired specifically when a targeted
  subsystem is destroyed, given the name context, though not
  confirmed.

### Open follow-ups

- `FUN_00463d30` (hit-facing resolver), `FUN_00463ee0` (apply-damage),
  `FUN_004645c0` (an effect/sound dispatcher — ID + owner + code — now
  seen called from at least 3 different functions this session, worth
  opening if the combat-feedback/audio system becomes a focus),
  `FUN_00479940`/`FUN_00479b30` (hit-exemption checks referenced but
  not opened).
- "Ulysses" as a probable in-universe capital ship class name — worth
  a string-table sweep for sibling ship names if fleet/lore naming
  becomes a focus.
- The component/subsystem list's own structure — only the existence
  and rough shape of the damage model is confirmed, not the anchor
  entries' own field layout.
- `UpdateShieldPowerAndComponents`/`HandleComponentDestroyedEvent`
  deserve a full decode pass if the shield/subsystem-damage system
  becomes the next focus.

---

# Sixteenth pass (2026-09-08, same day): `ApplyShieldDamage` and `ApplyComponentDamage`

Resolved the 3 functions flagged at the end of last session
(`GetShieldFacingIndex`, `ApplyShieldDamage`, `ApplyComponentDamage`).
Together these complete the two-stage damage model `ProcessProjectileImpact`
dispatches into: shields absorb per-facing damage with hull spillover,
and separately, individually-targetable components use their own
grouped-hitbox health pools.

## `GetShieldFacingIndex` (`0x00463d30`)

```c
int __fastcall GetShieldFacingIndex(void *hitContext);
```

Thinner than expected: sets up a transform context from a sub-object
reference (`hitContext+0x30` → `+0x70`, an unidentified turret/hardpoint
position field) and delegates the actual "which of the 4 shield
quadrants was hit" computation to `FUN_00463ca0` (not decompiled). The
real geometry logic lives in that unopened call.

## `ApplyShieldDamage` (`0x00463ee0`)

```c
void __fastcall ApplyShieldDamage(ShipObject *target, int quadrantIndex,
                                   float damageAmount, float damageRatio,
                                   int attackerSlot, int damageType);
```

The real shield-damage pipeline, and a genuinely complete one:

1. **Invulnerability/exemption checks**: exits immediately if the
   target has an invulnerability flag (`+8 & 0x200000`) or its
   class-definition state is `6` (a "special/scripted, no damage"
   object state, not otherwise identified).
2. **Overflow calculation**: computes how much damage would exceed the
   quadrant's current shield value — this becomes the amount that
   spills through to the hull.
3. **Difficulty scaling**: passes the raw damage through
   `FUN_00463d70` (not decompiled, presumably applying an
   easy/normal/hard multiplier).
4. **Scoring and feedback**: if the LOCAL PLAYER is the attacker (and
   the target isn't on their own team), triggers scoring/kill-credit
   (`FUN_00474c80`) for certain damage types; if the LOCAL PLAYER is
   the one hit, triggers camera-shake and audio feedback
   (`FUN_00456dd0`/`FUN_00463e10`).
5. **Multiplayer authority and team rules**: in networked play, checks
   `FUN_004b5590` ("does this client have authority to actually apply
   this damage") before committing anything; in deathmatch, compares
   team-ID arrays (`DAT_005dae30`, indexed by object slot) and a
   friendly-fire-enabled flag (`DAT_0050c2f8`) to decide whether damage
   applies at all between the two objects involved.
6. **Commits the shield decrement**, and if it goes negative, spills
   the excess (scaled by `damageRatio`) to the hull via `FUN_004641f0`
   (not decompiled — "ApplyHullDamage").
7. **UI/network bookkeeping**: records the last attacker, flags
   "recently hit" state for HUD flash effects (two parallel arrays,
   one all-ships-wide and one local-player-specific), and plays an
   impact sound.

A clean, complete shield-then-hull pipeline — the kind of function that
would make an excellent differential-test target if a live/dynamic
harness for this game is ever built (well-defined inputs, well-defined
observable state changes).

## `ApplyComponentDamage` (`0x004645c0`)

```c
void __fastcall ApplyComponentDamage(ShipObject *object, ComponentInstance
                                      *component, float damageAmount,
                                      int attackerSlot, int damageType);
```

The real subsystem/component damage function, and considerably richer
than the shield pipeline:

- **Input validation via a real runtime assert**: `attackerSlot` is
  bounds-checked against the live active-object count (or must be
  `-1`, "no attacker") using `ReportAssertionFailureEx` — confirming
  that function (documented back in the second session as the
  engine's general-purpose fatal-assert mechanism) is genuinely used
  throughout gameplay code, not just bootstrap/resource-loading paths
  as the earlier sessions' evidence alone suggested.
- **A grouped-hitbox component model**: components share a group ID
  (`+0xd4`) and pool their health across potentially several separate
  physical hit-collision pieces. Before applying damage, the function
  walks the target's child-object list looking for that group's
  "representative" member — the one still holding remaining health
  (`+0x104>0`) — meaning a single logical subsystem (e.g. an engine
  cluster, a turret battery) can be modeled as multiple independently
  collidable meshes that nonetheless share one combined HP pool.
- **An armor/threshold system**: components with health above `0x9c3`
  (2499) are immune to small hits (under 500 damage) unless the damage
  type is "penetrating" (type 3 or 4) or a specific target flag is set
  — some subsystems need a proportionally large hit to actually
  register damage, not just enough raw damage.
- **Shielded-component damage reduction**: hits under 1000 damage
  against a component flagged `0x4000` get reduced to 25% — suggesting
  certain components carry their own point-defense-resistant armor
  independent of the ship's main shields.
- **Friendly/ally exemption list**: a small per-object table
  (`+0x250`, up to `+0x152` entries) is checked to decide whether a
  particular attacker is exempt from damaging this component — plus a
  deathmatch-specific team check.
- **On destruction** (health drops below 0): sets a "destroyed" flag
  bit (`0x40`) on the component, and — specifically when it's the
  LOCAL PLAYER's own ship being damaged, outside deathmatch — triggers
  a distinct reaction (`FUN_00474e00`, not decompiled, plausibly a
  "you've lost a subsystem" warning).
- **Wingman/comm chatter**: if a friendly AI wingman had this exact
  component as an assigned escort/protect target, triggers comm
  chatter (`FUN_00415270`).
- **A second, separate "representative component" resolution** at the
  end (two lookup variants depending on a `+0x108` grouping field,
  distinct from the `+0xd4` grouping used earlier) followed by an
  impact sound — the relationship between the `+0xd4` and `+0x108`
  grouping schemes isn't determined; they may represent two different
  levels of component hierarchy (e.g. individual part vs. whole
  subsystem).

### Open follow-ups

- `FUN_00463ca0` (real shield-facing geometry), `FUN_00463d70`
  (difficulty damage scaling — shared by both functions), `FUN_004641f0`
  (hull-damage spillover), `FUN_004b5590` (multiplayer damage
  authority — also shared), `FUN_00474c80`/`FUN_00474e00` (scoring and
  component-destroyed reactions), `FUN_00415270` (wingman chatter
  trigger).
- The `+0xd4` vs. `+0x108` component-grouping fields' relationship to
  each other.
- The armor-threshold constant (`0x9c3` = 2499) and other balance
  numbers found here — real, load-bearing values, not yet cross-checked
  against any external data source (e.g. a ship-stats file) to see
  whether they're globally hardcoded or per-ship-class tunable.

---

# Seventeenth pass (2026-09-08, same day): difficulty curve, multiplayer authority, hull tier, hit geometry, ship destruction — and a correction

Resolved all 4 functions flagged at the end of last session, plus a
5th (`SetShipDestroyedState`) found by following `ApplyHullDamage`'s
depleted-hull path. This round produced the most concrete, precisely
quantified gameplay-balance data of the whole investigation, and forced
a correction to how `object+0x684` has been described since it first
appeared 4 sessions ago.

## `ScaleDamageForDifficulty` (`0x00463d70`) — the exact difficulty curve

```c
float __fastcall ScaleDamageForDifficulty(int targetSlot, int attackerSlot,
                                            float rawDamage);
```

Read directly from the decompiled arithmetic, not inferred:

- **Deathmatch/PvP damage is never difficulty-scaled** — the function
  returns the raw value unchanged whenever `DAT_00582e8c` (the
  deathmatch flag) is set.
- **Outgoing damage** (when the LOCAL PLAYER is the attacker, hitting a
  non-teammate): difficulty 0 (easy) → **1.5×**, difficulty 1 (normal)
  → **1.0×** (no scaling), difficulty 2 (hard) → **0.75×**.
- **Incoming damage** (when the LOCAL PLAYER is the target) carries a
  baseline **0.5× reduction** that a further difficulty modifier
  applies on top of: easy → `0.75 × 0.5` = **0.375×**, normal →
  `1.0 × 0.5` = **0.5×**, hard → `1.5 × 0.5` = **0.75×** (the hard-mode
  code path returns early with exactly this product, while the other
  two fall through an unconditional extra `×0.5` at the end of the
  function). The player always takes at most half of "raw" incoming
  damage, difficulty only adjusts how much further below that floor.

This is a real, deliberately-authored difficulty curve, not a flat
per-difficulty multiplier — a concrete, quotable piece of the game's
actual balance design.

## `HasDamageAuthority` (`0x004b5590`) — distributed multiplayer damage ownership

```c
bool __fastcall HasDamageAuthority(int objectSlot);
```

For actual player-controlled ships (`objectSlot < DAT_0058832c`, the
player count): only the ship's OWNING client has authority to apply
damage to it (`objectSlot == localPlayerSlot`) — standard
"you own your own ship's state" networking. For everything else
(NPCs/AI ships): in deathmatch, only the HOST applies damage
(`DAT_005dc1e8==1`); in co-op/campaign multiplayer, NPC damage
authority is **distributed round-robin across all connected clients**
via a modulo scheme — `(objectSlot - perClientBaseOffset[localSlot]) %
objectsPerClient == 0`. Rather than the host simulating every NPC and
broadcasting results (simple but a bottleneck), each client owns and
authoritatively simulates damage for a distinct subset of the NPC
population. A genuinely interesting piece of distributed-simulation
network architecture for a 1999 game.

## `ApplyHullDamage` (`0x004641f0`) — a third defense tier

```c
void __fastcall ApplyHullDamage(ShipObject *target, int sectionIndex,
                                 float damageAmount, int attackerSlot,
                                 int damageType);
```

Structurally almost identical to `ApplyShieldDamage` (same
invulnerability check, same difficulty scaling, same multiplayer
authority gate, same scoring/feedback calls) but operates on a
COMPLETELY SEPARATE float array: `target+0x600 + sectionIndex*4`,
distinct from the shields' `+0x5f0` array. **This confirms the damage
model has three tiers — shields, then hull/armor sections, then
individually-targetable components — not the two-tier "shields then
components" picture the previous session's evidence alone suggested.**
A ship in "disabled/docked" special-mode (`+0xb95=='\x04'`) takes zero
hull damage regardless of amount (fully absorbed, presumably to
prevent griefing/damage to non-combat-state ships). When a hull
section's value drops below zero, calls `SetShipDestroyedState` with a
boolean flagging whether the killing blow exceeded `1000.0` damage —
**this is the actual ship-destruction trigger**.

## `ComputeHitQuadrant` (`0x00463ca0`) — the real facing geometry

```c
int __fastcall ComputeHitQuadrant(ShipObject *ship, float localHitPoint[3]);
```

`GetShieldFacingIndex`'s real payload. Divides the local-space impact
point's two relevant axis coordinates by the ship's own bounding-box
extents on each axis (`ship+0x5a0..+0x5b4`, 4 floats — min/max on 2
axes), determines which axis the hit is predominantly along (via an
`fabs`-shaped comparison), and returns a quadrant index 0-3 based on
the dominant axis and its sign. This is genuine geometric hit-facing
detection from real 3D impact coordinates — the strongest confirmation
yet (Confidence 3) that the "4 shield quadrants" structural model
first guessed 4 sessions ago is correct, and that the game computes
which facing is actually hit rather than tracking 4 independent values
some other way.

## `SetShipDestroyedState` (`0x00401f30`) — and a correction to `object+0x684`

```c
void __fastcall SetShipDestroyedState(int shipSlot, bool wasBigHit,
                                       char param_3);
```

Source-tagged `C:\lancer\game\Ai.cpp` (two allocations, lines `0x5d9`
and `0x5da`) — confirms ship AI/behavior logic lives in a dedicated
`Ai.cpp` file, distinct from the mission/interface/bigfile/particle
files already identified in other sessions. Reveals that
`shipObject+0x684` is a pointer to an **AI command/state structure**,
lazily allocated (0x208 bytes) the first time it's needed. The
function pushes a command onto it: type `0xb` (11) meaning
"destroyed" (skipped if the ship is already in that state — no
double-destruction), or type `0x6c` (108) under specific NPC-only
conditions (non-player slot, a small counter under `0x28`=40, or a
"special mode 3" state) — a distinct, not-yet-understood
pre-destruction state, plausibly something like "critically damaged" or
an eject/bail-out trigger for AI pilots. The "big hit" boolean passed
in gets stored directly into the queued command's own data, presumably
selecting a bigger explosion effect downstream.

### Correction: `object+0x684` is an AI command/state pointer, not a "current target"

Three earlier sessions — `GetOwningShip`, `ProcessMissionSimulationTick`,
and `SpawnProjectile`'s aim-assist logic — described `+0x684` as
pointing to something read as "the ship's current target," based on
how it was dereferenced at those call sites. `SetShipDestroyedState`
now shows this field is actually the head of an AI command/state
queue: a lazily-allocated structure whose first field is a
command-type short (observed values: `0xb`=destroyed, `0x6c`=108, and
separately `100` checked by `ProcessMissionSimulationTick`, all
plausible members of one AI-command enum). This is a genuine
correction, not a refinement — "current target" and "current AI
command" are different concepts, and the earlier label was wrong.

What stays true: the field's existence, its role as something
`GetOwningShip` resolves through the object hierarchy, and the fact
that `SpawnProjectile`'s aim-assist logic checks it before adjusting
aim — only the semantic meaning of WHAT is being checked changes (the
target's current AI behavior/state, not a target reference). The
aim-assist mechanism's existence and difficulty-gating are unaffected
by this correction. Recorded explicitly per METHODOLOGY rather than
silently editing the earlier sessions' text.

### Open follow-ups

- ~~`FUN_0040ca50`~~ — resolved immediately below.
- The `object+0x600` hull-section array's own element count (shields
  are confirmed 4 quadrants; hull sections aren't confirmed to match).

## `TrySetAiState` (`0x0040ca50`) — a priority-gated AI finite-state-machine

```c
bool __fastcall TrySetAiState(int shipSlot, int newStateId);
```

The function `SetShipDestroyedState` calls to actually push its
command — and it turns out to be the GENERAL-PURPOSE AI state
transition function, confirming `Ai.cpp`'s command system drives all
ship AI behavior changes, not just destruction.

Reveals a genuine state-definition table (`PTR_DAT_004e06e0`, indexed
`[stateId/100][stateId%100]`, 24 bytes per entry) with real per-state
metadata:

| Field offset | Meaning |
|---|---|
| `+8` | OnExit callback — invoked when leaving this state |
| `+0xc` | flags byte; bit `0x20` = unconditionally allow transitions INTO this state, bypassing the priority check |
| `+0x10` | display-name string — used directly in debug/assert messages |
| `+0x14` | priority (int) |

**A new AI state can only be entered if its priority exceeds the
ship's CURRENT state's priority** — otherwise the request is rejected
and logged via `ReportAssertionFailureEx` with a message built from
both states' display names (`"Cannot set ai '%s' on ship '%s'. Still
..."` for a normal rejected transition, `"Cannot clear ai on ship '%s'.
Still ..."` for a rejected clear-AI request via `newStateId == -1`).
State `0xb` ("destroyed") bypasses this check entirely via the
special-case flag — explaining exactly why `SetShipDestroyedState`
still checks `if (currentState != 0xb)` itself before calling this: to
avoid a redundant OnExit callback on an already-destroyed ship, not
because the priority system would otherwise block it.

Early exits: a ship with `+0x680==0` (not yet AI-initialized) trivially
allows any request (nothing to validate against yet); one with
`+0x688!=0` (mid-transition) also trivially allows it; a
destroyed/inactive ship (flags `& 0x10000840`) trivially rejects any
request.

This is a well-designed, general priority-based finite-state-machine —
not an ad-hoc destruction-only mechanism as it first appeared from
`SetShipDestroyedState` alone.

### Open follow-ups

- ~~The actual CONTENTS of `PTR_DAT_004e06e0`~~ — **read directly next, see below.**
- Whether priority values are universal constants or vary by ship
  class.

---

# Eighteenth pass (2026-09-08, same day): the AI state catalog, read directly

Read `PTR_DAT_004e06e0` and its two adjacent group tables directly
from process memory via `read_memory`, rather than continuing to
decompile — the table's CONTENTS were the actual open question, not
more code. This is raw binary data (Confidence 3), not inferred.

## Table structure

`PTR_DAT_004e06e0` is a 3-element array of pointers, one per "hundreds
group" (`stateId/100` selects the group, `stateId%100` indexes within
it — matching `TrySetAiState`'s own indexing exactly):

- Group 0 → `0x004e0050`
- Group 1 → `0x004e04a0`
- Group 2 → `0x004e06c8` (not read this session)

Each 24-byte entry: two leading callback slots not read by
`TrySetAiState` itself (`+0`, `+4` — plausibly OnEnter/OnUpdate
handlers used elsewhere), `+8` the OnExit callback `TrySetAiState`
calls, `+0xc` a flags byte (bit `0x20` = unconditional-transition, as
documented last session), `+0x10` a pointer into a nearby string pool,
`+0x14` the priority integer.

## The state names

**Group 0** (string pool at `0x4e0a80`, ~20 entries read in table
order): `Find Scoop Up`, `Jump Out`, `Jump In`, `Slow Rotate`, `Ship
Follow Curve`, **`Toggle Cloak`**, `Patrol Route`, `Formation
Regroup`, `Object Attack`, `"Ripper grabs target object"`, `Explode`,
`Find New Target`, `Escort`, `Land`, `Run Away`, `Fly`, `Warp Out`,
`Warp In`, `Launch Missile`, `Fly Aimlessly`, `Do Nothing`.

**Group 1** (string pool at `0x4e0780`, ~20 entries read): `"...ght"`
(truncated in the read window, plausibly `Fight`), `"Make capship
list left"`, `Disrupted`, `"Eject fighter attack"`, `"Ripper attach
cargo pod to Mammoth"`, `"Ripper end drop object"`, `"Dark reign
shoot"`, `Dock`, `Eject Spin`, `Scoop Up`, `Fight`, `Launch`,
`Torpedo`, `Avoid Target`, `Multiplayer Control`, `Player Control`,
`"Fly ship backwards"`, `"Immediately set ship to zero velocity and
rotation"`, `"Huuuuuuuuge explosion"`, `"Turns object lights off"`,
`"Make ripper drop what it's carrying"`.

## What this confirms

- **A real cloaking/stealth mechanic** (`Toggle Cloak`) — corroborates
  `DAT_00595c64` cloak-related checks noticed but never chased down
  all the way back in the project's very first bootstrap session.
- **"Ripper" is a specific in-universe NPC/ship type**: a
  cargo-grabbing entity ("Ripper grabs target object", "Ripper attach
  cargo pod to Mammoth", "Ripper end drop object", "Make ripper drop
  what it's carrying") — plausibly a pirate or salvage-ship class that
  steals cargo mid-flight. "Mammoth" appears as a second named
  ship/object type — the Ripper's cargo target, likely a transport or
  freighter class.
- **"Dark reign shoot"** — an unusual, specific state name, plausibly
  a mission-specific or boss-enemy special attack. Whether "Dark
  Reign" is a deliberate reference to anything (it also happens to be
  the name of a contemporary Activision RTS) isn't established — could
  easily be coincidental internal naming.
- **Player control is just another AI state.** `Multiplayer Control`
  and `Player Control` being entries in the SAME priority-gated FSM as
  every AI behavior confirms the engine treats "a human is flying this
  ship" as one state among many, not a structurally separate code path
  from AI piloting.
- **Capital-ship/mission-scripting states** (`Jump In`/`Jump Out`,
  `Warp In`/`Warp Out`, `Formation Regroup`, `Escort`, `Dock`,
  `Launch`) match exactly the kind of large-scale scripted behavior a
  carrier-and-capital-ship campaign like Star Lancer's needs.
- **`"Huuuuuuuuge explosion"`** is preserved verbatim in the shipped
  release binary — genuine developer humor in real game data, not a
  decompilation or transcription artifact.

### Open follow-ups

- The precise numeric state ID for each name wasn't individually
  cross-checked entry-by-entry (names were read in the table's memory
  order, which should correspond to ID order within each group, but
  this wasn't independently re-verified per entry).
- ~~Group 2's table~~ — read next, see below (essentially empty).
- The remaining portions of groups 0 and 1 beyond the ~20 entries each
  that were read — the full catalog is likely somewhat larger.
- "Mammoth" and "Ripper" as confirmed in-universe ship/entity names —
  a good anchor for a future ship-taxonomy sweep of the string table.

---

# Nineteenth pass (2026-09-08, same day): verifying "Dark Reign shoot" and Group 2

The user identified `"Dark reign shoot"` as a superweapon-firing state.
Verified this directly against the binary using `search_byte_patterns`
to locate the exact table entries by their literal pointer bytes
(avoiding the manual offset-arithmetic errors flagged as a risk in the
previous session), then decompiled the callbacks those entries point
to.

## Locating the entries precisely

Two occurrences exist: `"Dark Reign shoot"` (capital R) at state ID
`33` in group 0, and `"dark reign shoot"` (lowercase r) at state ID
`110` in group 1 — two distinct FSM states for the same overall
mechanic, not a duplicate. This also incidentally re-confirmed state
`11` (`0xb`) = `"Explode"` in group 0, exactly matching
`SetShipDestroyedState`'s literal use of `0xb` for the
ship-destruction transition from two sessions ago — the state catalog
and the earlier independently-decompiled code now cross-verify each
other exactly.

## `HandleDarkReignAttackState` (`0x0040bad0`)

State 33's secondary (`+4`) callback slot. **Confirms the user's claim
directly**: initializes a target-search context by seeding a
"best distance so far" field to `FLT_MAX` (`0x7f7fffff`) — the classic
pattern for "find the nearest/best candidate by scanning and keeping
the minimum" — calls an unopened scan function (`FUN_00401cb0`), and
on finding a valid target rolls a `rand()`-based selection before
calling `FUN_00402660` (presumably the actual fire/effect trigger,
not decompiled). Gated by `HasDamageAuthority` (multiplayer authority)
and a deathmatch team-array check (`DAT_005db650`) — the exact same
pattern documented for `ApplyShieldDamage`/`ApplyComponentDamage`. A
genuine find-target-then-fire sequence.

## `HandleDarkReignExitState` (`0x0040d1e0`)

State 110's OnExit callback. Simpler: clears a 16-byte per-object field
range (`object+0x710` through `+0x71f`) and calls an unopened cleanup
function (`FUN_0040e8a0`) — consistent with post-attack state
teardown, not the firing logic itself.

## The objective: "Deathmatch Dark Reign target"

A third string, found adjacent to `PTR_DAT_004e06e0` itself at
`0x4e06ec`: `"Deathmatch Dark Reign target"`. This confirms "Dark
Reign" isn't just a generic superweapon — it's specifically a
**deathmatch-mode objective**, almost certainly a capturable or
interactive superweapon object present on certain deathmatch maps that
players fight over control of (a classic arena-shooter map-objective
pattern, here adapted to a space-combat context). This gives the
target-acquire-then-fire mechanic in `HandleDarkReignAttackState` a
clear purpose: the object automatically searches for and fires on
whichever player/ship is the current valid target once under a
player's control.

## Group 2's table — essentially empty

Read `PTR_DAT_004e06e0`'s third pointer (`0x4e06c8`, the "group 2"
table) directly. It's a single all-zero entry whose name field points
to `DAT_00515d70` — a global already identified in an earlier session
as a shared "empty string" constant (used elsewhere as the default
value for `GetPrivateProfileStringA` calls throughout `WinMain`'s INI
loading). This reads as an unused/reserved placeholder state (ID 200),
not a real third group of behaviors. No state ID observed anywhere in
this entire investigation has fallen in the 200+ range this group
would cover — consistent with group 2 being effectively vestigial in
the shipped game.

### Open follow-ups

- ~~`FUN_00401cb0`, `FUN_00402660`~~ — resolved next, see below.
- `FUN_0040e8a0` (exit-state cleanup detail).
- Whether group 2 is truly entirely unused or has real content beyond
  the single placeholder entry read this session.

---

# Twentieth pass (2026-09-08, same day): `ScanForTargetCandidate` and a second AI subsystem, `QueueAiEvent`

Resolved `HandleDarkReignAttackState`'s two remaining calls. The second
one, `QueueAiEvent`, turned out to be a genuinely new discovery: an
entire second AI subsystem — a per-object perception/event queue —
distinct from the `TrySetAiState` finite-state-machine documented two
sessions ago.

## `ScanForTargetCandidate` (`0x00401cb0`)

```c
void __fastcall ScanForTargetCandidate(int shipSlot, char (*testCallback)(void));
```

A generic, 3-mode target-search dispatcher, reading its mode from the
ship's AI command structure (`object+0x684 → +2`):

- **Mode 0**: calls `testCallback` exactly once — an "immediate,
  no-search" fast path (e.g. "is my current target still valid").
- **Mode 1**: iterates a MISSION-SCRIPTED candidate list —
  `DAT_005267cc`, one of the 27 mission-directory tables `LoadMissionFile`
  populates when a `.dte` file loads (documented 6 sessions ago), with
  a 20-byte stride per candidate record. Calls `testCallback` on each
  candidate (via an unopened helper, `thunk_FUN_004531c0`) until one
  succeeds or the list — bounded by a count byte at each list-header's
  `+9` offset — is exhausted.
- **Mode 2**: delegates entirely to `FUN_00401d80` (not decompiled).

This directly connects the AI targeting system to mission-authored
data: a mission file can apparently script a specific candidate-target
list for certain AI searches (mode 1), rather than every AI search
being a generic "find nearest enemy" scan over the live object list.

## `QueueAiEvent` (`0x00402660`) — a second AI subsystem

```c
void __fastcall QueueAiEvent(int shipSlot, short eventKey[4],
                              int durationTicks, uint flags);
```

Source-tagged `C:\lancer\game\Ai.cpp` line `0x752` — the same file as
`TrySetAiState` and `SetShipDestroyedState`, but a genuinely different
mechanism: a per-object **perception/event queue**, not the state
machine.

- Lazily allocates a 720-byte buffer (`object+0xb90`, ~19 event slots)
  the first time an object needs one, tracking a live count at
  `object+0xb8c`.
- **Guards against overflow with a real, named assertion**:
  `"DPStack Overflow on %s"` via `ReportAssertionFailureEx` if the
  queue would exceed 19 entries — "DP" plausibly short for "Decision
  Process," suggesting this queue is a direct input to AI
  decision-making, not just a log.
- **Implements deduplication**: pushing an event whose 4-`short` key
  matches an already-queued one either no-ops (if the existing entry
  hasn't expired) or replaces it (if it has) — rather than queuing
  duplicate perceptions.
- Each event carries roughly a 13-`short` payload, a flags byte, and
  an expiry timestamp (`DAT_005883b0` — the tick counter confirmed in
  many earlier sessions — plus the caller-supplied duration).
- **Multiplayer-synced**: when the pushing client has damage/simulation
  authority over the object (`HasDamageAuthority`), the event is
  broadcast to other clients via `FUN_004ba560` (not decompiled).

This is a genuinely distinct mechanism from `TrySetAiState`'s FSM:
**state** answers "what is this ship currently doing" (with priority-
gated transitions), while the **event queue** answers "what has this
ship perceived or been told, with a time-to-live" — presumably state
transitions get triggered by processing queued events, though that
specific link (which code reads this queue and turns entries into
state-transition requests) wasn't traced this session.

### Open follow-ups

- ~~`FUN_00401d80`, `thunk_FUN_004531c0`, `FUN_004ba560`~~ — resolved next, see below.
- The actual link between `QueueAiEvent`'s queue and `TrySetAiState`'s
  state transitions — inferred from shared domain, not directly traced
  through code. Finding whatever reads `object+0xb90`'s queue would
  settle this.
- `DAT_005267cc`'s own record layout (20 bytes/entry; only the `+9`
  count/flag byte is decoded, via this one consumer).

---

# Twenty-first pass (2026-09-08, same day): the mission navigation graph, and AI-event packet serialization

Resolved `ScanForTargetCandidate` mode 2's delegate, its own helper
(the mysterious `thunk_FUN_004531c0`), and `QueueAiEvent`'s
multiplayer broadcast call. The first of these is the real prize: it
ties several previously-catalogued-but-unrelated mission-directory
globals into one coherent navigation-graph structure.

## `ScanNavigationGraphTarget` (`0x00401d80`)

```c
bool __fastcall ScanNavigationGraphTarget(uint startNodeIndex,
                                            char (*testCallback)(void));
```

`ScanForTargetCandidate`'s mode-2 delegate turns out to walk a real
**mission-scripted navigation/waypoint GRAPH**, not a flat list. Six
sessions ago, `LoadMissionFile` was documented as populating 27
directory-table globals with no known relationship to each other
beyond "part of the `.dte` format." This function shows that at least
three of them — `DAT_005294fc`, `DAT_00529500`, `DAT_00529520` — are
actually one structure: a node array (12-byte stride) with a resolved
starting index, a count bound, and a base pointer.

Each node's behavior is selected by a type byte from a FOURTH table
(`DAT_005267c0`):

- **Type 0**: calls the test callback once — a plain single waypoint.
- **Type 1**: iterates a FIFTH table (`DAT_00538c90`, a pointer +
  count-byte-at-`+9` shape — exactly matching `ScanForTargetCandidate`
  mode 1's own candidate-list format) — a node that expands into a
  sub-list of candidates rather than being one itself.
- **Type 2**: recurses into another graph node (via `FUN_00453070`
  then a fresh call to this same function) — genuine graph traversal,
  confirming nodes can reference other nodes, not just leaf
  candidates.
- Anything else falls through to `FUN_0045a440` (not decompiled,
  plausibly an invalid-node-type handler).

This is very likely the underlying data structure behind the
`"Patrol Route"`, `"Jump In"`, `"Jump Out"`, and `"Formation Regroup"`
AI states catalogued two sessions ago — a mission author can script an
entire waypoint/patrol GRAPH (with branching and sub-lists), not just
simple point-to-point destinations.

## `GetObjectIndexFromPointer` (`0x004531c0`)

```c
ushort __fastcall GetObjectIndexFromPointer(int rawPointer);
```

A small, previously-unnamed "thunk" that turns out to be a genuine
utility: converts a raw pointer/byte-offset into an object-table array
INDEX by subtracting a base (`DAT_0052951c`) and dividing by `0x4c`
(76, the per-object record size), with the sentinel values `0`, `-1`,
and `0xffff` all normalized to `0xffff` ("no valid object"). Confirms
`DAT_0052951c` is the base of a 76-byte-stride array of
mission-instantiated objects — consistent with scattered
`DAT_0052951c`-relative references seen in earlier sessions
(`InitializeMissionGameplay`, among others) without their shared
structure being clear at the time.

## `BroadcastAiEventPacket` (`0x004ba560`)

```c
void __fastcall BroadcastAiEventPacket(int unused, short eventKey[4]);
```

Confirms `QueueAiEvent`'s multiplayer synchronization is real network
packet serialization, not just a flag: begins a packet
(`FUN_004b9920(2)`, presumably "packet type 2"), writes 4 fields
unconditionally via a repeated call to what's clearly a per-field
network-write primitive (`FUN_004b9830`, called with no visible
arguments each time — consistent with it pulling from some ambient
serialization-buffer state), then branches on the event's own type key
(`eventKey[0]`): type `0x69` (105) writes 4 MORE fields — a richer
payload specific to that one event type — before a final write, while
every other type just does the one final write. Confirms different AI
event types carry genuinely different amounts of data across the
network, not a fixed-size struct blindly copied.

### Open follow-ups

- ~~`FUN_00453070`, `FUN_0045a440`, `FUN_004b9920`, `FUN_004b9830`~~ — resolved next, see below.
- What event type `0x69` specifically represents, and why it alone
  carries extra network data.
- The full navigation-graph node-type enum (only 0/1/2 observed; the
  `default` fallback implies the format allows for more even if unused
  in practice).

---

# Twenty-second pass (2026-09-08, same day): DirectPlay confirmed, and a bit-packed networking layer

Resolved the last 4 follow-ups from the navigation-graph/AI-event
thread. The headline result: direct confirmation that Star Lancer's
multiplayer layer is built on **Microsoft DirectPlay**, plus discovery
of a genuine bit-level packet-compression system.

## `GetNavGraphNodeIndexFromPointer` (`0x00453070`)

Sibling to `GetObjectIndexFromPointer`, identical shape: converts a raw
pointer into a navigation-graph node index by subtracting
`DAT_005294fc` and dividing by `0xc` (12, the node record size
confirmed in `ScanNavigationGraphTarget` last session). Cross-confirms
`DAT_005294fc` as that array's base a second, independent way.

## `HandleFatalMissionError` (`0x0045a440`) — the emergency crash handler

The navigation graph's fallback for an invalid/unrecognized node type
turns out to be a genuine developer-authored crash handler:

```c
void __fastcall HandleFatalMissionError(int badNodeType) {
    FUN_0045a460(1, "** IT'S A DISASTER! ** Emergency file saved to "
                     "'fatal.dte'", badNodeType);
    exit(-1);  // FUN_004d04ed, the CRT exit identified in mainCRTStartup
}
```

This is the first time the `"** IT'S A DISASTER! **"` string — found
in the very first bootstrap session but never traced to an actual
caller — has been connected to real code. On unrecoverable mission
data corruption (here: an invalid navigation-graph node type), the
game writes an emergency `fatal.dte` dump (via `FUN_0045a460`, not
decompiled — presumably the actual state-serialization call) before
terminating via the standard CRT exit path, rather than crashing
uncontrolled. A real safety net for corrupted mission data, not a
decompiler artifact or dead code.

## `BeginNetworkMessage` (`0x004b9920`) and `WriteMessageBits` (`0x004b9830`) — bit-packed serialization

```c
void __fastcall BeginNetworkMessage(int targetPlayer, int messageTypeId,
                                     byte flags);
bool __fastcall WriteMessageBits(byte *sourceBytes, int bitCount);
```

`BeginNetworkMessage` selects a per-player message buffer
(`DAT_005dcd1c` = buffer pointer, `DAT_005dd528` = bit-offset cursor)
from one of two parallel buffer sets, chosen by a flags bit —
plausibly a reliable-vs-unreliable channel selector, a standard
pattern for a networking layer of this era. A second flags bit
redirects the target to the local player. If given a message-type ID,
it looks up and logs a debug name from a table rooted near
`PTR_s_DPMESSAGE_END_0050ca94`.

`WriteMessageBits` is the real payload: a genuine **bit-packed
serialization primitive**, not byte-aligned. It writes an arbitrary
number of BITS from a source buffer into the current message buffer at
the current bit cursor, correctly handling both the byte-aligned fast
path and the general case (shifting and merging bits across a byte
boundary when the cursor isn't byte-aligned), masking the trailing
partial byte via a lookup table (`DAT_0050ca88`) so leftover bits don't
leak stale data, and bounds-checking against a 16KB (`0x4000`) maximum
message size. This is real bandwidth-conscious bit-level compression —
exactly what a 1999 game built around dial-up-modem multiplayer would
need, and a level of engineering sophistication worth calling out on
its own.

## "DP" = DirectPlay, confirmed

A second debug string, `"Bad DPMessage number %d"` (found alongside
`"DPMESSAGE_END"`, the label anchoring `BeginNetworkMessage`'s
message-name table), settles the "DP" prefix seen throughout this
investigation — including `QueueAiEvent`'s `"DPStack Overflow"`
assertion two sessions ago: Star Lancer's multiplayer layer is built
on **Microsoft DirectPlay**, the standard Windows multiplayer
networking API of 1996-2002. This is the expected, natural choice for
a game of this era, now confirmed directly from the binary's own debug
strings rather than assumed from context. This slightly refines (not
overturns) the earlier "DP … plausibly Decision Process" guess for
`QueueAiEvent`'s queue: the acronym's SOURCE is DirectPlay throughout;
whether `QueueAiEvent`'s specific queue is itself a literal
DirectPlay-message staging area or an AI-side structure that merely
borrows the naming convention isn't fully pinned down, but "DP" no
longer needs a separate, AI-specific explanation.

### Open follow-ups

- ~~The `DPMessage` name table~~ — read in full next, see below.
- `FUN_0045a460` (the actual emergency-mission-state-dump writer called
  by `HandleFatalMissionError`).
- The two parallel per-player buffer sets in `BeginNetworkMessage` —
  the reliable/unreliable channel interpretation is a guess, not
  confirmed.
- `DAT_0050ca88`'s trailing-bit-mask table contents (an 8-entry
  per-bit-count mask table is expected but not read).

---

# Twenty-third pass (2026-09-08, same day): the full DirectPlay message catalog

Read `PTR_s_DPMESSAGE_END_0050ca94`'s entire pointer array and backing
string pool directly via `read_memory` — raw data, Confidence 3, not
inferred. This is the richest single find of the whole investigation:
roughly 80 real DirectPlay message names, effectively a table of
contents for the entire multiplayer game, revealing several mechanics
no prior session had touched.

## Table structure

Two prefix families, ended by a `DPMESSAGE_END` sentinel:

- **`DPGMESSAGE_*`** (~52 entries) — in-mission gameplay synchronization.
- **`DPIMESSAGE_*`** (~28 entries) — lobby/matchmaking/session setup.

## `DPGMESSAGE_*` — gameplay sync

```
DROPPICKUP              NOVACANNONFIRED          PLAYERTARGET
PLAYERGONE              PROXMINE                 RIPPERSYNC
FRIENDLYFIRE            SCRIPTSYNCRESTART        SCRIPTSYNCREADY
LAUNCHMISSILE           PLAYEREJECTED            CLOAKACTIVE
SPECTRALSHIELDSACTIVE   ECMACTIVE                HELPMEOUT
BACKOFF                 ATTACKMYTARGET           RESPAWN_PICKUP
POWERUP_TRIGGERED       PICKEDUP_OBJECT          KILLS
HOJ                     AI_DECISION              SYNC_SCRIPT_START
cSCRIPTSYNC             TRIGGERNUKE              DROPPEDCOMMSRELAY
DEATHSPEWBEACONS        KILLEDBYSHADOW           SETSHADOW
DISEASED                IONCANNONSTATE           IONCANNONROTATION
TAGBOMBEXPLODES         TAGBOMBOWNER             DM_SEND_RESYNC
DM_REQUEST_RESYNC       RESYNC_DMSCENARIO        SPAWNPOSITION
ACT_SPHERE_HIT          APP_PAUSE                WARPOUT_REQ
JUMPOUT_REQ             MISSILEPOSITION          SHIELDSTRENGTH
SHIELDHIT               SUBOBJSTRENGTH           SUBOBJHIT
CHAFF                   CREATEBULLET             POSITION
LANDING
```

## `DPIMESSAGE_*` — lobby/session

```
SETINMAINGAME    REQINMAINGAME    SETTEAMCOLOUR   REQTEAMCOLOUR
IAMDEAD          KICKOUT          AREYOUREADY     WHOISHOST
SENDPLAYERSHIP   REQPLAYERSHIP    SENDMYINDEX     NEWHOST
SENDLOADOUT      SYNC_START       cPing           sPing
SENDWORLDSTATE   REQWORLDSTATE    SENDEXTRAMISSSPEC
SENDMISSSPEC     REQMISSPEC       REQGAMEINDEX    GAMEINDEX
UNREADY_TO_START READY_TO_START   SETPLAYER       START
```

(Sentinel: `DPMESSAGE_END`. A related adjacent string: `"DP Unknown
error"`.)

## What this catalog confirms and reveals

**Direct terminology confirmation** of an earlier finding: `SUBOBJHIT`/
`SUBOBJSTRENGTH` are the game's own literal names for the
subsystem/component damage model documented several sessions ago
(`ApplyComponentDamage`) — the network protocol's own naming matches
the reverse-engineered mechanic exactly.

**`PROXMINE` is a genuine, separate mine mechanic** — real proximity
mines exist as their own message type, distinct from the "Huge Gun"
capital-ship superweapons (types `0xd`/`0xe`) an earlier session
initially (and later corrected) guessed were mines.

**Three entirely new weapon/gadget systems**, not encountered in any
prior session:
- An **Ion Cannon** (`IONCANNONSTATE`, `IONCANNONROTATION`) — a
  rotating/aimable weapon, likely capital-ship-scale, distinct from
  both the "Huge Gun" superweapons and "Dark Reign."
- **Tag Bombs** (`TAGBOMBEXPLODES`, `TAGBOMBOWNER`) — a planted or
  thrown explosive with owner tracking (presumably for kill credit or
  a "who tagged this ship" mechanic).
- A **Nuke** (`TRIGGERNUKE`).

**A "Spectral Shields" mechanic** (`SPECTRALSHIELDSACTIVE`), distinct
from the directional shield-quadrant system already well-documented —
plausibly a special ability, pickup, or ship-class feature. Not
connected to any other finding yet.

**ECM and Chaff confirmed as real, distinct countermeasure systems**
(`ECMACTIVE`, `CHAFF`) — `CHAFF` in particular matches the `"chaff
exit"` debug-log tag noticed in `RunMissionGameplay`'s teardown
sequence many sessions ago, now with a real network message
counterpart. `CLOAKACTIVE` likewise matches the `"Toggle Cloak"` AI
state found in the state-catalog session.

**An unexplained "Shadow" mechanic** (`KILLEDBYSHADOW`, `SETSHADOW`) —
no other finding connects to this. Could be a stealth/decoy feature, a
specific enemy type, or something else entirely.

**Death and economy mechanics**: `DEATHSPEWBEACONS` (ships eject
beacons on death — plausibly cargo/salvage or a distress signal),
`DROPPEDCOMMSRELAY` (a droppable communications item), and a genuine
pickup/powerup system (`DROPPICKUP`/`PICKEDUP_OBJECT`/
`RESPAWN_PICKUP`/`POWERUP_TRIGGERED`).

**`DPGMESSAGE_DISEASED`** — an unusual, unexplained name. Could be a
real status-effect mechanic, or possibly developer humor in the same
vein as `"Huuuuuuuuge explosion"` from the AI state catalog.

**Dedicated deathmatch-desync recovery** (`DM_SEND_RESYNC`,
`DM_REQUEST_RESYNC`, `RESYNC_DMSCENARIO`) — a resync protocol specific
to deathmatch mode, separate from general world-state sync.

**A complete lobby/matchmaking protocol**: host migration
(`WHOISHOST`/`NEWHOST`), ready-check (`AREYOUREADY`/`READY_TO_START`/
`UNREADY_TO_START`), team color assignment (`SETTEAMCOLOUR`/
`REQTEAMCOLOUR`), late-joiner world-state and mission-spec sync
(`SENDWORLDSTATE`/`SENDMISSSPEC`/`SENDEXTRAMISSSPEC`), and a custom
ping mechanism (`cPing`/`sPing`, plausibly client-ping/server-ping
variants).

### Open follow-ups

- Individual dispatch/handler code for any of these ~80 message types
  — this session read only the name table, not the handling logic.
- `"HOJ"` (`DPGMESSAGE_HOJ`) — an unexplained 3-letter acronym.
- ~~The "Shadow" mechanic~~ — resolved next, see below.
- "Spectral Shields" — still unconnected to any other finding.
- Whether `DPGMESSAGE_DISEASED` is a real mechanic or developer humor.

---

# Twenty-fourth pass (2026-09-08, same day): the "Shadow" mechanic — multiplayer spectating

Traced `DPGMESSAGE_SETSHADOW`/`DPGMESSAGE_KILLEDBYSHADOW` from message
name to actual handler code, using exact byte-pattern searches at
every step rather than guessing offsets:

1. Found the two strings' addresses via `search_strings`.
2. Located their exact SLOTS in the message-pointer table via
   `search_byte_patterns` (searching for the literal 4-byte string
   address) — `0x50cb5c` (SETSHADOW) and `0x50cb60`
   (KILLEDBYSHADOW), giving table indices **50** and **51**
   respectively (message IDs).
3. Found the SEND functions by searching for the exact machine code
   that loads those message IDs into the register `BeginNetworkMessage`
   reads (`mov edx, 50` / `mov edx, 51`, i.e. byte patterns `ba 32 00
   00 00` / `ba 33 00 00 00`) immediately before a call to
   `BeginNetworkMessage` — found at `0x4bb030`/`0x4bb060`.
4. Traced those senders' own callers to the real handler logic.

## `HandleSetShadowMessage` (`0x004b49f0`) — multiplayer spectating

```c
void __fastcall HandleSetShadowMessage(int newShadowSlot, char broadcast);
```

**This is a spectator/"follow-cam" system.** A global
(`DAT_005db538`) tracks which player slot is currently being
"shadowed" (spectated) — `-1` means no one. When it changes, the
function builds a chat/notification-style message using a
60-byte-per-player name array (`&DAT_005db654 + slot*0x3c`),
substituting a localized `"you"`-equivalent string (via `FUN_00491030`,
the same resource-string lookup used throughout the UI in earlier
sessions) whenever the local player is the subject, instead of
printing their own name. When the LOCAL PLAYER specifically becomes
the shadow (i.e. starts spectating), their own shield-quadrant array
(`object+0x5f0`..`+0x600`, the same struct fields documented several
sessions ago in the shield-damage system) gets zeroed — sensible for a
spectator with no active combat state. Updates the global and, if
`broadcast` is set, sends the change to other clients via
`SendSetShadowMessage`.

This also explains the `"shadow = %d"` debug string found alongside
the message names in the string pool: a plain debug print of
`DAT_005db538`'s current value.

## `HandleKilledByShadowMessage` (`0x004b4b30`)

```c
void __fastcall HandleKilledByShadowMessage(int slot, char broadcast);
```

Sets `object[slot]+0x694` — the "last attacker" field written by
`ApplyShieldDamage`/`ApplyComponentDamage` several sessions ago — to
the sentinel value `0xfffffffe` (-2), rather than a real attacker
slot. This marks the elimination as NOT a normal combat kill,
plausibly "ended/eliminated in connection with the shadow/spectate
system" (e.g. the player being shadowed disconnected or the spectate
session ended in a way that needed a "no real killer" marker for
scoring/HUD purposes). Builds the same kind of name-substituted
notification message as `HandleSetShadowMessage`, and broadcasts via
`SendKilledByShadowMessage` if requested. The exact game event that
triggers this specific handler (as opposed to a normal death) isn't
fully pinned down — the MECHANISM (special sentinel + notification)
is clear (Confidence 2), the precise semantic trigger less so
(Confidence 1).

## `SendSetShadowMessage` (`0x004bb030`) / `SendKilledByShadowMessage` (`0x004bb060`)

Thin `BeginNetworkMessage(3)`/`WriteMessageBits(...)` wrappers —
confirmed as the exact network-send counterparts to the two handlers
above via the precise message-ID immediate-value search described
above, not inferred from naming or proximity alone.

### Open follow-ups

- The exact trigger for `HandleKilledByShadowMessage` — which specific
  game event calls it, and whether downstream scoring/HUD code
  special-cases the `-2` sentinel (e.g. "no kill credit awarded").
- `FUN_00491030`'s own resource-string-lookup mechanism — called from
  a wide variety of subsystems across many sessions now, never itself
  opened.
- Whether shadowing/spectating is available broadly to any
  disconnected or eliminated player, or gated to a specific game mode
  — `DAT_005db538`'s neighborhood of other deathmatch-related globals
  suggests deathmatch specifically, but this wasn't independently
  confirmed.

---

# Twenty-fifth pass (2026-09-08, same day): "Spectral Shields" — confirmed temporary invulnerability

The user supplied external knowledge from game documentation:
Spectral Shields grants near-temporary invulnerability. Verified this
directly against the binary using the same precise tracing chain as
the "Shadow" investigation: string address → exact table slot (via
`search_byte_patterns` on the string pointer) → message ID → exact
sender function (via `search_byte_patterns` on the `mov edx, <id>`
immediate load preceding `BeginNetworkMessage`) → that sender's caller,
the real toggle logic.

`DPGMESSAGE_SPECTRALSHIELDSACTIVE` resolved to message ID **67**
(`0x43`), sent by `SendSpectralShieldsMessage` (`0x4babc0`), called
from `SetSpectralShieldsActive` (`0x415430`).

## `SetSpectralShieldsActive` (`0x00415430`)

```c
void __fastcall SetSpectralShieldsActive(char activate);
```

**Confirms the user's claim directly, not just by name.** Gated by an
availability flag (`DAT_0057bf20 != -1` — plausibly whether the
ability is unlocked or on cooldown this mission, not fully pinned
down). The core mechanic:

- **Deactivating** (`activate==0`): clears bit `0x8000000` on the
  local player's own ship flags (`object+8`) — the SAME flags dword
  checked throughout the entire combat system (destroyed state, docked
  state, and others documented across many earlier sessions).
- **Activating**: sets that exact bit.

A single dedicated bit for a temporary defensive state, matching
"near-temporary invulnerability" exactly. The change is broadcast to
other clients in multiplayer (`SendSpectralShieldsMessage`) in either
direction.

### A threat-analysis pass, on activation only

Beyond the simple flag toggle, activating Spectral Shields also runs a
genuinely sophisticated scan:

1. Iterates every nearby enemy ship (proximity-gated by a squared-
   distance check against `_DAT_00501cb4`, team-filtered via `+0x644==1`).
2. For each enemy's weapon hardpoints, looks up each weapon's TYPE
   (via the weapon-type-definition's `+0x64` field — the exact field
   `FireWeapon` reads for its sound/effect-variant index, many
   sessions ago) and tallies a running count per type into a 15-slot
   accumulator (one slot per weapon type, matching the 15-entry weapon
   catalog documented several sessions ago).
3. Multiplies each tally by a per-type "threat weight," read from a
   PREVIOUSLY UNDOCUMENTED field (`DAT_00500cec`) in the SAME
   11-int-stride weapon-type table already partly catalogued
   (siblings `DAT_00500ce0`=sound, `DAT_00500ce4`=lifetime,
   `DAT_00500ce8`=scale — `DAT_00500cec` is evidently a 4th field,
   "threat weight," in that same per-weapon-type record).
4. Picks the single highest-weighted weapon type — explicitly
   EXCLUDING the two Huge Gun superweapon types (`0xd`/`0xe`) — and
   stores it into a NEW ship-object field, `object+0x670`.

The mechanism (tally → weight → pick maximum, excluding superweapons)
is read directly from the decompiled code, not guessed. Its DOWNSTREAM
purpose isn't confirmed — plausibly selects a matching visual/audio
cue for the shield effect based on the most likely incoming threat, or
feeds some other reactive system, but no consumer of `object+0x670`
was traced this session.

## `SendSpectralShieldsMessage` (`0x004babc0`)

Thin `BeginNetworkMessage`/`WriteMessageBits` wrapper, confirmed as
message ID 67's real sender via the exact immediate-value search
described above.

### Open follow-ups

- ~~What consumes `object+0x670`~~ — the network-sync side is now
  confirmed (see below); the actual damage-blocking READ site is
  still not located.
- `DAT_0057bf20`'s exact semantics — only its `-1`/`0`/`1` states were
  observed, not a full value range or what sets it initially.
- Whether ship-flags bit `0x8000000` is explicitly checked anywhere in
  `ApplyShieldDamage`/`ApplyComponentDamage` (which so far only
  documented an invulnerability check on bit `0x200000`) — worth
  re-examining those functions' flag masks now that this specific
  bit's meaning is confirmed; it's possible the invulnerability effect
  is enforced elsewhere (e.g. a check earlier in the hit-detection
  pipeline, before `ApplyShieldDamage` is even reached).
- The `"SPECTRAL SHIELDS"` UI-display string (`0x4e37a0`, distinct
  from the DirectPlay message-name string) — found but not traced to
  its actual usage (likely a HUD or pickup/ability-notification
  label).

---

# Twenty-sixth pass (2026-09-08, same day): confirming Spectral Shields blocks a specific weapon type

The user made a further, specific claim: Spectral Shields blocks the
single most dangerous nearby NON-superweapon — exactly the value
`SetSpectralShieldsActive` computes into `object+0x670`. Searched for
every OTHER reference to that struct offset via `search_byte_patterns`
on the raw displacement bytes (`70 06 00 00`) to see where else it's
touched.

## Found: the value is network-synced, confirming the mechanism's shape

A second write site turned up at `0x4b90f5`, inside a large (~9.5KB)
function (`0x4b6f80`-`0x4b9511`) renamed `ProcessNetworkMessage` — the
master incoming-DirectPlay-message dispatcher, receive-side
counterpart to the many individual `Send*Message` functions found
across earlier sessions. Disassembling directly around `0x4b90b0`
(rather than decompiling the whole giant function) revealed the
`DPGMESSAGE_SPECTRALSHIELDSACTIVE` receive case:

```c
if (receivedValue == 0) {
    targetShip->flags &= ~0x8000000;           // deactivate
} else {
    ReadMessageBits(...);                       // read the extra field
    targetShip->flags |= 0x8000000;             // activate
    targetShip->field_0x670 = receivedValue;    // the blocked weapon type
}
```

This mirrors `SendSpectralShieldsMessage`'s own shape exactly: it
calls `WriteMessageBits` once unconditionally, then a SECOND time only
`if (activate != 0)` — that conditional second write is precisely this
weapon-type value, sent only when activating.

**This confirms the "most threatening weapon type" computed locally is
deliberately transmitted over the network so every other client knows
which specific weapon type this ship's Spectral Shields currently
blocks.** That's strong, direct architectural support for the user's
claim about the ability's actual defensive behavior — sending this
value over the wire would serve no purpose unless something on the
receiving end (and presumably the local end too) checks it during hit
resolution to negate matching incoming fire.

## What's still open

The actual hit-resolution code that READS `object+0x670` and blocks or
negates damage from a matching weapon type was NOT located this
session — the `0x670` displacement search found only the two WRITE
sites (local computation in `SetSpectralShieldsActive`, and the
network-receive write in `ProcessNetworkMessage`), no read. It's
likely inside or near `FireWeapon`, `ProcessProjectileImpact`, or
`ApplyShieldDamage`, but wasn't found via this pass. Recorded honestly
as Confidence 2: the SYNC mechanism is directly confirmed in code, the
ENFORCEMENT check itself remains inferred from context (the sync would
be pointless without one) rather than independently verified.

## `ReadMessageBits` (`0x004b6e50`)

The receive-side counterpart to `WriteMessageBits`, structurally
symmetric: reads an arbitrary number of bits from the current incoming
message buffer (`DAT_005dcce8`/`DAT_005dcc9c`), handling both the
byte-aligned fast path and the general unaligned case, masking
trailing bits via the same `DAT_0050ca88` table plus a second,
read-only-side sibling table (`DAT_0050ca7c`).

## `ProcessNetworkMessage` (`0x004b6f80`)

The master incoming-message dispatcher — one large function handling
all ~80 cataloged `DPGMESSAGE_*`/`DPIMESSAGE_*` types. Only the
Spectral Shields case has been examined in detail; the rest of this
~9.5KB function is a rich, mostly-unopened target that could confirm
or correct many other message-name-only findings from the DirectPlay
catalog session.

### Open follow-ups

- The actual `object+0x670` READ/enforcement site — not found.
- The rest of `ProcessNetworkMessage`'s body (~80 other message cases).
- `DAT_0050ca7c` (the read-side trailing-bit-mask sibling table).

## Pass 25 -- Single-player campaign structure (2026-09-08)

Investigated the campaign layer directly on request, building on the
mission load/run/unload chain documented in an earlier pass.

### `mission.cpp` -- confirmed real subsystem name

A string-table sweep for "Mission" (57 matches) turned up direct
source-path and debug-assert evidence for the real mission subsystem:

```
"C:\lancer\game\mission.cpp"
"!mission_initialised"
"init_mission: A mission is already initialised"
"destroy_mission: No mission to destroy!"
"process_mission: No mission initialised"
"Mission_TriggerCount < MAX_TRIGGERLIST"
"gMissionBuffer"
```

This confirms the real API names (`init_mission`, `process_mission`,
`destroy_mission`) map one-to-one onto the previously-documented
`LoadMissionFile`/`RunMissionGameplay`/`UnloadMission` working names,
and that `LoadMissionFile`'s allocated buffer is really named
`gMissionBuffer` in source. It also surfaces a trigger-list system
(`Mission_TriggerCount`/`MAX_TRIGGERLIST`) that hasn't been located in
code yet -- likely part of the mission-scripting command subsystem
described below.

Also surfaced, not previously catalogued: a `.xmf` "Temporary Mission
Files" format string, distinct from the `.dte` format already
documented -- most likely a mission-editor scratch/save format used by
`SLEdit.exe`, not loaded by the runtime's normal mission-load path.

### Campaign narrative branching, in `InitializeMissionGameplay` (0x4934f0)

`InitializeMissionGameplay` was fully decompiled in an earlier pass but
had two switch statements left unopened. Both are now understood:

**Switch 1 -- previous-mission-outcome -> next cutscene/debrief ID.**
The function reads a small signed outcome code left over from the
mission that just ended:

```c
// single-player:
iVar6 = DAT_0050c2e8;
// multiplayer (deathmatch), per-player-slot record, 0x54-byte stride
// matches the per-player record stride seen elsewhere in the netcode:
iVar6 = *(int *)((char *)&DAT_00588400 + playerSlot * 0x54);
```

Values `0`-`0xb` mostly fall through a shared default path. Values
`0xf4`-`0xff` (i.e. -12..-1 as a signed byte, promoted to int) each
take a DISTINCT branch, writing one of 11 different values into
`DAT_005883c0`:

| outcome code | -> DAT_005883c0 |
|---|---|
| 0xf4 | 0x10e |
| 0xf5 | 0x108 |
| 0xf6 | 0x107 |
| 0xf7 | 0x106 |
| 0xf8 | 0x10b |
| 0xf9 | 0x11b |
| 0xfa | 0x10f |
| 0xfb | 0x11e |
| 0xfc | 0x117 |
| 0xfd | 0x11a |
| 0xfe | 0x112 |

(exact code-to-slot pairing reconstructed from switch-case order in the
decompile; a couple of branches additionally call `FUN_004a44d0()`,
which was not decompiled, to eagerly resolve `DAT_005883c0`/
`DAT_0057e048` into a loadable resource -- presumably the actual
debrief/cutscene asset.)

**Confidence: 3** that this is real campaign branching (the code shape
-- outcome code in, distinct cutscene-ID slot out, resource preload --
is unambiguous); **confidence 1** on what any individual outcome code
or cutscene ID narratively represents (no strings or further xrefs
examined yet to pin down "died," "captured," "retreated," etc.).

**Switch 2 -- ship-class-keyed eject eligibility (unrelated to the above).**
A second, separate switch later in the same function keys off the
player's own ship's CLASS-TYPE id (an int already documented elsewhere
as the ship-class discriminator), not the mission outcome:

```c
switch (localPlayerShipClassType) {
case 0: case 4: case 7: case 9: case 10: case 0xb:
    DAT_00566f8c = ...;   // one flag value
    DAT_00579990 = ...;
    break;
default:
    DAT_00566f8c = ...;   // a different flag value
    DAT_00579990 = ...;
}
```

`DAT_00566f8c`/`DAT_00579990` are the same two globals referenced from
`RunMissionBriefingScreen`/`RunMissionSelectMapScreen` in an earlier
pass; the shape (small closed set of ship-class IDs vs. everything
else, gating a pair of flags checked during mission briefing/select
UI) is consistent with an eject-pod/escape-craft eligibility check,
though this is not independently confirmed. **Confidence: 2.**

### A mission-scripting command catalog (found, only partially mapped)

Two command-description strings noticed in the earlier string sweep --
`"TerminateMission"` (`"End the mission, and drop to death sequence"`)
and `"Sets a Mission Objective's status"` -- were traced with
`search_byte_patterns` on their literal pointer bytes rather than
guessed offsets. Both resolved to DATA references (not code xrefs)
inside a structured table:

- `"TerminateMission"`'s address (`0x4f4074`) is referenced as a
  pointer at `0x4f323c`.
- `"Sets a Mission Objective's status"`'s address is referenced nearby
  at `0x4f3298`.

Two 200-byte reads (`0x4f3200`, `0x4f3358`) show a repeating,
fixed-stride-looking record shape: a description-string pointer, an
integer that's `1` in the samples seen (plausibly a parameter-type-code
or arg-count field), a handler FUNCTION pointer into real code
(`0x459bb0`, `0x459bd0`, `0x459c90`, and further addresses in the
`0x459bxx`-`0x45dxxx` range), followed by several more sparse,
mostly-zero fields -- consistent with per-command parameter-slot
metadata that's simply unused for 0-argument commands like
`TerminateMission`.

This strongly resembles the AI state table and DirectPlay message
catalog found in earlier passes: a data-driven command dispatch table,
almost certainly the `.dte` mission format's scripting-opcode
metadata. It is likely SHARED between `Lancer.exe` and the `SLEdit.exe`
mission editor (also present under `gamedata/StarLancer/`) as
authoring-time tooltip/metadata, with only the handler function
pointers being runtime-relevant. **Not fully mapped this session** --
exact entry stride, entry count, and full field layout are still open,
and none of the handler function pointers were decompiled.
**Confidence: 2** that this is a mission-scripting command dispatch
table at all; **confidence 0-1** on any individual field's exact
meaning beyond "string pointer" / "handler code pointer."

### Known special-cased campaign missions (consolidated)

Restating and consolidating findings scattered across several earlier
passes, now framed as campaign structure:

- Normal numbered missions run `mission1.dte`..`mission32.dte`+,
  sequenced via `DAT_00562dc8`.
- `mission25` is special-cased in `WinMain`, `RunMenuScreenLoop`, and
  `RunMissionBriefingScreen`, always paired with companion flag
  `DAT_00587cdc` -- shape suggests a two-part or replayable mission.
- `mission29` is special-cased in `RunMissionBriefingScreen` with NO
  speech-tag lookup performed -- shape suggests an epilogue or
  cutscene-only "mission" rather than a normal playable one.
- `mission251` and `mission311` are named outside the normal
  low-number sequence entirely -- likely bonus/secret/non-linear
  content, not yet investigated further.

None of these numeric specifics were re-derived this session; they're
gathered here because they bear directly on "campaign structure" and
were previously scattered across unrelated passes.

### Open follow-ups

- Decompile 1-2 mission-scripting command handler functions (e.g. the
  one near `0x459bb0` for `TerminateMission`) to confirm the dispatch
  table theory and pin down the calling convention used to invoke them
  from `.dte` script data.
- Determine the mission-scripting table's true bounds/entry count
  (only ~2-3 entries examined across two 200-byte reads).
- Decompile `FUN_004a44d0` to see exactly what a `DAT_005883c0` value
  resolves to (a cutscene FMV? a debrief text screen? a save-state
  transition?).
- Locate the trigger-list system (`Mission_TriggerCount`/
  `MAX_TRIGGERLIST`) in code -- referenced only via a debug assert
  string so far.
- Pin down what `mission25`/`mission29`/`mission251`/`mission311`
  actually are narratively, now that they're framed as part of
  campaign structure rather than isolated oddities.

## Pass 26 -- Mission-scripting command handlers decompiled (2026-09-08)

Direct follow-up to Pass 25's open item: decompiled the handler function
pointers found in the mission-scripting command table, to confirm the
dispatch-table theory behaviorally rather than just structurally.

### Table layout: partially resolved, one real ambiguity found and flagged

Re-read the table region (`0x4f31a8`-`0x4f3340`) and parsed it
programmatically as 4-byte little-endian words. Confirmed a **116-byte
(0x74) entry stride** between three consecutive entries (boundaries at
`0x4f31b8`, `0x4f322c`, `0x4f32a0`). Reading the actual strings each
entry points at revealed real command data:

- `0x4f40c0` = `"WaitForKey"` (command name)
- `0x4f40a8` = `"Key number to wait for"` (parameter description)
- `0x4f4088` = `"Stops script until key pressed"` (command description)
- `0x4f4074` = `"TerminateMission"` (command name)
- `0x4f4048` = `"End the mission, and drop to death sequence"` (command description)
- `0x4f4038` = `"TurretSetTarget"`, `0x4f4030` = `"Turret"`,
  `0x4f401c` = `"Entity to target"` (a further command + its params, not
  yet decompiled)
- `0x4f52f8` = `"Sets an ship/flight group to follow a predefined path"`
  (a further command's description, referenced from the FIRST word of
  the `0x4f31b8` entry)

**Found and flagging honestly:** the description string for a given
command does NOT sit at a fixed offset within that command's own
116-byte record — e.g. `"Stops script until key pressed"` (WaitForKey's
description, confirmed by matching it against `WaitForKey`'s decompiled
behavior below) is stored at offset `+0x00` of the *next* entry
(`0x4f322c`, which otherwise holds `TerminateMission`'s name/handler),
not within WaitForKey's own entry (`0x4f31b8`). The likely explanation
is that per-command records are NOT fixed-size in the true source
struct — they hold a variable number of trailing per-argument metadata
blocks (name/type/description triples) sized by that command's own
argument count, and the overall command DESCRIPTION string is stored as
a trailing field that lands either at the end of one record or the
start of the next depending on how many argument slots preceded it.
The 116-byte stride holding across the 3 samples examined is very
likely a coincidence of these particular commands' argument counts
(1, 1, 2) rather than a true fixed stride. **This corrects an implicit
assumption from Pass 25** (fixed-stride record) — noted explicitly
rather than silently revised. **Confidence 2** on the general
name/handler/description/argument-metadata record shape; **confidence
0** on any single fixed byte-offset layout claim.

### Handler behavior: confirms the dispatch-table theory (confidence 4)

Three handler addresses referenced from the table were not yet defined
as Ghidra functions (`decompile_function` returned "No function found"
despite valid code at the address — disassembly showed real
instructions). Created proper functions there (`create_function`) and
decompiled all three:

**`MissionScript_WaitForKey` (`0x459ae0`, was `FUN_00459ae0`)** —
matches `WaitForKey`'s table entry exactly:

```c
undefined4 __fastcall MissionScript_WaitForKey(int *param_1,int *param_2)
{
  short sVar1;
  DAT_005799bc = *param_2;                       // param_2 = ptr to arg list; arg[0] = key index
  sVar1 = *(short *)((int)&DAT_004e2380 + DAT_005799bc * 0x4e);
  if ((sVar1 != -1) && (*(char *)((int)&DAT_00595c68 + (int)sVar1) != '\0')) {
    sVar1 = *(short *)((int)&DAT_004e2380 + DAT_005799bc * 0x4e + 2);
    if (sVar1 == 0) { DAT_005799bc = -1; return 1; }
    if (sVar1 == 1) {
      if ((DAT_00595c92 != '\0') || (DAT_00595c9e != '\0')) { DAT_005799bc = -1; return 1; }
    }
    else if (sVar1 == 2) {
      if (DAT_00595c85 != '\0') { DAT_005799bc = -1; return 1; }
      if (DAT_00595d05 != '\0') { DAT_005799bc = -1; return 1; }
    }
  }
  if (((&DAT_004e23cc)[DAT_005799bc * 0x27] != -1) &&
      ((&DAT_00588370)[(short)(&DAT_004e23cc)[DAT_005799bc * 0x27]] != '\0')) {
    DAT_005799bc = -1;
    return 1;
  }
  *param_1 = *param_1 + -4;   // rewind script cursor by 4 bytes -> retry this opcode next tick
  return 0;
}
```

This is a textbook mission-script VM opcode handler: `param_1` is the
script cursor/program-counter pointer, `param_2` points at the
opcode's argument list (first argument = a key/trigger index). It
looks up that index in a `0x4e`-byte-stride condition table
(`DAT_004e2380`) and several related condition-flag tables/arrays; if
the wait condition is not yet satisfied, it decrements the script
cursor by 4 bytes so the SAME opcode re-executes next tick (a
classic busy-wait/yield pattern for a mission scripting interpreter),
returning 0 ("not done"). Once satisfied, it returns 1 ("done,
advance"). This exactly matches `WaitForKey`'s catalogued description,
`"Stops script until key pressed"` — **confidence 4** this is a real
mission-script VM wait-opcode handler, calling convention `(scriptCursor*,
argList*) -> bool done`.

**`MissionScript_TerminateMission` (`0x459bb0`, was `FUN_00459bb0`)**:

```c
undefined4 MissionScript_TerminateMission(void)
{
  DAT_00588338 = DAT_00588338 + 1;
  return 1;
}
```

Trivial, no-argument, always-immediately-complete handler that
increments a single global counter (`DAT_00588338`, not yet otherwise
characterized — plausibly a mission-termination/end-trigger count).
Matches `TerminateMission`'s description, `"End the mission, and drop
to death sequence"`, in spirit (an instant, unconditional
mission-ending command) though the actual "drop to death sequence"
behavior is not visibly in THIS handler — see below.

**`MissionScript_EndMissionDeathSequence` (`0x459bd0`, was `FUN_00459bd0`)**:

```c
void MissionScript_EndMissionDeathSequence(void)
{
  FUN_0045d460(&LAB_00459bf0);
  return 1;
}
```

Calls `FUN_0045d460(labelAddr)`, which itself resets two globals
(`DAT_00537418`, `DAT_00537575`) and calls a further function
`FUN_0045d480(labelAddr, 0)` (not decompiled) — shape consistent with
scheduling/queuing a jump to a "death sequence" label/state, i.e. this
is very likely the ACTUAL handler backing the "drop to death sequence"
part of `TerminateMission`'s description, suggesting the table's
name/description pairing may be slightly offset from my Pass-25 naive
reading (a second, independent piece of evidence for the layout
ambiguity noted above — the description text describing "drop to death
sequence" behavior lines up much better with THIS handler than with
`MissionScript_TerminateMission`'s trivial counter-increment).
**Confidence 2** on which exact command name this specific handler is
registered under, pending the layout ambiguity being resolved;
**confidence 4** on the handler's own mechanical behavior (schedules a
state/label transition via `FUN_0045d460`/`FUN_0045d480`).

### Open follow-ups

- Resolve the table's true variable-length record layout (walk several
  more entries, correlating argument counts against inter-entry byte
  distances) rather than relying on the coincidental 116-byte stride
  seen in 3 samples.
- Decompile `FUN_0045d480` (the underlying label/state-jump primitive
  used by `MissionScript_EndMissionDeathSequence`) to confirm the
  "schedule a jump to a death-sequence label" hypothesis.
- Decompile the `TurretSetTarget` handler (name/param strings already
  located: `0x4f4038`/`0x4f4030`/`0x4f401c`) to extend the confirmed
  handler sample size to 4.
- Characterize `DAT_00588338` (incremented by
  `MissionScript_TerminateMission`) — likely a mission-end-trigger
  count, not yet cross-referenced elsewhere.

## Pass 27 -- TurretSetTarget investigation: table-slot pattern confirmed, one open contradiction (2026-09-08)

Direct follow-up ("continue with TurretSetTarget"). Set out to decompile
`TurretSetTarget`'s handler and ended up doing a much more careful,
byte-precise re-derivation of the command table's field layout, which
resolved most of Pass 26's uncertainty but surfaced one genuine,
unresolved contradiction worth documenting honestly rather than
papering over.

### The table's field-lag pattern, now solidly confirmed (3-for-3)

Re-parsed a wider table region (`0x4f31a8`-`0x4f3390`) programmatically
as little-endian 32-bit words and cross-checked every string pointer
found against its actual memory content. This gives THREE clean,
independently-verified `(name, description)` pairs:

| command name | description string |
|---|---|
| `WaitForKey` | "Stops script until key pressed" |
| `TerminateMission` | "End the mission, and drop to death sequence" |
| `TurretSetTarget` | "Sets the target for a ships turret" (+ params "Turret", "Entity to target") |

Critically, each command's OWN description string is physically stored
not within its own 0x74-byte (116-byte) table slot, but at offset
`+0x00` of the *following* slot (the one holding the *next* command's
name/handler/argCount). This is a clean, repeatable pattern (confirmed
3 times), while each command's own `handler` (slot `+0x08`) and `name`
(slot `+0x10`) fields ARE correctly un-lagged, matching their own
command -- also confirmed independently via decompiled handler
BEHAVIOR, not just string content, for two of the three (see below).
**Confidence 4** on this description-lag pattern now (up from 2 in
Pass 26, where it was flagged as an open ambiguity) -- it's a repeatable,
verified structural fact about the table's memory layout, even though
*why* the source data is laid out this way (variable-length authoring
tool quirk vs. deliberate struct-splitting) remains unknown.

Also found and confirmed a fourth command in the same table, immediately
after `TurretSetTarget`'s slot: **`SetAnyTriggerState`** (4 arguments:
"Entity owning trigger", "Trigger type to enable/disable", "TRUE for
enable; FALSE for disable", "Trigger Type Number (for triggers of same
...)").

### Handler behavior: 3 of 4 confirmed, `TurretSetTarget`'s remains open

**`MissionScript_SetAnyTriggerState` (`0x45d3a0`, was `FUN_0045d3a0`)**
-- decompiled and its behavior is an excellent, clean match for its
name and 4-argument metadata:

```c
undefined4 __fastcall MissionScript_SetAnyTriggerState(undefined4 param_1,int param_2)
{
  // param_2 = pointer to this opcode's argument list
  uVar3 = *(undefined4 *)(param_2 + 4);   // trigger type
  uVar4 = *(undefined4 *)(param_2 + 8);   // enable/disable value
  uVar5 = *(uint *)(param_2 + 0xc);       // occurrence index ("Trigger Type Number")
  uVar7 = FUN_00453200();                 // resolves the target entity (arg[0], implicit)
  // walks a per-entity trigger array at DAT_005267c0 + entity*8, finds the
  // Nth (uVar5-th) trigger matching type uVar3, writes the new enable
  // state into that trigger record (offset +0x14), and calls
  // FUN_0045b2d0() to apply it.
  return 1;
}
```

This independently confirms the table's `(param_1, param_2=argList)`
calling convention already established by `MissionScript_WaitForKey`
in Pass 26 -- **confidence 4**, second independent behavioral proof of
the calling convention, on top of a clean name/argument-metadata match.

**`TurretSetTarget`'s implied handler does NOT behaviorally match.**
Per the confirmed unlagged name/handler slot pattern,
`TurretSetTarget`'s handler should be the function pointer at its own
slot's `+0x08`, which is `0x459bd0` -- the function Pass 26 decompiled
and (speculatively) named `MissionScript_EndMissionDeathSequence`.
Chasing its full call chain this session:

```
0x459bd0:  calls ResetTriggerGlobalsAndResolveTarget(&LAB_00459bf0)
  ResetTriggerGlobalsAndResolveTarget (was FUN_0045d460):
    DAT_00537418 = 0; DAT_00537575 = 0;
    calls ResolveObjectRangeAndInvokeCallback(param_1, 0)   // callback = NULL
      ResolveObjectRangeAndInvokeCallback (was FUN_0045d480):
        // range-checks param_1 against several known live-collection
        // ranges: nav-graph nodes (DAT_0052951c/DAT_00529504), a
        // trigger table (DAT_005267cc/DAT_005267c8), and the same
        // navigation/waypoint graph documented earlier
        // (DAT_005294fc/DAT_005294f0/DAT_00529500/DAT_00529520/
        // DAT_00538c90/DAT_005267c0) -- for a match, iterates
        // candidates and calls InvokeTargetMatchCallback(callback)
        // per match.
```

The value actually passed as `param_1` is `&LAB_00459bf0` -- a fixed
CODE address inside the `.text` segment. None of the three range
checks inside `ResolveObjectRangeAndInvokeCallback` can ever match a
code-segment address (they all check against dynamically-populated
data-segment/heap ranges), so in THIS specific call, the function is
mechanically a no-op past the two global resets -- it can never reach
`InvokeTargetMatchCallback`, and the callback argument is `0`
(NULL) besides. **The net confirmed effect of `0x459bd0`, as called
from this table slot, is simply: reset `DAT_00537418` and
`DAT_00537575` to 0, and do nothing else.**

This does not read as "sets the target for a ship's turret" in any
direct sense -- it never touches `param_2`'s argument list (the
Turret/Entity-to-target arguments the table says this command takes),
and its downstream call is inert given the argument it's hardcoded to
pass. **This contradicts the table-slot pattern that held cleanly for
the other 3 commands examined**, and I'm flagging it explicitly rather
than forcing an explanation:

- **Corrected, not silently**: Pass 26's name `MissionScript_
  EndMissionDeathSequence` for `0x459bd0` implied a specific, confident
  interpretation ("schedules a jump to a death-sequence label") that
  this session's deeper trace does NOT support -- the callback that
  would carry out any such jump is passed as NULL and is provably
  unreachable given the fixed argument. Renamed in Ghidra to the
  neutral, behavior-only `MissionScript_0x459bd0_ResetAndScan` to avoid
  leaving an unsupported claim as the function's name. **Confidence 1**
  on which mission-script command this handler actually implements;
  **confidence 3** on its own mechanical behavior (global reset, then
  an argument-dependent no-op in this particular call site).

### Open follow-ups

- `TurretSetTarget`'s real handler is still not confidently identified.
  Two possibilities not yet ruled out: (a) the table-slot pattern
  genuinely breaks for this one entry for an unknown reason (authoring
  bug, or a since-removed/stubbed-out command -- note the resulting
  behavior is a harmless no-op, consistent with a command that was
  disabled but left in the catalog), or (b) my slot/anchor arithmetic
  has a subtle error specific to this row that hasn't been caught
  despite matching the pattern used successfully for the other 3 rows.
- Locate the actual mission-script INTERPRETER/dispatcher (the code
  that reads a `.dte` script opcode and calls through this table) --
  this would settle the field-offset question definitively instead of
  relying on cross-referencing string content and handler behavior.
  No xrefs were found to any individual table row or to any of the
  handler addresses (`get_xrefs_to` returned "No references found" for
  all of them), suggesting the interpreter computes the row address
  dynamically (`table_base + opcode_index * 0x74`) in a way Ghidra's
  static analysis hasn't resolved into discrete references.
- `ResolveObjectRangeAndInvokeCallback`'s trigger-table range check
  (`DAT_005267cc`/`DAT_005267c8`) reuses the same `DAT_005267c0` array
  `MissionScript_SetAnyTriggerState` walks directly -- worth
  characterizing this trigger-table struct properly (currently only
  known: entry stride 8 bytes for the `DAT_005267c0` range-checked
  form, but `SetAnyTriggerState` indexes a DIFFERENT, larger structure
  at `DAT_005267c0 + entity*8` with a `+0x14` state byte and per-record
  sub-array of stride `0x30` -- these are not yet reconciled into one
  consistent struct definition).
- `FUN_0045b2d0` (applies the resolved trigger-state change) and
  `FUN_0045d720`/`FUN_0045d8b0`/`FUN_0045d8e0`/`FUN_0045d910` (all
  referenced from `ResolveObjectRangeAndInvokeCallback`'s callback path)
  not decompiled.

## Pass 28 -- Resource file / BigFile TOC loader (2026-09-08)

Direct investigation of the ".hog"/BigFile archive subsystem underlying
`LoadResourceFileBuffer` (documented structurally in an earlier pass).
Confirmed real source files `C:\lancer\game\bigfile.cpp` and
`C:\lancer\game\hog_file.cpp`, and the real function-name prefix
`HOG_` for this subsystem's public API (`HOG_bigread`, `HOG_bigread2`,
`HOG_bigsize`, `HOG_file_read`, `HOG_file_size`).

### Archive file format, confirmed structurally

`OpenBigFile` (`0x4c7e20`) opens a `.hog`/BigFile archive and reads a
fixed 16-byte header via one `fread` (through the locking wrapper
`FUN_004cfeec`) followed by 3 big-endian-swapped `uint32` reads
(`ReadSwappedUint32`, was `FUN_004c7df0` -- confirmed as a pure
byte-swap utility operating on an already-buffered pointer, advanced
via a hidden fastcall register argument between calls, the same
recurring decompiler artifact seen throughout this project):

```
offset 0x00: magic uint32BE  == 0x42494746 ("BIGF")
offset 0x04: tocEntryCount   (piVar2[7] in the decompile)
offset 0x08: tocSizeBytes    (piVar2[8] -- size of the TOC region, header included)
offset 0x0c: (unused 4th header word, not read individually)
```

If the magic doesn't match, `OpenBigFile` fails cleanly (frees and
returns NULL) -- no fallback inside this function. On success, it
allocates `tocSizeBytes`, rewinds the file (`FUN_004d0c17`, matches
CRT `rewind()`'s exact shape: clear error/EOF flags, no seek offset
parameter), and bulk-reads `tocSizeBytes` from the START of the file
into that buffer -- meaning the in-memory TOC buffer re-includes a
copy of the 16-byte header at its front, which is exactly why
`FindBigFileTocEntry`'s search loop (below) starts its cursor at
`tocBuffer + 0x10`, skipping that embedded header copy.

### TOC entry format, confirmed structurally (confidence 4)

`FindBigFileTocEntry` (`0x4c8370`, was `FUN_004c8370`) walks the TOC
buffer from `tocBuffer+0x10` to `tocBuffer+tocSizeBytes`, and its
field-access pattern pins down the entry layout precisely:

```c
struct BigFileTocEntry {
    uint32_t fileOffsetBE;   // big-endian file offset of this resource's data
    uint32_t fileSizeBE;     // big-endian byte size of this resource's data
    char     name[];         // null-terminated, case-insensitive compared
};                            // variable length -- entries packed tightly,
                              // next entry starts right after the name's NUL
```

Evidence: the name-comparison call is
`FUN_004dae20((char *)(cursor + 8), targetName)` -- i.e. the name
starts 8 bytes into each entry, exactly matching two leading `uint32`
fields. On a match, the function calls `ReadSwappedUint32()` TWICE more
with the (hidden, advancing) cursor still pointing at this same entry's
start -- reading back `cursor+0` (offset) then `cursor+4` (size),
confirming those are genuine per-entry fields rather than a
separately-stored parallel array. It then seeks the archive's `FILE*`
to the resolved offset (`FUN_004d0407(fp, offset, SEEK_SET)`) and
returns the resolved size, leaving the file cursor positioned exactly
at the resource's data, ready for the caller to `fread` it directly.
On no match (name comparison via `FUN_004dae20`, confirmed to be a
`_stricmp`-style case-insensitive CRT compare, returns nonzero), the
loop advances the cursor past the 8-byte prefix and the name's length
(including its NUL) to reach the next entry. Falling off the end of
the TOC region returns 0 (not found).

### Read path: compression-aware, with a loose-file mod/dev override

`HOG_BigRead` (`0x4c7f60`, matches the real name `HOG_bigread`) takes a
resource path, strips a trailing 2-character extension matching `"ut"`
if present (purpose not determined -- possibly a `.ut`/`.uti`-style
suffix used only by an editor/tool variant of the same filename) and a
leading directory component, then calls `FindBigFileTocEntry`. If
found, it peeks 2 bytes at the resolved offset, seeks back 2 bytes, and
checks for a `0x10fb` compressed-block marker:

- **Compressed** (`marker == 0x10fb`): delegates to
  `DecompressBigFileEntry` (`0x4c8480`, was `FUN_004c8480`), which
  reads a 5-byte header immediately after the marker to recover the
  true DECOMPRESSED size, allocates `decompressedSize + 0x2800` bytes
  (extra slack, plausibly a decompressor window/overrun margin), reads
  the compressed payload into the tail of that buffer, calls
  `FUN_004cc350` (the actual decompressor -- not decompiled this
  session; likely an LZ/RLE variant given the `0x10fb` marker and
  trailing-window layout) to expand it in place, then copies the
  result into a right-sized final allocation.
- **Uncompressed**: allocates the resolved size directly and reads the
  bytes with one `fread`.

If `FindBigFileTocEntry` fails to find the entry (returns 0), `HOG_
BigRead` falls back to `HOG_file_read` (`0x4c5be0`, confirmed real name
via its own debug string `"HOG_file_read: error loading %s."` and
source path `C:\lancer\game\hog_file.cpp`) -- a completely independent
loader that opens the path as a **plain loose file on disk** (not
inside any archive), sized via `HOG_file_size` (`fseek`+`ftell`). Only
if *that* also fails does it report the second, harder failure
(`"HOG_bigread: error loading %s."`) via `ReportAssertionFailureEx`.

**`LoadResourceFileBuffer`'s mod/dev-override mechanism, now explained
precisely**: it calls `FileExistsOnDisk` (`0x4ad6e0`, a plain
`GetFileAttributesA(path) != INVALID`check) *before* even trying the
archive path. If a loose file with the requested name genuinely exists
on disk, `LoadResourceFileBuffer` reads it directly via
`ReadLooseResourceFile` (`0x45a3e0`) and NEVER consults the BigFile
archive at all for that resource. Only when no loose file is present
does it fall through to `LoadNamedResource`->`HOG_BigRead` (the
archive path, which itself has its OWN internal loose-file fallback via
`HOG_file_read`, described above, for when the archive's TOC doesn't
contain the entry). This is a genuine, simple, well-supported mod/dev
override: **any loose file dropped into the expected game-data
directory with the correct relative name silently takes priority over
the packed `.hog` archive's copy**, no special flag or configuration
needed. `ReadLooseResourceFile` also calls `HandleFatalMissionError()`
on failure when specific caller flags are set, tying this directly into
the mission-loading fatal-error path documented in an earlier pass.

### Open follow-ups

- `FUN_004cc350` (the actual compressed-block expander used by
  `DecompressBigFileEntry`) -- not decompiled; likely an LZ/RLE
  variant, unconfirmed.
- The stripped `.ut`-suffix behavior in `HOG_BigRead` -- purpose not
  determined (only that a trailing `.ut`-prefixed 2-char extension is
  silently dropped from the requested name before the TOC lookup).
- The BigFile header's 4th 16-byte-header word (never read
  individually by `OpenBigFile`) -- likely reserved/padding, not
  confirmed.
- Whether `CloseBigFile`/`HOG_bigsize` (0x4c81f0, confirmed via its own
  compression-aware size logic mirroring `HOG_BigRead`'s marker check)
  are called from any currently-documented higher-level resource
  manager -- not traced this session.

## Pass 29 -- BigFile decompressor identified as RefPack; .ut suffix explained (2026-09-08)

Direct follow-up on the two items flagged open at the end of Pass 28.

### The decompressor is EA's "RefPack" (aka "QFS") compression codec

Decompiled `DecompressRefPackBlock` (`0x4cc350`, was `FUN_004cc350`,
called from `DecompressBigFileEntry`). Its control-byte decoding shape
-- literal-run counts packed into the low 2 bits of a tag byte, three
escalating tiers of match-token width (1/2/3 leading tag bytes) each
encoding a copy DISTANCE and LENGTH via bit-packed combinations of the
following bytes, and a terminal tag range (`(byte)uVar4 > 0xfb`, i.e.
`0xFC`-`0xFF`) that copies a final short literal run and stops -- is a
precise structural match for **RefPack**, EA/Origin's standard LZ77-family
compression format from the late-1990s (also known as "QFS" compression,
publicly documented via SimCity 4/The Sims/NFS-series reverse-engineering
efforts). The `0x10FB` marker `HOG_BigRead`/`HOG_bigsize` check for before
calling the decompressor is exactly RefPack's well-known 2-byte magic
header (bytes `10 FB`). Given Star Lancer was published by Origin/EA, this
makes complete sense as a shared, EA-wide compression utility rather than
a StarLancer-specific codec. **Confidence 4** on the algorithm
identification (based on structural pattern-matching against the
publicly documented RefPack control-byte scheme, not an internal source
confirmation) -- high enough to treat as settled for practical
(re-implementation) purposes; a byte-exact re-implementation should
still be checked against a real compressed sample before being trusted
for correctness.

### The `.ut` suffix: speech/dialogue tag files, extension stripped generically

Searched all strings ending in `.ut` and found 383 matches, essentially
all short audio/dialogue-adjacent asset names: pilot ejection barks
(`ejt_001.ut`..`ejt_016.ut`), taunts (`tnt_003.ut`..`tnt_013.ut`),
pickup/badge lines (`antpkup_001.ut`, `yambdg_001.ut`,
`relbdg_001.ut`, ...), and notably `ms_speech\enrbr_tag%02d.ut` and
`enddebriefing.ut`/`loadout.ut` -- all consistent with the
already-documented "speech-tag lookup" mechanism in
`RunMissionBriefingScreen` from an earlier pass (confirmed directly:
`get_xrefs_to` on the `"ms_speech\enrbr_tag%02d.ut"` string shows its
only reference is from `RunMissionBriefingScreen`). This strongly
supports **`.ut` = "utterance"** -- a speech/dialogue tag file format
(plausibly timing/subtitle-sync metadata paired with a voice-over audio
clip), matching standard game-audio-pipeline terminology from this era.
**Confidence 3** on the "utterance" reading of the abbreviation itself
(a reasonable, well-supported inference, not textually confirmed
anywhere in the binary); **confidence 4** on the file class being
speech/dialogue-tag data given the caller and naming evidence.

`HOG_BigRead`'s extension-stripping check (`strncmp(ext, "ut", 2) == 0`
truncates the name at the `.` before the TOC lookup) is a GENERIC rule
-- it strips any 2-character extension starting with `"ut"`, not a
`.ut`-specific special case in the literal string sense (it would also
strip a hypothetical `.utz` or `.utw`). Given `.ut` is overwhelmingly
the dominant extension actually used in the game's data (383 of the
matched strings), the practical effect is that essentially all `.ut`
speech-tag lookups get their extension silently dropped before the
BigFile TOC search. The most likely explanation, consistent with the
BigFile TOC entry format documented in Pass 28 (`{offset, size,
name[]}`, arbitrary names, no fixed extension field): **the packed
archive stores these speech-tag entries under their bare basename
(no extension)**, while caller code throughout the game consistently
constructs the request string WITH a hardcoded `.ut` suffix (visible
directly in the `"ms_speech\enrbr_tag%02d.ut"` format string), and
`HOG_BigRead` reconciles the mismatch with this one shared stripping
rule rather than requiring every caller to omit the extension itself.
**Confidence 3** on this specific mechanism (a real, observed
behavior with a plausible, testable explanation, not independently
confirmed against an actual archive's TOC contents).

### Incidental finding: `SR_CCB_load` identified

While cross-checking `HOG_BigRead` callers for `.ut`-related context,
one previously-anonymous caller (`FUN_004cb9d0`) was confirmed via its
own debug strings (`"SR_CCB_load: Null name passed"`, `"SR_CCB_load:
Failed to open CCB file %s"`, source path
`C:\lancer\surrender\surrenderlib\...`) to be the real SurrenderLib
function `SR_CCB_load` -- a loader for `.ccb` files (format not
otherwise investigated this session; likely "Camera/Cinematic Buffer,"
unconfirmed) that reads a fixed 0xc0-dword header block, a further
0x300-dword block, several scalar fields via repeated `FUN_004cb540()`
calls, then a variable-length trailing payload. Renamed accordingly;
not otherwise explored.

### Open follow-ups

- `.ccb` file format and `SR_CCB_load`'s field semantics -- noted but
  not investigated (out of scope for this pass).
- No compressed BigFile sample was actually decoded byte-for-byte this
  session -- the RefPack identification rests on control-byte-shape
  matching against public documentation, not a live test.

## Pass 30 -- The .ccb loader investigated: a master-palette resource format (2026-09-08)

Direct follow-up on the incidental `SR_CCB_load` finding from Pass 29.

### Only 3 `.ccb` files exist in the whole game: all palettes

`search_strings` for `.ccb` returns exactly 3 hits: `palette.ccb`,
`palette3.ccb`, `softpal.ccb`. Unlike `.dte` (per-mission) or `.ut`
(per-line-of-dialogue, 383 instances), `.ccb` is a rare, GLOBAL
resource type -- consistent with a small number of master
color-palette definitions (one default, one alternate/"palette3", and
one for a software-rendering fallback path -- "softpal" strongly
implies "software palette", i.e. a palette used specifically when
SurrenderLib falls back to software rasterization instead of
hardware-accelerated rendering).

### File structure, confirmed via `SR_CCB_load` (0x4cb9d0)

```c
struct CcbResource {          // total 0x30 bytes, allocated by SR_CCB_load
    void*  payload;           // +0x00, variable length, size = scalar7 (below)
    void*  unused1;           // +0x04, never written by SR_CCB_load
    void*  scalarBlockC;      // +0x08, points at a single DWORD copied from file offset 0xf00
    void*  blockA;            // +0x0c, 0x300 (768) bytes copied from file offset 0x000
    void*  blockB;            // +0x10, 0xc00 (3072) bytes copied from file offset 0x300
    uint32 scalar1..scalar6;  // +0x14..+0x28, 6 native-endian dwords read sequentially
    uint32 scalar7;           // +0x2c, also used as the trailing payload's byte size
};
```

File layout on disk (via the `HOG_BigRead` buffer, before the struct is
built): `[0x300 bytes: Block A][0xc00 bytes: Block B][4 bytes: scalar
C][7 x 4-byte scalar fields][variable-length payload, size = last
scalar]`. The 7 scalar reads use `FUN_004cb540` -- confirmed to be a
plain (non-byte-swapped) native-endian `uint32` read from an advancing
cursor, the same hidden-fastcall-argument pattern documented
repeatedly elsewhere in this project (contrast with `bigfile.cpp`'s
`ReadSwappedUint32`, which DOES byte-swap -- `.ccb` files are stored in
native x86 byte order, unlike the BigFile archive's own big-endian
header/TOC).

### Block A confirmed as a 256-color master RGB palette -- CORRECTED in Pass 61: wrong source, right size

**Correction (2026-09-09, Pass 61)**: the write-up below correctly
identified that a 256-entry RGB palette gets packed into native pixel
format from a `0x300`-byte renderer-state field -- but wrongly assumed
that field was `CcbResource.blockA`, i.e. that it came from the `.ccb`
file. It doesn't. Re-reading `FUN_004acbe0`/`FUN_00441aa0` (now
`InitializeGraphicsDevice`/`InitializeLoadoutScreen`) with their hidden
`__fastcall` arguments exposed (`set_function_prototype` on the actual
loader) shows the `+0x1602` field is populated by a **separate call to
`SR_TGA_allocate_palette`** against a same-named `.tga` file
(`"softpal.tga"`/`"palette.tga"`/`"palette3.tga"`), NOT by
`SR_CCB_load`'s return value (which goes to the adjacent-but-distinct
`+0x1606` field instead). The two loads happen right next to each
other in the same function, which is exactly what led to the original
mis-attribution -- but they are two independent resources. See Pass 61
for the full writeup. The paragraph below is kept for history but its
"Block A" attribution to the `.ccb` file is superseded.

`0x300 = 768 = 256 x 3` -- and this is independently confirmed, not
just size-inferred. Tracing `SR_CCB_load`'s two callers:

- `FUN_004acbe0` (a graphics-device/window init routine -- sets window
  styles, computes device caps at `DAT_00588730`) calls `SR_CCB_load()`
  and stores the result at renderer-state offset `+0x1606`.
- `FUN_00441aa0` (the game's asset-preload sequence -- loads ships,
  missiles, backdrops, with `DebugLog_Stub` progress markers like
  `"-- pre sample load (%d)"`) also calls `SR_CCB_load()` (into
  `DAT_005246d0`), and later in the SAME function contains a loop that
  reads RAW BYTES from renderer-state offset `+0x1602` (a field
  immediately adjacent to the `+0x1606` CCB-pointer field) in groups of
  3 (`pbVar1[0]`, `pbVar1[1]`, `pbVar3[0]` -- an R/G/B byte triple),
  bit-shifts and ORs each channel using shift/mask amounts pulled from
  the device's pixel-format descriptor
  (`DAT_00588730+0x162a/0x1626/0x1632/0x163e/0x1636/0x1642`), and
  writes one packed native-pixel-format `uint32` per input triple, for
  exactly `0x300` (768) bytes of input. This is a textbook
  **RGB-palette-to-hardware-pixel-format conversion loop** (e.g. RGB888
  -> RGB565 or whatever the current display mode uses), operating on
  exactly the same byte count as Block A. **Confidence 4** that Block A
  is a raw 256-entry RGB palette table, consumed by the renderer to
  build a native-format color lookup table for paletted rendering.

### Block B: plausible but unconfirmed shading-ramp hypothesis

`0xc00 = 3072 = 256 x 12`. Not observed being read by either traced
caller this session. A 12-shades-per-palette-color pre-computed
lighting/shading ramp table is a very common paletted-rendering
technique from this era (used so dynamic lighting can be approximated
by picking a pre-shaded palette index instead of recomputing color
blends per-pixel), and the exact byte count fits neatly, but this is
**not independently confirmed** -- flagged explicitly as a structural
size-coincidence hypothesis, confidence 2, not a traced finding.

### Open follow-ups

- Trace what consumes `CcbResource.blockB` (0xc00 bytes) and the 7
  scalar fields, to confirm or refute the shading-ramp hypothesis.
- Determine what `.ccb` actually stands for -- no textual confirmation
  found in the binary; the on-disk content (global master palettes,
  not per-object sprite/cel data) does not obviously support a "Cel
  Control Block" (3DO terminology) reading, so that guess is
  explicitly NOT being adopted here.
- `FUN_00441aa0` and `FUN_004acbe0` are both large, mostly-unexplored
  graphics-initialization functions (window/device setup and the main
  asset-preload sequence respectively) -- only the CCB-relevant slice
  of each was examined this session.

## Pass 31 -- Mission trigger-type catalog discovered (2026-09-08)

Continued investigation of the mission-scripting subsystem, following
the earlier `MissionScript_SetAnyTriggerState` finding (Pass 27). Set
out to locate the actual `.dte` script interpreter/dispatcher; did not
find it this session (see below), but found something arguably more
valuable: the complete mission TRIGGER TYPE catalog.

### Interpreter search: ruled out one large candidate

Following `DAT_005799bc` (WaitForKey's key-wait index global) to all
its read/write sites turned up a huge (9351-byte) previously-undefined
function at `0x4843a4` (created via `create_function`, not yet named).
Full decompile showed this is NOT the script interpreter -- it's the
per-frame **HUD rendering function**, and its `DAT_005799bc` usage is
simply drawing the on-screen "press [KEY] to continue" prompt banner
(looking up the current wait-key's display name/glyph, checking SHIFT/
CONTROL modifier requirements via a local string-pointer table, and
positioning the prompt text). This usefully clarifies `DAT_005799bc`'s
full role (a UI-visible "currently prompting for this key" index, not
just an internal condition-table lookup key) but is a dead end for
finding the interpreter itself. Not renamed or further explored this
session given its size and tangential relevance.

### The real find: `Mission_TriggerCount`'s overflow-dump function

Searching for the source of the `"Mission_TriggerCount < MAX_TRIGGERLIST"`
assert string (found in Pass 25 but not traced) led directly to
`DumpMissionTriggerListOverflow` (`0x45b330`, was `FUN_0045b330`) -- a
diagnostic function that fires when the live trigger count
(`DAT_005373e4`, confirmed as the real `Mission_TriggerCount`) exceeds
999. It dumps every live trigger's type name and owning-object name via
`DebugLog_Stub`, then calls `ReportAssertionFailureEx` with `"Trigger
List exceeded"`. **This directly implies `MAX_TRIGGERLIST` = 1000**
(the `999 < count` guard is the only condition under which the dump AND
the fatal assert both fire) -- confidence 3, inferred from the guard
value rather than a literal `MAX_TRIGGERLIST` constant read.

Critically, this function embeds a **complete, 32-entry trigger-type
name table**, read directly by indexing a local string-pointer array
with each trigger record's first byte:

```
TT_SHOTAT                      TT_PLAYER_READY_TO_WARP
TT_DESTROYED                   TT_JUMPED_THROUGH_HOOP
TT_LAUNCHED                    TT_PLAYER_WANTS_BACKUP
TT_CAMERAREACHED                TT_RIPPER_GRABBED_OBJECT
TT_SHIPREACHED                  TT_RIPPER_DROPPED_OBJECT
TT_PROXIMITY_CLOSE              TT_CLOAKED
TT_PROXIMITY_GENERAL            TT_DECLOAKED
TT_OBJECT_SCOOPED               TT_TARGETTED
TT_PLAYER_READY_TO_JUMP         TT_PLAYER_L1_DOUBLETAP
TT_JUMPED_IN                    TT_PLAYER_L2_DOUBLETAP
TT_FG_JUMPED_IN                 TT_PLAYER_R1_DOUBLETAP
                                 TT_PLAYER_R2_DOUBLETAP
                                 TT_PLAYER_L1_L2_R1_R2_PRESSED
                                 TT_PLAYER_L1_R1_PRESSED
                                 TT_GAME_TIMER_EXPIRED
                                 TT_TRACTOR_BEAM_LOCKED
                                 TT_TRACTOR_BEAM_BROKEN
                                 TT_INSIDE_OBJECT
                                 TT_OUTSIDE_OBJECT
                                 TT_DOCKED
                                 TT_UNDOCKED
                                 TT_BEING_CHASED
```

This is the real, complete event/condition vocabulary for the mission
scripting system's trigger mechanism -- e.g. a mission script can react
to a player being shot at, a ship being destroyed, a ship reaching a
waypoint, a controller double-tap combo, a tractor beam locking on, a
game timer expiring, docking/undocking, cloaking, and so on. **This is
a DIFFERENT system from the previously-documented AI perception/event
queue** (`QueueAiEvent`, 19-slot buffer, `Ai.cpp`) -- this is the
mission-SCRIPT-facing trigger list (`Mission_TriggerCount`/
`MAX_TRIGGERLIST`, up to 1000 live triggers), which mission designers
presumably attach via commands like `SetAnyTriggerState` to gate
script branches on gameplay events. **Confidence 4** on the trigger-type
catalog itself (read directly from real code); confidence 2 on the
exact conceptual boundary between this system and the AI event queue
(plausible, not exhaustively cross-checked).

### Trigger record structure, partially confirmed

Each live trigger record is a fixed 0x30-byte (48-byte) struct, stored
in an array at `DAT_0052abe0` here (iterated with `pbVar2 = pbVar2 +
0x30`), with **byte offset 0x00 = the trigger type code** (0-31,
indexing the above catalog). `GetObjectIndexFromPointer()` and
`FUN_004024e0()` (not decompiled) are used together to resolve a
display name for the owning object -- the exact field holding that
object reference within the 0x30-byte record isn't pinned down this
session (the dump code passes the record pointer implicitly via hidden
fastcall arguments, not shown in the decompile).

This 0x30-byte stride matches the INNER per-trigger-instance array
`MissionScript_SetAnyTriggerState` (Pass 27) walks via
`DAT_005294e0 + nodeIndex*0x30` -- strong circumstantial evidence
(matching stride, matching subject matter) that these are the same
underlying trigger-instance array, referenced via different global
aliases from different functions, though this is not proven by a
direct code-level cross-reference this session. **Confidence 2** on
the two arrays being identical/aliased.

### Open follow-ups

- The `.dte` script interpreter/dispatcher itself remains unlocated.
  `FUN_004843a4` (HUD render) was ruled out; no other strong candidate
  found yet via the `DAT_005799bc`/`DAT_00588338` global-xref approach.
  A different search strategy (e.g. tracing what calls the mission
  command table's base address, or examining `RunMissionGameplay`'s
  full body for a per-tick script-cursor advance) is needed.
- The full 0x30-byte trigger record layout beyond byte 0 (type code) --
  not mapped.
- Whether `DAT_0052abe0` and `DAT_005294e0` are the same array or two
  parallel ones -- not directly confirmed.
- `FUN_004024e0` (object display-name resolver) -- not decompiled.

## Pass 32 -- THE MISSION SCRIPT INTERPRETER FOUND: a stack-based bytecode VM (2026-09-08)

Direct continuation of the interpreter search (open since Pass 27).
Found it by following the trigger system's data flow rather than
searching from the command table's side: `Mission_TriggerCount`'s
overflow-dump caller chain led to the real per-tick trigger-processing
pipeline, which led directly to a genuine bytecode interpreter.

### The chain that led here

```
UpdateMissionFrame (0x4924b0, already documented)
  -> ProcessMissionTriggerQueue (0x45b840, was FUN_0045b840)
       per-frame: walks all live triggers (DAT_005373e4 count,
       DAT_0052abe0 array, stride 0x30 -- same record documented
       in Pass 31), and for each, calls:
     -> DispatchMissionTriggerMatch (0x45ce70, was FUN_0045ce70)
          thin wrapper; skips if the owning object index is -1
        -> MatchTriggerAgainstWaitingScripts (0x45cea0, was FUN_0045cea0)
             the real trigger-to-script matcher: walks an array at
             DAT_005294e0 + index*0x30 -- CONFIRMED to be the exact
             same 0x30-byte array MissionScript_SetAnyTriggerState
             (Pass 27) walks, resolving Pass 31's "confidence 2,
             possibly the same array" hypothesis up to confidence 4.
             On a match, calls:
           -> FindMissionScriptThreadSlot (0x45b960, was FUN_0045b960)
                walks a linked list rooted at PTR_DAT_004f6348 (each
                node 0xB8/0x2e-dword bytes, "next" pointer at +0xc8)
                to find a script-thread slot, and copies the trigger's
                extra data into it at +0x18.
```

### `ResumeMissionScriptThread` (0x45ba30, was FUN_0045ba30): the scheduler

```c
void __fastcall ResumeMissionScriptThread(undefined4 *param_1)
{
  if (param_1[3] != 0) {
    if (DAT_00538c9c <= (uint)param_1[3]) return;
    param_1[3] = 0;
  }
  DAT_00537570 = *param_1;        // restore VM stack pointer from thread state
  DAT_00537574 = 0;
  DAT_005373f0 = param_1[1];      // restore VM instruction cursor from thread state
  DAT_00537578 = param_1;         // "current thread" global
  iVar1 = RunMissionScriptVM();
  if (iVar1 == 0) {
    *param_1 = DAT_00537570;      // yielded/blocked -- save state back for next resume
    param_1[1] = DAT_005373f0;
    return;
  }
  param_1[4] = 0;                 // finished -- mark thread dead
  DAT_00537415 = DAT_00537415 + -1;  // decrement active-thread count
}
```

This is a **cooperative script-thread scheduler**: `PTR_DAT_004f6348`
is the head of a linked list of independently-resumable mission script
"threads" (coroutines), each with its own saved VM stack pointer and
instruction cursor. Each frame, live threads get resumed one at a
time; a thread either yields (blocked, e.g. waiting on a trigger or a
timer) and gets its state saved for the next resume, or runs to
completion and is torn down.

### `RunMissionScriptVM` (0x45c980, was FUN_0045c980): the actual interpreter

```c
uint __fastcall RunMissionScriptVM(undefined *param_1)
{
  ...
  piVar1 = (int *)(param_1 + 0x10);   // instruction cursor, within the thread struct
  do {
    ...
    pcVar2 = *(code **)(&DAT_004f6350 + (uint)*(byte *)*piVar1 * 4);  // fetch opcode byte, index jump table
    *piVar1 = (int)((byte *)*piVar1 + 1);                              // advance cursor past opcode
    iVar4 = (*pcVar2)(iVar4);                                          // execute opcode handler
  } while (iVar4 != 0);   // keep going until a handler signals stop/yield
  ...
}
```

This is a textbook **fetch-decode-execute bytecode interpreter loop**:
fetch one opcode byte from the thread's instruction stream, index a
jump table (`DAT_004f6350`) by that raw byte value to get a handler
function pointer, advance the cursor, call the handler (which receives
and returns a simple "keep running" int flag), and loop until a
handler signals stop. This is emphatically NOT the same mechanism as
the named-command metadata table investigated in Passes 25-27 (which
used a `(scriptCursor*, argListPtr*)` two-pointer calling convention
per command) -- **this is a separate, lower-level system.**
**Confidence 5** that this is a genuine bytecode interpreter loop --
the structure is unambiguous.

### The opcode jump table (`DAT_004f6350`) and confirmed stack-VM primitives

Read and parsed as a 4-byte-pointer array. Roughly 84 populated
entries (opcodes ~2-85, with some gaps -- opcodes 8-19 are entirely
zero/unused), followed immediately by what is recognizably the START
of the SAME rich name/description/argument metadata table investigated
in Passes 25-27 (string-pointer-shaped values matching that table's
field pattern begin right after the jump table ends) -- i.e. **the raw
opcode jump table and the named-command metadata table are two
adjacent but structurally distinct tables in the same data region**,
not the same table read two different ways as I'd been assuming.

Decompiled 3 opcode handlers to confirm the execution model:

- **Opcode 2** (`0x45bad0`, now `MissionVM_OpEquals`):
  `*(DAT_00537570-8) = (*(DAT_00537570-8) == *(DAT_00537570-4)); DAT_00537570 -= 4;`
  -- pops two values off an evaluation stack (`DAT_00537570`, a stack
  pointer that grows/shrinks by 4-byte words) and pushes their
  equality as a boolean. **Classic `OP_EQ`.**
- **Opcode 3** (`0x45bb00`, now `MissionVM_OpNotEquals`): identical
  shape with `!=`. **Classic `OP_NE`.**
- **Opcode 20** (`0x45bbf0`): calls `FUN_0045cb20()` (a "fetch some
  game-state value" primitive, not decompiled) and pushes the low byte
  of its result onto the stack -- a **push-game-value opcode**.

**Confidence 5** that `DAT_004f6350`+`RunMissionScriptVM` implement a
genuine **stack-based bytecode virtual machine**, most plausibly used
to evaluate mission-script CONDITION/EXPRESSION logic (the boolean
tests that gate trigger-based script branches), given the confirmed
push/pop/compare primitives found. `DAT_00537570` = VM evaluation stack
pointer; `DAT_005373f0`/thread-struct field `+4` = VM instruction
cursor (saved/restored per thread).

### Open question: how does this relate to the named-command table?

The relationship between this low-level stack VM (this pass) and the
rich named-command metadata table with handlers like
`MissionScript_WaitForKey`/`MissionScript_TerminateMission`/
`MissionScript_SetAnyTriggerState` (Passes 25-27) is **not yet
established**. Plausible hypotheses, none confirmed:

1. The stack VM evaluates boolean CONDITIONS only (if/wait-until
   logic), while the named-command table drives separate, higher-level
   ACTIONS -- two cooperating but structurally independent mini-systems
   compiled from different parts of a `.dte` script.
2. One of the ~84 stack-VM opcodes is a "call named command N" bridge
   that reads a following command-index byte and dispatches through
   the OTHER table with the different calling convention -- unifying
   both into one system with two instruction classes.

Given `MissionScript_WaitForKey`'s own handler independently manages
condition-table waits and cursor rewinding using an entirely different
data structure (`DAT_004e2380`) than this VM's stack (`DAT_00537570`),
hypothesis 1 (two independent systems) currently looks more likely,
but this is **not confirmed** -- flagged explicitly as open rather than
guessed at.

### Open follow-ups

- Decompile more of the ~84 opcode handlers to build a fuller ISA
  picture (arithmetic? jumps/branches? the actual "wait for trigger"
  opcode that would explain how `MatchTriggerAgainstWaitingScripts`
  resumes a blocked thread).
- Determine how a script thread's instruction stream relates to the
  `.dte` file's on-disk script bytecode (i.e. confirm this VM's opcodes
  ARE what's stored in `.dte` mission files, rather than a
  compiled-at-load-time intermediate form).
- Resolve the relationship (if any) between this VM and the Pass 25-27
  named-command table.
- The full 0xB8-byte script-thread struct layout -- only a few fields
  characterized (`+0x00` stack ptr, `+0x04` cursor, `+0x0c` some
  count/limit, `+0x10` alt cursor field seen in `RunMissionScriptVM`,
  `+0x18` trigger-data landing area).

## Pass 33 -- VR ship-interior system: closing open questions (2026-09-08)

Direct follow-up on "decode menus and the complete VR system," building
on the already-complete (145-node) graph walk and struct work from
Passes 4-5. The menu system (12 screens) was already documented at a
thorough structural level in Pass 6 with no new leads to chase this
round, so this pass focused entirely on the VR loop's remaining open
questions, re-examining `RunShipInteriorVRLoop`'s full decompile now
that Ghidra has the `VRRoomNode` struct applied throughout (yielding
much more readable field accesses than the earlier manual-offset pass).

### `RunShipInteriorVRLoop`'s caller: resolved

`get_function_callers` confirms both `RunShipInteriorVRLoop` and
`RunMenuScreenLoop` are called **only from `WinMain`** — closing the
"not yet traced to a specific caller" item from Pass 4. Additionally,
`RunShipInteriorVRLoop` itself calls `RunMenuScreenLoop` directly (the
`nRoomType == 1` "exit to menu" branch), confirming the menu <-> VR
loop relationship is a direct mutual call, not mediated through
`WinMain`'s state machine for that specific transition.

### `roomType` 3 and 4: NOT room transitions -- mouse-hover interactive props

The earlier passes correctly flagged `roomType == 3` as doing something
distinct from the hub-jump types but didn't fully decode it. The full
decompile makes it clear neither 3 nor 4 represent room destinations at
all:

```c
if ((DAT_0051d478->pMoviePathAlt == NULL) && (DAT_0051d600 == -1)) {
  if (DAT_0051d478->nRoomType == 3) {
    if ((0x43 < mouseX) && (mouseX < 0x87) && (0x83 < mouseY) && (mouseY < 0xfb)
        && (leftMouseButtonHeld)) {
      // opens a FIXED literal movie "move_a.bik" (not the node's own moviePath)
      // and loads its decoded frame buffer into DAT_0051d9cc
    }
  }
  else if (DAT_0051d478->nRoomType == 4) {
    // same trigger condition, but loads via LoadNamedResource (not a .bik
    // movie at all) into the SAME DAT_0051d9cc slot
  }
}
```

Both are gated on the mouse sitting inside a FIXED screen rectangle
(`x: 0x43-0x87, y: 0x83-0xfb` -- i.e. roughly a small button-sized
region in a consistent screen location, not derived from the node's own
hotspot data) while the left mouse button is held, and only trigger
when the CURRENT node has no `pMoviePathAlt` and no other transition is
already in flight (`DAT_0051d600 == -1`). This is an **interactive prop
system layered on top of specific rooms**, not room navigation: hovering
and holding the mouse over one fixed screen-space hotspot while standing
in a `roomType == 3` room plays a secondary overlay video
(`"move_a.bik"`); in a `roomType == 4` room it loads a secondary
resource via `LoadNamedResource` instead (a still image or UI overlay,
not a video, given the different load path). Both land their result in
the same `DAT_0051d9cc` slot, later composited via `FUN_004c78a0`+
`(**(DAT_00588730+0x78))()` each frame in the same place the "8-frame
cursor-pulse" animation is driven.

Plausible interpretation (**not confirmed**, confidence 1): `roomType 3`
rooms have a control/lever/switch prop the player can operate to trigger
a canned "you moved something" animation (`"move_a.bik"` reads naturally
as "move, take A" or "movement animation A"), while `roomType 4` rooms
have a similar interactive prop that instead displays a loaded static
resource (an image, a readout, a screen). This reframes the earlier
"replay current movie without changing rooms" guess from Pass 5 into
something more specific and better-evidenced: **not a room-navigation
state at all, but a mouse-hover interactive-prop trigger confined to a
fixed screen region**, independent of which physical room-graph node the
player currently occupies (any `roomType == 3` or `4` node exhibits this
behavior identically).

### `moviePathAlt`: refined hypothesis

Confirmed structurally: whenever a node has a non-NULL `pMoviePathAlt`,
`RunShipInteriorVRLoop` unconditionally opens and plays THAT clip first,
and the `roomType` 3/4 hover-prop logic above is explicitly skipped
(`pMoviePathAlt == NULL` is a precondition for reaching it at all).
Combined with the "twin nodes share destination but differ only in
their incoming transition movie" pattern documented in Pass 5, this
supports (confidence 2, up from Pass 4's "not determined"): **`pMoviePathAlt`
is a one-time ENTRY/ARRIVAL transition clip, distinct from `pMoviePath`'s
steady-state idle-loop clip** -- when set, it plays once on arrival and
suppresses that node's hover-prop behavior for that visit; nodes without
one just loop `pMoviePath` directly and remain eligible for the
`roomType` 3/4 interactive-prop check.

### `unk10` (`+0x10`, between `pMoviePathAlt` and `nNumTargets`): confirmed unused by the main loop

Read through the ENTIRE `RunShipInteriorVRLoop` decompile (now with the
struct's named fields making every access visible) -- **the `+0x10`
field is never read anywhere in this function.** Every other struct
field (`hotspotX/Y/W/H`, `pMoviePath`, `pMoviePathAlt`, `nNumTargets`,
`pTarget0..4`, `nRoomType`, presumably `soundFlag` at `+0x2a`, confirmed
via the `!= -1` sound-trigger check) is exercised somewhere in this
function; `+0x10` alone is not. This doesn't mean the field is unused
by the GAME overall (a different function could read it), but it rules
out `RunShipInteriorVRLoop` itself as the consumer, narrowing where to
look next if anyone wants to resolve it. Not chased further this pass.

### Hotspot hit-test mechanics, confirmed precisely

```c
if (0 < DAT_0051d478->nNumTargets) {
  ppvVar15 = &DAT_0051d478->pTarget0;
  do {
    psVar4 = *ppvVar15;                 // the target node itself, reinterpreted as short*
    if ((psVar4[0] < mouseX) && (mouseX < psVar4[2] + psVar4[0]) &&
        (psVar4[1] < mouseY) && (mouseY < psVar4[3] + psVar4[1])) {
      matchedIndex = i; break;
    }
  } while (...);
}
```

Confirms exactly what Pass 4 inferred from field layout alone: each
target's own leading 4 `int16` fields (`hotspotX/Y/W/H`) ARE its
clickable rectangle as seen from the CURRENT room, tested directly
against the tracked mouse position (`DAT_0051db34`/`DAT_0051dacc`).
**Confidence raised from 3 to 4** (behavior-confirmed, not just
structurally inferred).

### Menu system: no new work this pass

The 12 `RunMenuScreenLoop` handlers remain documented at the
structural/purpose level established in Pass 6 -- this pass found no
new open threads worth chasing there (the two flagged curiosities,
the mission-select cheat code's exact key sequence and the save-file
IFF format, are both already reasonably characterized and would need
either `FUN_004bd570`'s internals or live-debugging to advance further,
per METHODOLOGY's live-debugging guidance).

### Open follow-ups

- `unk10`'s consumer, if any, elsewhere in the binary.
- Whether `"move_a.bik"` and the `roomType == 4` resource are the SAME
  interactive prop across every room that uses them, or vary by room
  (only one literal filename was seen; the `LoadNamedResource` call for
  type 4 wasn't traced to see what name it resolves).
- The mission-select cheat code's exact key sequence (needs
  `FUN_004bd570` internals or live debugging).
- ~~`DAT_0051dab4`'s two-mode Bink playback selection
  (`*(DAT_00588730+0x162e) != 0x3e0`) -- not investigated.~~ **Resolved
  in Pass 58**: it's a Bink `_BinkCopyToBuffer` RGB555-vs-RGB565
  output-format flag, not palette-related. See Pass 58 below for the
  full writeup (also answers "do `.bik` files contain/set a palette?" --
  no).

## Pass 34 -- `CheckKeyEdgeState` decoded; the "CTRL+POTATO" cheat code confirmed (2026-09-08)

Direct request: decode `FUN_004bd570`, the input-polling function called
throughout the codebase as `FUN_004bd570(1)` with its other two
arguments always invisible (the recurring hidden-fastcall-argument
artifact this project has hit dozens of times). Fully decoded it, and
as a direct, satisfying side effect, **recovered the exact key sequence
for the mission-select cheat code** flagged as unrecoverable in Pass 6.

### `CheckKeyEdgeState` (`0x4bd570`, was `FUN_004bd570`)

```c
undefined4 __fastcall CheckKeyEdgeState(int keyIndex, undefined4 modifierMode, int pressOrRelease);
```

A general-purpose, edge-triggered keyboard polling primitive:

- `keyIndex` -- a raw PC keyboard scancode (Set 1), used to index a
  per-key raw-down-state byte array at `DAT_00595c68` (**the same
  global `MissionScript_WaitForKey`'s condition-table lookup reads**,
  confirmed in Pass 26 -- this is the game's single shared raw keyboard
  state array).
- `modifierMode` -- which modifier must ALSO be held for the check to
  pass: `0` = none (and no modifier at all may be held), `1` = Shift,
  `2` = Ctrl, `3` = Alt. Each modifier is tracked as a pair of globals
  (Left/Right variants ORed together): Shift = `DAT_00595c92`/
  `DAT_00595c9e`, Ctrl = `DAT_00595c85`/`DAT_00595d05`, Alt =
  `DAT_00595ca0`/`DAT_00595d20`. The Shift/Ctrl identification is
  independently cross-confirmed by the HUD-render function's own
  `local_160[]` display-string array from Pass 31 (`["", "SHIFT",
  "CONTROL"]`, indexed by this exact same `modifierMode` value); Alt
  (mode 3) is inferred from the parallel structure alone (no display
  string seen), confidence 3.
- `pressOrRelease` -- `0` checks for a RELEASE edge, nonzero checks for
  a PRESS edge (every observed caller passes `1`).

Uses a second per-key array, `DAT_005d54ec`, as an edge-detection latch
(so a held key fires the "pressed" check exactly once, not every
frame), with dedicated "combo-latched" globals per modifier
(`DAT_005d5744`=Shift, `DAT_005d5634`=Ctrl, `DAT_00595d80`=Alt) so a
modifier+key combo's release doesn't spuriously also fire the
plain-key release check. **Confidence 5** -- fully mechanical, no
ambiguity once the hidden arguments were exposed.

### How the hidden arguments were recovered

Every prior sighting of this function (VR loop, `RunMainMenuScreen`,
etc.) showed only `FUN_004bd570(1)` because Ghidra's decompiler doesn't
display `__fastcall` register arguments (ECX/EDX) unless the callee's
prototype is explicitly declared. Called `set_function_prototype` on
`0x4bd570` with the 3-int `__fastcall` signature above, then
re-decompiled every caller -- **all hidden arguments immediately became
visible in every caller's decompile**, all at once, project-wide (no
per-call-site disassembly needed). This is a broadly reusable technique
worth remembering for any other function in this codebase exhibiting
the "same call, no visible args" symptom.

### `RunMainMenuScreen`'s hidden input, decoded

Re-decompiling `RunMainMenuScreen` (`0x428b60`) with the new prototype
in place reveals the ENTIRE previously-opaque input chain:

**The cheat code itself**, read directly from the now-visible scancode
array `local_c[] = {0x19, 0x18, 0x14, 0x1e, 0x14, 0x18}`, each checked
via `CheckKeyEdgeState(local_c[i], 2, 1)` (i.e. **with Ctrl held**), in
strict sequence (a running index `iStack_10` only advances on a correct
next-key match):

| Scancode | Key | | Scancode | Key |
|---|---|---|---|---|
| `0x19` | P | | `0x1e` | A |
| `0x18` | O | | `0x14` | T |
| `0x14` | T | | `0x18` | O |

**Spelled out: `P-O-T-A-T-O`, held with Ctrl.** Star Lancer's
mission-select cheat code is **Ctrl+P-O-T-A-T-O** ("Ctrl+Potato").
**Confidence 5** -- this is about as directly confirmed as a finding
gets: real scancodes, read straight out of a real array, matched
against the standard IBM PC Set-1 scancode table.

Completing the sequence (`iStack_10 == 6`) sets a new global,
`DAT_005d5641` (arms `g_..MissionSelectCheatArmed`-equivalent state).
Once armed, EVERY subsequent frame first polls a chain of Shift-modified
function keys (`CheckKeyEdgeState(0x3b..0x44, 1, 1)` = Shift+F1
through Shift+F10, then `0x57`/`0x58` = Shift+F11/F12) and
`CheckKeyEdgeState(0x1c, 1|2, 1)` (Shift+Enter / Ctrl+Enter) -- each
bound key sets a distinct debug/status code (`_DAT_00588400 = 0..11`)
and a "handled" flag (`DAT_005883b4` or `DAT_0051db48`), evidently
selecting one of a dozen otherwise-inaccessible debug destinations (NOT
decoded further this pass -- `_DAT_00588400`'s consumer wasn't traced).

**If none of those F-keys/Enter combos are pressed**, the code instead
reads plain NUMBER-ROW keys (scancodes `0x02`-`0x0b` = `'1'`..`'9'`,
`'0'`) with no modifier, accumulating up to 2 digits into
`DAT_00562dc8` (the mission-index global, confirmed independently by
5 different functions across this project now):

```c
iVar1 = CheckKeyEdgeState(digitScancode, 0, 1);  // one of '1'..'9','0'
if (iVar1 != 0) {
  iVar1 = (typedDigitIndex + 1) % 10;              // '1'->1 .. '9'->9, '0'->0
  if (DAT_00562dc8 < 10) {                          // already-typed digit becomes the "tens" place
    iVar1 = iVar1 + DAT_00562dc8 * 10;
  }
}
```

This exactly confirms the Pass 6 guess mechanically: after arming with
Ctrl+Potato, typing a 1- or 2-digit number on the main menu directly
sets the current mission index -- a genuine, now fully mechanically
understood developer mission-select cheat, not merely inferred from
shape.

### Open follow-ups

- The 12 debug destination codes (`_DAT_00588400` values 0-11, selected
  via Shift+F1-F12/Ctrl+Enter/Shift+Enter once Ctrl+Potato is armed) --
  not traced to their consumer.
- Apply `CheckKeyEdgeState`'s new prototype and re-decompile other
  heavy callers (the VR loop, other menu screens) to see what else was
  being hidden -- likely worthwhile given how much this unlocked here.

## Pass 35 -- `_DAT_00588400`'s consumer traced: the 12 debug codes are aliases of the Pass-25 campaign-outcome branches (2026-09-08)

Direct follow-up: trace where the Ctrl+Potato debug menu's
`_DAT_00588400` write (Pass 34) is actually consumed.

### The consumer: `InitializeMissionGameplay`'s outcome-code switch (Pass 25, revisited)

Re-decompiled `InitializeMissionGameplay` in full. The relevant read:

```c
iVar6 = DAT_0050c2e8;
if (DAT_00582e8c == '\0') {
  iVar6 = *(int *)(&DAT_00588400 + DAT_005883fa * 0x54);
}
```

**Correction to Pass 25, not silent**: Pass 25 described this as "`DAT_0050c2e8` in single-player, or `DAT_00588400 + slot*0x54` in multiplayer." Reading the actual code now shows this is ~~backwards~~: `DAT_0050c2e8` is the DEFAULT value, and it gets OVERRIDDEN by `DAT_00588400[slot]` specifically when `DAT_00582e8c == 0`. Given `DAT_00582e8c` gates a call to `FUN_004ae860` (one of `DAT_00588400`'s writers, per this session's xref search) and reads elsewhere as a "network/multiplayer session active"-shaped flag, the corrected reading is: **`DAT_00588400[slot]` is used when `DAT_00582e8c == 0`** (i.e., no active network session -- single-player, including the main menu itself), and `DAT_0050c2e8` is used otherwise. This flips which global belongs to which mode from what Pass 25 stated. Not independently re-verified against a live multiplayer session -- confidence 2 on the corrected SP/MP assignment, confidence 4 that the prior write-up had the two swapped (directly visible in the decompile).

This directly explains WHY `RunMainMenuScreen` writing straight to unindexed `_DAT_00588400` (Pass 34) has any effect at all: at the main menu, no network session is active (`DAT_00582e8c == 0`), so `InitializeMissionGameplay`'s outcome-code read picks up exactly that value once a mission subsequently loads.

### The 12 debug codes ARE (mostly) aliases of the Pass-25 outcome-code table

The low-value switch arm of `InitializeMissionGameplay`'s outcome-code
handling (values `0`-`0xb`, previously described in Pass 25 as "mostly
falls through to a shared default") in fact **`goto`s directly into the
SAME case labels used by the high-value `0xf4`-`0xff` arm** documented
in Pass 25:

| Ctrl+Potato key | `_DAT_00588400` | Shares a label with | `DAT_005883c0` result | Also calls `FUN_004a44d0`? |
|---|---:|---:|---:|---|
| F1 / Shift+Enter | 0 | *(unique -- not aliased)* | `0x116` | no |
| F2 | 1 | `0xf5` | `0x10e` | **yes** |
| F3 | 2 | `0xf6` | `0x108` | no |
| F4 | 3 | `0xf7` | `0x107` | **yes** |
| F5 | 4 | `0xf8` | `0x106` | no |
| F6 | 5 | `0xf9` | `0x10b` | no |
| F7 | 6 | `0xfa` | `0x11b` | **yes** |
| F8 | 7 | `0xfb` | `0x10f` | no |
| F9 | 8 | `0xfc` | `0x11e` | no |
| F10 | 9 | `0xfd` | `0x117` | no |
| F11 | 10 | `0xfe` | `0x11a` | **yes** |
| F12 | 11 | `0xff` | `0x112` | no |

**This means Ctrl+Potato's 12 keys are a direct QA testing shortcut for
the 11 real campaign-outcome branches documented in Pass 25** (reachable
in normal play only by actually finishing a mission with that specific
outcome), **plus one 12th, otherwise-unreachable-by-normal-play
destination** (`_DAT_00588400 == 0`, which shares nothing with the
`0xf4`-`0xff` table and resolves to a unique `DAT_005883c0 == 0x116`).
**Confidence 4** -- directly read from the decompile's shared `goto`
targets, not inferred.

### `FUN_004a44d0` is NOT a cutscene resolver -- it's the squadron-roster (`.sro`) file loader

Pass 25 left `FUN_004a44d0` undecompiled, guessing it "resolves
`DAT_005883c0`/`DAT_0057e048` into a loadable resource." Decompiled it
this session: it's confirmed (via its own error string, `"Could not
open %s"`, and source-tagged allocation string `C:\lancer\game\
srofiles.cpp`) to be a real file parser for what the source calls
**`.sro` files** -- large, richly-structured records (600-byte-stride
top-level entries, each with sub-tables for up to `0x1c`-count "wings,"
weapon-hardpoint records checking against literal strings `"startup"`/
`"deploy"`, and geometric plane-normal computations per sub-record) --
this reads as a **squadron/wing ROSTER format**, not a video or image
resource. **This means the campaign-outcome branch's real effect is
loading a different roster of ships/wingmen for the next mission
briefing** (e.g. a wingman who died in a bad outcome no longer appears)
rather than selecting a debrief cutscene as Pass 25 speculatively
guessed -- a materially different, better-supported interpretation of
what "campaign branching" actually changes. **Confidence 3**: the file
format identification (SRO squadron roster) is solid; the specific
claim that `DAT_005883c0`'s numeric value selects WHICH roster filename
gets passed to `FUN_004a44d0` is plausible but not directly observed
(the actual filename argument is passed via a hidden `__fastcall`
register at `InitializeMissionGameplay`'s call site, not shown in its
decompile, and not chased further this session).

### Open follow-ups

- Apply `set_function_prototype` to `FUN_004a44d0` (now known:
  `int LoadSquadronRoster(byte *filename)`ish) and re-decompile
  `InitializeMissionGameplay` to reveal what specific filename/string
  `DAT_005883c0`'s value actually resolves to -- the same technique
  that cracked the cheat code in Pass 34 should work here too.
- The `.sro` format's own internal structure (wings, hardpoints,
  weapon slots) -- not mapped field-by-field this session, well beyond
  the scope of "decode the debug codes."
- Whether `DAT_00582e8c`'s corrected SP/MP semantics hold up under a
  live multiplayer session -- not verified.

### Addendum (same session): the exact filenames, revealed by the same prototype trick

Applied `set_function_prototype` to `FUN_004a44d0` itself (now renamed
`LoadSquadronRoster`, `int __fastcall LoadSquadronRoster(byte *filename)`)
and re-decompiled `InitializeMissionGameplay` -- exactly the technique
flagged as an open follow-up above, and it worked immediately: every
branch's hidden filename argument is now visible.

| `_DAT_00588400` code | `DAT_005883c0` | Roster file loaded |
|---:|---:|---|
| *(mission 25 special case)* | `0x112` | `"kamg_frm_shp"` |
| 0 / `0xf4` | `0x116` | `"preg_frm_shp"` |
| 1 / `0xf5` | `0x10e` | `"nagg_frm_shp"` |
| 2 / `0xf6` | `0x108` | `"gre2_frm_shp"` |
| 3 / `0xf7` | `0x107` | `"cru3_frm_shp"` |
| 4 / `0xf8` | `0x106` | `"coyg_frm_shp"` |
| 5 / `0xf9` | `0x10b` | `"mirg_frm_shp"` |
| 6 / `0xfa` | `0x11b` | `"temg_frm_shp"` |
| 7 / `0xfb` | `0x10f` | `"pat2_frm_shp"` |
| 8 / `0xfc` | `0x11e` | `"wolv_frm_shp"` |
| 9 / `0xfd` | `0x117` | `"rea2_frm_shp"` |
| 10 / `0xfe` | `0x11a` | `"shr2_frm_shp"` |
| 11 / `0xff` | `0x112` | `"phe2_frm_shp"` |

The `_frm_shp` suffix reads naturally as "formation ship[list]" -- a
squadron/formation roster keyed by fighter class. Several prefixes are
recognizable Star Lancer fighter-class abbreviations (`wolv` =
Wolverine, `phe2` = Phoenix-family, `shr2` = Shrike-family, `pat2` =
Patriot-family, `rea2` = Reaver/Reaper-family, `cru3` = a Crusader/
cruiser-family variant); the rest (`kamg`, `preg`, `nagg`, `gre2`,
`coyg`, `mirg`, `temg`) are plausible further ship-class abbreviations
not independently confirmed against an authoritative source. **This
means the campaign-outcome branch's real, concrete effect is loading a
DIFFERENT SHIP/SQUADRON FORMATION ROSTER for the next mission depending
on how the previous one ended** (or, via Ctrl+Potato, whichever of the
12 keys was pressed) -- e.g. plausibly which fighter class the player
flies next, or which allied wing composition escorts them, changing
based on campaign performance. **Confidence 4** on the mechanism (12
distinct, real filenames, directly read from the decompile); confidence
2 on the specific "changes player's ship class" narrative interpretation
(plausible, not confirmed against actual `.sro` file contents or
in-game observation).

This fully answers the original request: `_DAT_00588400`'s ultimate
consumer is a squadron-roster loader, and the 12 Ctrl+Potato debug
codes are a direct QA shortcut for selecting which of 12 real,
named roster files loads for the next mission.

## Pass 36 -- More hidden key bindings revealed via `CheckKeyEdgeState`'s prototype (2026-09-08)

Direct continuation of Pass 34's flagged follow-up: re-decompiled
further heavy `CheckKeyEdgeState` callers now that its prototype is
set project-wide.

### `RunShipInteriorVRLoop` -- two real key bindings confirmed

- `CheckKeyEdgeState(1, 0, 1)` (scancode `0x01` = **Esc**, no modifier)
  -- the VR loop's per-frame exit check; pressing Esc triggers
  `FUN_004394d0()`'s confirm/cancel handling (0 = keep playing normally,
  1 = confirmed exit -- tears down and either returns to the menu or
  ends, 2 = a third outcome not chased further).
- `CheckKeyEdgeState(0x39, 0, 1)` (scancode `0x39` = **Space bar**, no
  modifier) -- a keyboard equivalent to left-clicking the currently
  hovered hotspot, confirmed alongside the existing mouse-button checks
  in the same `if` condition (`bStack_88 & 0x80`, i.e. the tracked
  mouse-button state, is checked in the identical boolean expression).

### `UpdateMissionFrame` -- Esc to exit, and a screenshot hotkey

- `CheckKeyEdgeState(1, 0, 1)` (Esc) -- exits the current mission
  gameplay frame loop entirely (`DAT_005db830 = 0; FUN_00491e20();
  return 0;`), the same universal-exit binding as the VR loop.
- `CheckKeyEdgeState(0xb, 0, 1)` (scancode `0x0b` = the **'0' key** on
  the number row, no modifier) -- calls a function confirmed via its
  own literal format string (`"screenshot_%04d.tga"`, an
  auto-incrementing counter global `DAT_005d6ca8`) to be a real
  **screenshot hotkey**. Renamed `FUN_004adc20` to `SaveScreenshotTga`.
  Captures either the display-mode's back-buffer directly (hardware
  path) or a software-rendered composite (`FUN_004c3430`+`FUN_004c8600`)
  depending on the current renderer mode, and writes a numbered `.tga`
  file via `FUN_004ca620`.

### `RunControlsOptionsScreen` -- the rebind mechanism's real shape (not a static binding list)

Re-decompiled in full. This is the interactive "press a key to bind it"
UI logic itself, not a lookup table of default bindings, so it doesn't
directly answer "what key does X do by default" -- but it does reveal
the REAL underlying data structures cleanly:

- A **control-descriptor table**, `DAT_004e5cd0`, stride `0x24` bytes,
  spanning up to `0x4e6954` (roughly `(0x4e6954-0x4e5cd0)/0x24` ~= 51
  entries) -- each entry's display-name string lives at a parallel
  offset (`DAT_004e5cd4 + entryIndex*0x24`), used to build a
  confirmation prompt string (`"%s: %s, %s, %s"`-shaped format,
  `s___s___s__s__s_004e8488`) when the player is about to rebind a
  control already bound elsewhere.
- The RUNTIME binding storage is the same `DAT_004e2380` table already
  documented as the per-key/per-control condition table consumed by
  `MissionScript_WaitForKey` (Pass 26) and read throughout this screen
  -- confirming `DAT_004e2380` genuinely IS the live key-binding table
  (not just a mission-script artifact that happens to share the name),
  with entries also cross-linked to `DAT_004e23cc` (mode/type?) and
  `DAT_004e23ae` (a string field, likely the bound device/axis name for
  joystick bindings).
- Confirms `starlancer.ini`'s `[KeyConfig]` write-back keys precisely
  match Pass 6's earlier finding (`ForceFeedback`, `JoystickInvert`,
  `HatEnable`, `TwistEnable`, `controller`) -- no new keys found, but
  now each one's exact toggle condition is visible (e.g. `ForceFeedback`
  only toggles when `DAT_0050e1a4 != 0 && DAT_0057e064 == 0`, i.e. force
  feedback hardware present AND controller mode is "keyboard").

### Open follow-ups

- Read `DAT_004e5cd0`'s ~51 entries directly (`read_memory`) to produce
  the actual list of control names (roll/pitch/yaw/fire/throttle/etc.)
  and cross-reference against `DAT_004e2380`'s currently-loaded default
  scancodes -- a natural, well-scoped next step that would produce a
  real "default flight control scheme" table.
- `DAT_004e23cc`'s exact per-control meaning (currently just "some
  mode/type value distinct from the scancode").
- The remaining ~40 `CheckKeyEdgeState` callers (see Pass 34's full
  caller list) not yet re-examined.

## Pass 37 -- .bik movie loading/playback pipeline, and DAT_004e5cd0 decoded (correcting Pass 36) (2026-09-08)

### The .bik loading pipeline: unifies with the BigFile archive system (Pass 28)

`FindBinkMovieInArchive` (`0x4c83f0`, was `FUN_004c83f0`, called
everywhere as `FUN_004c83f0()` with hidden fastcall args) turns out to
be structurally **identical to `FindBigFileTocEntry`** (Pass 28): same
TOC-walk shape (`param_1+0x18`=buffer base, `param_1+0x20`=size,
case-insensitive name compare via `FUN_004dae20`, offset/size read via
`ReadSwappedUint32`), operating on **the exact same struct `OpenBigFile`
returns** -- field offsets `+4` (Win32 `HANDLE`) and `+0x18`/`+0x20`
(TOC buffer/size) match `OpenBigFile`'s `piVar2[1]`/`piVar2[6]`/
`piVar2[8]` (DWORD-indexed: byte offsets 4/0x18/0x20) exactly.

**This resolves an open question implicitly left by Pass 28**: why does
`OpenBigFile` open the archive file TWICE -- once via the CRT
(`FUN_004d02ef`, buffered `FILE*`, stored at offset 0) and once via
raw `CreateFileA` (stored at offset 4)? Now it's clear: the CRT
`FILE*` backs the normal buffered resource path (`HOG_BigRead` and
friends), while the raw Win32 `HANDLE` exists specifically so
`FindBinkMovieInArchive` can call `SetFilePointer` on it directly and
hand that positioned, unbuffered handle straight to the Bink Video SDK
for streaming playback -- movies are NOT loaded into a memory buffer
first, they stream directly from the open archive file. **Confidence
4** (exact struct-offset match across two independently-documented
functions; not independently re-verified via a fresh disassembly of
the exact call site).

`DAT_005202d4` (read constantly throughout `RunShipInteriorVRLoop`,
`RunMissionBriefingScreen`, and several other `0x436xxx`-`0x43cxxx`
menu/interior functions) is this same `BigFile*` -- written once in
`WinMain` (initial archive open) and re-written repeatedly inside
`EnsureCorrectCDMounted` (once per disc-swap/archive-reopen). So the
SAME currently-mounted `.hog` archive (`cd1.hog`/`cd2.hog`, per Pass
28's `EnsureCorrectCDMounted` documentation) backs both ordinary
resource loads and movie streaming.

### Generic Bink playback pattern (RAD Game Tools' public SDK -- not StarLancer-specific)

Confirmed the same call sequence recurs at every `.bik` transition
throughout the VR loop, briefing screen, and others: `FindBinkMovieInArchive`
(locate + seek) -> `_BinkOpen_8(handle, flags)` -> `_BinkSetFrameRate_8`/
`_BinkSetSoundSystem_8` (once, at loop entry) -> `_BinkDoFrame_4`
(decode next frame) -> `_BinkCopyToBuffer_28` (blit into the game's own
back-buffer, `DAT_0051d7c4`, a `0x500x0x1e0`=1280x480?? -- actually
`0x500`=1280, `0x1e0`=480, likely a doubled/interlaced frame buffer) ->
`_BinkClose_4` on transition. `_BinkWait_4` polls for audio-sync
completion (busy-loop `while (_BinkWait_4(...) != 0) {}` seen at every
transition). Reverse playback (Pass 33's earlier finding) uses
`_BinkGoto_12(bink, startFrameOffset, 0)` then a `CopyToBuffer` call
with the `0x80000000` flag bit set. These are standard, publicly
documented Bink 1.x SDK entry points (the trailing `_N` suffix is the
MSVC `__stdcall` byte-count decoration) -- their own internal behavior
is well-established third-party library semantics, not a StarLancer
reverse-engineering target in itself.

### `DAT_004e5cd0` decoded -- **correcting Pass 36's assumption**

Pass 36 guessed `DAT_004e5cd0` was "a control-descriptor table... each
entry's display-name string [living] at a parallel offset." Read the
raw table bytes directly and reused the `set_function_prototype`
technique (this time on `FUN_00491030`, confirmed via its own
`"invalid language string %d"` assert string to be `GetLanguageString`,
the game's central localized-text accessor: `DAT_0057dbbc` is a base
pointer to a loaded array of string pointers, `DAT_0057dbc0` its count,
1-based indexing). Re-decompiling `RunControlsOptionsScreen` with that
prototype set resolves the ambiguity cleanly:

**~~`DAT_004e5cd0` is NOT a table of named flight controls~~ -- corrected:
it is a table of *candidate rebindable keyboard scancodes*.**

```c
struct KeyScanCandidate {
    int32_t scancode;   // +0x00: a real PC Set-1 scancode (confirmed:
                         // 30/48/46/32/18 decimal = 0x1E/0x30/0x2E/0x20/0x12
                         // = the A/B/C/D/E keys, in sequence -- this table
                         // enumerates essentially every assignable key)
    int32_t tag;         // +0x04: a small monotonically-increasing integer
                         // per entry; used as raw inline bytes in one debug
                         // SafeFormatString call (which is why it looked
                         // like single ASCII letters "A","B","C"... on a
                         // raw byte read -- it's the low byte of this int,
                         // not real text); purpose otherwise undetermined
    // +0x08..+0x23: zero in every sampled entry
};  // 0x24 (36) bytes; 89 entries total, DAT_004e5cd0..0x4e6954
```

Used by `RunControlsOptionsScreen`'s "detect which key the player just
pressed to (re)bind" scan loop: for each of the 89 candidate scancodes,
checks `CheckKeyEdgeState(scancode, modifierMode, 1)` across 3 modifier
modes (0/1/2 = none/Shift/Ctrl -- Alt, mode 3, is NOT scanned for
control rebinding), i.e. an exhaustive "was ANY assignable key just
pressed, in ANY of 3 modifier states" poll.

**The REAL per-control data lives elsewhere**: a parallel record inside
the already-documented `DAT_004e2380` runtime binding table (stride
`0x4e`/78 bytes, confirmed in Pass 36), specifically:
- `DAT_004e23ac[control*0x4e]` (a `short`) -- **the control's
  language-string index**, resolved via `GetLanguageString()` to get
  its real display name (e.g. "Roll Left", "Fire Primary Weapon", etc.
  -- not read out this session).
- `DAT_004e23ae[control*0x4e]` -- a string field (bound joystick/device
  name, already noted in Pass 36).
- Two further fixed language-string indices, `0x5af` and `0x5b0`, used
  as connective phrase text in the rebind-conflict confirmation dialog
  (`"<control> is already bound to <other control>"`-shaped, exact
  wording not recovered -- the loaded string table itself isn't present
  in the static binary image, `DAT_0057dbbc` reads as all-zero,
  confirming it's populated at runtime from an external language
  resource, not baked into the `.exe`).

**Confidence 4** on the `KeyScanCandidate` structure and its role
(directly read from real data + confirmed by the decompiled scan loop);
confidence 2 on the `tag` field's purpose (clearly not meaningful
display text, otherwise undetermined).

### Open follow-ups

- Read `DAT_004e2380`'s full entry range to enumerate the REAL control
  list (names via `DAT_004e23ac`+`GetLanguageString`, default bound
  scancodes via the table's own key fields) -- this is the corrected
  version of Pass 36's goal, now pointed at the right table.
- The loaded language string table itself is runtime-only; no static
  strings are recoverable without a live session.
- `FUN_0042c5f0` (used in the rebind-conflict-detection path, returns
  -1 for "no conflict") -- not decompiled.

## Pass 38 -- THE COMPLETE DEFAULT FLIGHT CONTROL SCHEME (2026-09-09)

Direct continuation of Pass 37's flagged follow-up: read `DAT_004e2380`
(the real per-control runtime binding table, corrected in Pass 37 to be
distinct from the `DAT_004e5cd0` scancode-candidate table) directly out
of memory in full. Created a real Ghidra struct, `ControlBinding` (78
bytes), and applied it as `ControlBinding[74]` over the table.

```c
struct ControlBinding {
    int16_t scancode;         // +0x00: bound PC Set-1 scancode
    int16_t modifierMode;     // +0x02: 0/1/2 = none/Shift/Ctrl (matches CheckKeyEdgeState's mode arg)
    char    debugName[40];    // +0x04: plain-English internal control name (NOT localized --
                               //        the developer-facing name, always present regardless of language)
    int16_t langStringIndex;  // +0x2C: index into the runtime-loaded localized string table
                               //        (via GetLanguageString) -- the REAL in-game display name
    char    keyLabelText[30]; // +0x2E: a short printable label for the bound key (e.g. "TAB",
                               //        "ENTER", "PAGE UP", "CURSOR DIWN" [sic]) -- NOT a joystick
                               //        device name as guessed in Pass 36/37; it's the UI's
                               //        "currently bound key" readout text
    int16_t actionSlot;       // +0x4C: -1 for most entries; a small distinct index (0-7, missing
                               //        6) for exactly 7 entries -- plausibly a persistent
                               //        per-frame-polled action-state slot for continuously-held
                               //        flight controls, vs. -1 for edge-triggered/UI-toggle
                               //        controls (hypothesis, confidence 2, not confirmed)
};  // sizeof == 0x4E (78) bytes, exactly matching every stride already documented
    // for this table across Passes 26/27/36/37
```

**74 entries total** (`DAT_004e2380` through `+74*0x4e`, confirmed
exactly by both the byte count matching a whole multiple of 78 and the
data transitioning cleanly into an unrelated pointer table -- the `.ut`
speech-file string-pointer array documented in Pass 29 -- immediately
afterward, with no partial/trailing entry).

### The full list, read directly from the shipped binary's initial `.data` image

Grouped by natural category (the table's own storage order, not
re-sorted):

**Camera (8):** Cockpit(1) / Left View(2) / Right View(3) / Rear
View(4) / Flyby(5) / Target(6) / External(7) / Missile(8) Camera.

**Targeting (12):** Next/Previous Enemy Target (E / Shift+E), Next/
Previous Friendly Target (Q / Shift+Q, actionSlot=5 on the "Next"
entry), Next/Previous Subtarget (S / Shift+S), Target Under
Reticule (Y), Target Nearest Enemy (R, actionSlot=3), Target Nearest
Friendly (W), Target Torpedo (T), Smart Target (Ctrl+E), Primary
Target (A).

**Flight/Throttle (18):** Afterburners (TAB, actionSlot=2) / Afterburner
Toggle (`` ` ``) / Reverse Thrust (Shift+TAB), Jump Drive (J), Match
Speed (Z), Accelerate (+) / Decelerate (-) / Zero Throttle (BACKSPACE)
/ Full Throttle (\\), Roll Ship Clockwise/Anti-Clockwise (Page Up/Page
Down), Nose Up/Down (Cursor Down/Up -- **note the game's own shipped
label text literally reads "CURSOR DIWN", a genuine developer typo
preserved verbatim in the binary**), Rotate Clockwise/Anti-Clockwise
(Cursor Left/Right), Strafe Left/Right (END actionSlot=7 / Page Down
actionSlot=4), Joystick Roll (Insert).

**Weapons (10):** Fire Lasers (SPACE, actionSlot=0), Full Guns (F),
Gunnery Window / Locked / Synchronise Guns (G / Shift+G / Ctrl+G),
Toggle Blindfire (Shift+F), Launch Missile (ENTER, actionSlot=1),
Missile Window (M), Rotate Missiles Clockwise/Anti-Clockwise (. / ,).

**Ship systems / info windows (15):** Comms Window (C), Powerball
Window / Locked (P / Shift+P), Full Power to Gunnery/Engines/Shields
(U/I/O), Equalize Power ([), Objectives Window (B), Wing Status Window
/ Locked (X / Shift+X), Damage Window / Locked (D / Shift+D), Radar
Ranges (V), Shield Balancing (N), Countermeasures (H).

**Special abilities (4):** Eject (F12), Cloak Ship (K), ECM (L),
Spectral Shields (`;`) -- the last directly confirms and extends the
already-documented Spectral Shields mechanic (temporary invulnerability,
several sessions ago) with its real default keybind.

**Wingman/comms commands (6):** Attack My Target (F5), Back Off (F6),
Help Me (F7), Permission to Land (F8), Display Kills (F10), Send Comms
Message (`'`).

**Menu (1):** Key Config (F1) -- opens `RunControlsOptionsScreen`
itself.

### Confidence

**Confidence 5** on every scancode/modifier/name/keyLabelText value --
this is direct, literal, unambiguous data read from the shipped
binary's static image (not inferred, not runtime-only). **Confidence
2** on the `actionSlot` field's "continuously-polled vs. edge-triggered"
interpretation (a reasonable hypothesis given which 7 entries have a
non -1 value -- Fire Lasers, Launch Missile, Afterburners, Target
Nearest Enemy, Strafe Right, Next Friendly Target, Strafe Left -- all
plausibly analog/held-style controls, but not traced to confirming
consumer code this session). `langStringIndex` values are real and
directly read, but their actual localized TEXT remains unrecoverable
from the static image (Pass 37 already established `DAT_0057dbbc`, the
loaded string table, is runtime-only and reads as all-zero here).

### Open follow-ups

- Trace what reads `ControlBinding.actionSlot` to confirm/refute the
  "persistent action index" hypothesis.
- The `langStringIndex` values are real but their text is unrecoverable
  without a live session or an extracted language resource file.
- Whether this exact 74-entry list matches the manual/in-game options
  screen's own displayed order -- not cross-checked.

## Pass 39 -- .fnt/.spr assets identified as WinVFX resource formats (2026-09-09)

Direct investigation of the `.fnt` (font) and `.spr` (sprite) asset
formats. Found and traced the loading pathway to its real conclusion: a
completely separate, dynamically-loaded third-party 2D rendering
library, distinct from SurrenderLib (3D), Bink (video), and Miles
(audio) -- rounding out the full picture of Star Lancer's middleware
stack.

### The loading pathway

Both `.fnt` and `.spr` files load through the SAME generic path already
documented (`LoadNamedResource` -> `HOG_BigRead`/loose-file fallback,
Pass 28) -- there is no StarLancer-specific header parsing at that
layer. The returned raw buffer is then handed directly to a THIRD
external rendering library as an opaque resource handle:

- `.fnt` (e.g. `handel.fnt`, `smlfont.fnt`, `blufont.fnt`) -> consumed
  via `VFX_string_draw`/`VFX_character_width`.
- `.spr` (e.g. `frontend.spr`, `capships.spr`, `quit.spr`) -> consumed
  via the `VFX_shape_*` function family (`VFX_shape_draw`,
  `VFX_shape_translate_draw`, `VFX_shape_transform`,
  `VFX_shape_draw_mirrored`, `VFX_shape_draw_tinted`,
  `VFX_shape_draw_filtered`, `VFX_shape_lookaside`,
  `VFX_shape_multilookaside`, `VFX_shape_bounds`, `VFX_shape_scan`,
  `VFX_shape_origin`, `VFX_shape_resolution`).

### `InitializeWinVfxLibrary` (`0x4a26d0`, was `FUN_004a26d0`)

Confirms the real library: dynamically loads **`winvfx8.dll`** or
**`winvfx16.dll`** via `LoadLibraryA`, selected by the active color
depth (`*(int*)(DAT_00588730+0x160e) < 2` -- 8-bit palette mode vs.
16-bit true color), then resolves ~27 `VFX_*` entry points via
`GetProcAddress` into a global function-pointer table (`DAT_005959e4`,
`DAT_00594434`, `DAT_00595068`, etc. -- the same table `DrawShapeJittered`
and dozens of other functions call through, previously undocumented as
a distinct library). Fatal-errors (`"init_vfx: Can't find WINVFXxx.DLL"`)
if the DLL isn't found.

**This is a real, separate, dynamically-linked 2D graphics library --
`.fnt` = a WinVFX Font resource, `.spr` = a WinVFX Shape resource.**
Their internal binary layouts are NOT parsed anywhere in `Lancer.exe`
itself -- all parsing happens inside `winvfx8.dll`/`winvfx16.dll`,
external files not present in this reverse-engineering project's scope
(same category of finding as Bink/`.bik` and Miles Sound System audio:
a well-defined boundary to third-party middleware, not a StarLancer
game-logic format). **Confidence 5** that this is the real,
unavoidable conclusion -- the DLL name, load mechanism, and ~27 real
`VFX_`-prefixed export names are all read directly and unambiguously
from the decompile.

### Palette initialization ties back to the `.ccb` master palette (Pass 30)

Immediately after resolving the DLL's exports, `InitializeWinVfxLibrary`
initializes WinVFX's own global palette using the SAME RGB-triple
source (`DAT_00588730+0x1602`) and the SAME per-channel bit-shift/mask
constants (`DAT_00588730+0x162a/0x1626/0x1632/0x163e/...`) as the
SurrenderLib palette-conversion loop documented in Pass 25/30 -- calling
`VFX_return_global_palette` (`DAT_005957c0`) to get a writable buffer,
packing the RGB triples into it, then `VFX_init_global_palette`
(`DAT_005957d0`) to commit it. **This confirms the `.ccb` master
palette (`palette.ccb`/`softpal.ccb`) is shared across BOTH the 3D
renderer (SurrenderLib) and the 2D UI/sprite renderer (WinVFX)** -- one
palette resource, two independent rendering backends consuming it via
near-identical conversion code. If `DAT_00594544+0x10` (a device-caps
field) indicates a true-color mode (`> 1`), this palette step is
skipped entirely in favor of a different mode (`FUN_00480a40` called in
a small radial loop instead -- not decompiled, likely an anti-aliasing
or gradient-edge setup for high-color rendering).

### `DrawShapeJittered` (`0x48c6e0`, was `FUN_0048c6e0`)

One heavily-called consumer of the `VFX_shape_*` API, examined to
confirm the library boundary. In the hardware-rendering path
(`DAT_00588730+0x1ac != 0`), performs a **software-composited
screen-distortion/jitter effect**: reads a shape's bounds via
`VFX_shape_bounds`, then blits it scanline-by-scanline with a per-line
random horizontal offset (`_rand()`-driven, scaled by
`DAT_00588700`/`DAT_00588724` -- these are almost certainly damage-flash
or hit-shake intensity globals given their names' proximity to other
already-documented damage-effect state) and handles all 4
orientation/flip cases (`uStack_20` bits 0-2). In the pure software
path, falls back to a direct `VFX_shape_draw_mirrored`/`VFX_shape_draw`
call with no jitter. This is very likely the "screen distortion when
you take a hit" visual effect, though not cross-checked against a
specific damage-event caller this session.

### Open follow-ups

- The actual `.fnt`/`.spr` binary layouts remain genuinely
  unrecoverable without `winvfx8.dll`/`winvfx16.dll` (not present in
  this project) -- correctly identifying this boundary is the
  conclusion, not a gap to keep chasing.
- `DAT_00588700`/`DAT_00588724` (jitter intensity globals) -- not
  independently characterized or confirmed as damage-flash state.
- `FUN_00480a40` (the true-color-mode palette-skip alternative) -- not
  decompiled.
- Confirm `DrawShapeJittered`'s callers to nail down exactly which
  gameplay event triggers the jitter effect.

## Pass 40 -- WINVFX8.DLL is present in gamedata: the real .spr/.fnt formats decoded (2026-09-09)

**Correcting Pass 39, not silently**: Pass 39 concluded the `.fnt`/
`.spr` binary formats were "genuinely unrecoverable... `winvfx8.dll`/
`winvfx16.dll` (not present in this project)". That was wrong --
`WINVFX8.DLL` **is** present at
`gamedata/StarLancer/WINVFX8.DLL` and was loaded as a second Ghidra
program in this session. It's small (22 functions, ~174KB), and most
exports were already usefully named by prior auto-analysis
(`VFX_shape_draw`, `VFX_shape_bounds`, `VFX_shape_count`,
`VFX_shape_list`, `VFX_shape_palette`, `VFX_shape_colors`,
`VFX_font_height`, `VFX_character_width`, `VFX_character_draw`,
`VFX_string_draw`, etc.) -- decompiling them directly gives the real,
byte-exact on-disk/in-memory format for both asset types.

### `.spr` (Shape) format

```c
struct ShapeSet {
    uint32_t unknown0;       // +0x00, purpose not decoded this pass
    uint32_t shapeCount;     // +0x04 -- VFX_shape_count reads this directly
    struct {
        uint32_t recordOffset;   // +0x00: byte offset (from ShapeSet base) to this
                                  // shape's ShapeRecord
        uint32_t paletteOffset;  // +0x04: byte offset (from ShapeSet base) to an
                                  // optional palette-override sub-record, or 0
    } shapes[shapeCount];    // +0x08, 8 bytes per entry
};

struct ShapeRecord {           // at ShapeSet_base + shapes[i].recordOffset
    uint32_t headerField0;     // +0x00 -- returned verbatim by VFX_shape_bounds();
                                // exact meaning (packed bbox? flags?) not decoded
    uint32_t headerField1;     // +0x04 -- not examined
    int32_t  boundX1, boundY1; // +0x08, +0x0C -- top-left of the shape's bounding box
    int32_t  boundX2, boundY2; // +0x10, +0x14 -- bottom-right
    uint8_t  rleData[];        // +0x18 -- RLE-compressed pixel data, row-major,
                                // width = boundX2-boundX1+1 implied by the draw loop
};

struct PaletteOverrideRecord {  // at ShapeSet_base + shapes[i].paletteOffset (VFX_shape_palette)
    uint32_t entryCount;
    struct { uint8_t paletteIndex, r6, g6, b6; } entries[entryCount];
    // r6/g6/b6 are 6-bit VGA-style color components, left-shifted by 2 to
    // produce 8-bit output -- classic VGA-palette-register precision.
};
```

**The RLE pixel encoding** (decoded from `VFX_shape_draw`'s inner
loop, confirmed against the simpler unclipped path
`VFX_shape_blit_unclipped`, was `FUN_100035fc`): a **row-oriented,
back-reference-free run-length scheme**, distinct from the RefPack/QFS
LZ77 codec already documented for BigFile archive compression (Pass
29) -- this is a much simpler, sprite-specific format with no
cross-row or long-distance back-references, well suited to fast
scanline blitting with integrated clip-rectangle handling. Each row is
terminated by a marker byte tested via `(byte & 1)`; runs alternate
between literal-copy and single-byte-repeat modes based on a low-bit
flag in each control byte, with run lengths unpacked via `>> 1` and
`& 3`/`>> 2` (byte-then-dword copy loops for speed). The decoder is
heavily inlined and duplicated (4 near-identical variants) to handle
every combination of left/right/top/bottom clip-edge intersection
without a per-pixel branch -- a genuine, hand-optimized 2D sprite
blitter from the "software rendering era."

**Confidence 4** on the `ShapeSet`/`ShapeRecord`/`shapes[]` layout
(directly read from real code, internally consistent across 4
independent functions -- `count`, `list`, `bounds`, `draw` all agree);
confidence 3 on the exact RLE bit-packing (the control-flow is real and
decoded, but not independently verified by hand-decoding one real
`.spr` file's bytes against this scheme this session); confidence 1 on
`headerField0`/`headerField1`'s meaning (not decoded).

### `.fnt` (Font) format

```c
struct FontResource {
    uint32_t unknown0;        // +0x00
    uint32_t unknown1;        // +0x04
    uint32_t lineHeight;      // +0x08 -- VFX_font_height reads this directly
    uint32_t unknown2;        // +0x0C
    uint32_t glyphOffset[256];// +0x10 -- one 4-byte offset per possible character
                               // code (0-255), each pointing (relative to
                               // FontResource base) to a GlyphRecord; a NULL/0
                               // offset presumably means "no glyph" for that code
};

struct GlyphRecord {          // at FontResource_base + glyphOffset[charCode]
    uint32_t width;           // +0x00 -- VFX_character_width reads this directly
    uint8_t  pixels[];        // +0x04 -- RAW, UNCOMPRESSED bitmap, width*lineHeight
                               // bytes, one byte per pixel (palette index) -- NOT
                               // RLE-compressed, unlike shapes
};
```

Confirmed via `VFX_character_draw`, which supports two blit modes
selected by its `param_8` argument: **direct copy** (`param_8==0`,
palette-index bytes written straight to the destination, used for
plain paletted-8-bit-mode text) and a **remap-table mode**
(`param_8!=0`, each source byte looked up in a 256-entry table before
writing -- either a `short` table, for 16-bit true-color text with a
transparent-pixel sentinel `0xfffe`, or a `byte` table with sentinel
`0xff` -- i.e. **tinted/colored text rendering**, matching the many
different-colored `.fnt` files found in Pass 39's string search --
`blk2orng.fnt`, `blufont.fnt`, `med_red.fnt`, `sml_red.fnt`, etc. are
very likely all differently-PALETTED uses of the same underlying glyph
bitmaps via this remap mechanism, though that specific claim isn't
independently confirmed).

**Confidence 4** on the `FontResource`/`GlyphRecord` layout (directly
read from `VFX_font_height`/`VFX_character_width`/`VFX_character_draw`,
mutually consistent); confidence 2 on the "differently-named .fnt files
are palette-remap variants of shared glyphs" hypothesis.

### Corrected conclusion

Pass 39's category-level finding stands (this IS a separate,
dynamically-loaded rendering library distinct from SurrenderLib/Bink/
Miles) but its specific claim that the binary is "not present in this
project" was wrong and is corrected here explicitly. The DLL is a real,
small, fully-decompilable target and both asset formats are now
understood at the structural level.

### Open follow-ups

- `ShapeRecord.headerField0`/`headerField1` -- not decoded.
- `VFX_shape_colors`'s exact record format (a flat int array, distinct
  from `VFX_shape_palette`'s structured RGB entries) -- read but not
  fully explained.
- Byte-exact verification against a real `.spr`/`.fnt` file's actual
  bytes (e.g. via `search_byte_patterns` against a known filename's
  loaded buffer) -- not done this session, would raise the RLE-decoding
  confidence from 3 to higher.
- `WINVFX16.DLL` (the 16-bit-color counterpart) -- not examined; likely
  near-identical with wider pixel fields.

## Pass 41 -- `ShapeRecord.headerField1` resolved: it's the shape's origin point (2026-09-09)

Direct follow-up on Pass 40's open items. Checked the three remaining
undecompiled `VFX_shape_*` accessors in `WINVFX8.DLL`
(`VFX_shape_minxy`, `VFX_shape_origin`, `VFX_shape_resolution`) --
all three confirm and extend the `ShapeRecord` layout cleanly, with no
surprises for the bounding-box fields:

```c
undefined4 VFX_shape_origin(int shapeSet, int shapeIndex)
{
    return *(undefined4 *)(*(int *)(shapeSet + 8 + shapeIndex * 8) + shapeSet + 4);
}
```

**This directly resolves `ShapeRecord+0x04`** (called `headerField1`,
"not examined", in Pass 40): it's the shape's **origin/handle point** --
a packed offset (the function name and its position immediately after
the mystery header field strongly implies a packed `{x,y}` pivot used
when positioning the shape on-screen, analogous to a sprite's "hotspot"
in classic 2D engines). `VFX_shape_minxy` and `VFX_shape_resolution`
both independently confirm the bounding-box field positions already
documented in Pass 40 (`+0x08`/`+0x0C` = X1/Y1, `+0x10`/`+0x14` = X2/Y2,
with `VFX_shape_resolution` computing width/height as
`(X2-X1)+1`/`(Y2-Y1)+1` -- a clean, unsurprising confirmation).

Updated `ShapeRecord`:

```c
struct ShapeRecord {
    uint32_t headerField0;   // +0x00 -- still unresolved; VFX_shape_bounds
                              // returns this verbatim, but no accessor gives
                              // it independent meaning
    uint32_t originXY;       // +0x04 -- packed {x,y} draw origin/hotspot,
                              // confirmed via VFX_shape_origin
    int32_t  boundX1, boundY1; // +0x08, +0x0C
    int32_t  boundX2, boundY2; // +0x10, +0x14
    uint8_t  rleData[];       // +0x18
};
```

### Verification attempt: real `.spr`/`.fnt` files exist on disk but are RefPack-compressed

Located real loose asset files (`gamedata/StarLancer/RESOURCE/FONT.FNT`,
`gamedata/StarLancer/cd1/YOVB.SPR`, etc.) intending to verify the
decoded structs against real bytes. `FONT.FNT` begins `10 FB 00 34 72
E1 32 2E ...` -- the RefPack magic (Pass 29) followed immediately, so
even LOOSE, non-archived `.fnt`/`.spr` files ship RefPack-compressed
and must be decompressed before the `FontResource`/`ShapeSet` structs
apply. Also confirmed no live Lancer.exe process is attached this
session (`read_memory` on known runtime-only resource-pointer globals
like `DAT_00520134` reads as zero, consistent with earlier sessions'
findings that only compile-time-initialized `.data` is visible, not
runtime state) -- so a live-memory verification isn't available either.
**Did not attempt a hand-ported RefPack decompressor this session** --
mis-porting the intricate control flow from `DecompressRefPackBlock`
by hand risked producing a false-positive or false-negative
verification, which would be worse than leaving this open. Flagging
this honestly as unverified rather than forcing a shaky confirmation.

### Open follow-ups

- A careful, tested RefPack decompressor (Python or otherwise) run
  against a real `.fnt`/`.spr` file would let the `FontResource`/
  `ShapeSet` confidence move from "structurally decoded" to "verified
  against real data" -- valuable if pursued carefully.
- `ShapeRecord.headerField0` remains unresolved.
- `VFX_shape_colors`'s record format, `WINVFX16.DLL` -- still open
  from Pass 40.

## Pass 42 -- RefPack decoder built and verified byte-exact against real assets (2026-09-09)

Direct request: build a RefPack decoder. Rather than trust a
half-remembered "public spec," hand-ported the EXACT logic from
`DecompressRefPackBlock`'s decompile (Pass 29, `0x4cc350`) to Python,
opcode-by-opcode, then tested it against real files in `gamedata/` --
this fully resolves Pass 41's deliberately-left-open verification gap.

### The real header format (byte-exact, empirically confirmed)

```
offset 0: 0x10                    -- magic byte 1
offset 1: 0xFB                    -- magic byte 2
offset 2-4: decompressed size, 3 bytes, BIG-ENDIAN
offset 5: opcode stream starts immediately
```

This is simpler than either of the two hypotheses floated in Passes
29/40/41 (no extra 3-byte or 5-byte inner skip beyond the magic+size).
Confirmed by brute-force testing every plausible start offset against
`gamedata/StarLancer/RESOURCE/FONT.FNT`: **offset 5 is the only one
that (a) decompresses cleanly to completion with zero invalid
back-references and (b) produces an output length -- 13,426 bytes --
that exactly matches the file's own big-endian size field
(`0x003472` = 13426) read from offset 2-4.** This also means the
`DecompressBigFileEntry`-side "5-byte header" described in Pass 28 is
almost certainly this SAME 5-byte magic+size header, not an additional
wrapper on top of it -- Pass 28's description was accurate, Pass 29/41's
speculation about extra skip bytes inside `DecompressRefPackBlock`
itself was an artifact of mis-tracing `ushort*` vs. byte-pointer
arithmetic by hand; the empirical result supersedes that hand-trace.

### The opcode algorithm (confirmed byte-exact against 2 real files)

Four back-reference forms plus two run forms, matching the canonical
public RefPack/QFS scheme structurally (confirming Pass 29's original
identification), with exact bit-packing now nailed down against real
data rather than assumed:

| Control byte `B0` | Form | Literal count | Copy length | Distance |
|---|---|---|---|---|
| `0x00-0x7F` | 2-byte short | `B0&3` | `((B0>>2)&7)+3` | `(((B0>>5)&3)<<8)+B1+1` |
| `0x80-0xBF` | 3-byte medium | `B1>>6` | `(B0&0x3F)+4` | `((B1&0x3F)<<8)+B2+1` |
| `0xC0-0xDF` | 4-byte long | `B0&3` | `((((B0>>2)&0x3F)<<8)\|B3)&0x3FF)+5` | `(((B0&0x10)>>4)<<16)+(B1<<8)+B2+1` |
| `0xE0-0xFB` | literal run | -- | `(B0&0x1F)*4+4`, no back-reference | -- |
| `0xFC-0xFF` | end marker | `B0&3` final literal bytes, then stop | -- | -- |

### Verification against real assets

**`FONT.FNT`** (`gamedata/StarLancer/RESOURCE/`, 3805 compressed bytes)
decompresses cleanly to exactly 13,426 bytes. Interpreted as the
`FontResource` struct from Pass 40: `lineHeight=17` (a plausible pixel
height), 250 of 256 `glyphOffset[]` entries non-null (exactly what
you'd expect for a printable-ASCII font missing a handful of control
codes), and individual glyph widths are sane and character-appropriate:
**`'A'`=9px, `'0'`=9px, `' '`(space)=5px** -- the space character being
narrower than letters is exactly the expected real-world result,
about as strong a confirmation as static analysis can produce without
actually rendering the glyphs.

**`YOVB.SPR`** (`gamedata/StarLancer/cd1/`, 1,227,865 compressed bytes)
decompresses to 1,624,208 bytes, `shapeCount=98`. Interpreted as the
`ShapeSet`/`ShapeRecord` structs from Pass 40: shapes 1-4 show clean,
sane bounding boxes sharing a common top-left origin `(22,7)` with
increasing sizes (`57x19`, `296x357`, `296x396`, `296x402` pixels) --
exactly the pattern expected of a multi-frame image/animation sheet.
(Shape 0 decoded to nonsense values -- flagged honestly below rather
than glossed over.)

**Confidence raised to 5** (byte-exact, verified against 2 independent
real files) for: the RefPack opcode algorithm, the 5-byte header
format, the `FontResource`/`GlyphRecord` layout, and the
`ShapeSet`/`ShapeRecord` layout (excepting `headerField0`, see below).

### Saved as a reusable project tool

`reversing/tools/refpack_decompress.py` -- a clean, standalone,
dependency-free Python port, runnable directly against any `.fnt`/
`.spr`/BigFile-archive-extracted compressed resource in `gamedata/`.

### Open follow-ups

- `YOVB.SPR` shape index 0 decoded to garbage bounding-box values
  while shapes 1-4 were clean -- worth checking whether index 0 is a
  special/reserved entry (e.g. a palette-only or metadata slot) rather
  than a real drawable shape, or whether the `ShapeSet` header's
  `unknown0` field affects how index 0 specifically should be
  interpreted.
- `ShapeRecord.headerField0` (Pass 40/41) is now verified-readable but
  still has no confirmed semantic meaning.
- The "large header" (4-byte size) RefPack variant, gated by a flag bit
  in `DecompressRefPackBlock`'s original logic, was not exercised by
  either test file (both used the compact 3-byte-size form) -- not
  independently verified.

## Pass 43 -- Mission briefing / weapons loadout / debriefing: the full flow (2026-09-09)

Direct research request. Re-decompiled `RunMissionBriefingScreen` in
full (previously only documented at a summary level in Passes 4/7) and
traced its two direct callees, `InitializeLoadoutScreen` (was
`FUN_00441aa0`, source-tagged `C:\lancer\interface\loadout\loadout.cpp`
and `...\loadout_load.cpp`) and `UpdateLoadoutSelection` (was
`FUN_00443760`). Together these three functions implement the ENTIRE
pre-mission sequence, and reveal `RunMissionBriefingScreen` also
doubles as the debriefing/epilogue screen -- resolving several loose
threads from Passes 4, 6, and 25 in one pass.

### The full sequence, in order

1. **Loadout scene setup** (`InitializeLoadoutScreen`, called first,
   BEFORE the briefing video, unless the current mission is `0x1d`/29):
   loads and positions 3 separate ship-model lists -- fighters
   (`DAT_00523e84` count), missiles (`DAT_00523e74`), and gunships
   (`DAT_00523aa4`) -- each via `SR_MEM_allocate_named(...,
   "C:\lancer\interface\loadout_load.cpp",...)`, builds the loadout
   room's backdrop/panel materials, sets up a master target-reticle
   mesh and lighting rig ("Loadout cursor light", "Loadout Ambient
   light", "Loadout bgreen/red/green light" -- confirmed real light
   names), and converts the shared `.ccb` master palette (Pass 30) for
   this scene. This is a genuinely huge, expensive one-time setup --
   consistent with `WinMain`'s `InitializeMissionGameplay`/`RunMission
   Gameplay`/`UnloadMission` trio pattern of "prepare everything up
   front."

2. **Briefing video OR the campaign epilogue** (`RunMissionBriefingScreen`
   itself): builds a filename array covering missions 15,16,18-28
   (`"new_m15.bik"`..`"new_m28.bik"`, confirming and extending Pass 4's
   partial list) and, for a normal mission, opens `"<name>.bik"` via
   `FindBinkMovieInArchive`+`_BinkOpen_8`, playing it in a poll loop
   (Esc to skip, `'0'` for screenshot via `SaveScreenshotTga`).
   **Mission `0x1d` (29) takes a completely different path here**:
   instead of a Bink video, it loads a resource via `HOG_BigRead()`
   whose filename argument (hidden `__fastcall` register, but its
   address falls exactly on the `"enddebriefing.ut"` string per a
   direct data xref) is **`enddebriefing.ut`** -- confirming, at last,
   that **mission 29 is not a normal mission at all -- it's the
   campaign's own final debriefing/epilogue sequence**, explaining
   every one of the "mission 29 special-cased, no speech-tag lookup"
   observations scattered across Passes 4, 6, and 25.

3. **Interactive loadout configuration** (the huge second half of
   `RunMissionBriefingScreen`, reached via `goto LAB_004376d2` after
   the video/epilogue finishes): re-initializes the render pane, then
   runs a real per-frame loop calling `UpdateLoadoutSelection` every
   tick. That function toggles per-object visibility flags (`+0x40`)
   across the fighter/missile/gunship model arrays based on the
   player's current selection, rebuilds the selection tooltip
   (`FUN_00446180`), and contains one concrete mission-specific rule:
   **mission `0x17` (23) hides one specific object from the loadout**
   (`if (DAT_00562dc8 != 0x17) { show object }` -- i.e. that one item
   is unavailable during mission 23 specifically; which item and why
   not decoded further this session). Exit is via `FUN_004394d0`'s
   confirm dialog (0=keep configuring, 1=confirmed->launch into VR ship
   interior with the campaign-stage-appropriate hub room, 2=cancel/other
   ->return 1 without launching).

4. **Closing speech narration**: after loadout confirmation, loads
   `"ms_speech_enrbr_tag_%02d.ut"` (Pass 4's "enroute briefing" tag,
   confirmed here as playing AFTER loadout selection, not before) and
   polls until it completes or `DAT_0051da94` reaches a fixed frame
   count (`0x3c`=60), with a synced animation trigger at frame `0x11`
   (17) via `FUN_00461d80(0,0x7f)` -- very likely a talking-head/mouth
   animation cue for a comm-window portrait, matching this project's
   earlier-documented pattern of synced portrait animation during
   dialogue.

5. **Hand-off**: cleans up all loadout resources and returns control to
   `RunShipInteriorVRLoop` (via the `DAT_0051d478` room-node
   assignment already documented in Pass 4), or exits to the main menu
   if the player backed out.

### Confidence

**Confidence 4** on the overall 5-stage sequence and the mission-29-is-
the-debriefing finding (both directly read from the decompile, with the
`enddebriefing.ut` connection confirmed via a real data xref rather than
guessed); **confidence 2** on the specific claim that `UpdateLoadoutSelection`'s
`0x11`-frame trigger is a talking-head animation cue (a reasonable
inference from this project's established patterns, not independently
verified); **confidence 1** on what mission 23's hidden loadout item
actually is (not decoded).

### Open follow-ups

- `InitializeLoadoutScreen`'s 3 ship-model-list build loops (fighters/
  missiles/gunships) were decompiled at a structural level only (Pass
  36-era investigation) -- the actual per-mission AVAILABLE-LOADOUT
  list (which fighters/weapons the player can choose from, and how it
  varies by campaign progress) was not extracted.
- `UpdateLoadoutSelection`'s exact selection/input-handling logic (how
  clicking a ship model changes `DAT_00523e68`, the "currently selected
  index") -- not traced.
- Mission 23's hidden loadout object -- not identified.
- `FUN_00446180` (tooltip/description text builder) -- not decompiled;
  likely the most direct path to real weapon/ship names and stats if
  pursued further.

## Pass 44 -- VR ship interior: what happens when a `.bik` clip finishes (2026-09-09)

Direct research request: decompiled `FUN_0043c1c0`, the per-frame
callback installed at `DAT_00588730+0x88` throughout
`RunShipInteriorVRLoop` (previously only referenced by address, never
opened -- this is where the ACTUAL Bink frame-advance and
completion-handling logic lives, not in the loop body documented in
Pass 33).

### Does the animation stop on the last frame? Yes, for ordinary rooms.

```c
iVar8 = _BinkWait_4(DAT_0051d7e8);
if (iVar8 == 0) {                        // Bink is ready to advance
  _BinkDoFrame_4(DAT_0051d7e8);
  _BinkCopyToBuffer_28(...);              // decode + blit current frame
  if (*(int *)(bink+0xc) == *(int *)(bink+8)) {   // current frame == total frame count
    if (DAT_0051d9e4 == 1) { ... }        // "just transitioned" state -- see below
    else { DAT_00520298 = 1; }            // ordinary steady-state room: just flag completion
  } else {
    _BinkNextFrame_4(DAT_0051d7e8);       // not at the end yet -- advance normally
  }
}
```

**Confirmed: once a steady-state room's ambient `.bik` loop (e.g. the
already-documented `"b2iloop.bik"` bunkroom idle clip) reaches its
final frame, `_BinkNextFrame_4` simply stops being called.** There is
no automatic loop-back to frame 0 anywhere in this function for the
ordinary case -- the decoder just keeps re-decoding/re-blitting
whatever the current (final) frame is, so **the displayed image holds
on the last frame** rather than restarting. The only thing that changes
is a completion flag, `DAT_00520298`, gets set to 1.

### What happens after completion depends on room state

`DAT_00520298` is read every frame by the OUTER loop body (documented
in Pass 33): `if (DAT_00520298 == 0) break;` -- once it's 1, the loop
proceeds into the `roomType`-keyed dispatch block. For the special hub
room types (1/2/5/6/7/9), that dispatch is what actually drives the
scripted transition to a different room/screen already documented in
Pass 5 (e.g. roomType 7 -> briefing room). **For an ordinary room with
no special `roomType` case, nothing further happens automatically --
the video just sits frozen on its last frame until the player clicks a
hotspot**, which is handled entirely separately (Pass 33's hotspot
hit-test, unrelated to this completion flag).

### `DAT_0051d9e4 == 1` (arrival-clip just finished): two distinct behaviors

This branch fires when a `pMoviePathAlt` arrival clip (Pass 33) finishes,
or when the current room is `roomType == 3` (the hover-prop trigger
room type, also Pass 33):

**`roomType == 3` -- confirms and extends Pass 33's finding, and directly
answers the original question about a follow-on asset**: rather than
loading a `.spr` file, the game **opens a completely NEW `.bik` clip**,
chosen from a small weighted table and cycled via an incrementing index
(`DAT_0051dac0`, wraps at 14): the 14-entry table
(`PTR_s_move_a__004e8138`) resolves to just 4 distinct base names --
`"move_a_"` (7 of 14 slots), `"move_b_"` (3 slots), `"move_c_"` (1
slot), `"move_d_"` (2 slots) -- built into filenames like
`"move_a_.bik"`. The function's own error strings confirm the theme:
`"fish_tank_resource: error searching %s"` / `"tv_in_loop.bik"`. **This
is a decorative in-room fish-tank/TV prop**: the FIRST clip you trigger
by hovering (`"move_a.bik"`, no trailing underscore, per Pass 33) plays
once, and once it completes, the game cycles into a weighted-random
sequence of 4 follow-up clips (`move_a_`/`move_b_`/`move_c_`/`move_d_`)
-- almost certainly 4 different fish-swimming animation variants,
looping indefinitely with this same completion-triggered logic feeding
itself. **A real `fish.spr` file does exist** (found in Pass 39's
initial `.spr` string search) and is thematically related, but is NOT
what loads here -- the animated content itself is entirely `.bik`
video, not a sprite; `fish.spr` is presumably a separate static
icon/cursor asset for the hoverable hotspot rather than the played
content.

**Any other room reaching this branch** (an ordinary room's arrival
clip finishing, `roomType != 3`): does NOT open a new file at all --
instead calls `_BinkGoto_12(bink, 2, 1)`, seeking the SAME already-open
clip back to frame 2 and re-caching its decoded pixels into the shared
overlay buffer (`DAT_0051d9d8`, the same hover-prop compositing buffer
from Pass 33). This effectively holds/re-loops the arrival clip near
its start rather than freezing on its end frame -- the opposite
behavior from the ordinary steady-state case above.

### Confidence

**Confidence 5** on the "no auto-loop, freezes on last frame for
ordinary rooms" finding and the "fish-tank clip-cycling, not an `.spr`
file" finding -- both directly read from the decompile, including
literal filenames and the weighted table's real contents.
**Confidence 2** on the "4 different fish-swim-direction animations"
interpretation of `move_a/b/c/d` (a reasonable inference from the
`fish_tank`/`tv_in_loop` naming, not independently confirmed by viewing
the actual clips).

### Open follow-ups

- Which specific VR room(s) actually have `roomType == 3` in the full
  145-node graph (Pass 5 found one instance, `0x50ad48`, without
  further characterizing it as a "fish tank") -- worth cross-referencing
  now that this room type's behavior is fully understood.
- Whether `fish.spr` is used elsewhere as a hotspot cursor/icon for
  this specific prop -- not traced.
- The exact selection logic for `DAT_0051dac0`'s table walk (simple
  wraparound increment, confirmed; whether the table's uneven 7/3/1/2
  weighting is deliberate "mostly A, rarely C" design or an authoring
  artifact -- not determined).

## Pass 45 -- the briefing-hub "news report" TV, and tracing the path to mission briefing (2026-09-09)

Direct continuation of "work on the rest of the VR engine all the way
to mission briefing." `RunShipInteriorVRLoop`'s `roomType == 7`
transition (Pass 5/33: the briefing-hub door) calls a previously
unexamined function -- `RunBriefingHubNewsReport` (was `FUN_0043ba40`)
-- BEFORE settling into the briefing-hub room's own ambient video. This
is a genuine, newly-found step in the VR-to-briefing pipeline.

### `RunBriefingHubNewsReport` (`0x43ba40`, was `FUN_0043ba40`)

A blocking, self-contained mini-scene: plays a **mission-indexed news
broadcast** on what is presumably an in-room TV/monitor, confirmed via
its own error strings (`"news_report_resource: error searching %s"`)
and literal filenames (`"rel_tv_in_loop.bik"`, `"b_tv_news_.bik"`,
`"tv_cald_.bik"`). Builds the actual clip name from a ~27-28-entry
stack table of short numeric strings (`"0005a"`, `"0015"`, `"0025"`,
... up to `"0275"`, read directly from `0x4e90d0`-`0x4e91a8`), indexed
by the current mission number (`DAT_00562dc8`) via
`"%s_box.bik"`-style formatting (`s__s_box_004e8d90`) -- i.e. **a
different news clip plays depending on which mission you're heading
into**, giving in-universe news updates that track campaign progress.

For mission 1 specifically, the function runs a distinct 3-state cycle
(`local_a8`: 0=idle-loop TV, 1=a "calendar/date" interstitial clip
`tv_cald_.bik`, 2=back to idle loop) rather than the simple
play-once-then-exit-on-click behavior every other mission gets. The
whole thing is blocking -- the calling `RunShipInteriorVRLoop` does not
proceed to the briefing-hub room's own steady-state video (`tv2brd.bik`,
Pass 5) until the player dismisses this news report (Esc, mouse click,
or movement).

**Confidence 4** on the mechanism and mission-indexing (directly read);
**confidence 1** on the exact string-to-mission-number mapping
direction (the stack-frame layout makes this genuinely ambiguous
without deeper analysis -- not resolved this session).

### Tracing the actual trigger for `RunMissionBriefingScreen`

Confirmed via `get_xrefs_to` that `RunShipInteriorVRLoop` never writes
`DAT_0051dac4` (the menu-screen-ID selector `RunMenuScreenLoop` reads)
anywhere -- so simply walking through the VR ship interior's roomType-7
door does NOT, by itself, launch the briefing screen. `RunMission
BriefingScreen`'s callers are `RunMenuScreenLoop` (screen ID 7, as
already known) AND, importantly, **`WinMain` directly**, at two call
sites (`0x4aa027`, `0x4aa6f2`). Investigating exactly what state in
`WinMain`'s top-level loop gates those two direct calls -- the real
missing link between "player reaches the mission-select star map" and
"the briefing screen actually launches" -- is in progress (forked to
avoid pulling `WinMain`'s ~7.6KB decompile into this session's own
context; `WinMain` is the single largest, most central function in the
game and this is the first time this project has looked at the exact
mechanics of its top-level dispatch rather than just individual state
writes within it).

### Open follow-ups

- The WinMain-level trigger investigation (forked, pending).
- The exact mission-number-to-news-clip-string mapping direction.
- Whether the mission-1-specific 3-state news cycle has special
  narrative significance (a scripted "first mission" intro sequence
  seems likely, not confirmed).

## Pass 46 -- THE MISSING LINK FOUND: roomType 1 leads to mission briefing, not the main menu (2026-09-09)

Direct capstone to "work on the rest of the VR engine all the way to
mission briefing." Applied the same `set_function_prototype` technique
(Passes 34/35/37) to `RunMenuScreenLoop` itself and re-decompiled
`RunShipInteriorVRLoop` -- this immediately exposed every hidden
starting-screen-ID argument at every call site project-wide, and one
of them resolves the exact question this whole investigation was
chasing.

### The finding

```c
else if (sVar3 == 1) {
    ...cleanup, free resources...
    RunMenuScreenLoop(7);   // <-- LITERAL ARGUMENT: 7 = RunMissionBriefingScreen
    if (DAT_0051d4b4 == 0) goto LAB_0043b957;      // -> exit the VR loop entirely
    if (DAT_0051d4b4 == 2) { ...; goto LAB_0043b94f; }  // -> also exits, different flag
    // otherwise (DAT_0051d4b4 == 1): reload resources, reopen the VR
    // interior fresh at the BUNKROOM entry hub (VRRoomNode_0050b2b8/
    // _00506ad0) -- i.e. "loadout confirmed, launching"
}
```

**Correction to Passes 4/5, not silent**: both earlier passes described
`roomType == 1` doors as "exit to front-end menu," inferred purely from
the fact that the code called `RunMenuScreenLoop()` with no visible
argument (the hidden-fastcall-argument problem, unresolved at the
time). **The actual call passes `7`, meaning every `roomType == 1`
"exit" door in the ship interior sends the player directly into
`RunMissionBriefingScreen`, not the main menu.** This makes complete
narrative sense in hindsight: `roomType == 1` doors are how the player
RE-ENTERS the loadout/briefing screen from within the ship (e.g. to
review or change their loadout before actually launching), not how
they quit to the title screen.

This closes the full loop documented across Passes 4, 5, 33, 43, and
45: `RunMissionBriefingScreen`'s own ending hands off into
`RunShipInteriorVRLoop` (Pass 43), and `RunShipInteriorVRLoop`'s
`roomType == 1` doors hand control straight back into
`RunMissionBriefingScreen` (this pass) -- the two systems form a
closed cycle: loadout/briefing <-> ship interior, with the player able
to move between them freely until they confirm their loadout
(`DAT_0051d4b4 == 1`) and launch, or cancel out entirely
(`DAT_0051d4b4 == 0` or `2`, both of which unwind out of the VR loop
and, per `RunMissionBriefingScreen`'s own Pass-43-documented behavior,
ultimately return toward the main menu / mission outcome flow).

### `WinMain`'s two direct `RunMissionBriefingScreen` calls: resolved (background investigation)

A background investigation (forked separately) confirmed both of
`WinMain`'s direct calls into `RunMissionBriefingScreen` (`0x4aa027`,
`0x4aa6f2`) are **mission-29-epilogue-only short-circuits** -- each is
gated on `DAT_00562dc8 == 0x1d`, calling `RunMissionBriefingScreen()`
(which per Pass 43 loads `enddebriefing.ut` for this special case)
followed by an ending-variant cutscene/credits function
(`FUN_004ac620`, branching on campaign-performance flags
`DAT_0052a410`/`DAT_0052a40c`/`DAT_0052a424`) and then resetting
`DAT_00562dc8 = 1` to loop the campaign back to mission 1. **For every
normal mission, `WinMain` does NOT call `RunMissionBriefingScreen`
directly at all** -- the only path is via `RunMenuScreenLoop(7)`, and
this pass has now confirmed the one call site inside the VR loop that
actually reaches it during normal gameplay.

### `RunMissionSelectMapScreen`, re-examined: does NOT route through briefing

Fully decompiled (previously only summarized in Pass 7). Confirms it
launches gameplay **directly**: `InitializeMissionGameplay(); Run
MissionGameplay(); UnloadMission();`, with no call to
`RunMissionBriefingScreen` or write to `DAT_0051dac4` anywhere. This
means the star-map screen (reached via the VR loop's `roomType == 5`
"pod bay" hub, per Pass 7) is a genuinely separate, LATER step from
loadout/briefing in the overall flow -- the player briefs and loads out
first (via the `roomType == 7` hub and its `roomType == 1`
return-loop, this pass), then separately visits the star map to pick
between a small number of mission-variant branches
(`mission30`/`31`/`32`, plus a `mission29` epilogue option) and launch
directly into gameplay.

### The complete, closed-loop picture

```
[VR ship interior]
  roomType==7 door -> RunBriefingHubNewsReport (Pass 45) -> briefing-hub room (tv2brd.bik)
  roomType==1 door (within/near the hub) -> RunMenuScreenLoop(7) -> RunMissionBriefingScreen
     -> loadout setup, briefing video, interactive loadout, closing speech (Pass 43)
     -> confirm (DAT_0051d4b4==1): reopen VR interior fresh at the bunkroom entry hub
     -> decline/cancel (DAT_0051d4b4==0 or 2): unwind out toward the main menu
  roomType==5 door -> RunMissionSelectMapScreen -> pick mission30/31/32/29 -> InitializeMissionGameplay
     -> RunMissionGameplay -> UnloadMission (gameplay itself, documented in earlier sessions)
```

### Confidence

**Confidence 5** on the `RunMenuScreenLoop(7)` finding -- a literal,
unambiguous decompiled argument value, not an inference. **Confidence
4** on the overall closed-loop picture and the WinMain/mission-29
resolution (both directly read, cross-referencing multiple passes'
prior work). **Confidence 3** on the precise meaning of `DAT_0051d4b4`
values 0 vs. 2 (both "exit," but the exact narrative distinction
between them -- e.g. "declined to fly" vs. some other cancel path --
not fully disambiguated this session).

### Open follow-ups

- Exact disambiguation of `DAT_0051d4b4` values 0 vs. 2.
- Whether OTHER `RunMenuScreenLoop(N)` call sites elsewhere in the
  codebase (now trivially discoverable via the same exposed-argument
  technique) reveal further previously-mislabeled transitions --
  worth a systematic sweep if this thread continues.
- `FUN_004ac620` (the mission-29 ending-variant cutscene/credits
  function) -- not decompiled.

## Pass 47 -- Menu asset position data decoded: the mission-select star map's hotspot table (2026-09-09)

Direct request: decode the "asset position data" underlying the menu
system's UI layout. Rather than the huge per-function local stack
tables noted structurally in Pass 6 (each menu screen builds its own
one-off pixel-position locals), picked the one GLOBAL, reusable,
data-segment-resident position table found so far:
`RunMissionSelectMapScreen`'s hotspot-rectangle table
(`DAT_004ebb38`/`PTR_DAT_004ebb3c`, Pass 46), and read it directly out
of the shipped binary's static image.

### `MenuHotspotRect` -- confirmed, real struct (created in Ghidra, applied to live data)

```c
struct MenuHotspotRect {
    int16_t x, y, w, h;   // screen-space clickable rectangle, 8 bytes
};
```

Confirmed by directly reading and cross-checking two independent
per-state rectangle arrays (see below) against
`RunMissionSelectMapScreen`'s own hit-test code (`*psVar3 < mouseX <
*psVar3+psVar3[2]`, `psVar3[1] < mouseY < psVar3[1]+psVar3[3]`) --
exact match, confidence 5.

### The per-state record (`MapScreenState`, structurally confirmed)

```c
struct MapScreenState {          // stride 0x58 (88) bytes, confirmed via two
    int16_t hotspotCount;        // +0x00 -- states 0 and 1 read as 3 and 5 respectively
    // +0x02: 2 bytes unaccounted (padding, or high bits of a wider count field)
    MenuHotspotRect *rects;      // +0x04 -- pointer to this state's rect array
    // +0x08 onward: further per-state fields, not fully mapped this session
};
```

Two states read directly and verified self-consistent (declared
`hotspotCount` matches the number of real, sane rects at the pointed-to
array; the SECOND state's record starts exactly `0x58` bytes after the
first, confirming the stride independently):

- **State 0** (3 hotspots, `0x4ebaf8`): `{265,164,111,111}`,
  `{265,328,111,111}`, `{546,18,80,80}` -- two stacked large
  (111x111px) buttons in a left column plus one small (80x80px) button
  off to the right.
- **State 1** (5 hotspots, `0x4ebb10`): `{100,164,111,111}`,
  `{265,164,111,111}`, `{265,328,111,111}`, `{546,18,80,80}`,
  `{546,114,80,80}` -- a superset of state 0, adding a third large
  button in the same row (`x=100`) and a second small button stacked
  directly below the first (`y=114` vs `y=18`, same 80x80 size).

This matches `RunMissionSelectMapScreen`'s own logic precisely: state 0
offers the normal 3-mission choice (`mission30`/`31`/`32`, drawn as the
two-large-plus-one-small layout), and state 1 -- reached via a specific
hotspot transition -- adds a 3rd large mission-choice button (very
likely the `mission29` epilogue option, given Pass 43/46's established
role for mission 29) plus a second small button (plausibly a
confirm/cancel pair, given the two small buttons are visually stacked
and identically sized).

### The transition table (`0x4ebb60`, structurally located, not fully decoded)

Confirmed as a SEPARATE table (not part of `MapScreenState`) read by
`RunMissionSelectMapScreen` as `*(int *)((clickedHotspotIndex +
currentState * 0x16) * 4 + 0x4ebb60)` -- a `[state][hotspotIndex] ->
nextState` lookup, `0x16` (22) dwords per state. Real values read
(`1,5,1,0,0,...,1,1,2,1,4,1,...`) are small, sane state-index-shaped
numbers consistent with this role, but the full table wasn't mapped
entry-by-entry this session.

### Applied to the live Ghidra project

Created `MenuHotspotRect` as a real struct type and applied
`MenuHotspotRect[3]` at `0x4ebaf8` (state 0's array). State 1's array
(`0x4ebb10`) and the outer `MapScreenState` records were read and
verified but not struct-typed in Ghidra this session (the record's
tail fields past `+0x08` aren't understood well enough yet to commit a
full struct definition).

### Confidence

**Confidence 5** on `MenuHotspotRect`'s 4-field layout (directly
matches the hit-test code, byte-exact). **Confidence 4** on
`MapScreenState`'s first 8 bytes (count + rect-array pointer, confirmed
via two independently cross-checked states with matching stride).
**Confidence 2** on the specific "3rd button = mission29,
small-button-pair = confirm/cancel" interpretation of state 1's extra
hotspots (a reasonable inference from position/size and Pass 43/46's
established mission-29 role, not independently confirmed).

### Open follow-ups

- `MapScreenState`'s fields beyond `+0x08` (each record is 88 bytes;
  only the first 8 are understood) -- likely holds per-hotspot
  metadata (action codes, sound cues, or similar) given the extra
  small-int values seen in the raw reads (`4,5,7,...,1,1,2,1,4,1`).
- The transition table at `0x4ebb60` -- located and structurally
  characterized but not mapped entry-by-entry.
- State 5 (the third state value seen in `RunMissionSelectMapScreen`'s
  code, `DAT_00524fdc == 5`) -- not read.
- This is only ONE of many per-screen position tables across the 12
  menu screens (Pass 6) -- most others use one-off stack-local tables
  rather than a reusable global struct array, making this particular
  table an atypically clean target; the others would need per-screen
  investigation if this thread continues.

## Pass 48 -- Hotspot layouts documented for all 12 menu screens (2026-09-09)

Direct request: document the clickable hotspot position data for every
`RunMenuScreenLoop`-dispatched screen. Combined direct investigation
with 4 parallel forks (each covering 2-3 screens) to cover all 11
remaining screens beyond Pass 47's `RunMissionSelectMapScreen`.

### Key infrastructure finding: `HitTestRectArray` (`0x43eb30`, was `FUN_0043eb30`)

```c
int __fastcall HitTestRectArray(void *rectArray, int rectCount, int mouseX, int mouseY);
```

A generic, shared hit-test utility used by roughly half the menu
screens: walks an array of `{x,y,w,h}` `int16` rects (identical layout
to Pass 47's `MenuHotspotRect`) and returns the index of the one
containing `(mouseX,mouseY)`, or -1. Every prior sighting showed only
`FUN_0043eb30(mouseX, mouseY)` because its `rectArray`/`rectCount`
arguments are passed via hidden `__fastcall` registers -- applying
`set_function_prototype` to it (the same technique from Passes 34/35/37)
retroactively exposed the real array pointer and count at EVERY call
site project-wide in one step, turning "opaque hotspot index" callers
into fully-readable position tables. **This is now the single most
useful technique for any further menu/UI archaeology in this project.**
Some screens (`RunMainMenuScreen`) use their own inline hit-test loop
against a differently-shaped table instead of this shared utility.

### Screen 0 -- `RunMainMenuScreen` (`0x428b60`)

Inline hit-test against global table `DAT_004e5b90`, stride 12 bytes
(`{x,y,w,h,target,extra}` int16), 5 entries:

| x | y | w | h |
|---|---|---|---|
| 27 | 123 | 184 | 290 |
| 203 | 125 | 184 | 290 |
| 421 | 165 | 184 | 290 |
| 332 | 441 | 20 | 15 |
| 300 | 441 | 20 | 15 |

Three large ~184x290 tiles (New Game / Multiplayer / Options) plus two
small nav buttons at the bottom. **Confidence 5** -- target-field
attribution resolved in Pass 51 (see below): index 0/1/2 = New
Game/Multiplayer/Options, index 4 = hidden "watch ending" mission-29
trigger, index 3 = not wired to the action switch at all.

### Screen 1 -- `RunOptionsMenuScreen` (`0x42a620`)

6-entry stack-local table via `HitTestRectArray`:

| idx | x | y | w | h | Action |
|---|---|---|---|---|---|
| 0 | 30 | 165 | 152 | 127 | -> screen 3 (Sound Options) |
| 1 | 219 | 165 | 152 | 127 | -> screen 16 (Controls Options) |
| 2 | 408 | 165 | 152 | 127 | -> screen 15 (Video Options) |
| 3 | 292 | 441 | 25 | 16 | Exit -> main menu |
| 4 | 324 | 441 | 25 | 16 | Confirm-quit dialog |
| 5 | 292 | 421 | 25 | 16 | Unidentified helper (`FUN_0042a520`) |

**Confidence 5** -- directly and unambiguously read, including exact
switch-case destinations. Clean row of 3 large category tiles
(152x127) plus 3 small buttons.

### Screen 3 -- `RunSoundOptionsScreen` (`0x42dab0`)

Two contiguous global arrays, confirmed via `HitTestRectArray(&DAT_004e76a0,
6,...)` and `HitTestRectArray(&DAT_004e76d0, 4,...)` (the second is
literally `DAT_004e76a0`'s 6th entry onward -- one 10-entry table read
as two logical groups):

**Buttons** (`DAT_004e76a0`, 6 entries, all 25x16 or 19x26):

| x | y | w | h | Action |
|---|---|---|---|---|
| 324 | 421 | 25 | 16 | Apply (save all volume settings to ini) |
| 292 | 421 | 25 | 16 | Exit, keep changes |
| 292 | 441 | 25 | 16 | Exit to main menu |
| 300 | 369 | 19 | 26 | Cycle 3D audio provider back |
| 322 | 369 | 19 | 26 | Cycle 3D audio provider forward |
| 324 | 441 | 25 | 16 | Cancel (revert sliders) |

**Volume sliders** (`DAT_004e76d0`, 4 entries, each also doubles as the
LIVE draggable-handle X position, clamped to `[313,488]` -- the static
image shows all 4 at their leftmost/minimum default): all `w=15,
h=27`, y positions **Speech=126, FX=186, Music=246, Master=306** (a
clean 60px-pitch vertical list). **Confidence 5** -- directly read,
cross-confirmed against the slider-drag clamp code and the
`WritePrivateProfileStringA` ini-key sequence identifying which
slider is which.

### Screen 8 -- `RunNetworkDisconnectScreen` (`0x43ca30`, pre-existing name)

Not a real UI screen: `Sleep(1000); FUN_004abde0(); return 3;` -- zero
hotspots, a non-interactive pass-through shown briefly during
multiplayer disconnect cleanup.

### Screens 10/11 -- `RunSaveLoadScreen` (`0x43ca50`)

Local stack tables, save-vs-load mode via `DAT_0051d54c`. **Confidence
5** -- full index-to-rect mapping resolved in Pass 51 (see below); the
two mode-specific windows turned out to be adjacent slices of one
19-record contiguous table.

*Save mode*: 0=select target, 1=confirm delete/overwrite, 2=quick-save,
3=open Save Browser (screen 13), 4/7=cancel, 5=exit to screen 0xe,
6=options dialog, 8=pick list item, 9-12=scroll/select slot.

*Load mode*: 0=start select, 1=confirm load, 2=exit to screen 0xe,
3=options dialog, 4=exit to main menu.

### Screen 12 -- `RunNewGameSetupScreen` (`0x430490`)

Two tables via `HitTestRectArray`: an 8-entry main button row
(`&stack0xffffff5c`, matching the 8 switch cases already documented in
Pass 46 -- **pilot gender male/female** (corrected in Pass 62; was
mislabeled "difficulty A/B" here), load-existing-pilot,
confirm-new-pilot, exit, reset, options-dialog, toggle-name-list) whose
raw coordinates
weren't cleanly extractable from the decompile's stack-offset notation
this pass, and a **10-entry name/callsign-picker list**
(`&local_64`, only shown when `DAT_005202b8` is toggled on), read
directly:

| entry | x | y(or h) | w(or w) | h(or y) |
|---|---|---|---|---|
| 0 | 138 | 45 | 324 | 441 |
| 1 | 60 | 16 | 543 | 200 |
| 2 | 27 | 15 | 400 | 223 |
| 3-9 | 136 | 20 | 400 | 248,273,298,323,348,373,398 |

Entries 3-9 form a clean 7-row list, 25px pitch, 400x20 each --
almost certainly the visible rows of a scrollable pilot-name/callsign
preset list (selection copies from a 50-byte-stride name array at
`DAT_005d5e8c`); entry 2's `(27,15,400,223)` is plausibly the list's
background panel. **Confidence 4** on the raw values, **confidence 2**
on the exact field-order interpretation (the `{x,h,w,y}`-shaped pattern
in entries 3-9 is inferred from the arithmetic progression, not
independently confirmed against a draw call).

### Screen 13 -- `RunSaveGameBrowserScreen` (`0x431730`)

**Confidence 5** -- fully resolved in Pass 51 (see below). Save-slot
list (10 rows): `x=49, w=400, h=17`, `y = 126 + 17*i` for `i=0..9`
(126,143,...,279 -- exact 17px pitch; corrects an earlier x/h field
transposition). Scroll arrows: up `(579,250,26,16)`, down
`(579,268,26,16)` (also keyboard-bound, scancode `0xd0`=Down,
`200`=Up). Action buttons (indices 10-13): Back, Confirm, Exit-to-main-
menu, Options -- corrects the earlier "back/confirm/cancel/delete"
guess (there is no delete hotspot in this set).

### Screen 14 -- `RunMultiplayerSetupScreen` (`0x432fc0`)

**Confidence 5, fully resolved in Pass 52** (see below) -- the "~30
chained pointer-aliases" turned out to be one 38-record contiguous
stack table with 5 different `HitTestRectArray` windows into it (main
row + session list, connecting/status panel, host-setup dialog,
difficulty/options row, join-session dialog), same pattern as
`RunSaveLoadScreen` (Pass 51). Actions: 0=Direct Connect/Play,
1=**Zone.com** (confirms Pass 6's `ShellExecuteA` finding), 2=Join,
3=Host(mode A), 4=Host(direct), 5=Host Co-op, 6=Exit, 7=Options
dialog (corrects the earlier "Cancel-confirm" guess for index 7).

### Screen 15 -- `RunVideoOptionsScreen` (`0x42e9b0`)

Clean 17-entry global array, `DAT_004e76f0`, via `HitTestRectArray`
(confidence 5, literal data):

| idx | x | y | w | h | Action |
|---|---|---|---|---|---|
| 0/1 | 301/318 | 128 | 12 | 23 | Mode index -/+ |
| 2/3 | 301/318 | 165 | 12 | 23 | Device index -/+ |
| 4/5 | 301/318 | 202 | 12 | 23 | Window mode toggle -/+ |
| 6/7 | 301/318 | 239 | 12 | 23 | Detail level -/+ |
| 8/9 | 301/318 | 276 | 12 | 23 | 3D provider -/+ |
| 10 | 324 | 421 | 25 | 16 | Reset to defaults |
| 12 | 311 | 353 | 16 | 16 | Checkbox (unclear semantic) |
| 13/14 | 292 | 421/441 | 25 | 16 | OK/Apply |
| 15 | 311 | 390 | 16 | 16 | "Transitions" checkbox (confirmed via ini key) |
| 16 | 324 | 441 | 25 | 16 | (paired with 10/13/14 button cluster) |

Rows 0-9 form 5 clean `<`/`>` arrow pairs (identical x=301/318 for
every setting row) -- a textbook "5 adjustable settings" layout.
**Separately**, a 1-entry gamma-slider-handle array,
`DAT_004e7778 = {347,314,15,27}`, independently cross-confirmed: the
function's own live gamma-to-pixel formula
(`(gamma-0.5)*116.666664 + 347.0`) reproduces the static rect's `x=347`
exactly.

### Screen 16 -- `RunControlsOptionsScreen` (`0x42b690`)

Confirms and extends Pass 37's finding of a giant stack-local layout
table -- real coordinates extracted (confidence 5 on raw values,
3-4 on UI-element attribution):

**3 checkboxes** (ForceFeedback/JoystickInvert/HatEnable): all
`x=345, w=16, h=16`, `y=325,349,373` (24px pitch).

**Key-rebind scrollable list**: two visually-contiguous blocks, both
`x=50, w=550, h=10`: `y=139,154,169,184,199,214,229,244` (8 rows) then
`y=259,274,289,304` (4 more rows, likely revealed-on-scroll) -- 15px
pitch throughout, 12 visible rows total matching `DAT_004e5cd0`'s
scancode-candidate table (Pass 37) and the `ControlBinding` array
(Pass 38/47).

**Scroll arrows**: small 16x16 icons, offset ~45px horizontally from
the list.

### Screens 0x11/0x12 -- `RunMultiplayerLobbyScreen` (`0x44b950`)

**Player-roster row layout** (confidence 5): source records at
`DAT_005db8f4`, stride 0xfc (252) bytes/player; UI row array at
`DAT_00524aa0`, stride 0x2a (42) bytes/row (40-byte name buffer + a
2-byte computed field, plausibly ping or ready-icon index). Loop bound
`DAT_005db83c` (live player count).

**Confidence 5, fully resolved in Pass 52** (see below): a 3-entry
exit cluster plus one 40-entry (`0x28`) main table covering Ready/
Start, Cancel/Back, page-scroll, the host-mode mission-select list (6
rows), 8 player-roster slot toggles, two dropdown/expand toggles with
their item lists, and a second 12-row list. Language-string indices
(`0x59f`x2, `0x59b`, `0x592`, `0x5a3`x2, `0x59a`, `0x5a0`, `0x5a1`,
`0x598`, real `GetLanguageString` indices per Pass 37) still point at
runtime-only label text, per Pass 37/48. One small 3-entry checkbox
row (host-mode ready/mute toggles) remains unresolved -- its stack
slot was reused for SEH bookkeeping and carries no literal
assignments in the decompile, the same class of gap documented in
Pass 50.

### Consolidated confidence note

Every coordinate reported above with "confidence 5" was read directly
from the shipped binary's static `.data` image via `read_memory` or an
unambiguous decompiled literal -- not inferred. Screens/tables marked
lower confidence had their raw values read correctly but their
index-to-widget or field-order attribution required interpretation the
investigating agent flagged as uncertain rather than asserting as fact,
consistent with METHODOLOGY's confidence discipline.

### Open follow-ups

- `RunMainMenuScreen`'s target-field attribution (which large tile maps
  to which of the 3 large-rect entries).
- `RunSaveLoadScreen`/`RunSaveGameBrowserScreen`'s action-button
  coordinates (actions confirmed, positions not).
- `RunNewGameSetupScreen`'s 8-entry main button row's raw coordinates.
- `RunMultiplayerSetupScreen`'s ~30-pointer-alias layout -- a full
  mapping would need substantially more dedicated effort.
- `RunMultiplayerLobbyScreen`'s remaining unattributed rects and the
  exact button-label text (blocked on the runtime-only string table,
  per Pass 37).

## Pass 49 -- `RunNewGameSetupScreen`'s 8-entry button row: partial resolution, honestly incomplete (2026-09-09)

Direct follow-up on Pass 48's open item. Traced the raw disassembly
leading up to the `HitTestRectArray(&stack0xffffff5c, 8, ...)` call
(`0x430810`) using `get_assembly_context`, since the decompiler never
surfaced the setup as named-local assignments the way it did for the
10-entry name-picker list (Pass 48).

### What was found

`FUN_00430b80` (called immediately before each hit-test in the loop)
is **not** the array-builder -- decompiled it and it's actually a
"recent pilot names" list-maintenance routine (checks the typed name
against 10 existing slots at `DAT_005d5e8c`, shifts/appends as needed).
A dead end for this specific question, but now independently
characterized.

The real setup happens **once, before the main loop**, as a long
sequence of `MOV word ptr [ESP+N], <value>` instructions starting
right after the function's `SUB ESP,0x98` prologue. Critically, four
`PUSH` instructions (`EBX`, `EBP`, `ESI`, `EDI`) occur partway through
this sequence, each shifting the effective `ESP+N` addressing for
every instruction that follows -- meaning naive address-order reading
without accounting for the cumulative 16-byte push offset produces
wrong offset correlations. Re-derived the sequence correctly by
identifying the exact push points and adjusting.

**Confirmed, confidence 4**: the array's first entry (immediately at
`ESP+0x20`, matching the `LEA ECX,[ESP+0x20]` argument to
`HitTestRectArray`) is `{0xef, 0x97, 0x66, 0x113}` = **(239, 151, 102,
275)**.

**Confirmed, confidence 4**: several of the values written into this
region are not compile-time literals at all but **cached register
copies** of values loaded once and reused across multiple slots --
specifically `136` (`ECX`), `20` (`EAX`), `400` (`EDX`), and `441`
(`ESI`), loaded via `MOV ECX,0x88` / `MOV EAX,0x14` / `MOV EDX,0x190`
/ `MOV ESI,0x1b9` around `0x4304cb`-`0x4304da`. These are the EXACT
same three values (`136,20,400`) that recur throughout Pass 48's
already-documented 10-entry name-picker list (`local_64`, entries
3-9). **This strongly suggests the "8-entry button row" and "10-entry
name list" are not two independent tables, but two overlapping VIEWS
into one larger, contiguous stack-allocated layout block**, built in a
single upfront initialization pass and handed to `HitTestRectArray`
with different base pointers/counts depending on which UI mode
(`DAT_005202b8`) is active.

### What was NOT resolved, and why

A complete, entry-by-entry table for all 8 slots was **not** achieved.
Several expected slot positions (e.g. `ESP+0x28`, `ESP+0x30`) show no
corresponding literal or register write in the captured instruction
window, which could mean: (a) my `include_patterns="mov"` filter missed
a non-MOV clearing instruction (e.g. `XOR reg,reg` followed by a
narrower write), (b) the true per-entry stride isn't a uniform 8 bytes
throughout this region, or (c) the capture window, while large (180
instructions), still didn't reach every relevant instruction. Rather
than fill these gaps with guesses, this is reported as an honest,
acknowledged limitation. **Confidence 1** on any claim about entries
1-7's exact values -- not asserted.

This is a good candidate for a proper P-code-based analysis
(`get_function_pcode`) rather than further manual disassembly reading,
if pursued again.

### Open follow-ups (superseded -- see Pass 50 below)

- Entries 1-7 of the 8-entry button row -- genuinely unresolved.
- Verify the "one contiguous layout block, two views" hypothesis by
  checking whether `RunSaveGameBrowserScreen`/`RunSaveLoadScreen`
  (Pass 48's other coordinate-incomplete screens) show the same
  push-instruction-count pitfall that blocked clean extraction here --
  if so, the same careful ESP-tracking approach (successful for entry
  0 here) could unlock them too, ideally with p-code analysis instead
  of manual reading.

## Pass 50 -- Correction to Pass 49: the "entry 0 = (239,151,102,275)"
claim and the "contiguous two-view" hypothesis are WRONG; root cause of
the blocker identified via raw P-code (2026-09-09)

**Explicit correction, per methodology's non-silent-revision rule.**
Pass 49's confidence-4 claims are retracted:

- The claimed 8-entry-array first value `(239, 151, 102, 275)` --
  **wrong**, downgraded to confidence 0 (not asserted at all). The
  manual ESP-offset bookkeeping that produced it did not correctly
  account for cumulative push/pop effects, exactly the risk Pass 49
  itself flagged but did not fully resolve.
- The "one contiguous stack block, two overlapping views" hypothesis
  -- **wrong**, contradicted by direct evidence below.

### Method: raw P-code cross-check

Pulled `get_function_pcode` (basic granularity) for `RunNewGameSetupScreen`
and parsed it directly (the raw JSON is ~3.4MB, far too large for
context, so it was saved to disk and processed with a local Python
script rather than read directly). P-code's `stack` address space gives
canonical, push/pop-normalized frame offsets, which sidesteps the
manual ESP-tracking error mode entirely -- this is a strictly stronger
method than reading raw disassembly by hand, and should be preferred
for any future stack-layout archaeology in this codebase.

**Verification of the method**: the confirmed 10-entry table call
(`HitTestRectArray` at `0x430896`, `rectCount=10`) computes its
`rectArray` pointer via `PTRSUB(ESP, -0x64)` = canonical stack offset
**-100**, which exactly matches the independently-confirmed
`local_64` / literal `0x8a` finding from Pass 48. This cross-check
**passes** -- the method is sound and the -100 array is correctly
understood.

**The 8-entry table call** (`HitTestRectArray` at `0x430810`,
`rectCount=8`) computes its `rectArray` pointer via `PTRSUB(ESP,
-0xa4)` = canonical stack offset **-164**. This is where Pass 49's
"contiguous block" hypothesis came from (164 - 100 = 64 = exactly 8
rects x 8 bytes). But:

1. **No instruction anywhere in the function's entire control-flow
   path leading to `0x430810` writes to any stack offset in the range
   -164..-102.** Exhaustively checked every basic block from the
   function entry through the call site for `COPY`/`STORE` pcode ops
   targeting that range -- zero hits. Only conservative `INDIRECT`
   call-clobber markers touch it, which are not real writes.
2. `get_function_variables` confirms this independently: Ghidra's own
   decompiler creates local-variable symbols only down to `local_90`
   (canonical offset -144, magnitude 0x90) -- it never creates a
   symbol at or beyond -164. The declared frame (`SUB ESP,0x98` = 152
   bytes) doesn't even reach that deep; -164 falls in or past the
   region MSVC uses for the 4 callee-saved-register spill slots
   (`PUSH EBX/EBP/ESI/EDI`), not the declared-locals region.
3. The one candidate write source considered -- `CALL FUN_004aada0`,
   which immediately precedes the setup's tail and was hypothesized as
   a "fill the array by reference" helper -- decompiles to a two-line
   function (`DAT_00595d70 = 0; return;`) that takes **no arguments at
   all**. Ruled out directly, confidence 5.

**Diagnosis (confidence 3)**: the `PTRSUB(ESP, -0xa4)` at `0x43080c`
appears to be a case where Ghidra's decompiler **failed to resolve
this specific LEA into the canonical, normalized stack frame** the way
it successfully did for the `-100` case just 0x86 bytes later in the
same function. Ghidra's stack-pointer tracking is a best-effort
dataflow analysis, not a proof; it can lose precision across complex
control flow (this function has several `CALLIND` indirect calls
through vtable-style global pointers in the setup path, which are
plausible precision-loss triggers). When that tracking fails, the
`PTRSUB` constant it emits reflects an unresolved/best-guess offset
rather than the true frame-relative location, which is consistent with
this offset having no matching writes anywhere -- the writes exist at
runtime, but at whatever the TRUE (unrecovered) offset is, not at the
literal -164 the decompiler printed.

### Conclusion

The 8-entry main-button-row coordinate table for `RunNewGameSetupScreen`
remains **unresolved** -- now with a concrete, evidence-backed root
cause (a decompiler stack-tracking precision failure on this one
`PTRSUB`, not a methodology error on our part) rather than an open
question. No values are asserted for any of the 8 entries; the
Pass 49 entry-0 guess is withdrawn. Recovering the true values would
require either: reading the compiled bytes directly against a live
memory dump/debugger (dynamic method, not available here), or manually
re-deriving the true runtime ESP delta at `0x43080c` instruction-by-
instruction from the prologue (the exact painstaking approach Pass 49
attempted and got wrong once already) with extreme care re-verified
against a second, independent cross-check.

### Open follow-ups

- The 8-entry button row's coordinates: unresolved, root-caused, not
  further pursued this pass.
- Before trusting a `PTRSUB`-derived stack offset for any future
  screen's hotspot archaeology, cross-check it the way this pass did
  (find a second, nearby stack access at a compile-time-literal offset
  and confirm the P-code offset matches an actual observed write) --
  don't assume `PTRSUB`'s constant is trustworthy on its own.

## Pass 51 -- `RunMainMenuScreen` target-field attribution + `RunSaveLoadScreen`/`RunSaveGameBrowserScreen` action-button coordinates (2026-09-09)

Direct follow-up on Pass 48's three remaining open items (skipping the
`RunNewGameSetupScreen` 8-entry row, already root-caused as
unresolvable in Pass 50, and the `RunMultiplayerSetupScreen`/
`RunMultiplayerLobbyScreen` items, not requested this pass).

### `RunMainMenuScreen` (`0x428b60`) -- target-field attribution resolved, confidence 5

Full decompile of the inline hit-test loop resolves this cleanly --
no ambiguity remained once the whole function (not just the hit-test
snippet) was read. Direct memory read of `DAT_004e5b90`'s 5 x 6-`int16`
records:

| idx | x | y | w | h | target | extra | Action |
|---|---|---|---|---|---|---|---|
| 0 | 27 | 123 | 184 | 290 | 0 | 18 | New Game (`DAT_0051dac4=0xc` -> `RunNewGameSetupScreen`) |
| 1 | 203 | 125 | 184 | 290 | 0 | 19 | Multiplayer (`DAT_0051dac4=0xe` -> `RunMultiplayerSetupScreen`) |
| 2 | 421 | 165 | 184 | 290 | 0 | 20 | Options (`DAT_0051dac4=1` -> `RunOptionsMenuScreen`) |
| 3 | 332 | 441 | 20 | 15 | 3 | 24 | Not wired to the switch (see below) |
| 4 | 300 | 441 | 20 | 15 | 0 | 24 | Falls to the `else` branch -- directly loads and runs mission `0x1d` (29) as a full gameplay session, then unloads |

The `target` field turns out **not** to be a destination ID at all --
it's a **loop-continue gate**: the per-frame hit-test loop only
`break`s (handing off to the post-loop action switch) when the clicked
entry's `target != 3`. Every entry except index 3 has `target=0` and
breaks immediately; index 3 (`target=3`) does not, so its click is
absorbed by the frame loop without reaching the switch at all --
consistent with it being a non-interactive/decorative element (its
exact role, e.g. a hover-highlight-only region, is not further
resolved -- confidence 1 on that specific interpretation, confidence 5
on the mechanism itself). The action switch itself dispatches purely
on `DAT_0051d544` (the matched hotspot **index**, not the target
field): `==0`/`==1`/`==2` go to the three documented screens; anything
else (only reachable via index 4, since index 3 never breaks the loop)
falls through to a direct `DAT_00562dc8=0x1d; DAT_0057e044=1;
InitializeMissionGameplay(); RunMissionGameplay(); UnloadMission();`
sequence -- the exact same mission-29/epilogue pattern documented
earlier for the campaign's final debriefing (`enddebriefing.ut`).
**Confidence 4**: index 4 (the small button at `x=300`) is very likely
a "Watch Ending / Credits" trigger that directly plays the campaign's
closing cinematic-mission, given the identical `0x1d` + `DAT_0057e044`
signature already tied to the epilogue path.

**Note, corrected**: this pass's decompile also turned up the 6-entry
scancode array `{0x19, 0x18, 0x14, 0x1e, 0x14, 0x18}` = **P-O-T-A-T-O**
driving the cheat sequence, which was first read as a brand-new
finding here. It is not new -- **Pass 34** (`CheckKeyEdgeState`
decoded, earlier in this document) already found and confirmed the
same "Ctrl+Potato" sequence at confidence 5. This pass's independent
read is a useful cross-check (it landed on the identical scancodes via
a different function's decompile) but the credit and the confidence-5
status both belong to Pass 34. Caught and corrected before being
double-counted in the tracking docs -- see the stale-entry note added
just above the original (pre-Pass-34) writeup.

### `RunSaveLoadScreen` (`0x43ca50`) -- action-button coordinates, confidence 5

The function builds one big 19-record, 4-`int16` (`{x,y,w,h}`) stack
table; `HitTestRectArray` is called with two different (base, count)
windows into it depending on mode -- this time **directly confirmed**
(not inferred): the SAVE-mode base pointer (`&local_178`) is literally
40 bytes (5 records) past the LOAD-mode base pointer (`&local_1a0`) in
the declared-locals list, i.e. LOAD mode uses records 1-5 and SAVE
mode uses records 6-18 of the same contiguous block. (Record 0,
`(201,217,84,21)`, isn't covered by either hit-test window -- it's
referenced only via a button-descriptor pointer, likely a
status/label field rather than a clickable hotspot.)

**Load mode** (`&local_1a0`, 5 entries):

| idx | x | y | w | h | Action |
|---|---|---|---|---|---|
| 0 | 45 | 140 | 149 | 21 | Start select |
| 1 | 464 | 386 | 28 | 28 | Confirm load |
| 2 | 323 | 420 | 28 | 20 | Exit to screen 0xe |
| 3 | 323 | 441 | 28 | 20 | Options dialog |
| 4 | 291 | 441 | 28 | 20 | Exit to main menu |

**Save mode** (`&local_178`, 13 entries):

| idx | x | y | w | h | Action |
|---|---|---|---|---|---|
| 0 | 45 | 179 | 149 | 21 | Select target / name field |
| 1 | 45 | 217 | 149 | 21 | Confirm delete/overwrite |
| 2 | 465 | 300 | 28 | 14 | Quick-save |
| 3 | 465 | 343 | 28 | 14 | Open Save Browser (`RunSaveGameBrowserScreen`) |
| 4 | 464 | 386 | 28 | 18 | Cancel |
| 5 | 323 | 420 | 28 | 20 | Exit to screen 0xe |
| 6 | 323 | 441 | 28 | 20 | Options dialog |
| 7 | 291 | 441 | 28 | 20 | Cancel |
| 8 | 567 | 242 | 28 | 18 | Pick list item |
| 9-12 | 359 | 179/192/205/218 | 232 | 13 | Scroll/select slot (4-row visible list, 13px pitch) |

Directly read, cross-confirmed against the already-documented
switch-case actions (Pass 48) -- **confidence 5** on both coordinates
and index-to-action mapping.

### `RunSaveGameBrowserScreen` (`0x431730`) -- action-button + scroll-arrow coordinates, confidence 5

Three separate `HitTestRectArray` windows into one 17-record
`{x,y,w,h}` block:

**Save-slot list** (10 rows, part of the 14-entry `&local_41c` window):
`x=49, w=400, h=17`, `y = 126 + 17*i` for `i=0..9` (126,143,...,279).
**Correction to Pass 48**: the earlier approximate reading reported
`x=17, w=400, h=49` -- the `x` and `h` fields were transposed. The
correct values are `x=49, h=17` (17px row pitch, matching the
already-correct pitch claim; only the two individual field values were
swapped).

**Action buttons** (indices 10-13 of the same 14-entry window):

| idx | x | y | w | h | Action |
|---|---|---|---|---|---|
| 10 | 292 | 421 | 25 | 16 | Back (exit browser -> `RunNewGameSetupScreen`) |
| 11 | 324 | 421 | 25 | 16 | Confirm (load, or save-with-overwrite-check) |
| 12 | 292 | 441 | 25 | 16 | Exit to main menu |
| 13 | 324 | 441 | 25 | 16 | Options dialog |

**Correction to Pass 48**: these were previously labeled "back,
confirm, cancel, delete" (a guess). The actual decompiled switch-case
bodies show 12 is "exit to main menu" (`DAT_0051dac4=0`) and 13 is
"options dialog" (the same `FUN_0042aa80`/`FUN_0042aaa30` pattern used
everywhere else in these screens) -- there is no delete action among
these four; "delete" was not implemented via this hotspot set.

**Scroll arrows** (separate 2-entry `&local_42c` window): up
`(579,250,26,16)`, down `(579,268,26,16)` -- **confirms** Pass 48's
approximate guess exactly; upgraded from confidence 3 to confidence 5.

**Overwrite-confirm dialog button** (new finding, separate 1-entry
`&local_434` window, only hit-tested while the "are you sure?" popup
is active): `(562,384,32,20)`.

### Open follow-ups

- `RunSaveLoadScreen` record 0 `(201,217,84,21)`'s exact role
  (referenced only via a descriptor pointer, not hit-tested directly).
- `RunNewGameSetupScreen`'s 8-entry button row remains unresolved
  (Pass 50 root cause stands).
- `RunMultiplayerSetupScreen`'s ~30-alias layout and
  `RunMultiplayerLobbyScreen`'s remaining rects -- not attempted this
  pass.

## Pass 52 -- `RunMultiplayerSetupScreen` and `RunMultiplayerLobbyScreen`: full hotspot layouts (2026-09-09)

Direct follow-up on the last two open items from Pass 48. Both screens
turned out to follow the exact same pattern discovered for
`RunSaveLoadScreen` in Pass 51: what looked like "~30 chained pointer
aliases" is actually **one big contiguous stack table**, with several
different `(base, count)` windows passed to `HitTestRectArray` for
different UI modes/dialogs, plus a parallel set of small
`{rectPtr, enabled, hover, langStringIndex}` button-descriptor
structs (used for rendering/labeling) that merely point back into the
same table -- those pointers are what earlier passes read as "aliases."
Once the flat table is reconstructed from all its literal-assignment
offsets, every window is a plain, directly-readable slice.

### `RunMultiplayerSetupScreen` (`0x432fc0`)

One 38-record `{x,y,w,h}` (`int16` x4) contiguous table, 5 different
`HitTestRectArray` windows into it depending on connection state:

**Main row + session list** (`&local_230`, count = `DAT_005dd568 + 8`
-- 8 fixed buttons plus one row per discovered LAN/internet session):

| idx | x | y | w | h | Action |
|---|---|---|---|---|---|
| 0 | 62 | 233 | 28 | 20 | Direct Connect / Play |
| 1 | 251 | 233 | 28 | 20 | Zone.com (`ShellExecuteA`, Pass 6) |
| 2 | 444 | 233 | 28 | 20 | Join |
| 3 | 62 | 255 | 28 | 20 | Host (mode A) |
| 4 | 251 | 255 | 28 | 20 | Host (direct) |
| 5 | 444 | 255 | 28 | 20 | Host Co-op |
| 6 | 292 | 441 | 25 | 16 | Exit to main menu |
| 7 | 324 | 441 | 25 | 16 | Options dialog |
| 8-15 | 66 | 292+12*i | 353 | 12 | Session list rows (8 visible, 12px pitch) -- index-8 = session table row |

**Connecting/status panel** (`&local_2e0`, count 3 or 4 depending on
connect mode): 4 stacked wide lines, all `x=455, w=178, h=20`, `y =
290, 339, 389, 439`.

**Host-setup dialog** (`&local_2c0`, 4 entries): `(372,305,28,20)`
Cancel/back, `(258,339,28,20)` Exit(`0xa`), `(258,373,28,20)`
Exit(`0x11`, lobby), `(198,305,169,21)` Options toggle.

**Difficulty/options row** (`&local_2a0`, 8 entries): 5 `<`/`>`-style
cycle fields (`20x15`, `x=208`/`411` at `y=295/338/381` -- 5 settings,
each wrapping through a small fixed count: 4/7/3/5/4 states
respectively) plus `(455,292,28,20)` Cancel, `(455,339,28,20)`
Exit(`0xa`), `(455,389,28,20)` Options toggle.

**Join-session dialog** (`&local_260`, 6 entries): `(373,305,28,20)`
Cancel, `(444,339,28,20)` Exit(`0xa`), `(444,373,28,20)` Exit(`0x11`),
`(198,304,169,21)` Options toggle, `(402,350,20,15)` scroll up,
`(402,368,20,15)` scroll down.

**Confidence 5** throughout -- every value read directly from the
reconstructed table, and the table's adjacency/windowing itself is
directly confirmed via matching base-pointer arithmetic (same method
validated in Pass 51), not inferred.

### `RunMultiplayerLobbyScreen` (`0x44b950`)

Two (really three) contiguous tables:

**3-entry exit cluster** (`&local_238`): `(201,126,79,21)` a
larger "Back"-style link near the top, `(578,312,25,16)` Exit
(`0xe`), `(578,334,25,16)` Exit (`0xe`, same destination as the
first).

**40-entry (`0x28`) main table** (`&local_220`, the big one):

| idx | x | y | w | h | Action |
|---|---|---|---|---|---|
| 0 | 578 | 356 | 25 | 16 | Ready / Start |
| 1 | 45 | 164 | 149 | 21 | Cancel / Back |
| 2 | 323 | 421 | 25 | 16 | Scroll page up |
| 3 | 291 | 441 | 25 | 16 | Scroll page down |
| 4-9 | see below | | | | Host-mode mission-select list (6 rows) |
| 10 (`0xa`) | 48 | 182 | 147 | 12 | Unused (no case label) |
| 11-18 (`0xb-0x12`) | see below | | | | Player-roster slot toggles (8) |
| 19 (`0x13`) | 435 | 172 | 162 | 12 | Dropdown/expand toggle |
| 20-23 (`0x14-0x17`) | 435 | 186/200/214/228 | 162 | 12 | Dropdown items (4) |
| 24 (`0x18`) | 266 | 130 | 28 | 14 | Second toggle |
| 25-36 (`0x19-0x24`) | see below | | | | Second list (12 rows) |
| 37-39 | 203 | 342/364/386 | 188 | 18 | Reserved/unused tail (same list pattern, no case label) |

Mission-select list rows (4-9): `(323,441,25,16)`, `(45,126,149,21)`,
`(464,388,32,21)`, `(428,251,28,14)`, `(428,266,28,14)`,
`(48,168,147,12)`.

Player-roster slot toggles (11-18): `(48,196,147,12)`,
`(48,210,147,12)`, `(48,224,147,12)`, `(48,238,147,12)`, `(0,0,0,0)`
(a genuinely zeroed slot -- one of the 8 roster positions is
literally a null rect, plausibly an always-empty/host-reserved slot),
`(435,130,162,12)`, `(435,144,162,12)`, `(435,158,162,12)`.

Second list rows (25-36): `(203,150,55,17)` x4 at `y=150/172/194/216`,
then `(399,168,28,14)` (an outlier -- likely a scroll/expand icon
embedded mid-list), then seven `188x18` rows at `x=203,
y=188/210/232/254/276/298/320`.

**Confidence 5** on all of the above -- direct literal reads,
adjacency confirmed via base-pointer arithmetic.

### What remains genuinely unresolved

One more small table exists: `HitTestRectArray(&pcStack_258, 3, ...)`,
used only in host mode for the "ready/mute/second-checkbox" 3-toggle
row (`DAT_00524a60`/`DAT_00524d74`/`DAT_00524d5c`). Unlike every other
table in this pass, `pcStack_258` sits in a stack region the compiler
reused for SEH exception-frame bookkeeping earlier in the function (it
is declared as a plain `char *`, not a run of `undefined2` locals) --
the decompile prints no literal-assignment lines for the 24 bytes this
window covers, so its coordinates are not recoverable from this
decompile the way every other table's are. **Confidence 0** on any
specific values for this one row; not asserted. This is the same
class of limitation documented in Pass 50, and would need the same
P-code cross-check treatment if pursued.

### Open follow-ups

- The 3-entry host-mode checkbox row's coordinates (`&pcStack_258` in
  `RunMultiplayerLobbyScreen`) -- unresolved, root cause identified.
- Button-label language-string indices were captured in passing for
  both screens' descriptor structs but not cross-referenced against
  `GetLanguageString` output (blocked on the same runtime-only string
  table noted in Pass 37/48).

## Pass 53 -- Palette-to-image mapping investigated (2026-09-09)

Investigated how palettes are matched to images from two angles, as
requested: (1) Lancer.exe's own code, and (2) grounding that against
three large pre-extracted asset dumps found in `gamedata/StarLancer/`
(`extracted/` = 2771 `PALETTE_N_32cols.pal`+`.png` pairs,
`out_palettes/` = 2771 `POWER_N_32cols.pal`+`.png` pairs,
`out_softpal/` = 2771 `SOFTPAL_N_32cols.pal` files) that are clearly
output from a third-party unpacking tool (numbered generically, not
using any real in-game resource names) rather than anything this
project produced.

### Code finding 1: NO shipped `.spr`/`.fnt` asset uses a per-shape palette override

The `.spr` format (Pass 39/41) has a documented per-shape mechanism for
exactly this purpose: each `ShapeRecord` entry in a `ShapeSet` carries
a `paletteOffset` field pointing at an optional
`PaletteOverrideRecord` (`{entryCount, {index,r6,g6,b6}[]}`), read by
`VFX_shape_palette`. To find out which images actually use it,
decompressed and parsed **all 337 `.spr` files** in `gamedata/`
(RefPack-decoded via `reversing/tools/refpack_decompress.py`) and
checked every shape's `paletteOffset` field directly:

- Total shapes across all files: **8583**.
- Shapes with a non-zero `paletteOffset`: **0**.

**Confidence 5** (exhaustive, direct, script-verified over every
shipped `.spr` file): despite the per-shape palette-override mechanism
existing in the code, **no shipped 2D sprite/UI image actually uses
it**. Every single shape draws through whatever the *currently active
global palette* is at draw time -- there is no per-image palette
selection to discover for this asset class, because the game doesn't
have one in practice.

### Code finding 2: palette selection happens per render CONTEXT (screen), not per image

Decompiled `InitializeLoadoutScreen` (`0x441aa0`, already
partially documented) to see how the mission-briefing/loadout screen's
3D ship-preview rendering picks its palette. It:

1. Saves the *currently active* renderer-state CCB pointer/palette
   fields (`DAT_00523a94`/`DAT_00523d30` <- `*(param_1+0x1606)`/
   `*(param_1+0x1602)`).
2. Calls `SR_CCB_load()` (the Pass 30 `.ccb` loader) to load a *fresh*
   `.ccb` resource into `DAT_005246d0` for this screen's own use.
3. Loads all the `.SHP` ship/missile/gunship models for the loadout
   roster via `LoadSquadronRoster` (see below).
4. At the very end, **restores** the original saved CCB
   pointer/palette fields back into the renderer state, then re-runs
   the exact RGB-triple-to-native-pixel-format packing loop documented
   in Pass 25/30 against that **restored (original, pre-screen)**
   palette, and calls `VFX_init_global_palette`.

**Confidence 4**: this shows palette assignment operates at the
*screen/render-context* granularity, not per individual model or
texture -- a screen can load its own `.ccb` for its 3D content, but
the final 2D/WinVFX global-palette conversion at screen teardown
explicitly reuses whatever palette was active *before* entering that
screen, not the newly-loaded one. This is consistent with finding 1:
this engine's actual palette model is "one active palette at a time,
switched per screen," not "one palette per image."

### `.SHP` format identified: ship/turret/pod 3D object files (438 in `gamedata/`), no per-file palette reference

`search_strings` for `.shp`/`.SHP` in `Lancer.exe` turns up real
fighter/gunship/turret/missile-pod model filenames (`USLF_prd.SHP`,
`predator_gun.SHP`, `German_grendal.SHP`, `21_screamer_pod.shp`, etc.
-- 262+ distinct string hits), all referenced from
`InitializeLoadoutScreen`'s model-list-building loops, each passed to
`LoadSquadronRoster` (`0x4a44d0`).

**Correction/clarification**: `LoadSquadronRoster` was named from its
`.sro` (squadron roster) usage in `InitializeMissionGameplay` (Pass
25/34's addendum). Its full decompile this pass shows it's actually a
**generic structured-text object-file parser** -- it parses
wing/formation sub-records, weapon hardpoints (string-matching
`"startup"`/`"deploy"` keywords), and geometric sub-records with
plane-normal computation, general enough to be reused for loading a
single `.SHP` ship/turret/pod model as a "roster of one." The name is
narrower than the function's real scope; not renamed this pass since
"squadron roster" is still accurate for its primary/original use.
**No CCB, RGB, or palette-related code appears anywhere in this
parser** -- confirms finding 2: individual `.SHP` model files don't
carry or select their own palette; whatever `.ccb` is active for the
current screen applies to all of them uniformly.

### The three extracted dumps: not groundable against any per-image code mechanism, and likely mostly scanner noise

Given findings 1 and 2, there is **no code-level per-image or
per-shape palette selection** for either `.spr` or `.SHP` assets that
the extracted dumps' `PALETTE_N`/`POWER_N`/`SOFTPAL_N` numbering could
correspond to -- the game simply doesn't index palettes by individual
image. Sampled several `N` values across all three folders directly:

| N | `PALETTE_N` (extracted/) | `POWER_N` (out_palettes/) | `SOFTPAL_N` (out_softpal/) |
|---|---|---|---|
| 0 | `(125,190,121), (121,182,113), ...` -- varied, plausible real colors | `(0,0,0), (12,8,0), (24,12,0), ...` -- warm ramp (dark red->orange), classic engine-glow/fire shading | `(0,0,0), (8,8,8), (16,16,16), ...` -- clean grayscale ramp |
| 1000 | `(169,169,165)` repeated | `(79,79,79)` repeated | mostly `(79,79,83)`-ish repeated |
| 1500-2770 | flat, low-variance R=G=B runs throughout | flat R=G=B runs throughout | flat R=G=B runs throughout |

Only `N=0` in each folder looks like genuinely varied, art-like color
data. Every other sampled index degrades into long runs of
near-constant, R=G=B (gray) triples -- **not what real sprite/texture
palettes look like**, but exactly what a naive brute-force "scan every
N bytes and interpret 3 bytes as RGB" heuristic produces when it walks
across non-palette binary data (padding, alignment, unrelated
structure fields) between genuine hits. `POWER_0`'s warm ramp and
`SOFTPAL_0`'s neutral grayscale ramp are individually plausible as a
real engine-glow/fire effect ramp and a real monochrome shading ramp
respectively (the latter matching Pass 30's still-unconfirmed "Block B
= 12-shade lighting ramp" hypothesis in `softpal.ccb`) -- but with
2770 further indices per folder mostly degrading to gray noise, this
project cannot responsibly assert a specific N-to-real-asset mapping
for the bulk of this data. **Confidence 1** that `N=0` in each folder
corresponds to something real; **confidence 0** (not asserted) for any
specific claim about `N>0`'s meaning.

### Bottom line

For the question "which palette belongs with which image": in
Lancer.exe's own logic, the honest answer is **there mostly isn't
one** -- `.spr`/`.fnt` 2D images never carry a per-shape override in
the shipped game (finding 1), and `.SHP` 3D models never carry or
reference a palette at all (finding 2's parser check). The real
mapping that exists is coarser: **one global palette is active at a
time, chosen from the 3 real `.ccb` files (`palette.ccb`/
`palette3.ccb`/`softpal.ccb`, Pass 30) and swapped per screen/render
context**, not per image. The `gamedata/` extraction dumps don't
reflect a finer-grained mapping than that -- they appear to be the
output of a heuristic scanner that mostly produced noise beyond its
first hit in each category.

### Open follow-ups

- `FUN_004a3040`/`FUN_004a3cb0` (called per-wing inside
  `LoadSquadronRoster`, likely converting parsed `.sro`/`.shp` records
  into renderer-ready structures) -- not decompiled this pass.
- Whether `.tga` files (142 in `gamedata/`, not examined this pass)
  carry embedded palettes of their own (TGA type 1 supports this
  natively) as an independent texture-palette mechanism separate from
  the `.ccb`/WinVFX system -- worth checking if 3D ship texture
  palettes specifically are wanted next.
- Identifying the actual third-party tool that produced the
  `extracted`/`out_palettes`/`out_softpal` dumps, to understand its
  real extraction logic -- out of scope for static analysis of
  `Lancer.exe` itself.

## Pass 54 -- Which palette is used for the menus? Direct answer (2026-09-09)

Direct follow-up on Pass 53. Applied `set_function_prototype` to
`SR_CCB_load` (`0x4cb9d0`, was `param_count: 0` -- hidden `__fastcall`
filename argument, same recurring technique from Passes 34/35/37/51)
and re-decompiled its only two callers.

### The menus use whichever of `softpal.ccb`/`palette.ccb` was loaded once at startup

`SR_CCB_load` has exactly 2 call sites in the whole binary:

1. **`InitializeGraphicsDevice`** (`0x4acbe0`, was `FUN_004acbe0` --
   renamed this pass; called 4x from `FUN_004a8600`, a device-mode
   try/fallback loop run once during startup):
   ```c
   if (*(int *)(DAT_00588730 + 0x1ac) == 0) {
       filename = "softpal.ccb";
   } else {
       filename = "palette.ccb";
   }
   pvVar2 = SR_CCB_load(filename);
   *(void **)(DAT_00588730 + 0x1606) = pvVar2;   // stored in renderer state, persists
   ```
2. **`InitializeLoadoutScreen`** (`0x441aa0`): unconditionally loads
   `"palette3.ccb"` into a separate local (`DAT_005246d0`), for its own
   3D ship-preview rendering -- and, per Pass 53, explicitly restores
   the *original* pre-screen palette pointer before re-deriving the
   final 2D/WinVFX global palette at teardown, so this third file never
   leaks into the menu system.

**Correction (2026-09-09, Pass 61)**: the sentence below treats
`+0x1606` (the `.ccb` result) and `+0x1602` as if they were the same
palette resource -- they aren't. Pass 61 found `+0x1602` is actually
populated by a *separate* call, `SR_TGA_allocate_palette("softpal.tga"
/"palette.tga")`, made in the exact same `if`/`else` branch right
before the `.ccb` load shown above. The conclusion below (menus use
whichever of the `softpal`/`palette` PAIR was loaded at startup, never
their own) still holds -- it's the mechanism/attribution of "the
palette" to `.ccb`'s own bytes specifically that needs correcting to
"the `.tga` sibling of whichever `.ccb` gets loaded."

No menu screen (`RunMainMenuScreen`, `RunMenuScreenLoop`, or any of its
12 dispatched screens) calls `SR_CCB_load` itself. **Confidence 5**:
the menus therefore render through whichever palette
`InitializeGraphicsDevice` loaded once at startup and left in
`rendererState+0x1606`/`+0x1602` -- **`softpal.ccb`** if
`rendererState+0x1ac == 0` (the flag Pass 25/30 already tied to a
software-vs-hardware renderer distinction -- "softpal" reads naturally
as "software-rendering palette"), or **`palette.ccb`** otherwise (the
hardware-accelerated path). This is a single, persistent, whole-game
default -- not something that changes per menu screen -- and it is the
exact same palette the mission-briefing/loadout screen restores when
it exits back to the menu (closing the loop with Pass 53's
per-render-context finding).

### Open follow-ups

- The exact condition that sets `rendererState+0x1ac` (hardware vs.
  software renderer selection) -- not traced this pass, referenced
  from `FUN_004a8600`'s fallback loop.
- `palette3.ccb`'s actual RGB content vs. `palette.ccb`'s, to see how
  different the loadout-screen's 3D lighting environment really looks
  from the menu's -- not compared byte-for-byte this pass.

## Pass 55 -- The `.SHP`/`.sro` 3D object format decoded: a generic tagged-chunk container (2026-09-09)

Direct follow-up on Pass 53's open item ("decode graphics formats for
ships, 3D objects, and textures"). Cracked the on-disk binary format
underlying both `.SHP` (438 ship/turret/pod models) and `.sro`
(squadron roster) files -- they share one loader
(`LoadSquadronRoster`, `0x4a44d0`) and one file format.

### The primitive: a generic tagged-chunk reader

`LoadSquadronRoster` doesn't read fields directly -- every single field
it populates comes from repeated calls to a small helper, `FUN_004a2eb0`,
which had `param_count: 0` (fully hidden `__fastcall` arguments,
exactly the recurring pattern from Passes 34/35/37/51/54).  Applied
`set_function_prototype` (`ReadTaggedChunk(void** outPtr, ushort tag,
uint elemSize)`, renamed from `FUN_004a2eb0`) and re-decompiled --
every hidden `tag` argument at every call site became visible at once,
across the whole function.

`ReadTaggedChunk`'s own logic, decoded directly:

```c
struct ChunkHeader {          // 6 bytes, repeats throughout the file
    uint16_t tag;
    uint16_t stride;          // bytes per item, AS STORED ON DISK
    uint16_t count;           // 0xffff tag = end-of-file sentinel
    uint8_t  payload[stride * count];
};
```

A single forward-only cursor (`DAT_005959f8`, seeded from
`SR_FileAlloc`'s -- renamed from `FUN_004cb420` -- whole-file memory
buffer) walks chunk-to-chunk, skipping any chunk whose `tag` doesn't
match the caller's request, until it finds one that matches or hits
the `0xffff` end sentinel. On a match, it allocates
`count * elemSize` bytes (the CALLER's expected element size, not
necessarily the disk stride) and copies `min(stride, elemSize)` bytes
per item -- a deliberately version-tolerant reader: old-format files
with a smaller on-disk record still load cleanly into a newer,
larger in-memory struct, with the extra tail bytes left zeroed.
**Confidence 5** -- directly read, and independently confirmed by
writing a Python chunk-walker against a real decompressed `.SHP` file
(`gren_frm.SHP`) that exactly reproduces this framing.

### Confirmed tag catalog (from `LoadSquadronRoster`'s full call sequence)

| Tag | elemSize | Scope | Role (confidence) |
|---:|---:|---|---|
| 0 | 0x68 (104) | once/file | File header, 1 record (5) |
| 1 | 600 | once/file | **Parts array** -- each record begins with a null-padded ASCII part name (confirmed directly in raw bytes: `"Gren frame"`, `"arms"`) (5) |
| 2 | 0x1c (28) | per-part | Sub-record array, further expands via tags 3/4/6 (4) |
| 3 | 0x50 (80) | per tag-2 item | Unresolved -- likely vertex-position or joint data (2) |
| 4 | 0x20 (32) | per tag-2 item | Unresolved -- likely per-vertex normal/UV (2) |
| 6 | 0x48 (72) | per tag-2 item | Unresolved (1) |
| 7 | 0x5c (92) | per-part | Mesh-adjacency-like array: each item optionally computes two "neighbor" pointers into the SAME array from stored indices (offset+0x40/+0x44), and copies a shared per-part value (offset+0x138 -- plausible material/color index, not confirmed) into every item (3) |
| 8 | 4 | per tag-7 item | A single index/flag driving the tag-7 adjacency computation above (2) |
| 9 | 0x7c (124) | per-part | Unresolved (1) |
| 0xa | 0x28 (40) | per-part | **Hardpoint/socket records** -- each contains an embedded ASCII keyword string at offset+6, matched against `"startup"`/`"deploy"` (and a third, garbled-in-decompile string) to classify animation state; further expands via tags 0xb/0xc (4) |
| 0xb | 0x1c (28) | per tag-0xa item | Unresolved (1) |
| 0xc | 0xc (12) | per tag-0xa item | Unresolved (1) |
| 0xd | 0xc (12) | per-part | Sub-record array, expands via tag 0xe (2) |
| 0xe | 0x14 (20) | per tag-0xd item | Unresolved (1) |
| 0xf | 0x54 (84) | per-part | **The renderable polygon/face list.** Confirmed via its consumer loop: a per-record vertex-count flag (`< 0` -> 3 = triangle, else 4 = quad), then a **cross-product face-normal computation** from 3 referenced vertex positions, normalized and stored back into the record (offset+0x44/+0x48/+0x4c = normal xyz, +0x50 = magnitude). This is unambiguously the 3D mesh's actual triangle/quad face data (5) |
| 0x10 | 0x4c (76) | once/file, read AFTER all parts | Unresolved -- read once at file scope, the natural place for a materials/textures table, but **not present at all** in the one sample file checked this pass (5 on "absent from this file", 0 on any semantic guess) |

### Textures: not embedded by filename in `.SHP` -- referenced indirectly, mechanism unresolved

Dumped every printable ASCII string in a fully-decompressed `.SHP`
file (`gren_frm.SHP`, 37686 bytes) looking for texture filenames
(`.tga`/`.mat`/`.bmp`) -- found only the two part names already noted
and one truncated fragment (`"cpit0"`, plausibly part of a hardpoint
name like `"cockpit0"`). **No texture/material filename is embedded
in this file.** Combined with tag 0x10 (the one file-scope array read
after all per-part data, and the most natural home for a
materials/textures table) being entirely absent from this sample,
texture assignment for `.SHP` models is **not** done by embedding a
filename per model or per part -- it must be either (a) a numeric
material index (the unresolved per-part `+0x138` field feeding every
tag-7 face record) resolved against some separately-loaded global
materials table, or (b) driven by filename convention/context outside
the `.SHP` file entirely (e.g. the same base name with a different
extension, or a fixed per-ship-class texture set loaded alongside).
**Not resolved this pass -- confidence 0 on any specific mechanism.**

### Open follow-ups

- Tags 3/4/6/8/9/0xb/0xc/0xe's exact field semantics -- structurally
  located (offsets, strides, nesting) but not decoded field-by-field.
- The per-part `+0x138` field's source and meaning (candidate
  material/texture index) -- not traced to where it's actually
  populated.
- Tag 0x10's content and purpose -- check a `.SHP`/`.sro` file that
  actually contains one (`gren_frm.SHP` doesn't) to see real payload
  bytes.
- `FUN_004a3040`/`FUN_004a3cb0` (per-hardpoint post-processing, called
  in `LoadSquadronRoster`'s second pass) -- not decompiled.
- `FUN_004c14f0`/`FUN_004c1370`/`FUN_004c11c0` (the vertex-fetch/
  normalize/length helpers used by the tag-0xf face-normal loop) --
  not decompiled; would likely reveal exactly how vertex indices map
  to positions.
- Whether `.tga` files (142 in `gamedata/`, still unexamined) are
  associated with ships via a naming convention observable in the
  BigFile TOC, independent of anything found in `.SHP` itself.

## Pass 56 -- `.SHP` tags decoded further: vertices, normals, hardpoint names/transforms; tag 0x10 hypothesis corrected (2026-09-09)

Direct follow-up on Pass 55's open tag list. Method: scanned all 438
`.SHP` files in `gamedata/` with a Python chunk-walker to collect
real on-disk stride/count statistics per tag (revealing several tags
have MULTIPLE on-disk stride variants -- different file-format
versions, consistent with `ReadTaggedChunk`'s version-tolerant
`min(diskStride, expectedSize)` copy behavior, Pass 55), then dumped
and hand-decoded real record bytes for the tags with the clearest
signal.

### Tag 4 = per-vertex record: CONFIRMED, confidence 5

32-byte on-disk records, directly decoded as floats:
```c
struct Vertex {          // tag 4
    float x, y, z;        // real ship-scale coordinates (100s-1000s of units)
    float nx, ny, nz;      // unit-length normal (|n| = 1.0, verified across every sampled record)
    int32_t field1, field2; // trailing pair, constant (1, 0) across every record sampled
};
```
Directly verified: every sampled normal has magnitude 1.0 to within
float precision, and every position falls in the same coordinate
range as the ship-hull floats already seen in Pass 55's raw hex dump.

### Tag 6 = named socket/hardpoint string label: CONFIRMED, confidence 5

64-byte on-disk records. Raw bytes begin with a null-terminated ASCII
string -- directly read as `"cpit0\0..."` (a cockpit-socket name),
which also explains the stray `"cpit0"` string fragment `strings`
turned up in Pass 55 (it wasn't a hardpoint-record fragment as
speculated then -- it's this tag's own field, read whole). This tag
is nested per tag-2 item, i.e. it's the human-readable name for
whatever tag 2 groups.

### Tag 3 = per-triangle-fan record with UV/shading data: well-supported, confidence 3

72/80-byte on-disk records (two file-format variants). Hand-decoding
5 consecutive records showed:
- 3 leading `int32` fields constant across an entire run of records
  (e.g. `0, 22, 0` -- plausible `{materialIndex, fanVertexCount,
  flag}` header shared by a whole triangle fan).
- 3 more `int32` fields forming a clean **sliding window** across
  consecutive records (`[2,3,20] -> [3,20,19] -> [20,19,8] ->
  [19,8,7]`, each record dropping the oldest index and adding one
  new one) -- the textbook on-disk encoding of a **triangle fan/strip**,
  each record naming one triangle's 3 vertex indices.
- 9 trailing `float`s (3 groups of 3) -- plausibly per-vertex UV or
  shading/blend data for the triangle's 3 corners, not independently
  confirmed against a draw call.
- A few more trailing small-int fields, not decoded.

**Confidence 3**: the fan/strip vertex-index structure is well
evidenced (the sliding-window pattern is not something noise would
produce); the exact meaning of the header fields and trailing floats
is inferred, not proven.

### Tag 9 = hardpoint attachment transform: plausible, confidence 3

100-168-byte on-disk records (4 format variants across the corpus,
124 bytes matching the loader's own expected size exactly in at least
one variant). Hand-decoded one 124-byte record: leading `int32=4`
(count?), then a real ship-scale `float3` position (`36.07, -58.24,
276.21`), then **two more unit-length `float3` vectors** (magnitude
1.0, forming what look like the first two rows/axes of an orientation
basis), then a run of zeros, then two more isolated scalars (`-400.0`
and `1000.0`) near the end. Reads naturally as a **hardpoint's local
attach transform**: position + orientation (forward/up, with right
implied by cross product) + a couple of range/radius-like scalars.
Not confirmed against a consumer.

### Tag 0xa (hardpoint record) refined

8/24-byte on-disk variants. The smaller (8-byte) samples decoded to a
leading `int32` numeric field (`16000` in the samples checked) with
the rest zeroed -- plausibly a range/distance value (weapon range,
detection radius) in the same large-integer unit scale seen
elsewhere. The embedded `"startup"`/`"deploy"` keyword string
(Pass 55) lives at a fixed offset within the LARGER on-disk variant
only; the 8-byte samples checked this pass didn't carry one.

### Tag 0xf: on-disk structure confirmed, but the tag is essentially unused

Cross-checked the earlier structural inference (16-byte on-disk
record = `{v0,v1,v2,v3}` vertex-index quad, `v3<0` meaning "triangle")
against two REAL populated instances, found by scanning all 438
files: `stalag.SHP` has exactly 2 tag-0xf chunks, one record each --
`(215,216,217,218)` and `(13,12,15,14)`. Both are clean, small,
plausible vertex indices, confirming the format. **But: across all
438 shipped `.SHP` files, tag 0xf appears with `count > 0` in only
these 2 places, total.** Despite Pass 55 identifying it as "the
renderable polygon/face list" based on its consumer code (a real
cross-product face-normal computation), **it is essentially unused in
practice** -- almost exactly the same surprise finding as Pass 53's
discovery that the `.spr` per-shape palette-override mechanism exists
in code but is never used by shipped assets. Tag 3's much more
common, much higher-count fan/strip records (above) are the far more
likely candidate for the actual rendered mesh surface in most ships.
**Confidence 5** on tag 0xf's on-disk structure; **confidence 4** on
it being rare-to-unused in the shipped game.

### Tag 0x10: Pass 55's "materials/textures table" guess is WRONG -- corrected

Found 73 `.SHP` files (of 438) containing populated tag-0x10 chunks
(all with the loader's expected 76-byte stride, e.g. `A_mammoth.SHP`
with 27 records, several single-asteroid files `Ast_1..7.SHP` with 1
record each). Decoded real records from both:

- First 12 bytes: **always a unit-length `float3`** (verified across
  every record in every sample) -- a direction/normal vector, not
  obviously tied to any UV or color.
- Remaining 16 `int32` fields: NOT texture/material indices or
  filenames. In the single-record `Ast_*.SHP` samples they're a
  uniform run of `0xFFFFFFFF` sentinels (64 bytes of "unused"). In
  the 27-record `A_mammoth.SHP` sample they're varied
  **bitmask-shaped** values (e.g. `0xFFF0F0F0`, `0xFFFCFFF8`,
  `0xFFFEFFFE` -- mostly-1 bit patterns with a handful of specific
  bits cleared), not small sequential indices and not readable
  strings.

This pattern -- a unit normal plus a per-record bitmask over up to
512 bit-positions -- reads much more naturally as a **collision/
bounding-plane table** (one record per hull face/plane: its outward
normal, plus a bitmask marking which other planes are
adjacent/visible/relevant, a classic technique for fast convex-hull
point-containment or backface culling) than as anything
texture-related. **Explicit correction to Pass 55**: tag 0x10 is
**not** a materials/textures table. Confidence 2 on the
"collision/bounding-plane" reinterpretation (structurally plausible,
not confirmed against a consumer); confidence 5 that it is NOT a
texture table (no strings, no clean small-index pattern anywhere
across 28 sampled records).

### Textures: still unresolved -- the most likely remaining candidate is now ruled out

With tag 0x10 corrected away from "materials table," there is now
**no remaining tag in the `.SHP` chunk catalog that plausibly carries
texture/material references** -- every tag has been either decoded
with a non-texture-related structure, or shown to carry no strings
and no small-index-into-a-table pattern. Combined with Pass 53's
finding that `.spr`/`.fnt` images never use per-shape palette
overrides, this project has now checked every avenue this session
turned up and found no per-model texture assignment mechanism at all
in the `.SHP` format itself. **Confidence 3** (strengthened from Pass
55's confidence 0): ship textures are most likely assigned by an
**external mechanism entirely outside the `.SHP` file** -- e.g. a
fixed filename convention tied to the ship's base name/class, or a
lookup driven by code in `InitializeLoadoutScreen`/mission-loading
that isn't part of the model file at all. Not confirmed; a good next
target would be tracing `FUN_004a3040`/`FUN_004a3cb0` (the two
per-hardpoint post-processing calls `LoadSquadronRoster` makes after
the chunk-parsing pass, not yet decompiled) rather than the file
format itself.

### Open follow-ups

- `FUN_004a3040`/`FUN_004a3cb0` -- now the most promising remaining
  lead for finding the actual texture-assignment mechanism.
- Tags 8/0xb/0xc/0xd/0xe -- still not decoded with real sample data.
- Tag 3's trailing float groups and leading header fields -- decoded
  structurally, not confirmed semantically.
- Whether tag 0x10's bitmask fields really are collision/visibility
  data -- would need to find its consumer to confirm.

## Pass 57 -- Combat engine: Spectral Shields enforcement site exhaustively searched (not found); 3 damage-pipeline helpers decoded, one mislabeled function corrected (2026-09-09)

Direct follow-up on the two oldest open items in the combat-engine
thread: the still-missing `object+0x670`/ship-flags-`0x8000000`
Spectral Shields enforcement READ site (flagged since the
twenty-fifth/twenty-sixth passes), and the three damage-pipeline
helper functions `ApplyShieldDamage`/`ApplyComponentDamage` call but
never opened (`FUN_00474c80`, `FUN_00474e00`, `FUN_00415270`).

### Spectral Shields damage-blocking: exhaustively searched, genuinely not found

Ran `search_byte_patterns` for the exact 4-byte displacement encoding
`70 06 00 00` (offset `0x670`) across the **entire binary**: exactly 2
hits, both already known WRITE sites (`SetSpectralShieldsActive`'s
local computation, `ProcessNetworkMessage`'s network-receive write).
Zero additional hits anywhere. Separately searched for the flag
constant `0x8000000` (bytes `00 00 00 08`) restricted to the
0x400000-0x4b0000 code range (where the combat/weapon/damage
functions live): the only two code-range hits are inside
`SetSpectralShieldsActive` itself (setting/clearing the bit) and
`ProcessNetworkMessage`'s corresponding network write -- nowhere else.

Directly re-decompiled the three most plausible enforcement sites --
`ApplyShieldDamage`, `ApplyComponentDamage`, and `ProcessProjectileImpact`
-- and confirmed by inspection that **none of them reference
`object+0x670` or ship-flags bit `0x8000000` anywhere in their
bodies.** `ApplyShieldDamage`/`ApplyComponentDamage` both check only
the pre-existing invulnerability bit `0x200000` (a different bit,
already documented).

**Confidence 5, a real negative finding, not just "not found yet":**
Spectral Shields' selected "biggest non-superweapon threat" value
(`object+0x670`) and its active-state flag (`0x8000000`) are computed,
stored, and network-synchronized, but **nothing in this executable
ever reads either of them back to actually block, reduce, or redirect
damage.** Given how thoroughly this was searched (full-binary
displacement scan, restricted flag-constant scan, plus direct
inspection of every plausible consumer function), the honest
conclusion is that either (a) Spectral Shields' "block the biggest
threat" behavior isn't implemented as a discrete damage-blocking check
at all -- perhaps the ability's real mechanical effect is something
else this project hasn't yet identified (e.g. a temporary shield-value
boost, an AI-targeting avoidance effect, or purely cosmetic/UI), or
(b) the check exists but is built from instructions this pattern-based
search can't catch (e.g. a bit-test instruction with a computed bit
index rather than a literal 32-bit immediate). This closes out the
"what's still open" item from the twenty-fifth session with a
definitive, well-evidenced answer rather than leaving it as a vague
"not found yet."

### Correction: `FUN_00474c80` is NOT a scoring/kill-credit function -- it's the friendly-fire warning voice-line escalation tracker

Earlier passes (documented at `ApplyShieldDamage`'s writeup) guessed
this was "scoring/kill-credit" based only on its call-site guard
condition. Decompiling it directly shows otherwise: it accumulates
damage dealt (`_DAT_00562cec += damage`) and, once a threshold (800.0
total) and a per-tick cooldown are both satisfied, escalates a warning
STAGE counter and plays one of three voice lines chosen by that stage
-- string table entries literally named `"ff_001.ut"`, `"ff_005.ut"`,
`"ff_009.ut"` (`"ff"` = **friendly fire**). Combined with its actual
call-site guard (`attacker == local player AND target's team flag ==
0`, i.e. hitting a friendly), this is unambiguously a **"stop shooting
your own team" escalating voice-warning system**, not a scoring
mechanism. Renamed `FUN_00474c80` -> `TrackFriendlyFireWarning`.
**Confidence 5** -- directly read, string-table-confirmed. This is an
explicit correction per METHODOLOGY, not a silent edit; the earlier
"scoring/kill-credit" guess in `ApplyShieldDamage`'s writeup above is
now known wrong.

### `SetComponentDestroyedNotification` (`0x474e00`, was `FUN_00474e00`) -- decoded

```c
void __fastcall SetComponentDestroyedNotification(int isNetworkHostEvent);
```

Small: sets a new local-player-ship field, `object+0x678`, to `1`
(a "just lost a subsystem" notification flag, plausible HUD-warning
trigger for the not-yet-traced consumer), or to `2` plus a network
broadcast (`FUN_004bb920`) when `isNetworkHostEvent==1` in a hosted
multiplayer session. **Confidence 4** on the mechanism, confidence 2
on `object+0x678`'s downstream consumer (not traced).

### `QueueCommChatterEvent` (`0x415270`, was `FUN_00415270`) -- decoded

```c
void __fastcall QueueCommChatterEvent(short eventType, short context);
```

Allocates a slot via `FUN_00402860` (plausibly a sibling to the
already-documented AI-event-queue allocator, `QueueAiEvent`/`0x402660`
-- not confirmed to be the exact same queue), writes the two
`short` arguments into it, then calls `FUN_0048c580` (immediate
processing?) and `FUN_004bb980` (network broadcast, matching the
`Send*`-pattern naming convention of many already-documented
functions). Matches its call sites' context (always fired alongside
friendly-fire and component-destruction events) well enough to keep
the "comm chatter" interpretation from earlier passes. **Confidence
2** -- the queue mechanism is directly read, but the exact meaning of
`eventType`/`context` and the target queue's relationship to
`QueueAiEvent` are not confirmed.

### Open follow-ups

- `FUN_00402860` (the event-slot allocator `QueueCommChatterEvent`
  uses) -- not decompiled; would settle whether this is the same
  queue as `QueueAiEvent` or a separate one.
- `FUN_0048c580`/`FUN_004bb980`/`FUN_004bb920` -- not decompiled.
- `object+0x678`'s actual UI/HUD consumer -- not traced.
- Given Spectral Shields' damage-blocking enforcement genuinely
  isn't findable via static search, a live-debugging pass (per
  METHODOLOGY's guidance for exactly this situation) is the natural
  next step if this mechanic becomes a priority again -- e.g. hook
  `ApplyShieldDamage`/`ApplyComponentDamage` at runtime and watch
  whether damage against a Spectral-Shielded target's dominant threat
  type actually changes.

## Pass 58 -- Do `.bik` files contain/set a palette? No -- confirmed directly (2026-09-09)

Direct question. Answered definitively from two independent angles:

**1. The import table.** `Lancer.exe` imports exactly 12 Bink SDK
functions: `_BinkOpen@8`, `_BinkOpenMiles@4`, `_BinkClose@4`,
`_BinkWait@4`, `_BinkDoFrame@4`, `_BinkNextFrame@4`,
`_BinkCopyToBuffer@28`, `_BinkGoto@12`, `_BinkPause@8`,
`_BinkSetFrameRate@8`, `_BinkSetSoundSystem@8`, `_BinkSetVolume@8`.
**There is no `BinkGetPalette`/`BinkSetPalette`-shaped import anywhere
in the binary** -- confirmed via a full import-table listing, not a
targeted string search that could miss an unusual name.

**2. `DAT_0051dab4`, the previously-unresolved "two-mode Bink playback
selection" flag** (open follow-up since the VR-loop passes), is now
decoded. It's the 7th argument to every `_BinkCopyToBuffer_28` call
site (the SDK's real `flags` parameter). Traced all 4 write sites
(`FUN_00438d50`, `RunShipInteriorVRLoop` x2, `FUN_0043efc0`) via
`get_assembly_context` -- every one computes it identically:

```asm
CMP dword ptr [rendererState+0x162e], 0x3e0   ; compare against 0x03E0
SETNZ AL
ADD  EAX, 3                                    ; -> 3 if equal, 4 if not
MOV  [DAT_0051dab4], EAX
```

`0x03E0` is the classic RGB555 **green-channel bitmask** (5-5-5 16-bit
color; RGB565's green mask would be `0x07E0`). `rendererState+0x162e`
sits directly among the already-documented pixel-format bit-shift
constants (`+0x1626`/`+0x162a`/`+0x1632`/`+0x1636`/`+0x163e`/`+0x1642`,
Pass 25/30) used everywhere else in this codebase to pack RGB triples
into the display's native format. **`DAT_0051dab4` is a 16-bit
RGB555-vs-RGB565 output-surface-format selector for Bink's own RGB
blit target -- not a palette mode.** (The one other bit ever OR'd into
it, `0x80000000` for reverse-playback transitions, is a separate
flip/direction flag, also not palette-related.)

### Conclusion

**No.** `.bik` files do not contain or set a palette in this game.
Bink's internal codec is YUV-based and `_BinkCopyToBuffer` blits
decoded frames directly as RGB555/RGB565 pixels into the game's own
framebuffer -- entirely independent of the `.ccb`-driven 8-bit master
palette system (Pass 30/54) that `.spr`/`.fnt` 2D assets and the menu
system use. Video playback and paletted 2D rendering are two
completely separate color pipelines in this engine; nothing connects
them. **Confidence 5** -- based on the full import table (an absence
that's easy to verify exhaustively) plus direct decoding of the one
flag that could plausibly have been palette-related.

## Pass 59 -- The `.spr` RLE format fully decoded and verified byte-exact; medal-case sprites decoded and visually confirmed against a real screenshot (2026-09-09)

Direct user request: decode `MEDAL1.SPR` (and the other 5 medal
sprites) to match a real in-game screenshot of the medal-case UI
(`SL_Medal_Case.webp`, user-supplied). This finally nailed down two
things Pass 41 had left at low confidence: the exact RLE opcode
format, and how per-image palettes actually work for `.spr` files
that don't use the (confirmed-unused, Pass 53) per-shape
`PaletteOverrideRecord` mechanism.

### The RLE opcode format, decoded precisely from `VFX_shape_blit_unclipped` (WINVFX8.DLL, `0x100035fc`)

Read the function directly rather than inferring from the more
complex clipped blitter (`VFX_shape_draw`). Per row, read a control
byte `CB`; `mode = CB & 1`, `count = CB >> 1`:

| `CB` pattern | Meaning |
|---|---|
| `CB == 0x00` | End of row |
| `mode==0` (even), `count>0` | **Repeat run**: next byte is a fill color; write `count` copies of it |
| `mode==1` (odd), `count>0` | **Literal run**: next `count` bytes are copied verbatim |
| `mode==1`, `count==0` (`CB==0x01`) | **Skip run**: next byte is a transparent-pixel skip distance |

Implemented this exactly in a new tool,
`reversing/tools/decode_spr.py`, and it decodes every shape in every
`MEDAL1-6.SPR` file cleanly on the first attempt with no garbled
pixels or misaligned rows -- **confidence 5**, upgraded from Pass 41's
confidence 3 (the earlier writeup's general shape was right, but this
pins down the exact bit layout and was verified against real files,
not just read from the decompile).

### Whole-file embedded palette, stored as a fake "shape 0"

`MEDAL1.SPR`'s `ShapeSet` header reports `shapeCount=7`, but shape
index 0's "record" doesn't parse as a valid `ShapeRecord` (garbage
bounding box) -- instead, it's exactly **768 bytes** (256 x 3) sitting
in the gap before shape 1's real record, and those bytes decode
cleanly as a **256-entry `{R,G,B}` palette table at 6-bit VGA
precision** (every byte observed `<= 0x3F`; scaling by 4 gives a
sane, varied 8-bit palette). This is a DIFFERENT mechanism from the
per-shape `PaletteOverrideRecord` documented in Pass 39/41 (which
really is unused, per Pass 53) -- it's a **whole-file private
palette**, conventionally stored as if it were shape 0, used for every
other real shape in the same file. This cleanly explains why
`paletteOffset` is 0 on every real shape (Pass 53's finding stands
unmodified) while medal/UI sprites still each get their own distinct
color scheme: **the palette is per-FILE, not per-shape, and lives in
the shape table's first slot by convention** rather than via the
`paletteOffset` field at all. **Confidence 5** -- directly read, and
independently confirmed by the fact that decoding with it reproduces
the real screenshot exactly (see below).

`decode_spr.py` detects this automatically: any shape entry whose
record doesn't parse as a plausible `ShapeRecord` AND spans exactly
768 bytes to the next shape is treated as this file's palette.

### Visual verification against the real screenshot

Decoded all 6 `MEDAL1-6.SPR` files (`gamedata/StarLancer/cd1/`) and
rendered every shape to PNG. Each file turned out to hold **7-9
animation frames of the same medal**, nearly identical except the last
couple of frames progressively draw in a bright white/red selection
border -- clearly a hover/select-highlight animation for the
medal-case screen. Using each file's final (fully-lit/selected) frame
and arranging all 6 in the same 2x3 grid as the user's screenshot
reproduces it exactly:

- `MEDAL1.SPR` -> top-left: ring of white stars around a pale
  blue/white center disc. **Matches the user's screenshot exactly.**
- `MEDAL2.SPR` -> top-middle: eagle/starburst medallion. Matches.
- `MEDAL3.SPR` -> top-right: purple 5-pointed star. Matches.
- `MEDAL4.SPR` -> bottom-left: dark/gunmetal star medal. Matches.
- `MEDAL5.SPR` -> bottom-middle: cross with a bright sunburst center.
  Matches.
- `MEDAL6.SPR` -> bottom-right: gold star hanging from a ribbon/chain
  loop. Matches.

**Confidence 5** -- this is about as strong a confirmation as static
analysis can produce: an independently-authored decoder, built purely
from reading the RLE consumer code, reproduces a real screenshot
pixel-for-pixel in overall appearance across 6 separate files.

### Open follow-ups

- The 5 small ribbon-bar icons visible at the bottom of the
  screenshot -- no `RIBBON*.SPR`/similarly-named file was found in
  `gamedata/`; likely a different resource name or embedded in a
  different asset entirely, not searched further this pass.
- `ShapeRecord.headerField0`/`headerField1` -- still unresolved (values
  seen this pass: `0x660049` for `MEDAL1`, `0x6a0e8e`/etc. for others,
  all constant across a single file's shapes -- plausibly a
  frame-timing or animation-group ID, not confirmed).
- Whether the "whole-file palette as fake shape 0" convention holds
  for `.spr` files outside the medal-case UI (e.g. `.fnt` files, or
  other UI `.spr` assets) -- only checked for the 6 medal files this
  pass.

## Pass 60 -- The `INTERFACE\*.bik` menu-transition videos: full call map (2026-09-09)

Direct request: find where/when each of the 26 `INTERFACE\*.bik`
fade/transition clips is played. Searched the full string table for
every requested filename, then mapped every hit's cross-references to
the menu-screen function that plays it.

### 8 of the 26 requested filenames are not referenced anywhere in the binary

`FADIGOPT.BIK`, `IGOPTFAD.BIK` (only `interface\igoptfad.tga` -- a
static backdrop image, not a video, exists), `MUL2OPT.BIK`,
`MULFA2OPT.BIK`, `MULTI2MM.BIK`, `OLDOPFAD2MM.BIK`, `SIN2OPT.BIK`,
`SINFA2OP.BIK` do not appear anywhere in the string table, as a
substring or otherwise -- confirmed with multiple independent regex
searches, not just one miss. **Confidence 5** these files are unused
by the shipped executable. `OLDOPFAD2MM` literally has "OLD" in its
name, strongly suggesting it's a deprecated leftover superseded by the
(real, used) `OPFAD2MM.BIK`; the others are plausibly from an earlier,
more fully-connected menu-transition design (every screen-pair having
its own dedicated fade) that got simplified down to the shared-fade
scheme actually shipped (below) before release.

### The other 18: full call map

Two previously-unnamed functions had to be identified first:

- **`RunInGameOptionsScreen`** (`0x4394d0`, was `FUN_004394d0`) --
  called from `RunMissionBriefingScreen` and `RunShipInteriorVRLoop`.
  The **pause-menu options screen reachable mid-mission/mid-VR**:
  offers save/load (via `RunSaveGameBrowserScreen`), and the same
  `RunSoundOptionsScreen`/`RunControlsOptionsScreen`/
  `RunVideoOptionsScreen` sub-screens the main-menu Options screen
  uses.
- **`RunMultiplayerDebriefScreen`** (`0x4296a0`, was `FUN_004296a0`) --
  called 3x directly from `WinMain`. Loads `interface\mpdebr.spr`
  and `itacbig.fnt`/`itacsml.fnt`, tracks per-player ready/disconnect
  state (`DAT_005db83c`-indexed), and can drop into
  `RunSaveGameBrowserScreen` -- the **post-mission multiplayer
  results/ready-check screen.**

| `.bik` file | Played from | When |
|---|---|---|
| `main2opt.bik` | `RunMainMenuScreen` | Main Menu -> Options |
| `main2mul.bik` | `RunMainMenuScreen` | Main Menu -> Multiplayer Setup |
| `main2sin.bik` | `RunMainMenuScreen` | Main Menu -> New Game Setup (single-player) |
| `opt2main.bik` | `RunOptionsMenuScreen` | Options -> Main Menu |
| `optfade.bik` | `RunOptionsMenuScreen` (3 sites) | Options -> its sub-screens (Sound/Controls/Video), returning to the SAME Options menu |
| `optfade2.bik` | `RunControlsOptionsScreen`/`RunSoundOptionsScreen`/`RunVideoOptionsScreen` | Sub-screen -> Options Menu (entered FROM the main-menu Options screen) |
| `igofade2.bik` | same 3 sub-screens | Sub-screen -> `RunInGameOptionsScreen` (entered FROM the in-game pause overlay) |
| `opfad2mm.bik` | same 3 sub-screens | Sub-screen -> Main Menu, exiting all the way out (main-menu-Options context) |
| `igof2mm.bik` | same 3 sub-screens, plus `RunSaveGameBrowserScreen` | Sub-screen/Save-browser -> Main Menu, exiting all the way out (in-game-pause context) |
| `sin2main.bik` | `RunNewGameSetupScreen` | New Game Setup -> Main Menu |
| `sinfade.bik` | `RunNewGameSetupScreen` | New Game Setup -> (a sub-flow, e.g. name/callsign picker) |
| `sinfade2.bik` | `RunSaveGameBrowserScreen` | Save/Load Browser -> `RunNewGameSetupScreen` context (single-player) |
| `sifad2mm.bik` | `RunSaveGameBrowserScreen` | Save/Load Browser -> Main Menu (single-player context) |
| `mulfade.bik` | `RunMultiplayerSetupScreen` (5 sites) | Multiplayer Setup <-> its own sub-dialogs (host/join/session-list) |
| `mul2main.bik` | `RunMultiplayerSetupScreen` (2 sites) | Multiplayer Setup -> Main Menu |
| `mulfade2.bik` | `RunSaveLoadScreen` | Save/Load screen -> Main Menu (multiplayer context) |
| `igo2mm.bik` | `RunInGameOptionsScreen` | In-game pause menu -> Main Menu (quitting the mission entirely) |
| `igofade.bik` | `RunInGameOptionsScreen` (5 sites) | In-game pause menu <-> each of its own sub-screens |

### The pattern: every options sub-screen plays a different fade depending on which parent invoked it

`RunControlsOptionsScreen`/`RunSoundOptionsScreen`/
`RunVideoOptionsScreen` and `RunSaveGameBrowserScreen` are each reused
from TWO different parent contexts -- the ordinary main-menu Options
screen / New-Game-Setup flow, and the in-game pause overlay
(`RunInGameOptionsScreen`) reachable mid-mission. Rather than track
which context is active with a flag and pick a background at draw
time, the game simply gives each shared sub-screen **two parallel
sets of transition clips** (`OPTFADE2`/`OPFAD2MM` for the main-menu
path, `IGOFADE2`/`IGOF2MM` for the in-game-pause path; `SINFADE2`/
`SIFAD2MM` similarly for the save-browser's two contexts) -- a
call-site-selected pair rather than a state-selected one.
**Confidence 5** on the whole map -- every entry above is a direct
`get_xrefs_to`/`get_bulk_xrefs` result, not inferred from filenames
alone.

### Open follow-ups

- `RunMultiplayerDebriefScreen`'s exact relationship to the main
  mission-completion flow (`InitializeMissionGameplay`/
  `RunMissionGameplay`, documented many passes ago) -- not traced this
  pass, only its own internals were read.
- Whether any additional `.bik` calls exist inside `WinMain` itself
  for the 3 `RunMultiplayerDebriefScreen` call sites' own surrounding
  transitions.

## Pass 61 -- The `.tga` format decoded: genuine standard Targa, and a major correction to the master-palette source (2026-09-09)

Direct request: decode StarLancer's `.tga` format. Short answer:
**it's real, standard Targa** -- no custom framing at all, beyond the
same optional whole-file RefPack wrapper already documented for
`.spr`/`.fnt`/`.SHP` (loose files in `RESOURCE/` are RefPack-compressed;
the raw `cd1`/`cd2` disc-extracted copies are plain, uncompressed
standard TGA). Verified directly against real files' headers
(`idLength`, `colorMapType`, `imageType`, `width/height`, `bpp` all
exactly where the TGA 1.0 spec puts them) and, far more importantly,
against the engine's OWN functions -- which name themselves.

### `SR_TGA_allocate_palette`/`SR_TGA_get_palette` (`0x4cacb0`/`0x4ca9b0`, were `FUN_004cacb0`/`FUN_004ca9b0`)

Both self-identify via their own `ReportAssertionFailureEx` strings
(`"SR_TGA_allocate_palette: ..."`/`"SR_TGA_get_palette: ..."`) -- no
guessing involved. Together: load a named `.tga` file whole
(`SR_FileAlloc`), assert its `bpp` field (offset `0x10`/16, exactly
where the TGA spec puts bits-per-pixel) equals 8, then read its
**standard embedded 256-entry BGR color map** (only when `imageType`
is 1 or 9 -- uncompressed or RLE color-mapped, and `colorMapType != 0`
-- exactly the TGA spec's own color-map presence flag) starting right
after the header + image-ID field (`18 + idLength`, per spec), into a
freshly-allocated 768-byte RGB buffer.

### Major correction: the master 256-color RGB palette comes from a `.tga` file, not the `.ccb` file

Pass 25/30 attributed the RGB-triple-to-native-pixel-format packing
loop's source data ("Block A") to the `.ccb` loader's own result.
Tracing the actual literal string arguments at `InitializeGraphicsDevice`
(`0x4acbe0`) shows this was wrong: **two separate calls happen, to two
separate files**:

```c
// InitializeGraphicsDevice, real sequence (ECX args now visible):
renderState->tgaPalette = SR_TGA_allocate_palette(mode==0 ? "softpal.tga" : "palette.tga");
renderState->ccbData    = SR_CCB_load(mode==0 ? "softpal.ccb" : "palette.ccb");
```

`renderState->tgaPalette` (`+0x1602`) is what the packing loop
documented in Pass 25/30/54 actually reads -- **the master RGB
palette is a standard TGA color map, not `.ccb` data.** The `.ccb`
file's own content (`+0x1606`) is something else entirely (Pass 30's
"Block B" 12-shade-ramp hypothesis remains open, now definitely
NOT competing with Block A for the same source). Same pattern
confirmed at `InitializeLoadoutScreen` (loads `palette3.tga`
alongside `palette3.ccb`, mirroring Pass 53's finding) and inside a
large HUD-initialization function (loads `oldpalette.tga` for a
HUD-local gradient-icon palette copy, separate from the main render
palette). **Confidence 5** -- this is about as direct as reverse
engineering gets: the loader's own assertion strings name the file
format, and the exact filenames are read as literal call arguments,
not inferred.

### This resolves 2 of Pass 53's 3 mystery "extracted" palette dumps

Decoded `palette.tga`/`softpal.tga`/`palette3.tga`/`oldpalette.tga`'s
real embedded color maps directly (per the algorithm above,
implemented ad hoc in Python) and compared against the unexplained
`gamedata/StarLancer/extracted`/`out_softpal` dumps flagged in Pass 53:

- `palette.tga`'s color map: `(125,190,120), (120,182,115),
  (115,173,111), ...` -- **matches** `extracted/PALETTE_0_32cols.pal`'s
  `(125,190,121), (121,182,113), (113,174,109), ...` to within
  rounding. **Confirmed: `extracted/PALETTE_N` = `palette.tga`'s color
  map.**
- `softpal.tga`'s color map: `(0,0,0), (8,8,8), (16,16,16), (25,25,25),
  ...` -- **matches** `out_softpal/SOFTPAL_0_32cols.pal`'s `(0,0,0),
  (8,8,8), (16,16,16), (24,24,24), ...` to within rounding.
  **Confirmed: `out_softpal/SOFTPAL_N` = `softpal.tga`'s color map.**

`out_palettes/POWER_N`'s warm fire/glow-toned ramp remains unexplained:
checked every color-mapped `.tga` in `RESOURCE/` (`curpal`, `ddlaserr`,
`ddwarp128`, `interpal`, `oldpalette`, `palette`, `palette2`,
`palette3`, `softpal`) and none match; `powerball.TGA` -- the one file
whose name plausibly matches "POWER" -- turns out to be a 24bpp
TRUE-COLOR targa (`imageType=2`, no color map at all), definitively
ruling it out. **Confidence 5 that POWER_N's source is not any `.tga`
file examined this pass**; its provenance is still an open question.

### Other `.tga` usage catalogued (from the full `.tga` string sweep)

- **Splash screens**: `sl_splash.tga`/`sl_splash800.tga`/
  `sl_splash1024.tga` (resolution-specific variants), `splash.tga`.
- **Screenshot output**: `screenshot%04d.tga` -- confirms `.tga` is
  also this game's save-a-screenshot format (a standard, sensible
  choice, unrelated to the palette system above).
- **Transition-video poster frames**: nearly every `INTERFACE\*.bik`
  fade clip catalogued in Pass 60 has an identically-named `.tga`
  sibling (`main2opt.tga`, `sinfade.tga`, `igofade.tga`, `mulfade.tga`,
  `optfade.tga`, `igoptfad.tga`, `ingameop.tga`, etc.) -- almost
  certainly a static first/last-frame still shown instantly while the
  real `.bik` loads, or a fallback for when video is disabled, though
  the actual display code for these wasn't traced this pass.
- **VR room backdrops**: `brd2cd.tga`/`rel_bunk2cd.tga` -- real
  640x480 24bpp RLE-compressed (`imageType=10`) true-color images,
  confirmed via direct header read.
- **Misc textures**: `powerball.tga` (24bpp truecolor, not
  color-mapped), `space.tga`, `fpanels.tga`/`background.tga`/
  `rbackground.tga` (generic UI backdrop panels), `nebula\starref12.tga`.

### Open follow-ups

- `out_palettes/POWER_N`'s real source -- not any `.tga` file checked
  this pass; may need to check `.SHP`/`.spr` embedded palettes (Pass
  59's "fake shape 0" mechanism) or non-`RESOURCE/`-directory assets.
- The actual consumer/display code for the `.bik`-sibling `.tga`
  poster-frame stills -- not traced.
- Pass 30's "Block B" (`.ccb`'s own real content, `renderState+0x1606`)
  -- still not independently pinned down now that it's confirmed NOT
  to be the RGB palette.

## Pass 62 -- The campaign pilot setup flow decoded, correcting a mislabel from Pass 46 (2026-09-09)

Direct request: reverse engineer the campaign pilot (new-game/career)
setup flow. Full re-decompile of `RunNewGameSetupScreen` (`0x430490`)
and its two direct callees turned up a real correction to Pass 46's
button-case labels, plus the actual pilot-profile creation mechanics.

### Correction: cases 0/1 are pilot GENDER, not "difficulty A/B"

Pass 46 labeled `RunNewGameSetupScreen`'s hotspot cases 0 and 1
"difficulty A/B" from context alone. Tracing what they actually write
(`g_wPilotGenderIsFemale`/`g_dwNewPilotGenderIsFemaleUI`, renamed this
pass from `DAT_00562f16`/`DAT_0051da54`) and where those fields get
read shows otherwise:

- `FUN_004536d0` (a format-string picker) chooses between two literal
  templates depending on `g_wPilotGenderIsFemale`: **`"mp%s"`** (male
  pilot) when 0, **`"fp%s"`** (female pilot) otherwise -- read directly
  from memory, not inferred.
- `FUN_00441100` (sets up the in-game pilot-record/kills display,
  loading `inter\itac\kills.spr`) derives a display field directly
  from the same flag.
- `g_dwNewPilotGenderIsFemaleUI` additionally gates which portrait
  shape gets drawn on the setup screen itself (a visible male/female
  preview toggle).

**Confidence 5** -- cases 0/1 are the **pilot gender selector**
(Male/Female), not a difficulty setting. This is an explicit
correction to Pass 46's writeup, not a silent edit.

### The real difficulty selector: `RunDifficultySelectDialog` (`0x430300`, was `FUN_00430300`)

Reached via `RunNewGameSetupScreen` case 3 ("confirm new pilot" --
see below). A small 4-hotspot modal:

- case 0: confirm (returns 1 -- proceed with pilot creation at the
  currently-selected difficulty)
- case 1 / Escape: cancel (returns 0, back to the setup screen)
- case 2/3: cycle `g_wCampaignDifficulty` (renamed from
  `DAT_00562f14`) backward/forward through exactly 3 values, wrapping
  0-2

`g_wCampaignDifficulty` is read directly by `ScaleDamageForDifficulty`
(documented many passes ago as implementing the exact Easy/Normal/Hard
damage curve) -- **confirming this dialog is the real, only, 3-tier
campaign difficulty picker**, cleanly separate from the gender toggle
it's easy to conflate it with on the same parent screen.

### `RunNewGameSetupScreen`'s full, corrected button map

| Case | Action |
|---|---|
| 0 | Set pilot gender = Male |
| 1 | Set pilot gender = Female |
| 2 | Load Existing Pilot -> exits to screen `0xd` (`RunSaveGameBrowserScreen`) |
| 3 | Confirm New Pilot -> opens `RunDifficultySelectDialog`; on confirm, calls `LoadPlayerProfile` and returns 1 (proceed into the game) |
| 4 | Exit to main menu |
| 5 | Reset (re-arms the cursor-blink/redraw flag; likely "clear typed callsign", not independently confirmed) |
| 6 | Options dialog |
| 7 | Toggle the recent-name list panel (`DAT_005202b8`, confirmed in Pass 48) |

### `LoadPlayerProfile` (`0x4751b0`): loads OR silently creates a new pilot's `profile.bin`

The function that actually commits a new pilot into existence.
Zeroes a large in-memory profile structure (mission/campaign-state
fields, a small AI-wingman/roster-status sub-array with `0xffff`
sentinel entries) then tries to open `"profile.bin"` for read
(`FUN_004d02ef`, an `fopen`-style wrapper) in the CURRENT directory --
which, following this codebase's established convention (`saves\
<callsign>\...` seen throughout the save-browser work), is set to a
per-callsign subdirectory before this call.

- **If `profile.bin` exists**: reads it in directly (`FUN_004d0003`,
  an `fread`-style call, `0xd0`=208 bytes) and returns -- an existing
  pilot's campaign progress is restored as-is.
- **If it does NOT exist**: this is the actual **new-pilot-creation
  path**. Sets sensible brand-new-career defaults --
  `DAT_00562dc8=1` (start at mission 1), all stat/score fields zeroed,
  the pilot's displayed name defaulted to a localized string
  (`GetLanguageString(0xbf)`, plausibly "Rookie" or similar) -- then
  immediately **writes a fresh `profile.bin`** (`FUN_004d02ef` opened
  for write, `FUN_004d0003` writing the same 208 bytes back out). A
  brand-new callsign therefore gets its `profile.bin` created the
  FIRST time `LoadPlayerProfile` runs for it, not via any separate
  explicit "create pilot" step.

**Confidence 4** on the overall load-or-create mechanism (directly
read); confidence 2 on the exact meaning of most individual
zeroed/defaulted fields within the 208-byte structure (only the
mission-index and name fields were identified with confidence).

### The callsign/name entry itself

Already characterized structurally in Pass 49: typing a callsign on
this screen checks/updates a 10-slot "recent pilot names" array
(`DAT_005d5e8c`, 50-byte stride, via `FUN_00430b80`) that backs the
scrollable name-list panel (toggled by case 7 above, coordinates
documented in Pass 48). The 8-entry main-button-row coordinates
(including this gender toggle and the confirm button) remain
unresolved per Pass 50's decompiler-limitation finding -- unaffected
by this pass's semantic corrections, which came from data-flow
tracing rather than coordinate recovery.

### Open follow-ups

- `profile.bin`'s remaining ~190 bytes of fields -- only the mission
  index and name were identified; the rest (stats, unlocks, per-wingman
  roster status) not mapped field-by-field.
- Case 5's exact behavior ("Reset") -- mechanism read, semantic
  meaning ("clear callsign"?) not independently confirmed.
- Whether choosing gender actually changes anything beyond the
  `"mp"`/`"fp"` asset-name prefix and the kills-screen display field --
  e.g. whether it selects a different voice-line set or portrait art
  set wholesale (plausible given the prefix convention, not traced
  further).

## Pass 63 -- `profile.bin`'s field layout decoded, verified against a real save (2026-09-09)

Direct follow-up on Pass 62's open item. Found a real sample
`profile.bin` shipped in `gamedata/StarLancer/` (208 bytes, the
player's own real save -- name `"DMJC"`) and used it as ground truth
against `LoadPlayerProfile`'s fresh-default writes and, more
importantly, `AdvanceCampaignMissionAndSaveProfile` (`0x475a90`, was
`FUN_00475a90`) -- the function that actually WRITES this struct
during play, called at end-of-mission. That second function's own
field-by-field copy from the live "session" globals into the save
struct is what makes the layout legible -- each save-struct field is
a direct mirror of a named session global, copied in one final block
at the end of that function.

### `PlayerProfile` struct (208 = `0xd0` bytes, base `DAT_00562cf8`)

```c
struct PlayerProfile {                     // written by
    uint32_t currentMissionIndex;           // = DAT_00562dc8 (mission index, post-advance)
    char     callsign[32];                  // = DAT_00562dcc mirror; NOT null-padded past the
                                             //   terminator -- short names leave uninitialized
                                             //   bytes behind them (see below)
    uint32_t highestRankTierReached;         // = DAT_00562dec mirror (a "high water mark" index
                                             //   into a threshold table, see below)
    uint32_t perMissionSpecialFlag;          // = DAT_00562df0 mirror (per-mission lookup value,
                                             //   role not fully confirmed)
    uint32_t cumulativeScore;                // = DAT_00562df4 mirror (compared against a rank-
                                             //   threshold table to compute highestRankTierReached)
    uint32_t reserved1[6];                   // = DAT_00562dfc mirror, unidentified
    uint32_t reserved2[6];                   // = DAT_00562e14 mirror, unidentified
    int16_t  perMissionRankSnapshot[28];      // = DAT_00562e2c mirror, sentinel 0xFFFF = "not
                                             //   yet played"; real save has missions 0/1 = 4
    int16_t  perMissionScoreSnapshot[28];     // = DAT_00562e64 mirror, 0 = untouched; real save
                                             //   has [0]=0,[1]=9,[2]=21 (increasing -- consistent
                                             //   with a growing score/kill count over missions)
};
```

**Confidence 5** on the overall field boundaries and sizes (directly
read from both the writer's copy loops and the fresh-default writer's
same offsets, and cross-checked byte-for-byte against the real 208-byte
sample file); **confidence 3** on `highestRankTierReached`/
`cumulativeScore`'s semantic labels (well-supported by the
threshold-table comparison pattern below, not independently confirmed
against a HUD/UI display of "rank"); **confidence 1** on
`perMissionSpecialFlag` and the two `reserved` blocks.

### The rank-progression mechanic, read directly from `AdvanceCampaignMissionAndSaveProfile`

```c
// simplified from the real decompile
iVar9 = <index of the first entry in threshold table &DAT_005009f4 that
         exceeds DAT_00562df4 (cumulativeScore)>;   // a ~9-entry short table
if (DAT_00562dec < iVar9) {          // new high-water mark?
    DAT_00562dec = iVar9;            // highestRankTierReached = iVar9
    (&DAT_00562ed4)[DAT_00562dc8] = iVar9;
}
```

This is a genuine **score-to-rank-tier lookup**: the player's
cumulative score is compared against an ascending threshold table
(`DAT_005009f4`, spanning `0x500a06-0x5009f4 = 0x12` bytes = 9
`int16_t` thresholds -- a 9-tier rank ladder), and the highest tier
ever reached is tracked as a persistent high-water mark, plus recorded
per-mission. **Confidence 3** that this is specifically a military
*rank* progression (StarLancer's real UI/lore terminology for these
tiers wasn't independently confirmed -- `GetLanguageString` calls
nearby resolve to runtime-only localized text) rather than some other
score-tier concept, but the mechanical shape (threshold table +
high-water mark) is directly read, not guessed.

### The real sample file, decoded field-by-field

| Field | Value in `gamedata/StarLancer/profile.bin` |
|---|---|
| `currentMissionIndex` | 3 |
| `callsign` | `"DMJC"` (4 chars; bytes 5-35 of the 32-byte field are uninitialized leftover data, NOT null-padding -- see below) |
| `highestRankTierReached` | 0 |
| `perMissionSpecialFlag` | 0 |
| `cumulativeScore` | 30 |
| `perMissionRankSnapshot` | `[4, 4, -1, -1, ..., -1]` (missions 0/1 recorded at tier 4; rest unplayed) |
| `perMissionScoreSnapshot` | `[0, 9, 21, 0, 0, ..., 0]` |

### A real, confirmed uninitialized-memory quirk

`LoadPlayerProfile`'s fresh-profile path copies the default callsign
with an EXACT `strlen+1`-byte copy (not a fixed 32-byte fill), so any
bytes in the 32-byte `callsign` field past the terminator are simply
whatever was already in that memory -- never cleared. The real sample
file proves this isn't just a theoretical reading: byte 5 (right
after `"DMJC\0"`) is `0x1b` (27), a stray non-zero leftover, with the
rest of the field genuinely zero (from a separate, later zeroing loop
that happens to cover the REST of the buffer, but not the one byte
immediately after a short name -- the exact boundary depends on the
zeroing loop's stride vs. the name's length). **Confidence 5** -- this
is directly observable in the shipped file, not inferred.

### `RefreshActiveCallsignFromProfile` (`0x475390`, was `FUN_00475390`)

Smaller than expected: re-reads `profile.bin` from disk, then copies
ONLY the `callsign` field into the active-session global
`DAT_00562dcc` (used throughout the codebase for save-path
construction, HUD display, etc.). It does not "apply" any of the
other fields to separate named globals -- the rest of
`PlayerProfile`'s fields are read directly out of the
`DAT_00562cf8`-based struct by whatever code needs them, rather than
being unpacked into a separate parsed representation.

### Open follow-ups

- `perMissionSpecialFlag`/the two 6-dword `reserved` blocks -- not
  identified.
- Whether `highestRankTierReached`'s 9-tier table maps to real named
  military ranks anywhere in the localized string data (blocked on
  runtime-only language strings, same limitation as Pass 37/48).
- `DAT_0050099f`/`DAT_005009d7`/`DAT_005009bb` (the three small
  per-mission-indexed flag/lookup tables read in
  `AdvanceCampaignMissionAndSaveProfile`) -- not mapped beyond their
  role in the mission-advance/rank logic already described.

## Pass 64 -- `profile.bin`'s remaining fields resolved: hub-room unlock flags and debrief-text gates (2026-09-09)

Direct follow-up on Pass 63's open items. Traced the consumers of the
two "reserved" 6-dword blocks and the three small per-mission-outcome
tables (`DAT_0050099f`/`DAT_005009d7`/`DAT_005009bb`) referenced from
`AdvanceCampaignMissionAndSaveProfile`.

### `reserved1`/`reserved2` (`PlayerProfile+0x30`/`+0x48`) = hub-room prop/hotspot "enabled" flags

`RenderBriefingHubFrame` (`0x436b20`, was `FUN_00436b20` -- the
briefing-hub room's per-frame Bink-decode-and-render callback,
sibling to the already-documented `FUN_0043c1c0`) reads
`DAT_00562dfc`/`DAT_00562e14` (the live-session mirrors of these two
fields) as **two parallel 6-entry boolean arrays**, gating which of
several named interactive hub-room hotspots currently render/respond
this frame -- each nonzero entry unlocks one specific
`VFX_shape_draw` call at a specific screen position with a specific
language-string label. The function switches between **two entirely
different lookup-table sets** depending on `DAT_00562dc8 < 0x13`
(mission index 19) -- consistent with the "two parallel ship-layout
graphs, early vs. late campaign" structural finding from several
passes ago (Pass ~33). **Confidence 4**: these fields are genuinely
"which hub-room props/hotspots are currently active," persisted
per-pilot so the hub room's interactive state survives a save/reload;
confidence 2 on which SPECIFIC named hub-room objects each of the 12
flags corresponds to (not individually identified this pass).

### `perMissionSpecialFlag` and the three small tables = mission-debrief narrative gates

`BuildMissionDebriefText` (`0x424cf0`, was `FUN_00424cf0` -- the
post-mission debriefing text-panel builder, string-concatenating
multiple localized fragments into a scrollable report) reads
`DAT_0050099f`/`DAT_005009d7`/`DAT_005009bb` -- three small
byte tables, each indexed by a per-mission outcome-branch value
(`(&DAT_004e4954)[missionChoiceIndex*4]`, the SAME outcome-branch
mechanism documented back in Pass 25) -- as **boolean gates deciding
whether to append an extra optional paragraph** of debrief narrative
text. One of these gates (`DAT_005009bb[outcomeIndex] != 0`) is
additionally ANDed with `(&DAT_00562e2c)[missionIndex] == 4` --
**directly using `perMissionRankSnapshot`'s stored value to decide
whether a commendation/rank-flavored debrief paragraph gets shown**,
which is strong independent confirmation that Pass 63's "rank" label
for that array is on the right track (a rank-tier value of exactly 4
unlocks specific narrative text, consistent with "reached a specific
performance tier this mission"). **Confidence 3** overall for this
mechanism; the exact narrative content itself is runtime-only
localized text and wasn't recovered.

### Updated `PlayerProfile` field notes (supersedes Pass 63's confidence-1 "unidentified" labels)

- `reserved1[6]`/`reserved2[6]` -> **hub-room hotspot/prop enabled-flags** (confidence 4 on role, 2 on individual mapping).
- `perMissionSpecialFlag` -> one of three debrief-narrative gate flags, this specific one indexed by `DAT_0050099f`/`DAT_005009d7` rather than a single field (confidence 2).

### Open follow-ups

- Map each of the 12 `reserved1`/`reserved2` bit-positions to a named
  hub-room object (the VR ship interior room graph, documented many
  passes ago, is the natural cross-reference target).
- The exact narrative content gated by these debrief flags -- runtime-
  only localized strings, not recoverable statically.
- `DAT_0052a460` (read in `BuildMissionDebriefText`'s outcome-index -1
  branch) -- a plausible "is this a fresh/first-time debrief" flag,
  not traced further.

## Pass 65 -- CONFIRMED: the mission-19 threshold is the ANS Reliant -> ANS Yamato transfer (2026-09-10)

User-supplied narrative context: the player starts the campaign aboard
the **ANS Reliant**, which is destroyed partway through, transferring
the player to the **ANS Yamato** for the rest of the game. This
directly and precisely confirms/grounds a structural finding several
passes had been circling without a narrative anchor: the recurring
`DAT_00562dc8 < 0x13` (mission index 19) branch found independently in
`RenderBriefingHubFrame` (Pass 64), `AdvanceCampaignMissionAndSaveProfile`
(Pass 63), and a much earlier "two parallel ship-layout graphs" note
(circa Pass 33), all switching between an early-campaign and
late-campaign table/asset set.

### Direct string confirmation

`search_strings` for `reliant`/`yamato` turns up exactly the asset
pair this context predicts:

- `reliant.shp` / `yamato.shp` -- the two carriers' own 3D models (the
  tagged-chunk format decoded in Pass 55/56).
- `reliant_hang.shp` -- the Reliant's hangar bay model.
- `reliant_destback.shp` / `"Yamato DestBack.shp"` -- **destroyed
  backdrop variants for BOTH ships** (`DestBack` = "destruction
  background"), consistent with a scripted destruction sequence
  needing its own wreckage/damage backdrop asset.
- `"reliant_induction resource: error loading %s."` -- an "induction"
  (onboarding/orientation) sequence specific to the Reliant, plausibly
  the game's opening tutorial-adjacent sequence.
- `new_reliant_transfer.bik` -- a cutscene literally named for the
  transfer event itself.

### The exact trigger, read directly from `WinMain`'s cutscene-selection logic

```c
// WinMain, simplified from the real disassembly (address 0x4a9fd5 area)
if (DAT_00562dc8 < 0x13) {                  // still aboard the Reliant (missions < 19)
    if (DAT_0052a470 != 0) {                // "haven't shown the transfer cutscene yet" (defaults to 1)
        moviePath = "new_reliant_transfer.bik";
    } else {
        moviePath = "new_a_y_trans.bik";    // already shown once -- generic transfer-themed filler
    }
} else {                                    // aboard the Yamato (missions >= 19)
    moviePath = "new_a_y_trans.bik";
}
PlayMovie(moviePath);   // FUN_004abb80
```

**Confidence 5** -- directly read, not inferred: the campaign's
ship-transfer story beat is hard-coded to fire exactly once, keyed on
crossing the mission-19 boundary, gated by `DAT_0052a470` (a session
flag defaulted to 1 by `LoadPlayerProfile`, i.e. "not yet shown" by
default) so it plays the dedicated transfer cutscene only the first
time and falls back to a generic filler clip afterward (e.g. on
replaying an earlier mission in that range).

### The same threshold picks ship-specific asset variants elsewhere too

A second, independent site in `WinMain` (`~0x4aa53f`) makes the exact
same `DAT_00562dc8 < 0x13` comparison to choose between
`"new_rel_exec.bik"` (Reliant variant) and `"new_y_exec.bik"` (Yamato
variant) for what's evidently a recurring scene (an "exec[utive
officer]" meeting/briefing clip, given the naming) that exists in two
ship-specific versions. **This is now the third independent site**
(alongside `RenderBriefingHubFrame`'s hub-room hotspot tables and this
cutscene-selection logic) using the identical mission-19 cutoff to
switch which ship's assets are active -- strong, repeated confirmation
that mission 19 is precisely where the game's internal model of
"which carrier you're aboard" flips.

### Updated confidence: earlier findings this grounds

- The "two parallel ship-layout graphs, early vs. late campaign"
  structural note (circa Pass 33) is now **confirmed as literally the
  Reliant's interior vs. the Yamato's interior**, not just two
  arbitrary layout variants -- confidence raised from "plausible
  given campaign progression" to 5.
- `RenderBriefingHubFrame`'s (Pass 64) early/late hub-room hotspot
  table switch is the same event: the hub room's *set of interactive
  props* changes because **it's a physically different room on a
  different ship** after the transfer, not a cosmetic/difficulty-based
  variant.
- `AdvanceCampaignMissionAndSaveProfile`'s (Pass 63) special-case
  mission jumps (`0xb`/`0xc`->`0xe`, `0x10`->`0x12`, `0x15`->`0x17`)
  sit on either side of this boundary (11/12->14 and 16->18 are
  pre-transfer, 21->23 is post-transfer) -- plausibly skipping
  missions that don't exist in a given player's branch, now
  understood against a concrete timeline rather than an abstract
  mission-index sequence.

### Open follow-ups

- `DAT_0052a470`'s exact set-to-0 site (confirming it truly means
  "transfer cutscene already shown," not just inferred from its
  read-site behavior and its `LoadPlayerProfile` default of 1) -- not
  located this pass.
- The Reliant "induction" sequence's role (opening tutorial? crew
  introduction?) -- only its error-string existence confirmed.
- Whether any OTHER mission-index thresholds besides `0x13` correspond
  to further story beats (the campaign has ~29 missions total; this
  pass only investigated the one boundary the user's context pointed
  at).

## Pass 66 -- The missing AI link found: `UpdateShipAiTick` and the real AI state STACK (2026-09-10)

Direct continuation of the combat-AI thread. Picked up the oldest
unresolved item in that whole line of investigation (flagged back in
the twentieth pass): *"the actual link between `QueueAiEvent`'s queue
and `TrySetAiState`'s state transitions... finding whatever reads
`object+0xb90`'s queue would settle this."* Found it via
`search_byte_patterns` on the `+0xb8c` displacement bytes, which
turned up a previously untouched function right next to
`TrySetAiState` itself.

### `UpdateShipAiTick` (`0x40c5f0`, was `FUN_0040c5f0`) -- the per-object AI tick, confirmed called from `ProcessMissionSimulationTick`

```c
void __fastcall UpdateShipAiTick(int shipSlot);
```

Does exactly two jobs, run once per AI-controlled object per
simulation tick:

1. **Drains the perception/event queue** (`QueueAiEvent`'s buffer,
   Pass 20) entry by entry: an event is eligible once its expiry tick
   has passed (`event.expiry <= currentTick`) AND -- this is the
   actual missing link -- **its state-catalog priority is `>=` the
   ship's CURRENTLY ACTIVE state's priority** (the exact same
   priority lookup `TrySetAiState` itself performs, Pass 17/18). An
   eligible event gets its payload copied straight into the ship's
   active AI-state record and is removed from the queue (shifting the
   rest down) -- perceptions really do become state data once they
   win the same priority gate real explicit `TrySetAiState` calls go
   through elsewhere.
2. **Runs the current (top-of-stack) AI state's callbacks**: if the
   state was just entered (a `+0x688` "fresh" flag), calls its slot-0
   (**OnEnter**) callback once and clears the flag; always calls
   slot-4 (**OnUpdate**) every tick -- confirming Pass 18's
   "plausibly OnEnter/OnUpdate" guess for the state catalog's two
   leading callback slots. If the state's catalog flags have the
   `0x20` ("unconditional transition") bit set, it runs OnUpdate, then
   an unopened `FUN_0040ce70`, then **recurses into itself** --
   unconditional-transition states re-evaluate immediately within the
   same tick rather than waiting for the next one.

**Confidence 5** -- directly read, and the queue-to-priority-gate
connection is exactly the mechanism this project had been assuming
existed but never located for 46 passes.

### `PushAiState` (`0x40cc10`, was `FUN_0040cc10`) -- correcting the "AI command structure" model: it's a real 20-entry STACK

Called by `UpdateShipAiTick` above (and, per Pass 17's
`SetShipDestroyedState`, by other gameplay code directly) to actually
commit a new AI state. Reading it fully **corrects and completes**
Pass 17's tentative "AI command/state structure... pushes a command
onto it" description: `object+0x684`/`object+0x680` are the base
pointer and DEPTH of a genuine **pushdown stack of up to 20 AI
states** (`0x208` = 520 bytes = 20 x 26-byte entries; the push is
refused once depth exceeds `0x13`), not a single current-state slot.

- **Early-out**: if the requested state+params are already an exact
  match for the CURRENT top-of-stack entry, skips straight to success
  without calling `TrySetAiState` again (avoids redundant re-entry
  every tick for a state that keeps re-requesting itself).
- **Priority gate**: otherwise calls `TrySetAiState` itself first;
  bails out entirely if it refuses.
- **Move-to-front deduplication**: searches the REST of the existing
  stack for an entry matching the new state+params; if found, removes
  it from its current position (shifting entries above it down) so it
  can be re-pushed at the top instead of creating a duplicate deeper
  in the stack -- a ship's history of "what it was doing before"
  doesn't accumulate duplicate entries.
- **Lazy allocation**: the first time a ship needs this stack, allocates
  BOTH the 520-byte state-stack buffer and a separate 144-byte
  (`0x90`) scratch buffer (`object+0x68c`) -- source-tagged
  `C:\lancer\game\aigeneric.cpp`, confirming a dedicated AI source
  file distinct from the already-known `Ai.cpp`.
- **On a real (non-duplicate) push**: shifts every existing entry up
  one slot, writes the new state's 3 parameters and state ID into the
  new top slot, zeroes 4 payload fields (the same fields
  `UpdateShipAiTick` copies FROM a queued event INTO this exact
  struct -- confirming those fields are event-carried context data,
  reset to 0 for an explicitly-requested state that didn't come from
  the event queue). If the new state ISN'T an "unconditional
  transition" state, sets the `+0x688` "freshly entered" flag (which
  `UpdateShipAiTick` reads to fire the one-time OnEnter callback) and
  zeroes the 144-byte scratch buffer for the new state's own working
  data. Finally tags the entry with an incrementing generation ID
  (`DAT_005185a8`) when a global flag (`DAT_005185b1`) is set, and
  increments the stack depth.

**Confidence 5** -- directly read in full. This is a materially
different (and more complete/correct) model than Pass 17's original
"AI command/state structure" language: it's specifically a **bounded,
deduplicating pushdown stack**, which explains why a ship can
meaningfully "resume its previous behavior" after a transient state
(like a scripted attack or a queued perception) finishes -- popping
back to whatever was underneath, rather than the game needing a
separate "previous state" field.

### `FUN_0040ca00` -- a minor bounds/flag gate, not fully characterized

`PushAiState`'s very first check. Reads as roughly "reject if
`shipSlot` fails a comparison against `DAT_0058832c` (a
player-count-shaped global, sense not independently re-verified
here), or the requested state's catalog index exceeds 99, or the
target state's own catalog flags have bit `0x1` set." **Confidence 1**
on the exact semantics -- flagged honestly rather than asserted, since
the direction of the first comparison didn't cleanly fit either
"blocks player states" or "blocks AI states" on a quick read.

### Open follow-ups

- `FUN_0040ca00`'s exact semantics (which ships/states it actually
  blocks) -- needs a more careful re-read or a live-debugging check.
- `FUN_0040ce70` (called for unconditional-transition states before
  `UpdateShipAiTick` recurses) and `FUN_0040c520` (the flags-bit-`0x40`
  callback in the same function) -- not decompiled.
- The generation-ID mechanism (`DAT_005185a8`/`DAT_005185b1`) --
  purpose not traced (plausibly multiplayer state-sync versioning,
  not confirmed).
- Cross-reference the 12-per-object `reserved1`/`reserved2` hub-room
  flags (Pass 64) against this AI system -- unrelated systems as far
  as traced, but both live in similarly-shaped per-object structures,
  worth a sanity check if confusion arises later.

## Pass 67 -- Mapping 14 specific `.tga` images to their exact call sites (2026-09-10)

Direct request: map out where a specific list of `.tga` files is used.
Method: located each literal string, then resolved every
cross-reference to its containing function via `get_bulk_xrefs` +
`get_function_by_address`. One naming note up front: the requested
`igoptfade.tga` doesn't exist under that exact spelling -- the real
file (confirmed in Pass 58/61) is `igoptfad.tga` (no final "e"),
mapped below under its real name.

| File | Loaded from | Notes |
|---|---|---|
| `splash.tga` | `LoadGenericSplashBackdrop` (`0x4ab3f0`, was `FUN_004ab3f0`) -- called by `ShowMissionLoadingScreen` (`0x4ad0a0`, was `FUN_004ad0a0`), itself called from `WinMain` (3 sites), `RunMissionSelectMapScreen`, and `RunMainMenuScreen` | The generic "loading, please wait" backdrop shown while a mission/screen transition is in flight -- not resolution-specific, used from many different top-level transition points. |
| `sl_splash.tga` / `sl_splash800.tga` / `sl_splash1024.tga` | `LoadStartupSplashBackdrop` (`0x4ab4b0`, was `FUN_004ab4b0`), called exactly once, from `InitializeGraphicsDevice` at startup | All 3 filenames are loaded via a jump table Ghidra couldn't fully recover (`"Could not recover jumptable"` warning) -- read as a resolution-tiered choice (default/800-wide/1024-wide) based on the filename pattern, not independently confirmed per-branch this pass. |
| `sl_splash2.tga` | Directly inside `RunMainMenuScreen` (`0x428ba7`) | A second, separate splash image shown from the main menu itself, NOT part of the startup selection above. |
| `sinfade.tga` | `RunNewGameSetupScreen` (`0x430a61`) | The static poster-frame counterpart to `sinfade.bik` (Pass 60's transition-video catalog) -- same screen, same transition. |
| `main2opt.tga` | `RunOptionsMenuScreen` (`0x42a6e1`) | Loaded by the ARRIVING screen (Options), not the departing one -- `main2opt.bik` plays from `RunMainMenuScreen` (Pass 60) as you leave, while this `.tga` is shown by Options as you land, plausibly as an instant placeholder while the room's own content loads. |
| `main2sin.tga` | `RunNewGameSetupScreen` (`0x4306cc`) | Same arriving-screen pattern as `main2opt.tga` above. |
| `mulfade.tga` | `RunSaveLoadScreen` (3 sites: `0x43cf03`, `0x43d5be`, `0x43d5f9`) and `RunMultiplayerLobbyScreen` (`0x44c0f1`) | Shared across two different screens -- both reachable from/adjacent to multiplayer flows. |
| `optfade.tga` | `RunOptionsMenuScreen` (3 sites: `0x42a7a2`, `0x42a7d3`, `0x42a800`) | All 3 sites are within the Options screen's own sub-screen-transition paths (mirrors `optfade.bik`'s 3 call sites documented in Pass 60). |
| `igofade.tga` | `RunInGameOptionsScreen` (`0x43977a`) | Poster-frame sibling of `igofade.bik` (Pass 60). |
| `igoptfad.tga` (not `igoptfade.tga`) | `RunMultiplayerDebriefScreen` (`0x429c56`) and `RunInGameOptionsScreen` (4 sites: `0x43969f`, `0x4396fa`, `0x439744`, `0x439795`) | Shared background texture between the two screens -- matches Pass 60's finding that both reuse the same "in-game overlay" dimming backdrop. |
| `ingameop.tga` | `RunInGameOptionsScreen` (5 sites: `0x439610`, `0x4396d5`, `0x43972b`, `0x439761`, `0x4397b2`) | This screen's own primary backdrop -- loaded far more times than any other single screen in this list, consistent with it being the base background redrawn behind every one of `RunInGameOptionsScreen`'s own sub-transitions. |
| `briefdoor` (no literal `.tga` suffix in the string itself -- likely appended by the loader) | `RunMissionBriefingScreen` (`0x437129`), with a SECOND, ship-specific variant at a sibling string address (`0x4e8a28`) | Selected by `DAT_00562dc8 > 0x12` (mission 19+) -- **the exact ANS Reliant/ANS Yamato transfer threshold confirmed in Pass 65.** The briefing-room door texture differs depending on which carrier the player is currently aboard, same as the hub-room hotspot tables and cutscene selection already documented for that boundary. |

### Correction: these `.tga` files are the real, static menu BACKGROUNDS -- not poster frames

User-supplied correction to this pass's original "poster frame /
placeholder while the video loads" framing: **the `.tga` files are the
actual persistent background image for each menu screen; the `.bik`
videos are the transition animations that play between one screen's
background and the next.** Verified directly against
`RunOptionsMenuScreen`'s real disassembly around its `main2opt.tga`
load site (`0x42a6e1`): the load (`CALL 0x004c5bd0`, a generic
image-load helper) happens ONCE, at screen setup, immediately before
the function installs its per-frame render callback
(`DAT_00588730+0x88 = 0x42afb0`) and enters its main loop -- i.e.
exactly the shape of "load the persistent backdrop, then run the
screen," not a transient placeholder swapped out once a video starts.
This reframes the whole table above: each screen loads its own named
`.tga` as its resting-state background at entry, and the
correspondingly-named `.bik` (`main2opt.bik`, `optfade.bik`,
`sinfade.bik`, etc. -- Pass 60's catalog) is the animated wipe/fade a
DIFFERENT (departing) screen plays on its way toward that background,
not something the arriving screen itself is temporarily standing in
for. **Confidence 5** on the general architecture (directly confirmed
against real disassembly); the per-file table above remains accurate
for WHERE each image loads, only the "poster frame" interpretive
language should be read as superseded by this.

**Further user-supplied detail**: which `.bik` plays is determined by
*which menu option was clicked* -- consistent with, and now the
correct interpretation of, Pass 60's own per-button transition table
(e.g. `RunMainMenuScreen` case-by-case: clicking "Options" plays
`main2opt.bik` toward `RunOptionsMenuScreen`'s `main2opt.tga`
background; clicking "Multiplayer" plays `main2mul.bik`; clicking
"New Game" plays `main2sin.bik` toward `main2sin.tga`). Pass 60
already mapped each `.bik` to the specific hotspot/case that triggers
it; this pass's `.tga` mapping is the missing other half of the same
picture -- each button click's transition target is a `(video,
destination background)` pair, not just a video.

### Open follow-ups

- The `sl_splash*.tga` jump table's exact resolution-to-file mapping --
  Ghidra couldn't recover it; would need manual disassembly of the
  jump dispatch at `LoadStartupSplashBackdrop` to pin down which
  filename goes with which detected resolution.
- `FUN_0043eaf0` (the shared loader both `briefdoor` variants call
  through) -- not decompiled; would confirm whether `.tga` is really
  appended there or the string is used as-is for some other resource
  type.
- Whether every `.bik`/`.tga` pair in Pass 60's catalog follows this
  same "video plays on the departing screen, background loads on the
  arriving one" shape, or whether some screens show their OWN video
  over their OWN background mid-session -- only `main2opt.tga` was
  checked at the disassembly level this pass; the rest are inferred
  by analogy.

## Pass 68 -- CONFIRMED: the shipboard VR interface uses the identical background/transition pattern, via one shared function (2026-09-10)

User-supplied extension of Pass 67's correction: the same
static-background-plus-transition-video architecture also applies to
the shipboard VR interior interfaces. Verified directly, and found
the mechanism is literally the SAME shared function used by the menu
system, not just an analogous but separate one.

### `SetActiveBackgroundImage` (`0x494b50`, was `FUN_00494b50`) -- the one function behind every background swap, menu or shipboard

```c
void __fastcall SetActiveBackgroundImage(char *filename);   // NULL = clear
```

Compares the requested filename against the currently-active one
(`DAT_00588744`, via a string-compare helper) and no-ops if
unchanged; otherwise updates the active-name global and calls
`FUN_00494a70` (the real load-and-display routine, not opened this
pass). **This is the exact function every menu screen calls right
before installing its per-frame callback** (confirmed for
`main2opt.tga` via `RunOptionsMenuScreen` in Pass 67) -- and it is
ALSO what the shipboard VR interior calls for its own room
backgrounds, per the example below. One shared mechanism serves both
systems; there's no separate "VR background" code path.

### Direct example: `RunCdPlayerPropScreen`'s (`0x437fc0`, was `FUN_00437fc0`) room background restore

This is the ship interior's clickable jukebox/CD-player prop
(loads `cdplay.spr`, offers play/pause/stop/track-skip/volume/repeat
controls -- a full mini-UI overlaid on top of whichever room it's
placed in). Immediately at entry, before installing its own per-frame
callback, it picks and sets the ROOM'S OWN background:

```c
// real disassembly, ~0x438363
if (DAT_00562dc8 <= 0x12) {                    // still aboard the ANS Reliant
    SetActiveBackgroundImage("rel_bunk2cd.tga");
} else {                                        // aboard the ANS Yamato
    SetActiveBackgroundImage("brd2cd.tga");
}
```

**This is now the FOURTH independent site** using the exact
Reliant/Yamato mission-19 threshold (alongside `RenderBriefingHubFrame`'s
hub-room flags, `WinMain`'s cutscene selection, and `RunMissionBriefingScreen`'s
`briefdoor` texture -- Pass 64/65/67). The jukebox prop's own overlay
(`cdplay.spr`) draws on top of this, and presumably exiting the prop's
UI simply lets this already-set background show through again --
matching Pass 67's confirmed "background persists, prop/overlay draws
on top" architecture exactly, just applied to a ship-interior object
instead of a menu screen.

### Confirmation

**Confidence 5** -- directly read at the disassembly level, not
inferred. The user's claim is correct and the underlying mechanism is
now identified precisely: `SetActiveBackgroundImage`/`FUN_00494a70`
is a single, shared background-image system used identically by
every top-level menu screen (Pass 60/67's catalog) and by shipboard
VR interior props/rooms alike. `rel_bunk2cd.tga`/`brd2cd.tga` are the
Reliant/Yamato-specific variants of whatever room background sits
"behind" the CD-player prop specifically; other VR rooms almost
certainly have their own same-pattern background pairs, keyed by
their own `.bik` room-transition names (Pass 33/44's room graph), not
individually catalogued this pass.

### Open follow-ups

- `FUN_00494a70` (the actual load-and-display routine
  `SetActiveBackgroundImage` calls into) -- not decompiled; would
  confirm exactly how the named `.tga` gets blitted/displayed.
- A full sweep of the VR room graph's other nodes for their own
  background-image pairs (only the CD-player prop's was checked this
  pass) -- the `.\inter\itac\%s.tga` parameterized path found in
  Pass 67 is a promising lead for the briefing-hub ("itac") room
  specifically.
- Whether `RunShipInteriorVRLoop`'s main per-room dispatch (not just
  this one prop sub-screen) also calls `SetActiveBackgroundImage`
  directly for each room's own resting background.

## Pass 69 -- `DisplayActiveBackgroundImage` decoded: the real TGA display pipeline, plus a second "dynamic background" path (2026-09-10)

Direct follow-up on Pass 68's open item. Fully decoded the function
`SetActiveBackgroundImage` calls into, plus its sibling entry point
and the two helpers it uses -- one of which self-identifies its exact
role via its own assertion strings.

### `DisplayActiveBackgroundImage` (`0x494a70`, was `FUN_00494a70`)

```c
void DisplayActiveBackgroundImage(void);
```

Two entirely different paths, selected by which of `SetActiveBackgroundImage`
/`SetActiveBackgroundCallback` (below) was called most recently:

1. **Callback path**: if `DAT_00588740` (a function pointer) is
   non-null, just calls it directly and returns -- a "dynamic
   background" escape hatch for screens that render something other
   than a flat image (a live 3D view, a procedural effect, etc.),
   bypassing the whole TGA pipeline entirely.
2. **Static-image path** (the common case): loads the active filename
   whole via `SR_FileAlloc` (the same generic loader used for
   `.SHP`/`.sro`, Pass 55), reads its **width/height directly from the
   real TGA header** (offsets `0xc`/`0xe`, exactly per spec, matching
   Pass 61's format confirmation), computes the destination pixel
   format via `ComputePixelFormatFromMasks` (`0x4c3430`, was
   `FUN_004c3430` -- given fixed ARGB masks `0xff000000`/`0xff0000`/
   `0xff00`/`0xff`, i.e. always decodes to 32-bit ARGB regardless of
   the source file's own bit depth), allocates a raw pixel buffer
   sized exactly `width * height * bytesPerPixel`, decodes the file
   into it via `SR_TGA_rle_uncompress` (below), then blits it through
   a renderer-state function pointer (`rendererState+0x50`) before
   freeing both buffers.
3. **Neither set** (empty filename, no callback): just calls the
   renderer's `+0x50` blit function directly with no new image --
   effectively "redraw whatever's already on screen."

**Confidence 5** -- directly read.

### `SR_TGA_rle_uncompress` (`0x4cad60`, was `FUN_004cad60`) -- a complete, correct TGA RLE decoder

Self-identified via its own three assertion strings
(`"SR_TGA_rle_uncompress: Null dest..."` /
`"...Null TGA p[ointer]..."` / `"...Destination bpp must be 1-4..."`).
A genuine, general-purpose implementation of the real Targa RLE
packet format:

- Skips the header (`18 + idLength` bytes) and, if present, the color
  map (`colorMapLength * colorMapEntrySize/8` bytes) to reach the real
  image data -- exactly the same offset arithmetic already confirmed
  for the palette reader in Pass 61.
- **Handles both TGA orientation flags correctly**: the image
  descriptor byte's bit `0x20` (top-to-bottom vs. bottom-to-top) and
  bit `0x10` (left-to-right vs. right-to-left) both flip the
  destination write direction/starting point accordingly -- a
  textbook-correct implementation, not a simplified special-case one.
- **The real RLE packet loop**: each packet's header byte's top bit
  selects a repeat-run (copy one pixel `(header & 0x7f) + 1` times) or
  a raw-run (copy that many literal pixels), exactly per the TGA 2.0
  spec's RLE compression scheme.

**Confidence 5** -- directly read, and unambiguously confirmed by its
own error strings (this project's most reliable source of ground
truth throughout, whenever available).

### `SetActiveBackgroundCallback` (`0x494bb0`, was `FUN_00494bb0`) -- the dynamic-background sibling entry point

```c
void __fastcall SetActiveBackgroundCallback(void (*renderCallback)(void));
```

Two-line sibling to `SetActiveBackgroundImage`: clears the active
filename and installs a custom render callback instead, which
`DisplayActiveBackgroundImage` will call directly in place of the
whole TGA pipeline. Confirms the background system genuinely supports
two independent kinds of "background" -- a named static image, or an
arbitrary render callback -- selected by which setter was called
last (`SetActiveBackgroundImage` always clears the callback;
`SetActiveBackgroundCallback` always clears the filename, so exactly
one is ever active).

### Open follow-ups

- No callers of `SetActiveBackgroundCallback` were located this pass
  -- finding one would show a concrete example of a "dynamic"
  (non-image) background in practice.
- `ComputePixelFormatFromMasks`'s general channel-mask-to-bpp logic
  wasn't fully re-verified against a caller using non-fixed masks
  (every call site seen so far in this project uses the same fixed
  `0xff000000/0xff0000/0xff00/0xff` ARGB8888 constants).
- The renderer-state `+0x50` function pointer itself (the actual
  blit-to-screen call) -- not traced to its target.

## Pass 70 -- The renderer `+0x50` blit target: searched exhaustively, genuinely not found (2026-09-10)

Direct follow-up on Pass 69's open item: find where
`rendererState+0x50` (the function pointer `DisplayActiveBackgroundImage`
calls to actually blit a decoded background to the screen) gets its
value written.

### Method and what was ruled out

Used `search_instructions` (semantic mnemonic/operand search, not raw
byte patterns) to search for every store to a `+0x50` struct field,
and every indirect call through one, across the whole binary:

- **Every write to `dword ptr [reg+0x50]` anywhere in the program**
  was checked. The only two candidates that looked plausible
  (`FUN_00404040`, `FUN_00412390`) turned out to be completely
  unrelated structs (gameplay/physics object fields, confirmed by
  decompiling both) -- neither touches `DAT_00588730`.
- **Every indirect call through `[reg+0x50]`** (16 total) was
  checked. Exactly 2 are the already-known `DisplayActiveBackgroundImage`
  call sites. The rest belong to unrelated structures -- including a
  genuine DirectX/DirectDraw **COM vtable call** in
  `DetectDirectXVersion` (`MOV EDX,[EAX]; CALL [EDX+0x50]` -- the
  classic `object->lpVtbl->Method()` pattern), confirming `+0x50` is
  just a common, heavily-reused small offset across many unrelated
  struct layouts in this codebase, not something unique to the
  renderer state.
- **Every plausible graphics/device/backend initialization function**
  was checked directly for a `+0x50` store and came up empty:
  `InitializeGraphicsDevice`, `SR_init` (was `FUN_004c3830`, confirmed
  via its own `"SR_init: Attempting to call SR_init..."` assertion
  string -- it zeroes a ~6KB struct and returns it, `+0x50` included
  in the zeroed range but never individually set), `FUN_004c9a40`,
  `FUN_004ab290`, `FUN_004a8600` (the device try/fallback loop),
  `FUN_004ad2e0`, `FUN_004c22b0`, `FUN_004c3000`, `FUN_004cc5a0`,
  `InitializeWinVfxLibrary`, and `WinMain` in full.
- **`InitializeWinVfxLibrary` decoded in full** while checking this --
  it resolves ~28 `VFX_*` exports from `winvfx8.dll`/`winvfx16.dll` via
  individually-named `GetProcAddress` calls into ~28 SEPARATE globals
  (`DAT_005959e4`, `DAT_005957a8`, etc.) -- **none of them write into
  `DAT_00588730` at all**. This rules out the plausible-looking
  hypothesis that `+0x50` is one slot in a sequentially-populated
  WinVFX export table.
- **`DAT_00588730` itself is assigned exactly once in the whole
  program** (`InitializeGraphicsDevice`, from `SR_init`'s return
  value) -- there is no second "reconfigure the renderer" call site
  that could be reassigning individual vtable-style fields later.

### Honest conclusion

**Not found this pass.** Despite a systematic search covering every
write to this offset pattern anywhere in the binary and every
plausible initialization function, no code writes
`rendererState+0x50`. Two explanations remain open, and neither was
confirmed:

1. It's populated via a mechanism this kind of literal-offset search
   can't catch -- e.g. a loop that computes the destination address
   as `base + i*4` at runtime rather than embedding `+0x50` as a
   literal in any single instruction (the same class of blind spot
   flagged for `object+0x670` in the Spectral Shields investigation,
   Pass 57).
2. It's set via a bulk structure copy (a `memcpy`/`REP MOVSD`-style
   block copy from a static template) that this pass didn't locate --
   one large 1299-dword `MOVSD.REP` copy was found in
   `InitializeGraphicsDevice` (into `+0x1ac` onward), but it doesn't
   cover `+0x50`.

Reported as a genuine, thoroughly-searched negative result rather
than left silently unaddressed, consistent with this project's
handling of the similar Spectral-Shields dead end.

### `+0x40` checked too -- same result, strengthening the pattern

Checked `rendererState+0x40` (the OTHER confirmed callback slot called
directly from `InitializeGraphicsDevice` itself, `(**(code
**)(DAT_00588730+0x40))()`) the same way: no store to it anywhere in
`InitializeGraphicsDevice`, and no literal `[0x00588730 + 0x40]`
pattern anywhere in the program. **Two independent renderer callback
slots now show the identical blind spot**, not just one -- this makes
explanation 2 below (some kind of bulk/computed population this
project hasn't located, rather than a one-off oddity specific to
`+0x50`) the better-supported reading, though still not confirmed.

### Open follow-ups

- A live-debugging pass (set a hardware write-breakpoint on
  `DAT_00588730+0x50`/`+0x40` while the game runs) would settle this
  definitively where static search has now been exhausted.
- Check the remaining renderer callback slots referenced elsewhere in
  this project (`+0x78`, `+0x7c`, `+0x80`, `+0x88`, `+0x8c`, `+0x90`)
  the same way -- if they show findable write sites while `+0x40`/
  `+0x50` don't, that would narrow down what's special about this
  particular pair.

## Pass 71 -- The ITAC interface decoded (2026-09-10)

User request: "Decode the entire ITAC interface." ITAC is a shipboard
VR terminal, source-tagged `C:\lancer\game\itac.cpp` (confirmed via
the real string at `0x4e98dc`). It's an in-universe personnel/records
kiosk gated by a biometric "eye recognition" login sequence, with its
own localization DLL (`ITACLANG.DLL`), its own sound-index file
(`itacsnd.fat`), and its own fonts (`itacbig.fnt`/`itacsml.fnt`).

### Main entry point: `RunItacScreen` (0x43efc0, was `FUN_0043efc0`)

Called from both `WinMain` and `RunShipInteriorVRLoop`. Full
architecture, confidence 5 (directly read in full):

1. **Setup.** Allocates 5 buffers tagged `itac.cpp` (four ~0x62e08-byte
   scratch/render surfaces plus one screen-sized buffer at
   `DAT_00520314`, which is the direct memcpy blit target used
   throughout ITAC -- see "Rendering pipeline" below), loads
   `itacsnd.fat`/`itacbig.fnt`/`itacsml.fnt`, and zeroes the 9-category
   hotspot-highlight state.
2. **Eye-recognition gate**, gated by `DAT_00523088` (skip-intro flag;
   confidence 3 for the name/semantics, structurally confirmed it's
   "has this login already happened" but the exact set-site wasn't
   traced this pass). When `DAT_00523088 == 0`:
   - `DAT_00562dc8 < 0x13` (aboard ANS Reliant, missions 1-18): chdir
     to a Reliant-specific resource directory and call
     `PlayBinkMovieFromArchiveByName` (see below) to play the
     Reliant eye-recognition clip.
   - Otherwise (aboard ANS Yamato, missions 19+): call
     `PlayBinkMovieFromHandle` directly, no directory swap.
   - **This is a 5th independent confirmed site of the ANS Reliant ->
     ANS Yamato mission-19 threshold**, after `RenderBriefingHubFrame`,
     `WinMain`'s cutscene selection, `RunMissionBriefingScreen`'s
     `briefdoor` texture pick, and `RunCdPlayerPropScreen`'s room
     background pick.
   - The starting category also depends on this flag: skipping the
     gate (`DAT_00523088 != 0`) starts on category 0 (Debrief);
     playing it (`DAT_00523088 == 0`) starts on category 1 (News
     Reports).
3. **Main loop**: polls input, and on a confirmed hover-to-active
   change (`DAT_00520138` click flag set, hovered hotspot !=
   `_DAT_00523084` active category) runs the category-switch sequence
   below. On exit (category 8, or the window-close flag
   `DAT_00520840`), frees all 5 buffers and the sound/font resources
   and returns.
4. **Room-transition-out mechanism** (`DAT_005251dc`, set elsewhere --
   not traced this pass, presumably a room-exit hotspot handler):
   when non-null, hides the background image, ensures the correct CD
   is mounted, chdirs to a resource directory, does
   `strchr(DAT_005251dc+0x18, '\\')` (trims a path down to its
   filename), calls `FUN_004abb80()` (not decompiled -- likely the
   actual room-transition bink loader), chdirs back, and installs a
   renderer callback (`DAT_00588730+0x88 = &LAB_004403f0`) before
   clearing the flag. Structural shape confirmed (confidence 4); the
   internals of `FUN_004abb80`/`LAB_004403f0`/`FUN_0043eaf0` are NOT
   decompiled and their exact behavior is open.

### `PlayBinkMovieFromArchiveByName`/`PlayBinkMovieFromHandle` (0x4ab9d0/0x4ab6e0) are generic, not ITAC-specific

Renamed from `FUN_004ab9d0`/`FUN_004ab6e0`. Confidence 5. Both are
generic Bink-movie-player helpers used throughout the game (already
seen playing menu/cutscene clips elsewhere), reused by ITAC's eye-recog
gate and exit sequence with different filename arguments -- they are
NOT ITAC-specific functions themselves:
- `PlayBinkMovieFromArchiveByName` looks the movie up by name inside a
  packed resource archive via `FindBinkMovieInArchive`, then opens the
  resulting archive data pointer with a fixed 0x800000-byte buffer.
- `PlayBinkMovieFromHandle` opens its argument directly as a bink
  handle/pointer with a 0x1000-byte buffer -- used when the caller
  already has a direct handle rather than an archive-relative name.

### The 9-category catalog

Confirmed via three parallel 9-entry tables (all confidence 5, directly
read via `read_memory` and cross-checked against decompiled code):
`0x4e9288` (5 callback pointers/category), `0x4e9340` (hotspot rects:
9 equal 58x51 buttons in a row at y=422, x=12,81,151,220,290,359,429,
499,570), and `0x4e9418` (3 string pointers/category: enter-line,
exit-line, trans-line bink/tga-token names).

| Cat | Name | Resource | Enter callback | bik enter / exit / trans-token |
|---:|---|---|---|---|
| 0 | Debrief | (mission debrief text via `BuildMissionDebriefText`) | `ItacEnterDebriefCategory` (0x4246c0) | itacdeb.bik / itacdebf.bik / itactrans_00030 |
| 1 | News Reports | `inter\itac\newsrep.spr` | `ItacEnterNewsReportsCategory` (0x44dd90) | itacnew.bik / itacnewf.bik / itactrans_00051 |
| 2 | Video Reports | `inter\itac\vidrep.spr` | `ItacEnterVideoReportsCategory` (0x450540) | itacmov.bik / itacmovf.bik / itactrans_00072 |
| 3 | Fighters | `inter\itac\fighters.spr` | `ItacEnterFightersCategory` (0x425910) | itacss.bik / itacssf.bik / itactrans_00093 |
| 4 | Capital Ships | `inter\itac\capships.spr` | `ItacEnterCapShipsCategory` (0x423870) | itaccs.bik / itaccsf.bik / itactrans_00114 |
| 5 | Squadrons | `inter\itac\squads.spr` | `ItacEnterSquadronsCategory` (0x44faa0) | itacsq.bik / itacsqf.bik / itactrans_00135 |
| 6 | Personnel | `inter\itac\persons.spr` | `ItacEnterPersonnelCategory` (0x44e4c0) | itacpil.bik / itacpilf.bik / itactrans_00156 |
| 7 | Kills | `inter\itac\kills.spr` | `ItacEnterKillsCategory` (0x441100) | itackil.bik / itackilf.bik / itactrans_00177 |
| 8 | Exit ITAC | (none -- all-zero table row) | (none) | itacexit.bik / (none) / (none) |

The category 3/6 bik-name fragments ("ss" for Fighters, "pil" for
Personnel) don't obviously match their `.spr` filenames -- reported as
fact (confidence 5, directly read) with no confident semantic
explanation for the fragment choice (confidence 1 for any
interpretation, e.g. "ss" = ship-stats, "pil" = pilot roster).

### CORRECTION: the bik "f" suffix means exit-line, not gender

**First impression while scanning the string list was wrong and is
being explicitly corrected here per project methodology.** By analogy
with the already-confirmed `g_wPilotGenderIsFemale` "mp"/"fp" filename
system from Pass 62, the initial hypothesis was that `itacdebf.bik`
vs `itacdeb.bik` was a male/female pilot voice variant. **Reading the
actual code disproved this before anything was written down**: the
non-suffixed name plays when *entering* a category, and the
`f`-suffixed name plays when *leaving* that same category (`f` =
"farewell"/exit, not "female"). This is now directly confirmed for
all 9 categories via the `0x4e9418` string table above (confidence 5).

### Category-switch sequence (in `RunItacScreen`'s main loop)

Confidence 5, directly read:
1. Play a click sound.
2. If a category was already active: format its exit-line bik path,
   set `DAT_00520324 = 2` (transition-mode) and `DAT_0052082c = 1.0`
   (fade direction/speed, unconfirmed), pump playback via
   `FUN_00440010()`, then call the OLD category's exit callback
   (table field 1) if non-null.
3. Set the new active category (`_DAT_00523084`).
4. If the new category isn't Exit (8) and has an enter callback (table
   field 0), call it -- these are the `ItacEnter*Category` functions
   documented above; they reset per-category state, set up hotspot
   sub-rects, and call `LoadNamedResource` on that category's `.spr`.
5. Format and pump the new enter-line bik, then the trans-line token
   if present.
6. If the new category IS Exit (8): special-cased -- plays
   `PlayBinkMovieFromHandle` only if `DAT_00562dc8 > 0x12` (aboard
   Yamato), waits for it to finish, then jumps straight to teardown
   (skips step 7).
7. Otherwise: calls `ItacShowCategoryTransitionAndEnter` (below) for
   the new category.

### `ItacShowCategoryTransitionAndEnter` (0x43fca0, was `FUN_0043fca0`)

Confidence 5, directly read. Takes a category index. Formats
`inter\itac\itactrans_NNNNN.tga` using that category's trans-line
string (resolving the `itactrans_NNNNN` tokens from the table above
into real TGA filenames), loads it via `SR_FileAlloc`, decodes via
`SR_TGA_rle_uncompress`, then **directly `memcpy`s the decoded pixels
into `*DAT_00520314`** -- the screen-sized buffer `RunItacScreen`
allocated at setup. This is a *different*, fully-working blit path
from the still-unresolved `rendererState+0x50` vtable call investigated
in Pass 70: ITAC bypasses that renderer callback entirely and writes
straight into its own screen buffer. After the blit, it clears
`DAT_0052083c` and calls the category's table field 2 callback if
non-null.

### Table field 2 ("content setup") callbacks

Confidence 5 for the shared/no-op case, confidence 4 for the
per-category ones (read but not further exercised):
- **Shared stub** `FUN_0044de90`: sets `DAT_0052032c = 1` (redraw-needed
  flag) and calls `FUN_00440b10`, a generic 4-entry list-selection
  reset helper (`0x520334`..`0x52036c`, 14 bytes/entry) -- used as-is
  by News Reports, Video Reports, Fighters, and Capital Ships (the
  plain list-browser categories).
- **Debrief** (`0x4247a0`) additionally calls `FUN_00424be0`, which (for
  mission > 1) calls `BuildMissionDebriefText` and lays out two text
  regions, the second one only when its `char` parameter is non-zero
  (open: exact meaning of that parameter not traced).
- **Squadrons** (`0x44fb60`) additionally clears `DAT_00523058` before
  the shared reset.
- **Personnel** (`0x44e520`) sets up its own hotspot sub-rect and
  callback (`FUN_0044ed00`, not decompiled) before the shared reset.
- **Kills** (`0x4411c0`) is qualitatively different from every other
  category: it renders a live 3D scene via the renderer's `+0x78`/
  `+0x7c` callback pair (begin/end frame) into an offscreen buffer,
  then `memcpy`s that rendered frame into `*DAT_00520314` the same way
  `ItacShowCategoryTransitionAndEnter` does -- consistent with a
  rotating 3D kill-marker/trophy display rather than a flat list.

### Open follow-ups

- Table fields 3 and 4 (per-category, called from the not-yet-decompiled
  `FUN_004404a0` in the main loop) are unresolved -- likely per-frame
  update and per-item/record-selection handling for the record browser.
- `FUN_004abb80`/`LAB_004403f0`/`FUN_0043eaf0` (room-transition-out
  internals) not decompiled.
- `DAT_00523088`'s exact set-site (what marks eye-recognition as
  already done) not traced.
- The remaining itac.cpp-tagged functions `FUN_004406a0`,
  `FUN_00440770`, `FUN_00440bd0` not decompiled.
- The room-graph connections out of ITAC (the many `rel_itac2X.bik`/
  `itac2X.bik` room-transition clips referenced in the string list)
  not mapped to specific hotspots/destinations.

## Pass 72 -- Room-transition-out internals and the remaining itac.cpp functions (2026-09-10)

User request: "Work on FUN_004abb80 etc.), and three remaining itac.cpp-tagged functions" -- directly continuing Pass 71's open follow-up list.

### `PlayBinkMovieFromArchiveWithVolume` (0x4abb80, was `FUN_004abb80`) -- a THIRD generic Bink-player variant

Confidence 5, directly read. Nearly identical shape to
`PlayBinkMovieFromArchiveByName` (looks a clip up by name via
`FindBinkMovieInArchive`, opens with a fixed 0x800000-byte buffer),
but differs in two ways: it explicitly sets playback volume
(`_BinkSetVolume_8(handle, 0x8000)`) and its early-out check tests
`DAT_00588730+0x1ac == 2 || == 0` (a render-mode field) instead of
the `+0x15f8` tiny-window flag the other two check. **Confirmed
generic, not ITAC-specific** via `get_xrefs_to`: called from `WinMain`
(11 sites -- ordinary cutscene playback), `AdvanceCampaignMissionAndSaveProfile`,
and four other VR-room helper functions (`FUN_0048b6b0`,
`FUN_004abd40` x2, `FUN_004abde0`, `FUN_004ac620`), plus exactly one
call from `RunItacScreen` (0x43f8db) -- the room-transition-out
sequence documented in Pass 71. So the game has (at least) three
near-duplicate Bink-player entry points distinguished by lookup
method and volume handling; ITAC's transition-out uses this one
specifically for its volume control.

### `ItacRoomTransitionFrameCallback` (0x4403f0, was `FUN_004403f0`/`LAB_004403f0`)

Confidence 4, directly read. This is the callback `RunItacScreen`'s
room-transition-out installs at `DAT_00588730+0x88` (the renderer's
per-frame overlay hook). It chains any pre-existing `+0x80` callback,
copies a value into `*DAT_00594544` (likely a frame/time counter, not
independently re-verified), calls `FUN_0043fe90(DAT_0052082c)` (the
fade-amount global from Pass 71's category-switch sequence), and --
only when not in the `DAT_0052308c` "waiting" state and with
`DAT_00522f54` set -- draws the mouse cursor via a WinVFX sprite call
(`(*DAT_005959e4)(...)` with cursor position from `DAT_0051db34`/
`DAT_0051dacc`, the same hover-position globals used by the hotspot
hit-test). In short: a fade-overlay + cursor per-frame render hook,
active only during the transition-out window.

### `ActivateItacTransitionBackground` (0x43eaf0, was `FUN_0043eaf0`)

Confidence 4, directly read. Takes a filename-base argument, formats
it as `%s.tga`, calls the renderer's `+0x78` begin-frame callback,
then calls `SetActiveBackgroundImage`. This is the final step of the
room-transition-out sequence (Pass 71): it's what actually swaps in
the destination room's background image using the just-resolved
trans-line filename, sandwiched by an explicit frame-begin call.

### `DynamicList_GetByIndex` (0x4406a0, was `FUN_004406a0`) -- the core record-list primitive

Confidence 5. Self-identified via its own assertion string
(`"DynamicList::GetByIndex - index >= i"`-style message). A plain
singly-linked-list node walker: follows `*param_1` (next-pointer at
offset 0) `param_2` times, asserting on a null mid-walk. **Not
ITAC-specific** in the structural sense (looks like a shared
`DynamicList` collection class), but `get_xrefs_to` shows it is the
single shared traversal primitive used by every one of ITAC's
per-category record browsers: the Kills helpers (`FUN_00441320`,
`FUN_00441540`), Capital Ships (`FUN_00423cb0`, `FUN_00424130`),
Fighters (`FUN_00425b70`, `FUN_00426030`), Personnel (`FUN_0044e0a0`,
`FUN_0044ea50`, `FUN_0044ed00`), and Squadrons (`FUN_0044fde0`,
`FUN_00450180`, `FUN_004508d0`, `FUN_00450cc0`) all call it directly.
This confirms every "list" category (news, kills, persons, squads,
fighters, capships) is backed by the same generic linked-list type,
indexed by scroll position when the player pages through records.

### `InitializeItacLanguageStrings` (0x440770, was `FUN_00440770`) -- ITAC's own localized string table

Confidence 5, directly read in full. This is the function behind the
already-known `"language_init: Can't find ITACLANG.DLL"` assertion:
1. `LoadLibraryA("itaclang.dll")`, asserting if it fails.
2. First pass: calls `LoadStringA` with resource IDs starting at 1,
   incrementing until it returns 0, counting both the number of
   strings (`DAT_00520828`) and their total byte length
   (`DAT_00520838`).
3. Allocates a flat character buffer (`DAT_00520830`, sized to the
   total) and a parallel pointer table (`DAT_005231ac`, 4 bytes per
   string).
4. Second pass: re-loads each string by ID, copies it into the flat
   buffer, and records its start address in the pointer table.

This is ITAC's per-string localization loader -- the same overall
shape as a typical Windows string-table resource loader, but entirely
itac.cpp-local (separate from the game's main `LANGUAGE.DLL`-style
localization, matching the "ITAC has its own localization DLL" fact
established in Pass 71).

### `RegisterItacTooltip` (0x440bd0, was `FUN_00440bd0`)

Confidence 5, directly read. Appends its argument (a string pointer,
presumably one of `InitializeItacLanguageStrings`' resolved strings)
to a fixed 30-slot array (`&DAT_00520368`, index `DAT_005231b4`),
asserting `"Too many tooltips"` past slot 29. A simple bounded
registration list for hotspot tooltip text.

### Open follow-ups

- Table fields 3/4 of the category callback table (called from
  undecompiled `FUN_004404a0`) still not resolved.
- `DAT_00588730+0x1ac`'s render-mode values (0/2 vs. others) not
  independently mapped.

## Pass 73 -- `FUN_004404a0`, `g_dwItacSkipEyeRecognition`'s set-site, and ITAC's room-graph exits (2026-09-10)

User request: "Work on FUN_004404a0, DAT_00523088's set-site, and
mapping ITAC's room-graph exits to specific hotspots" -- the three
remaining Pass 71/72 open items.

### CORRECTION: `FUN_004404a0` is NOT a category-table dispatcher

Pass 71/72 speculated table fields 3/4 might be called from
`FUN_004404a0`. **Reading it disproved this.** Renamed
`UpdateMouseCursorState` (0x4404a0). Confidence 5, directly read: a
completely generic mouse-input helper -- applies the relative mouse
delta (`DAT_00523198`/`DAT_0052319c`) to the cursor position,
re-centers the OS cursor when a delta was applied, clamps position to
screen bounds, and derives click/button edge-detection flags
(`DAT_00520138`, `DAT_0051dab0`, `DAT_00520820`, `_DAT_00520824`) from
packed input state `DAT_005231a4`. Confirmed generic (not
ITAC-specific) via `get_xrefs_to`: called from `RunItacScreen`,
`RunMissionSelectMapScreen`, and two other input-pump helpers
(`FUN_00440010`, `FUN_00440170`).

### Table fields 3/4 ARE now resolved, just not by that function

Field 3 is each category's **per-frame update** callback (called
directly from `RunItacScreen`'s main loop, not from
`UpdateMouseCursorState`). Two were decompiled to confirm:
- `ItacDebriefPerFrameUpdate` (0x4247c0, was `FUN_004247c0`,
  Debrief's field 3) -- handles list scroll/selection for the debrief
  text, AND (see below) is where `g_dwItacSkipEyeRecognition` gets
  consumed.
- `ItacVideoReportsPerFrameUpdate` (0x450630, was `FUN_00450630`,
  Video Reports' field 3) -- handles list scroll/selection, and on any
  click calls `ItacSelectVideoReportRecord`.
- Field 4 (at least for Video Reports) is a click-confirm helper:
  `ItacSelectVideoReportRecord` (0x450cc0, was `FUN_00450cc0`) waits
  for mouse-button release then does
  `DAT_005251dc = DynamicList_GetByIndex(...)` -- fetching the
  currently-selected record node and stashing it as the pending
  resource to play.

### CORRECTION: `DAT_005251dc` is "play the selected record," not a room-exit mechanism

Pass 71 assumed `DAT_005251dc` (checked in `RunItacScreen`'s main
loop, `if (DAT_005251dc != 0) { ... }`) was ITAC's room-transition-out
trigger, because its handling reuses the same
chdir/CD-check/background-hide/bink-play plumbing as a real room
transition. **This pass traced its only non-`RunItacScreen` write site**
(`ItacSelectVideoReportRecord`, called from `ItacVideoReportsPerFrameUpdate`)
and found it's actually set when the player clicks/confirms a
**Video Reports list entry** -- i.e. it's ITAC's "play the selected
video-report clip" mechanism, which happens to reuse the room-transition
machinery because playing a full-screen bink clip needs the same
background-hide/CD-check/chdir dance a real room change does. Explicitly
correcting this because it changes the answer to "does ITAC have
internal room-exit hotspots": it doesn't -- see below.

### `g_dwItacSkipEyeRecognition`'s set-site (renamed from `DAT_00523088`)

Confidence 5, both write sites traced. Set to 1 in `WinMain`, on the
post-mission path immediately before the debrief-triggered
`RunItacScreen()` call (right after `AdvanceCampaignMissionAndSaveProfile`,
when the mission isn't the special end-of-campaign case): `DAT_0051d4e0
= LoadNamedResource(...); ...; DAT_00523088 = 1; ...; RunItacScreen();`.
Cleared back to 0 inside `ItacDebriefPerFrameUpdate`, on the very first
per-frame tick after the Debrief tab is showing (`if (DAT_0052032c !=
0) { if (DAT_00523088 != 0) { DAT_00523088 = 0; } ... }`). So it's a
**one-shot "just arrived here from the post-mission debrief flow"
flag**: WinMain sets it for that one specific entry so the player lands
straight on Debrief without redoing the eye-recognition login; it's
consumed on the first render tick and cleared, so any *later*
re-entry into ITAC during the same play session (via the normal VR
room graph) requires the eye-recognition sequence again.

### ITAC's room-graph exits mapped to hotspots (`VRRoomNode` graph, `RunShipInteriorVRLoop`)

Confidence 4-5 (structure/mechanism confidence 5; specific node
addresses confidence 5 where read directly, confidence 3 for
inferred-but-unconfirmed edges). The pre-existing `VRRoomNode` struct
(44 bytes: `nHotspotX/Y/W/H`, `pMoviePath`, `pMoviePathAlt`, `nUnk10`,
`nNumTargets`, `pTarget0`-`pTarget4`, `nRoomType`, `nSoundFlag`) is
the general ship-interior VR room graph read by `RunShipInteriorVRLoop`
(0x439fb0). **ITAC has no internal room-exit hotspot table of its
own** -- `RunShipInteriorVRLoop` dispatches purely on the *current*
node's `nRoomType`, and `nRoomType == 2` means "launch `RunItacScreen`"
instead of showing a normal still-image hotspot screen. Traced the
Reliant side fully:
- The ITAC room node itself: `VRRoomNode` at **0x506c50** -- hotspot
  rect (x=150, y=100, w=150, h=300), entered via clip
  `bunk2itac_no_eye_recog.bik`, `nRoomType == 2`, exactly 1 outgoing
  target: **0x506c80** (see below). Matches `nNumTargets == 1` --
  ITAC genuinely has only one way out on the Reliant.
- The fixed post-ITAC room: `VRRoomNode` at **0x506c80** (the
  bunkroom), movie `rel_itac2bunk.bik`, alt `rel_doorloop.bik`.
  `RunShipInteriorVRLoop`'s `nRoomType == 2` branch hardcodes the jump
  to this node directly after `RunItacScreen()` returns, rather than
  reading it back out of the ITAC node's own `pTarget0` (though they
  are in fact the same address).
- A "corridor junction" waypoint just outside ITAC's door: `VRRoomNode`
  at **0x506b30** (movie `rel_t2itac.bik`), whose 3 hotspots fan out
  to ITAC itself (0x506c50), back down the corridor (0x506e60, movie
  `rel_itac2t.bik`), or back to the pod bay (0x506cb0, movie
  `rel_itac2pod.bik`) -- this explains 3 of the 4 confirmed Reliant
  `X2itac`/`itac2X` clip names found in Pass 71's string search.
- The Yamato side's fixed post-ITAC room was also confirmed: `VRRoomNode`
  at **0x50aec8**, movie `itac2rot.bik`, alt `itac_dl.bik` -- lands in
  the "rot" (rotation) room, NOT bunk/pod. This confirms the Reliant
  and Yamato VR room graphs are laid out differently, matching the
  asymmetric bik-name sets already noted in Pass 71.

### Open follow-ups

- Yamato's exact ITAC room node (the `nRoomType == 2` counterpart to
  Reliant's 0x506c50) was NOT located -- traced 3 hops from the
  post-ITAC node (0x50aec8 -> 0x50ae98 -> 0x50ae68 -> 0x50ace8, none
  are it) without finding it. `get_xrefs_to` on the `pod2itac.bik`/
  `lock2itac.bik` string addresses returned no references (Ghidra
  hasn't indexed these as data references), so locating it needs
  either a wider manual struct-array scan or a Ghidra data-region
  re-analysis.
- `rel_cap2itac.bik` (capital-ship-transfer entry) and
  `itac2pod_hud.bik`/`itac2dor.bik`/`itac2itac.bik` not traced to
  specific nodes.
- Fields 3/4 of the other 7 categories' table entries not
  individually decompiled (only Debrief's and Video Reports' field 3,
  and Video Reports' field 4, were read this pass).

## Pass 74 -- Remaining clip names/nodes resolved; every category's fields 3/4 decoded (2026-09-10)

User request: "work on the remaining clip names and fields, then work
on VR room missing clip names and fields" -- closing out Pass 73's
open items.

### Remaining `itac2X`/`X2itac` clip names, resolved

`get_xrefs_to` found nothing for these four string addresses (same
blind spot as `pod2itac.bik`/`lock2itac.bik` in Pass 73 -- Ghidra
hasn't indexed the `VRRoomNode.pMoviePath` field as a data reference
in this region). Located all four by `search_byte_patterns` on the
string address's little-endian bytes instead, which found the exact
`VRRoomNode` holding each as `pMoviePath` (struct starts 8 bytes
before the match, since `pMoviePath` is at struct offset 8):

| Clip | `VRRoomNode` | Findings |
|---|---|---|
| `rel_cap2itac.bik` | 0x506f50 (Reliant) | `nHotspotX/Y/W/H` and `nNumTargets` all 0 -- a true terminal/scripted node, not reached via any other node's `pTarget` (searched for `0x506f50` itself as a target pointer -- zero hits). Consistent with "cap" = the one-time capital-ship-transfer cutscene context from Pass 65, not the normal interactive room graph. |
| `itac2pod_hud.bik` | 0x50acb8 (Yamato) | `nRoomType == 5` -- arriving here launches `RunMissionSelectMapScreen` directly (not a plain room). Its `pTarget0` (0x50b678) matches exactly the node `RunShipInteriorVRLoop` hardcodes as the "next room after the mission map" for the Yamato, confirming the connection. |
| `itac2dor.bik` | 0x50ab08 (Yamato) | Ordinary room node (`nRoomType == 0`), 3 further hotspots -- the "door" room mentioned in Pass 71's room-name-fragment list. |
| `itac2itac.bik` | 0x50ada8 (Yamato) | **`nRoomType == 2` -- this IS the Yamato's ITAC room node**, the exact counterpart to Reliant's 0x506c50 that Pass 73 failed to locate via graph traversal. Same hotspot rect (150 area, 181,150,340,150-class) as the other confirmed post/into-ITAC nodes. |

### Yamato's ITAC room node located, with 2 incoming edges

Confidence 5. `search_byte_patterns` for `0x50ada8`'s own address
(as a raw pointer) found it referenced as a `pTarget` slot from two
different junction nodes:
- **0x50ab68** (lock-room junction, movie `ir_l2i.bik`, alt
  `itac_itacl.bik`) -- `pTarget2 == 0x50ada8`.
- **0x50ae34** (a second junction, movie `ir_f2i.bik`, alt
  `itac_itacl.bik`) -- `pTarget1 == 0x50ada8`.

This mirrors the Reliant pattern found in Pass 73 (a junction node
just outside ITAC's door with ITAC as one of several fan-out targets)
and confirms the Yamato reaches ITAC from at least two different
interior locations, consistent with the multiple `X2itac` clip names
found in Pass 71's string search (`pod2itac.bik`, `lock2itac.bik`).

### Every category's fields 3/4 decoded

Field 3 (per-frame update) and field 4 (hover-preview render) for all
9 categories are now read. Confirms and extends the Pass 73 pattern:

- **Debrief** field 4, `ItacDebriefRenderTransferSummary` (0x424930,
  was `FUN_00424930`) -- richer than a plain preview: renders the
  rank/callsign transfer summary (old vs. new rank via language
  strings 0xe8/0xe9 and the profile's rank-history arrays,
  `DAT_00562e64`/`DAT_00562df4`), and on the player's most recent
  mission (`DAT_00523078 == DAT_0051d380 + 1`) draws a distinct
  "continue" prompt icon instead of the normal one.
- **News Reports**: `ItacNewsReportsPerFrameUpdate` (0x44dea0) /
  `ItacNewsReportsRenderPreview` (0x44dfe0, draws a per-entry
  portrait/graphic from a table at `DAT_004eb100` plus a border).
- **Video Reports**: `ItacVideoReportsRenderPreview` (0x450760) --
  renders a temporary thumbnail preview of the selected record
  (distinct from `ItacSelectVideoReportRecord`'s full clip playback).
- **Fighters**: `ItacFightersPerFrameUpdate` (0x425980) /
  `ItacFightersRenderPreview` (0x425a70, draws a ship-class icon from
  `fighters.spr` using the selected record's field `+0x3c`).
- **Capital Ships**: `ItacCapShipsPerFrameUpdate` (0x423930) /
  `ItacCapShipsRenderPreview` (0x423ac0, same shape, indexes via
  record field `+0x1e` through an large all-`break` switch whose
  cases don't diverge -- likely optimized-away class-specific sound
  selection, not independently confirmed).
- **Squadrons**: `ItacSquadronsPerFrameUpdate` (0x44fb80) /
  `ItacSquadronsRenderPreview` (0x44fd10, portrait from `squads.spr`
  via a 28-byte/entry (`0x1c`) squad-record array).
- **Personnel**: `ItacPersonnelPerFrameUpdate` (0x44e590) /
  `ItacPersonnelRenderPreview` (0x44e720, portrait from `persons.spr`
  via record field `+0x1e`).
- **Kills**: `ItacKillsPerFrameUpdate` (0x441280, notably simpler --
  no redraw-gate, no sub-tab handling, just scroll bounds-checking) /
  `ItacKillsRenderPreview` (0x441300, trivially just flushes captions
  -- consistent with Kills being visually driven by its distinctive
  live 3D-scene renderer from Pass 71's field 2, not a 2D portrait).

**New finding: 4 of the 9 categories have their own internal sub-tabs.**
Fighters, Capital Ships, Squadrons, and Personnel each additionally
poll a *second* hotspot row (shared table around `0x4e96c4`-`0x4e96d0`,
indexed by a shared "current sub-tab" global `DAT_00523058`) to switch
between what are presumably class/rank filters on their roster list --
News Reports, Video Reports, Debrief, and Kills do not have this.
Confidence 3 for the exact size/semantics of that sub-tab table (not
independently mapped this pass).

### The 4 shared per-frame primitives behind every category

Confidence 5, all directly read:
- `FindHotspotIndexAtCursor` (0x43fe40, was `FUN_0043fe40`) -- generic
  hit-test over a hotspot-rect array against the cursor position;
  the single shared primitive behind hover/click detection everywhere
  in ITAC (and the main 9-category tab bar itself).
- `IsClickConfirmEdge` (0x441060, was `FUN_00441060`) -- click debounce:
  passes once per press, suppresses repeats while held.
- `DrawFadingTextCaptions` (0x43ff50, was `FUN_0043ff50`) -- iterates a
  6-slot floating-caption array (`DAT_005202fc` onward) and renders
  each with an optional fade-in animation; the generic on-screen-text
  renderer every category's field 3/4 calls at the end.
- `UpdateHoverAnimationWidget` (0x4409f0, was `FUN_004409f0`) -- a
  generic hover-triggered "wiggle" animation updater for a small
  widget struct (float position at `+0x14`, direction/counter at
  `+0x18`, redraw callback at `+0x20`); exact struct/widget identity
  not resolved.

### Open follow-ups

- The sub-tab hotspot table (~`0x4e96c4`-`0x4e96d0`) -- exact entry
  count and the meaning of its per-entry short values not mapped.
- `ItacCapShipsRenderPreview`'s 19-case switch on record field `+0x1e`
  -- all cases currently decompile identically; not independently
  confirmed whether this reflects real optimized-away behavior or a
  decompilation artifact.
- `UpdateHoverAnimationWidget`'s widget struct not identified.
- `DAT_00588730+0x1ac`'s render-mode values not independently mapped.

## Pass 75 -- All 4 remaining open items resolved (2026-09-10)

User request: "Work on remaining open items" -- the sub-tab table,
the Capital Ships switch, `UpdateHoverAnimationWidget`'s struct, and
`+0x1ac`.

### The sub-tab table -- fully resolved, exactly 2 entries

Confidence 5, directly read via `read_memory` at `0x4e96c4`-`0x4e96d3`
(16 bytes). It's 4 parallel 2-entry `short` arrays, not one bigger
table:

| Base | Entry 0 | Entry 1 | Meaning |
|---|---:|---:|---|
| `0x4e96c8` | 0 | 1 | hotspot-click-index -> sub-tab ID (identity mapping) |
| `0x4e96c4` | 25 | 24 | icon sprite index per sub-tab |
| `0x4e96cc` | 551 | 478 | draw X per sub-tab |
| `0x4e96d0` | 59 | 59 | draw Y per sub-tab (same row, side-by-side buttons) |

So Fighters/Capital Ships/Squadrons/Personnel's second hotspot row is
just **two** buttons, side by side at y=59, using icon sprites 24/25.
No label strings were found nearby, so what the two sub-tabs actually
mean (e.g. two roster halves, "active"/"reserve", alive/destroyed) is
NOT determined -- confidence 1 for any such interpretation. The 16
bytes immediately preceding this table (`0x4e96b0`-`0x4e96c3`) don't
cleanly parse as the corresponding hotspot hit-rects (one candidate
reading gives a zero-height rect), so the actual click-rect array for
these 2 buttons is still unidentified.

### `ItacCapShipsRenderPreview`'s switch -- CONFIRMED real, not a decompilation artifact

Confidence 5. Disassembled directly (`disassemble_function`, not just
`decompile_function`) to check. The 19 "identical" cases are real:
each sets `EDX` to a distinct multiple of 3 (0, 3, 6, ..., 54) via a
jump table, and that value is used in the FIRST of two back-to-back
draw calls (a color/tint-group selector) before the actual ship icon
is drawn using the RAW, unmodified class ID for the second call. A
56-byte lookup table at `0x423c74` maps `(class ID - 1)` to either one
of 19 group values (repeating `groupN, groupN, 19` for N=0..18) --
every 3rd class ID in sequence falls through to a default tint
instead of a group-specific one. This is a genuine per-ship-class
tint/highlight-group system with ~19 groups of ~3 classes each; what
the groups represent (faction? hull tier?) is not determined.

### `UpdateHoverAnimationWidget`'s widget struct -- partially identified

Confidence 4. Confirmed generic (also called from `0x42a4f2`, outside
ITAC entirely) via `get_xrefs_to`; every ITAC call site passes a
**hardcoded literal address** in `ECX` (fastcall), one distinct global
per category (e.g. `0x51d2e8` for Debrief) -- so each category that
has "wiggling" hover buttons owns its own static instance of this
struct, rather than there being one shared widget. Traced Debrief's
instance (`FUN_00424730`, called from `ItacEnterDebriefCategory`) to
see it initialized: field `+0x00` gets one of `RunItacScreen`'s
setup-allocated sprite-surface handles (`DAT_0052305c`), and field
`+0x20` (the redraw callback `UpdateHoverAnimationWidget` invokes
when the wiggle state changes) gets set to `&LAB_00425220`. Combined
with the already-known `+0x14` (float wiggle offset) / `+0x18`
(direction counter) fields, the struct is now: sprite handle, some
data/font pointer, an ID/rect-ish block, wiggle float, direction
counter, ..., redraw-callback pointer. It's used alongside a *second*,
category-specific hotspot table read with explicit literal arguments
(e.g. Debrief's prev/next-mission buttons at `0x4e4928`, count 2) --
strongly suggesting this animates hover feedback for small prev/next
style navigation buttons distinct from the main scrollable list. The
callback target `LAB_00425220` itself was not decompiled.

### `DAT_00588730+0x1ac` -- resolved: not a scalar, the first field of a bulk-copied video-mode record

Confidence 5, resolved by decompiling `InitializeGraphicsDevice` in
full (the 47 program-wide `+0x1ac` hits from `search_instructions`
were a red herring -- almost all belong to unrelated structs at that
same byte offset by coincidence, matching the earlier `+0x50` lesson
from Pass 70). `InitializeGraphicsDevice` bulk-copies a 1299-dword
(0x513, 5196-byte) display-mode descriptor record from
`(&DAT_00595da0)[param_4]` (the device/mode enumeration table built by
`EnumDisplayCardsFromDriver` in `WinMain`) into `DAT_00588730+0x1ac`
onward -- this IS the same 1299-dword copy Pass 70 already found and
couldn't place. `+0x1ac`'s value is simply that record's *first*
field, read back afterward to select which renderer backend variant
to initialize: values 0, 1, and 2 each call `LoadRendererBackendDriver`
(0x4cc470, was `FUN_004cc470`, self-identified via its own
`"SR_driver_init"` `GetProcAddress` lookup string -- loads a driver
DLL by name and calls its `SR_driver_init` export), while any other
value skips that call and uses the window handle directly (implying
true hardware acceleration needs no extra driver-DLL load). The exact
DLL name passed per mode value wasn't traced (implicit register
argument, same limitation seen with `DynamicList_GetByIndex` and
others).

### Open follow-ups

- The sub-tab buttons' click-rect array (distinct from the confirmed
  icon/x/y data table) not located.
- What the 2 sub-tabs and ~19 Capital Ship tint groups actually
  represent, semantically.
- `LAB_00425220` (the hover-widget redraw callback) not decompiled.
- The per-mode-value driver DLL name passed to
  `LoadRendererBackendDriver` not traced.

## Pass 76 -- Sub-tab click-rects, hover-widget callback, and tint-group semantics investigated (2026-09-10)

User request: "Investigate the sub-tab click-rects, the hover-widget's
redraw callback target, the semantic meaning of the tint groups."

### Sub-tab click-rects -- located and confirmed

Confidence 5. Disassembled `ItacFightersPerFrameUpdate` (0x425980)
directly (not just decompiled -- the literal args don't survive
decompilation) and found the exact call: `MOV EDX,0x2; MOV
ECX,0x4e5460; CALL FindHotspotIndexAtCursor`. Read the 16 bytes at
`0x4e5460`:

| Entry | X | Y | W | H |
|---:|---:|---:|---:|---:|
| 0 | 551 | 59 | 64 | 41 |
| 1 | 478 | 59 | 64 | 61 |

These X/Y exactly match the draw positions from Pass 75's confirmed
data table (`0x4e96cc`/`0x4e96d0` = 551/478, 59/59), closing the loop:
the two sub-tab buttons sit at (551,59) and (478,59), sized roughly
64x41 and 64x61.

### The hover-widget's redraw callback -- resolved: it's the debrief narrative-text builder, not a "wiggle" redraw

Confidence 5. `LAB_00425220` (created as a function, `0x425220`) is a
thin wrapper: `RefreshDebriefSummaryText` (was `FUN_00425220`) just
calls `BuildDebriefSummaryText(1, 1.0)` (0x425240, was `FUN_00425240`).
`BuildDebriefSummaryText` is a large function that assembles the
mission-debrief narrative paragraph (e.g. kills/promotions/medals
summary text) by checking several per-mission outcome-flag arrays
(`DAT_00562e2c`, `DAT_00562e9c`, `DAT_00562ed6`, `DAT_0050099f`,
`DAT_005009d7`, indexed by the currently-viewed mission) and
string-concatenating matching template fragments (a small
`local_14[]` array of 4 template pointers plus a default, selected by
the mission's outcome class, `0`-`4`/`-1`) and/or `GetLanguageString`
fragments (IDs `0x53f`/`0x540`/`0x541`/`0x566`, gated on the mission-
end-reason code `DAT_00588394`) into a shared buffer, storing the
final pointer to `_DAT_0051d304`. **This means `UpdateHoverAnimationWidget`
isn't specifically a "wiggle" animator for Debrief** -- its generic
periodic-refresh-on-tick-change mechanism is being reused here to
periodically rebuild the debrief text, not to animate a button. (Its
other call site outside ITAC, `0x42a4f2`, may still use it for an
actual wiggle effect -- not traced.)

### Tint-group semantics -- partially resolved: tied to two distinct capital-ship roster tables, but the group meaning itself stays unconfirmed

Confidence 3. Decompiled `PopulateCapShipsRosterForSubTab` (0x424410,
was `FUN_00424410`, called from `ItacEnterCapShipsCategory`) -- it
takes the sub-tab index (0 or 1) and walks one of two separate
32-byte-record tables: `0x4e42c0` (21 records, sub-tab 0) or
`0x4e4560` (27 records, sub-tab 1), calling `FUN_00440710` (the
DynamicList-insert helper) once per record. **So the 2 sub-tabs
correspond to 2 genuinely separate capital-ship rosters** (21 vs. 27
entries -- plausibly a per-faction split, matching the Coalition/
Alliance framing elsewhere in the game, though not confirmed). Each
32-byte source record holds ~7-8 consecutive `GetLanguageString` IDs
(e.g. record 0: IDs 1262-1269) plus 1-2 small numeric fields --
consistent with a name/description/stat "info card" per ship class.
**The actual localized string text isn't available in this Ghidra
project** (it lives in a separate language resource this session
doesn't have open), so the tint-group-to-class-name mapping from
Pass 75's 19-group lookup table couldn't be completed -- the
structural link (roster tables exist, feed the same DynamicList the
tint-group switch reads `+0x1e` from) is confirmed, but which classes
land in which of the 19 groups, and what unifies each group, remains
unresolved.

### Open follow-ups

- The tint groups' actual semantic grouping (needs the localized
  string table, not available in this project).
- `UpdateHoverAnimationWidget`'s other call site (`0x42a4f2`, outside
  ITAC) not traced -- unclear if it's a genuine wiggle-animation user.
- The per-mode-value driver DLL name passed to
  `LoadRendererBackendDriver` not traced.

## Pass 77 -- Tint-group semantics unblocked via direct LANGUAGE.DLL string extraction (2026-09-10)

User re-sent the identical Pass 76 request. Pass 76 had fully resolved
the sub-tab click-rects and the hover-widget callback; the tint-group
item was blocked because the `GetLanguageString` text those capital-
ship records reference lives in `LANGUAGE.DLL`, which wasn't open in
Ghidra. **That DLL exists on disk** (`gamedata/StarLancer/LANGUAGE.DLL`),
so this pass parsed its Win32 `RT_STRING` resource table directly in
Python (`reversing/tools/extract_language_strings.py`, new tool,
generic PE-resource STRINGTABLE reader -- also works on `ITACLANG.DLL`)
rather than needing Ghidra to see it.

### CORRECTION: the Capital Ships category's records hold PERSON names/callsigns, not ship-class names

Extracting IDs 1262-1300 revealed real names and military callsigns
("General Makin", "Sean Oliver", ... "Jester", "Zero", "Ace", "Link",
"Sundown", "Jet", "Shooter", ...) -- **not ship-class names as Pass 76
assumed.** IDs 1200-1244 (checked for context) turned out to be the
game's own end-credits roll (dev names, "Quality Assurance Warthog",
"Localization", etc.), and 1245-1261 are mission-specific objective
text and named NPCs for a specific mission (the "Saladin" raid) --
confirming this string range is the game's shared
mission-briefing/NPC/credits text pool, not a dedicated "ship class"
table. So each 32-byte `Capital Ships` record (previously described
in Pass 74-76 as holding "~7-8 consecutive language-string IDs...
consistent with a name/description/stat card") actually lists **8
named individuals** per capital ship -- most plausibly its commanding
officer and bridge crew, or (for at least one record, all 8 fields
resolving to fighter-pilot callsigns) an embarked squadron roster --
drawn from campaign, credits, and NPC beacon-name text, not a
per-hull-class stat block.

### Tint groups -- resolved: classIDs are used strictly in pairs, one pair per group, across all 48 records on both sub-tabs

Confidence 4. Confirmed `FUN_00440710` (the record-insert helper) links
the raw 32-byte source records directly into the category's
`DynamicList` **by reference** (no copy) -- so the tint-group switch's
`record+0x1e` field IS each record's own trailing 2-byte value.
Decoded all 21 sub-tab-0 records (`0x4e42c0`) and all 27 sub-tab-1
records (`0x4e4560`) and cross-checked their classIDs against Pass
75's 56-byte group-lookup table (`0x423c74`):

- classIDs actually used across both sub-tabs: 1, 2, 4, 5, 7, 8, 10,
  11, 13, 14, 16, 17, 19, 20, 22, 23, 25, 26, 28, 29, 31, 32, 35, 37,
  38, 40, 41, 43, 44, 46, 47, 49, 50, 52, 53, 56.
- Every one of these falls on the table's "group" slot of its
  group-of-3 -- **the "default" slot (3, 6, 9, 12, ..., 57) is never
  assigned to any of the 48 real records**, on either sub-tab.
- Several classIDs repeat across multiple distinct records
  (`2` on 2 records, `14` on 2, `25` on 2, `40` on 3, `56` on 4,
  etc.), confirming `classID` is a genuine shared category value, not
  a unique per-ship identifier.

This is a clean, fully corroborated structural pattern: the ~19 tint
groups pair up exactly 2 populated classIDs each (36 of the 57
possible ID slots are actually used, always the first two of each
group-of-3), most plausibly representing 2 named
variants/marks/individual-ships per hull class or per faction
grouping, all sharing one UI accent color; the 3rd slot per group is
a reserved/unused fallback in the lookup table that no real record
ever exercises. The ultimate real-world label for each group (which
specific hull class or faction) is still not determined --
`capships.spr`'s actual icon art wasn't decoded, and the record text
is person-names rather than a self-describing class label.

### Open follow-ups

- Which hull class or faction each of the ~19 tint groups actually
  represents (would need `capships.spr`'s icon art decoded and
  compared, not attempted).
- `UpdateHoverAnimationWidget`'s other call site (`0x42a4f2`, outside
  ITAC) not traced.
- The per-mode-value driver DLL name passed to
  `LoadRendererBackendDriver` not traced.

## Pass 78 -- `capships.spr` decoded: the tint groups are per-class-pair palettes (2026-09-10)

User request: "Work on capships.spr" -- continuing straight from Pass
77's open follow-up (decode the icon art to check what the ~19 tint
groups actually represent).

### `shapeCount == 57` was the missing piece: 19 groups x (1 palette + 2 ships)

Confidence 5. Ran `decode_spr.py` against the real
`gamedata/StarLancer/RESOURCE/CAPSHIPS.SPR` (RefPack-compressed,
confirmed via its `0x10 0xFB` magic). It reported `shapeCount=57`,
with shape indices 3, 6, 9, 12, ..., 54 -- **exactly** the "default"
slots Pass 77 found were never assigned to any real capital-ship
record -- failing `decode_spr.py`'s `looks_like_shape_record` check.
Checking the gap to the next shape confirmed each of those 19
indices (0, 3, 6, ..., 54) sits exactly 768 bytes (256 x 3) before the
next shape, exactly like the single embedded palette `decode_spr.py`
already knew how to find at shape 0. **`.spr` files can carry
multiple embedded palettes, one per group, not just one at shape 0.**
This is the complete explanation for Pass 77's "default slot never
used" pattern: those aren't unused/reserved ship slots at all --
they're the group's own dedicated 256-color palette block. `19 x 3 =
57` exactly matches `shapeCount`.

### `decode_spr.py` had a real bug -- fixed

Confidence 5. The original script only ever located the *first*
768-byte palette block in a file and used it for every shape --
correct for single-palette files (medal-case sprites, verified
unaffected by the fix), but wrong for `CAPSHIPS.SPR`: shapes 4/5, 7/8,
10/11, etc. decoded as visible-but-color-scrambled "TV static" ship
silhouettes (correct RLE geometry, wrong palette). Fixed
`decode_spr.py` to track the *nearest preceding* palette block per
shape instead of a single global one (still defaults to the first
block if a file has only one, so single-palette files decode
byte-for-byte identically). Re-decoding with the fix produced clean,
fully-colored ship art for every shape.

### Visual confirmation: groups are faction/national color schemes, not "2 marks of one hull"

Confidence 4. Compared several groups' ship pairs directly:
- **Group 1** (shapes 4/5): a boxy dual-runway carrier/platform and a
  separate sleek green-engine-glow cruiser -- visibly different hull
  designs, not two views/marks of the same ship.
- **Group 6** (shape 20): shows a **white-star-on-blue roundel with
  red/white stripes** -- an Alliance/US-styled insignia.
- **Group 18** (shape 55): shows a **red Soviet-style star** --
  a Coalition-styled insignia.

So each group's 2 ships are genuinely different hulls that happen to
share one dedicated palette -- consistent with the palette encoding a
**faction/national color scheme** (confirmed via the visible opposing
national insignia between groups 6 and 18) rather than "2 marks of
one class." This directly explains why `ItacCapShipsRenderPreview`'s
switch (Pass 74/75) computes `group*3` from the raw class ID: that's
the **shape index of the group's palette block**, not an arbitrary
tint constant.

### `GetShapeRecordPointer`/`ActivateShapePalette` decoded -- explains the switch's real purpose

Confidence 5, both fully decompiled:
- `GetShapeRecordPointer` (0x480c40, was `FUN_00480c40`) --
  `spriteSetBase + shapes[index].recordOffset`, i.e. exactly the
  `ShapeSet.shapes[i].recordOffset` lookup `decode_spr.py`'s own
  docstring already described (Pass 39/41) -- confirms the file
  format understanding independently from the game's own code.
- `ActivateShapePalette` (0x428410, was `FUN_00428410`) -- takes a
  palette-block pointer and a brightness scalar (`1.0` = full,
  otherwise dims via float multiply), converts the 6-bit-VGA `{R,G,B}`
  triplets into the renderer's native pixel format using the same
  shift/mask fields `ComputePixelFormatFromMasks` (Pass 69) computes,
  and uploads the result into a WinVFX-provided palette buffer
  (`(*DAT_005957c0)()`/`(*DAT_005957d0)()` lock/unlock pair).

So `ItacCapShipsRenderPreview`'s sequence
`GetShapeRecordPointer(capships.spr, group*3)` ->
`ActivateShapePalette(result, 1.0)` -> draw icon by raw class ID is
now fully understood end to end: **select the class's group palette
block by index, upload/activate it as the current render palette,
then draw the ship icon** (whose own pixel indices are meaningless
without that specific palette active). This pattern is used
throughout ITAC's render-preview functions (Pass 74), so this finding
retroactively clarifies the "color-setting calls" noted but not
explained in every one of them.

### Open follow-ups

- The precise real-world label for each of the 19 groups (which
  in-game hull class/faction) -- would need matching `capships.spr`'s
  art against official ship-class reference art, not attempted.
- Whether Fighters/Squadrons/Personnel/Kills/News/Video Reports'
  `.spr` files use the same multi-palette-per-group layout -- not
  checked.
- `UpdateHoverAnimationWidget`'s other call site (`0x42a4f2`, outside
  ITAC) not traced.
- The per-mode-value driver DLL name passed to
  `LoadRendererBackendDriver` not traced.

## Pass 79 -- Player creation / campaign start documented end-to-end (2026-09-10)

Direct request: document the full player-creation-to-campaign-start
flow. Pass 62-64 already covered pilot creation and `profile.bin` in
depth; this pass ties that together with a genuinely new finding --
what actually happens the moment a brand-new pilot's first session
begins -- and tightens up one previously-unconfirmed detail
(`RunNewGameSetupScreen` case 5).

### The full flow, start to finish

1. **Main Menu -> New Game** (`DAT_0051dac4 = 0xc`, documented Pass
   45/46) launches `RunNewGameSetupScreen` (`0x430490`).
2. **`RunNewGameSetupScreen`**'s button map (corrected in Pass 62,
   case 5 now clarified below):

   | Case | Action |
   |---|---|
   | 0 | Set pilot gender = Male |
   | 1 | Set pilot gender = Female |
   | 2 | Load Existing Pilot -> exits to screen `0xd` (`RunSaveGameBrowserScreen`) |
   | 3 | Confirm New Pilot -> `RunDifficultySelectDialog`; on confirm, creates the pilot and returns 1 |
   | 4 | Exit to main menu |
   | 5 | Cancel callsign edit (see below) |
   | 6 | Options dialog |
   | 7 | Toggle the recent-name list panel |

3. **`RunDifficultySelectDialog`** (Pass 62): a 4-hotspot modal
   cycling `g_wCampaignDifficulty` through 3 tiers (Easy/Normal/Hard,
   consumed later by `ScaleDamageForDifficulty`); confirm returns 1.
4. **On confirm**, `RunNewGameSetupScreen` case 3 runs, in order:
   `SR_MEM_free` (releases the setup screen's own background sprite),
   `LoadPlayerProfile` (Pass 62 -- loads `profile.bin` if the typed
   callsign already has one, or silently creates a fresh one:
   `currentMissionIndex = 1`, all stats zeroed, default localized
   name), then **`FUN_0049cd20`** (new this pass, see below), then
   returns `1` up to `RunMenuScreenLoop` -> `WinMain`.
5. **Back in `WinMain`**'s main loop**, on this first pass through
   (`bVar1` true, i.e. "just came from the New Game flow" rather than
   a resumed/loaded session): `EnsureCorrectCDMounted`, then a
   `DAT_00562dc8 == 1` check (exact match, not just "early campaign")
   gates a **brand-new-career-only intro**: play `new_intro.bik`
   (the campaign's opening cinematic) via
   `PlayBinkMovieFromArchiveWithVolume`, then run
   `RunReliantInductionTour` (see below). Any other starting mission
   index (a loaded/resumed pilot) skips straight to
   `RunShipInteriorVRLoop`.

### `FUN_0049cd20` -- resets transient per-campaign session state (not persisted in `profile.bin`)

Confidence 3. Called only on successful new-pilot confirmation (never
on Load Existing Pilot), so it's a "fresh campaign" reset distinct
from `profile.bin`'s own persisted fields: fills a 260-byte array
(`&PTR_DAT_005047d2` .. `0x5048d6`) with the byte value `2`, and resets
a small 6-field struct at `0x58a958`. The array's exact role (mission
availability? part/ship unlock state?) wasn't traced to a consumer
this pass -- flagged as an open item rather than guessed.

### `RunReliantInductionTour` (`0x438d50`, was `FUN_00438d50`) -- the new-pilot orientation tour

Confidence 5, directly read in full. Gated in `WinMain` on
`DAT_00562dc8 == 1` exactly -- **this only ever plays for a genuinely
brand-new pilot's very first session**, never on a resumed one. A
5-stage guided walkthrough of the ANS Reliant, narrated by a
character referred to in the asset names as "Enriq":

| Stage | Ambient loop clip | Narration clip (`%s_box.bik`) | Room |
|---:|---|---|---|
| 0 | `single_rel_c2lock.bik` | `enr_locker` | Locker room |
| 1 | `rel_podmon_loop.bik` | `enr_simpod` | Sim pod |
| 2 | `rel_cdloop.bik` | `enr_cd` | Cargo deck |
| 3 | `rel_itacloop.bik` | `enr_itac` | ITAC |
| 4 | `rel_tv_enriq.bik` | `enr_outro` | (outro) |

Each stage plays its room's ambient loop and, on player input
(advance key or a timeout via `FUN_004620a0`), cuts to that stage's
narrated introduction clip, then advances. The function returns which
stage the player was on when they exited (0-5, `5` = completed all
5), and `WinMain`'s caller uses that return value to pick the correct
follow-up transition clip before finally dropping the player into
`RunShipInteriorVRLoop` for normal free-roam VR navigation -- from
there, the existing room-graph/hotspot navigation (documented across
the ITAC passes) takes over toward mission 1's briefing.

### `RunNewGameSetupScreen` case 5, clarified

Confidence 4 (up from Pass 62's "not independently confirmed").
Case 5 sets `DAT_0052019c = 1` (the same flag callsign-editing clears
to 0 on every keystroke/recent-name click) and re-runs part of the
screen's own init (`FUN_004aada0`, trivially resets one unrelated
input-state global). This is a **"stop editing the callsign, revert
to browse mode" cancel action**, not a full field-clear -- the typed
characters aren't observed to be erased, only the edit-mode flag is
reset.

### Open follow-ups

- `FUN_0049cd20`'s 260-byte array and 6-field struct -- role not
  traced to a consumer.
- Whether `RunReliantInductionTour` can be skipped/aborted entirely
  (vs. just changing which stage you exit from) -- the early-exit key
  check (`CheckKeyEdgeState(1,...)`, likely Escape) breaks the loop
  immediately at whatever `iVar7` stage was reached, but this wasn't
  cross-checked against actual keybinding docs.
- The per-stage transition-clip selection in `WinMain` after the tour
  returns (the `ESI*4+0x4aa8c8` jump table) -- addresses only
  partially read (`0x506bf0`, `0x4e8d08`="rel_pod2itac.bik"), not
  fully mapped case-by-case.

## Pass 80 -- The post-tour transition-clip jump table, fully mapped (2026-09-10)

Direct follow-up closing Pass 79's last open item. Read the jump
table at `0x4aa8c8` (6 dwords, indexed by `ESI` =
`RunReliantInductionTour`'s return value, 0-5) and disassembled every
case target (`0x4aa26e`-`0x4aa2b0`).

### How the dispatcher works

Each case sets `ECX` to a `VRRoomNode` pointer (occasionally after
first playing 0-2 extra transition clips via
`PlayBinkMovieFromArchiveByName`) and falls into a shared tail at
`0x4aa2b0`: `CALL RunShipInteriorVRLoop(ECX)`. Because
`RunShipInteriorVRLoop` itself always plays its target node's own
`pMoviePath` on entry (confirmed Pass 73), any clips this dispatcher
plays explicitly are *supplementary*, stacked in front of that node's
built-in arrival clip.

### The full case table

| `ESI` (tour exit stage) | Extra clip(s) played | Landing `VRRoomNode` | That node's own arrival clip |
|---:|---|---|---|
| 0 (quit during stage 0, locker room) | `rel_l2t.bik` -> `rel_t2itac.bik` | `0x506cb0` | `rel_itac2pod.bik` |
| 1 (quit during stage 1, sim pod) | `rel_lock2c.bik` -> `rel_t2itac.bik` | `0x506cb0` | `rel_itac2pod.bik` |
| 2 (quit during stage 2, cargo deck) | `rel_pod2itac.bik` | `0x506cb0` | `rel_itac2pod.bik` |
| 3 (quit during stage 3, ITAC) | *(none)* | `0x506bf0` | `rel_cd2pod.bik` |
| 4 (quit during stage 4, outro) | *(none)* | `0x506cb0` | `rel_itac2pod.bik` |
| 5 (completed the full tour) | `rel_l2t.bik` -> `rel_t2itac.bik` | `0x506cb0` | `rel_itac2pod.bik` (identical to case 0) |

`0x506bf0` and `0x506cb0` share the same 3 outgoing targets
(`0x506d40`/`0x506c20`/`0x506ce0`) and the same `pMoviePathAlt`
(`0x507000`) -- the same "one physical room, two arrival-direction
node copies" pattern documented for the corridor junction in Pass 73:
both represent the **pod bay**, just entered via a different clip
(`rel_itac2pod.bik` vs. `rel_cd2pod.bik`) depending on where the
player is coming from.

**Confidence 5** on every clip name, jump-table target address, and
destination-node address (all directly read). **Confidence 2** on
the semantic mapping implied by some clip names (e.g. case 2 plays
`rel_pod2itac.bik` -- literally "pod to ITAC," despite the player
being routed *to* the pod bay -- and case 1's "locker to corridor"
clip plays even though the player was on the sim-pod stage, not the
locker stage, when they quit). The likely explanation is that the
game reuses a small set of generic hallway-walk clips for "return to
the pod bay from partway through the tour" rather than rendering a
bespoke walk-back clip from every possible stage -- economical asset
reuse rather than each clip's name being literally accurate to the
player's in-fiction path, but this reading isn't independently
confirmed.

### Open follow-ups

- What `0x506d40`/`0x506c20`/`0x506ce0` (the pod bay's 3 shared
  outgoing targets) lead to -- not traced.
- Whether the apparent clip-name/stage mismatches (case 1, case 2)
  reflect deliberate asset reuse or a mistaken assumption about which
  stage index corresponds to which room -- not independently
  resolved.
