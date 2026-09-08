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
direct entry to any mission number. The exact key sequence itself
isn't recoverable from static analysis (the decompiler doesn't expose
which key each `FUN_004bd570(1)` check is actually testing — that
information likely lives in `FUN_004bd570`'s own implementation or a
lookup table it references, not examined this pass). Confidence 2 for
the mechanism's shape (directly observed), Confidence 1 for the "this
is a cheat code" interpretation (very likely, not proven) — a good
candidate for live-verification per METHODOLOGY's live-debugging
guidance if anyone wants to actually find the key sequence.

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

- `FUN_00453070` (graph-node recursion prep for
  `ScanNavigationGraphTarget`'s type-2 case), `FUN_0045a440`
  (invalid-node-type fallback), `FUN_004b9920`/`FUN_004b9830` (the
  underlying network packet-write primitives — clearly a small, reused
  serialization API given how many call sites exist; worth opening if
  the multiplayer networking layer becomes a dedicated focus).
- What event type `0x69` specifically represents, and why it alone
  carries extra network data.
- The full navigation-graph node-type enum (only 0/1/2 observed; the
  `default` fallback implies the format allows for more even if unused
  in practice).
