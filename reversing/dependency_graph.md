# Dependency graph

Per-entry dependency edges for `confidence_db.md`, so "resolve this
subsystem" (see `METHODOLOGY.md`) is checkable: before marking a subsystem
resolved, its dependencies should mostly resolve to other entries in the
confidence database, not a wall of unrated references. Seeded 2026-09-07
with the program-entry/bootstrap cluster (the first subsystem investigated
on this project); extend as new subsystems are investigated.

Format: `Entry -> depends on: [list]` and, where useful, `Entry <- depended on by: [list]`.

## Program entry / bootstrap cluster

```
mainCRTStartup (0x4d1210)
  -> depends on: (CRT-internal helpers, unrated — FUN_004d51c8 heap init,
                  FUN_004d2b56 io init, FUN_004d606a, FUN_004d6ab0,
                  FUN_004d6863, FUN_004d67aa, FUN_004d04c0 — all CRT
                  boilerplate, not investigated further)
  -> calls: WinMain
  <- depended on by: (none — process entry point, invoked by the OS loader)

WinMain (0x4a8b10)
  -> depends on: GetVersionInfoAndInstanceTitle (builds the FindWindowA
                 title buffer, though see its own confidence_db.md note
                 about the dead-code quirk), RegisterGameWindowClass
                 (registers the class WindowProc is attached to; ALSO
                 called directly by WinMain itself right after
                 SR_MEM_init — its return value gates almost the entire
                 rest of the function), CreateGameWindow (actually
                 creates the HWND, depends in turn on
                 GetVersionInfoAndInstanceTitle), WindowProc (assigned as
                 WNDCLASSA.lpfnWndProc), SafeFormatString (used
                 throughout for path building), DebugLog_Stub (called
                 ~30x, all no-ops in this release build), the
                 display-mode/device-cache loader @0x4a89c0 (dmodes.bin,
                 depends on EnumDisplayCardsFromDriver), LoadLanguageStrings,
                 DetectDirectXVersion (gates the "DirectX Version %03x"
                 message box branch), ShowEulaDialog, InitializeHighResTimer,
                 LoadInstallPathsFromRegistry, OpenBigFile/CloseBigFile
                 (the main .HOG resource archive — SEPARATE from the
                 dmodes.bin loader, which uses its own private
                 fopen/fread/fclose calls, not this open/close pair),
                 LoadPlayerProfile (cross-confirms DAT_00562dc8 = current
                 mission index), FUN_004bcf70 (uninvestigated, see its
                 own note)
  -> depends on (NOT YET IN DB): the entire post-bootstrap state-machine
                 body (mission/multiplayer flow) — dozens of unrated
                 FUN_ calls, not enumerated individually yet
  <- depended on by: mainCRTStartup

RegisterGameWindowClass (0x4aa8e0)
  -> depends on: WindowProc (wired as lpfnWndProc)
  <- depended on by: WinMain

WindowProc (0x4a8300)
  -> depends on: HandleWindowActivationChange (called on WM_ACTIVATE/
                 WM_SYSCOMMAND-restore/WM_ENTERSIZEMOVE/WM_EXITSIZEMOVE/
                 WM_USER-poll — a hub for 5 different message paths;
                 calls two virtual methods, offsets +0x1c/+0x20, on up
                 to 3 engine objects — semantically probably
                 restore/suspend of render surfaces on focus change, but
                 the exact vtable identity is NOT confirmed, Confidence 1
                 on the "render surface" interpretation specifically),
                 SetCursorVisibility (called on SC_RESTORE and
                 WM_SETCURSOR), MinimizeGameWindow (WM_ACTIVATE
                 deactivate path — itself depends on
                 GetVersionInfoAndInstanceTitle, SetCursorVisibility,
                 HandleWindowActivationChange)
  <- depended on by: RegisterGameWindowClass (indirectly, via WNDCLASSA)

Display-mode/device-cache loader (0x4a89c0)
  -> depends on: dmodes.bin (data format, see confidence_db.md),
                 FUN_004d02ef/FUN_004cfeec/FUN_004d013c (fopen/fread/fclose
                 wrappers — CRT-level, not individually rated),
                 EnumDisplayCardsFromDriver (enumerates live display
                 modes for the cache-staleness comparison — resolved
                 this session, was NOT YET IN DB)
  <- depended on by: WinMain
```

## SurrenderLib diagnostics/assertion cluster

```
SR_printf (0x4c3640)
  -> depends on: FUN_004d05e0 (vsprintf-shaped formatter, NOT YET IN DB),
                 DebugLog_Stub (always called, no-op in this build),
                 DAT_005e82e4 (output-redirect callback — reader
                 confirmed, WRITER not yet found anywhere)
  <- depended on by: ReportAssertionFailure, ReportAssertionFailureEx,
                 and almost certainly many more call sites across the
                 2434-function binary not yet enumerated (this is the
                 engine's central logging primitive)

ReportAssertionFailure (0x4c37b0, 3-arg)
  -> depends on: SafeFormatString, SR_printf, SetAssertionCallback's
                 target global (DAT_005e82e8, conditionally invoked)
  <- depended on by: (callers not yet enumerated — this is a generic
                 fatal-error entry point likely reached from many
                 subsystems' error paths, not specific to bootstrap)

ReportAssertionFailureEx (0x4c3710, 4-arg)
  -> depends on: SafeFormatString, SR_printf, SetAssertionCallbackEx's
                 target global (DAT_005e82ec, conditionally invoked)
  <- depended on by: OpenBigFile's/the dmodes.bin loader's implied
                 "load failed" error paths in WinMain (WinMain calls
                 FUN_004c3710 directly with a 2-visible-arg shape at
                 the resource-load and msspeech-load failure points —
                 the other 2 args are likely 0/context-implicit)

SetAssertionCallback (0x4c3620) -> writes: DAT_005e82e8
SetAssertionCallbackEx (0x4c3630) -> writes: DAT_005e82ec
  <- depended on by: (their own callers not yet traced — who installs
                 these hooks is an open question)
```

## WinMain state-machine cluster (first dive)

```
RunMenuScreenLoop (0x4289d0)
  -> depends on: ALL 12 screen handlers now identified (see
                 confidence_db.md's "RunMenuScreenLoop's 12 screen
                 handlers" table) —
                 RunMainMenuScreen(0), RunOptionsMenuScreen(1),
                 RunSoundOptionsScreen(3), RunMissionBriefingScreen(7),
                 RunNetworkDisconnectScreen(8), RunSaveLoadScreen(10/11,
                 toggles DAT_0051d54c), RunNewGameSetupScreen(0xc),
                 RunSaveGameBrowserScreen(0xd), RunMultiplayerSetupScreen(0xe),
                 RunVideoOptionsScreen(0xf), RunControlsOptionsScreen(0x10),
                 RunMultiplayerLobbyScreen(0x11/0x12, toggles DAT_0051d54c)
  -> cross-hub edges found this pass: RunNewGameSetupScreen -> calls
                 RunSaveGameBrowserScreen directly (screen 12 -> 13);
                 RunSaveLoadScreen -> calls RunSaveGameBrowserScreen
                 directly mid-flow (not just via the dispatch table);
                 RunVideoOptionsScreen reads/writes the SAME device/mode
                 table (DAT_00595fe8 family) the dmodes.bin loader
                 (0x4a89c0, documented in an earlier session) populates
                 — a confirmed cross-subsystem link
  <- depended on by: WinMain (called from within the big state-machine
                 body, exact call sites not individually mapped —
                 WinMain's own decompile shows RunMenuScreenLoop called
                 directly in several branches of its post-bootstrap loop)

## Save-game IFF reader + resource loading (fourth session)

```
IffFile_Open / IffFile_FindFormChunk / IffFile_FindChunk / IffFile_Read /
IffFile_CloseChunkStack (0x490930/0x4909d0/0x490c40/0x45e8d0/0x490980)
  -> depends on: LoadNamedResource-family internals not required (this
                 class wraps its OWN file handle, separate from BigFile)
  <- depended on by: LoadGame (0x475430), and likely other not-yet-found
                 callers (this is described as a generic reusable class,
                 not save-specific — worth re-checking get_function_callers
                 on IffFile_Open if this area is revisited)

LoadGame (0x475430)
  -> depends on: IffFile_Open/FindFormChunk/FindChunk/Read/CloseChunkStack,
                 PTR_DAT_00500a24 (5-entry field tag table, tags not
                 read), the DAT_0052a3f0..DAT_0052a480 campaign-state
                 block (same block WinMain/LoadPlayerProfile touch)
  <- depended on by: RunSaveGameBrowserScreen (case 0xb, "load selected
                 slot"), FUN_004315c0 (NOT YET IN DB — also calls
                 IffFile_Open, not traced further)

Mission load chain:
RunMissionSelectMapScreen (0x44f3d0, VR loop roomType=5 destination)
  -> calls: InitializeMissionGameplay (with DAT_00562dc8 set to the
                 chosen mission number)

InitializeMissionGameplay (0x4934f0)
  -> depends on: LoadMissionFile (fatal via ReportAssertionFailureEx on
                 failure), a large not-decoded "previous mission result
                 code -> next mission-select code" branch table
  <- depended on by: RunMissionSelectMapScreen; ALSO called as part of
                 the FUN_004934f0/FUN_00494040/FUN_004942b0 trio seen
                 repeatedly in WinMain's own state machine and in
                 RunMainMenuScreen's "attract mode" loop — this trio is
                 almost certainly "load mission / run mission / unload
                 mission", the real gameplay entry point, reached from
                 at least 3 independent places

LoadMissionFile (0x451d90)
  -> depends on: LoadResourceFileBuffer, ReadMissionDirectoryEntry
                 (called 27x, once per directory entry), 27 distinct
                 mission-data-table globals (addresses known, layouts
                 NOT decoded — see confidence_db.md open follow-ups)
  -> depends on (NOT YET IN DB): FUN_0045cb40, FUN_00452010,
                 FUN_00453050, FUN_00457c10, FUN_0045cbc0 (5
                 finalization/cross-link passes run after all 27
                 directory entries are read)

LoadResourceFileBuffer (0x45a300)
  -> depends on: LoadNamedResource (archive path), FUN_004ad6e0 (NOT YET
                 IN DB, "direct file access allowed" check),
                 FUN_0045a3e0 (NOT YET IN DB, raw loose-file reader)

LoadNamedResource (0x4c5bd0) -> HOG_BigRead (0x4c7f60)
  -> depends on: OpenBigFile's archive handle (DAT_005202d4), SR_MEM_allocate
  <- depended on by: extremely widely used — menu screens, the VR loop,
                 mission loading all call this constantly. THE central
                 asset-loading choke point; a high-value target for
                 understanding exactly what asset types flow through it
                 if this project ever wants a full "list every resource
                 the game loads" pass
```

## Flight/combat gameplay core loop (fifth session)

```
RunMissionGameplay (0x494040)
  -> depends on: UpdateMissionTick (once per elapsed fixed-timestep
                 tick), FUN_00477670 (NOT YET IN DB, multiplayer
                 network tick, called in lockstep with
                 UpdateMissionTick), UpdateMissionFrame (once per
                 rendered frame), CheckMissionExitState (called instead
                 of UpdateMissionFrame when the pause/menu flag
                 DAT_0057e04c is set)
  <- depended on by: InitializeMissionGameplay (the load/run/unload
                 trio's middle leg — confirmed this session)

UnloadMission (0x4942b0)
  -> depends on: FreeMissionFile (0x45a530, the direct counterpart to
                 LoadMissionFile — confirmed via matching "mission
                 destroy" debug tag)
  <- depended on by: the same trio's third leg

UpdateMissionTick (0x477850)
  -> depends on (NOT YET IN DB): FUN_004774d0 (near-certainly the real
                 physics/AI simulation step — this wrapper does nothing
                 else of substance), FUN_0049ceb0/FUN_0049cf40
                 (multiplayer-specific alternate tick path)

UpdateMissionFrame (0x4924b0)
  -> depends on (NOT YET IN DB): FUN_00494400 (damage-severity visual
                 swap, called on state change), FUN_0046bd00 (engine
                 smoke particle emission), FUN_004150d0 (proximity/
                 distance warning trigger), the unrecovered per-object
                 struct (dereferenced at dozens of offsets, no type
                 recovered — see confidence_db.md's note on this being
                 a substantial subsystem in its own right, analogous to
                 wc3remake's Actor struct work), DAT_00539a34 mission
                 cutscene-state values 7/8/0x1a/0x1b/0x1c/0x1d
  <- depended on by: RunMissionGameplay's per-frame loop iteration

CheckMissionExitState (0x491fc0)
  -> depends on: DAT_0057daa4 (exit-signal code, values 5/6/7 mapped to
                 distinct exit behaviors)
  <- depended on by: RunMissionGameplay (called instead of
                 UpdateMissionFrame when paused)
```

## Physics/AI simulation step (sixth session)

```
ProcessMissionSimulationTick (0x4774d0)
  -> depends on: UpdateObjectPhysicsAndTimers, UpdateShieldQuadrants,
                 UpdateWeaponFiring (called per active object in
                 DAT_00587ce0), FUN_004c2690 (NOT YET IN DB, round-robin
                 per-tick extra work, called twice on one object/tick)
  <- depended on by: UpdateMissionTick (its only substantive work)

UpdateObjectPhysicsAndTimers (0x476c90)
  -> depends on: the ship-object struct's +0x14/+0x5c transform pair,
                 +0xa4 energy-capacity-group chain, +0xf8/+0x100 child
                 list
  -> depends on (NOT YET IN DB): FUN_0047c7b0, FUN_0047c800 (energy-
                 threshold-crossing events)
  <- depended on by: ProcessMissionSimulationTick (also recurses into
                 itself via the child-object list)

UpdateShieldQuadrants (0x476fc0)
  -> depends on: ship-object +0x5f0..+0x5fc (4 capped floats),
                 +0x10 class-definition pointer, +0xb95 mode byte
  <- depended on by: ProcessMissionSimulationTick

UpdateWeaponFiring (0x4770e0)
  -> depends on: ship-object +0x130/+0x134 hardpoint array, +0x140
                 energy pool, +0x13c ammo count, +0x14c alt-fire toggle,
                 FireWeapon (resolved next session)
  <- depended on by: ProcessMissionSimulationTick
```

## FireWeapon chain (seventh session)

```
FireWeapon (0x47c5f0)
  -> depends on: weapon-instance +0xac (-> weapon-type-def +0x64
                 variant index), the 200-entry projectile pool
                 (DAT_00563148), 2 global 15-entry tables keyed by
                 variant index (DAT_00500ce0 sound, DAT_00500f64
                 cooldown duration), the active-projectile linked list
                 (DAT_00563144 head)
  -> depends on (NOT YET IN DB): FUN_0047bdb0 (actual projectile spawn),
                 FUN_00499f20 (owner-info lookup)
  <- depended on by: UpdateWeaponFiring (direct player/AI fire
                 decision), FireChildTurrets (turret auto-fire)

FireChildTurrets (0x47c7b0)
  -> depends on: ship-object +0xf8/+0x100 child-object list (SAME
                 fields UpdateObjectPhysicsAndTimers documented —
                 cross-confirmed via independent usage), FireWeapon
  <- depended on by: UpdateObjectPhysicsAndTimers (as one of its two
                 energy-threshold-crossing event handlers)

SpawnWeaponVisualEffect (0x47c800)
  -> depends on: weapon-instance +0xa4 effect-anchor sub-table (count
                 +0x214, array +0x218, stride 0x7c), a global active-
                 effect object (DAT_005636dc)
  <- depended on by: UpdateObjectPhysicsAndTimers (the OTHER energy-
                 threshold-crossing event handler — confirmed distinct
                 from FireChildTurrets despite both being reached the
                 same way)

GetOwningShip (0x499f20)
  -> depends on: a weapon/mount object's +0xec parent-link chain,
                 walked to root, then that root's +0xa8 field
  <- depended on by: SpawnProjectile (aim-assist target lookup, local-
                 player check), FireWeapon (indirectly, via SpawnProjectile)

SpawnProjectile (0x47bdb0)
  -> depends on: the 200-entry projectile pool slot FireWeapon
                 allocated, the projectile-type-definition table
                 (DAT_00500ce0, now known to hold sound+lifetime+scale,
                 not just sound), a per-type mesh/visual table
                 (&DAT_00500cd0, stride 0x2c, NOT YET opened), a
                 per-type DirectInput force-feedback effect-handle
                 array (DAT_005ddc58 family), a 2-slot-per-side beam-
                 effect ring buffer (DAT_0056317x/DAT_0056316x),
                 GetOwningShip (for aim-assist and force-feedback
                 local-player checks), the main object array
                 (DAT_00587ce0) for its proximity-detonation scan
  -> depends on: CreateWeaponProjectileVisual (per-weapon-type mesh
                 builder — NOT transform/velocity init as first
                 guessed), CreateEffectObject (beam/glow effect
                 creation), PropagateAlertToChildren (proximity-alert
                 hierarchy propagation)
  <- depended on by: FireWeapon
```

## Weapon visual/arsenal chain (ninth session)

```
CreateWeaponProjectileVisual (0x47d9a0)
  -> depends on: weapon/projectile struct's type field (param_1[0]),
                 15 embedded mesh-filename literals (the real weapon
                 arsenal — see confidence_db.md table), CreateEffectObject
                 (huge-gun glow effect, types 0xd/0xe only)
  -> depends on: SetPosition, SetOrientationMatrix, CreateMeshInstance,
                 CreateMultiPartMeshGroup, CreateGroupNode (all
                 resolved this session — see below)
  -> depends on (NOT YET IN DB): FUN_0049c600 (second huge-gun-only
                 effect object)
  <- depended on by: SpawnProjectile

CreateEffectObject (0x4c4f30)
  -> depends on: SR_MEM_allocate (220-byte alloc, tagged surrenderlib
                 line 0x2b5)
  <- depended on by: SpawnProjectile (beam-weapon visual),
                 CreateWeaponProjectileVisual (huge-gun glow effect) —
                 confirmed genuinely generic, used by 2 independent
                 callers now

PropagateAlertToChildren (0x49bef0)
  -> depends on: ship-object +0xf8/+0x100 child-object list (THIRD
                 independent confirmation of these fields),
                 InvokeEffectAnchorCallback (called per object, resolved
                 this session — param_2 is a CALLBACK, not an "alert
                 source" as first described; correction noted in
                 confidence_db.md)
  <- depended on by: SpawnProjectile (proximity-detection reaction)
```

## Effect-anchor callback system (eleventh session)

```
InvokeEffectAnchorCallback (0x49bd30)
  -> depends on: object+0xa8 (mode switch), object+0xa4 -> +0x20c
                 (count) / +0x210 (array) effect-anchor sub-table (a
                 THIRD distinct anchor-table shape, alongside the
                 +0xa4 -> +0x214/+0x218 shape used by
                 SpawnWeaponVisualEffect — relationship between the two
                 NOT resolved), anchor-node +0x48 (leaf flag) / +0x50,
                 +0x54 (child-node offsets)
  -> depends on (NOT YET IN DB): the actual callback function(s)
                 passed in by real callers — unidentified, so the
                 traversal's PURPOSE remains unknown even though its
                 SHAPE is now clear
  <- depended on by: PropagateAlertToChildren

CreateParticleEmitter (0x49c600)
  -> depends on: SR_MEM_allocate
  <- depended on by: CreateWeaponProjectileVisual (huge-gun weapons
                 0xd/0xe only — the second of their two extra effect
                 objects, alongside CreateEffectObject)
```

## Projectile impact / shield / subsystem damage (twelfth session)

```
ProcessProjectileImpact (0x479b40)
  -> depends on: SpawnProjectile's "nearby object" queue (pool-slot
                 +0x64 count / +0x68 array, confirmed by matching
                 field shape), the type-0xd/0xe detection-radius bonus
                 (re-derived independently, cross-confirms
                 SpawnProjectile's own copy of this constant),
                 ship-object +0x5f0..+0x5fc shield-quadrant floats
                 (NOW READ/WRITTEN here as real damage-absorption
                 values — promotes that struct field from Confidence 1
                 guess to Confidence 2-3), _DAT_0051cf34/_DAT_0051cf78
                 (shared with UpdateShieldQuadrants — confirmed as
                 live per-quadrant damage-drain trackers),
                 InvokeEffectAnchorCallback (called recursively against
                 the HIT SHIP's own subsystem/component anchor list —
                 this IS the callback mystery's resolution)
  -> depends on (NOT YET IN DB): FUN_00463d30 (hit-facing resolver),
                 FUN_00463ee0 (apply-damage), FUN_004645c0 (effect/
                 sound dispatcher), FUN_00479940/FUN_00479b30 (hit-
                 exemption checks)
  <- depended on by: (not directly determined — reached via the
                 callback mechanism from SpawnProjectile's proximity
                 scan, not a direct call)

UpdateShieldPowerAndComponents (0x465380)
  -> depends on: PropagateAlertToChildren, a literal "Ulysses Fin"
                 component-name string (probable capital-ship class +
                 subsystem name), _DAT_0051cf34/_DAT_0051cf78
  -> NOT decoded in full detail this session

HandleComponentDestroyedEvent (0x495ac0)
  -> depends on: PropagateAlertToChildren, FUN_004645c0
  -> NOT decoded in full detail this session
```

## SurrenderLib scene-node primitives (tenth session)

```
SetPosition (0x4c0e60) -> trivial 3-float store, no dependencies
SetOrientationMatrix (0x4c2410)
  -> depends on (NOT YET IN DB): FUN_004c30e0/FUN_004c3100 (presumed
                 cos/sin)

CreateMeshInstance (0x4c4bd0)
  -> depends on: SR_MEM_allocate
  -> depends on (NOT YET IN DB): FUN_004c1be0 (x2), FUN_004c0e30 (x2)
                 — likely default-init for 2 sub-blocks (bounding
                 box + transform)
  <- depended on by: CreateWeaponProjectileVisual (single/multi-mesh
                 weapon cases), generic engine infrastructure —
                 presumably called far more widely than this session's
                 weapon-focused trace has covered

CreateMultiPartMeshGroup (0x4c4db0)
  -> depends on: SR_MEM_allocate
  -> same NOT-YET-IN-DB deps as CreateMeshInstance
  <- depended on by: CreateWeaponProjectileVisual ("BMO"-suffixed
                 multi-part weapons: PulseCannon, Collapsergun, and
                 the huge guns)

CreateGroupNode (0x4c51c0)
  -> depends on: SR_MEM_allocate, SetPosition, SetOrientationMatrix
  -> depends on (NOT YET IN DB): FUN_004c4190 (extra init step not
                 shared with CreateEffectObject)
  <- depended on by: SpawnProjectile (projectile root node)
```

## Menu-screen internals (NOT YET IN DB — next layer down)

Each screen handler calls several of its own not-yet-decompiled helpers.
Highest-value targets if this cluster is revisited:
  RunMultiplayerSetupScreen -> FUN_004bc720 (connect to selected session),
                 FUN_004b5c50 (network provider init, called by nearly
                 every multiplayer-adjacent screen)
  RunMultiplayerLobbyScreen -> FUN_004bcbe0/FUN_004bca70 (roster
                 refresh), FUN_004bcc70/FUN_004bcc20 (ready-flag toggles)
  RunControlsOptionsScreen -> FUN_0042c5f0/FUN_0042aa80 (key-rebind
                 conflict detection and confirmation dialog)
  RunSaveGameBrowserScreen -> FUN_0045e8d0 (save-thumbnail decode),
                 FUN_00490930/FUN_004909d0/FUN_00490c40/FUN_00490980
                 (an IFF-chunk reader family — FourCC-based, matches the
                 BigFile/HOG format's own magic-number style, likely a
                 shared "generic chunked file" reader used across many
                 subsystems, not just saves)

RunShipInteriorVRLoop (0x439fb0)
  -> depends on: VRRoomNode (struct, confirmed this session — see
                 confidence_db.md), OpenBigFile-family resource
                 resolution (FUN_004c83f0, NOT YET IN DB, "resource
                 search" step before every _BinkOpen), SafeFormatString,
                 ReportAssertionFailureEx (movie-not-found is fatal, not
                 a soft failure)
  -> depends on (NOT YET IN DB): the room-graph DATA itself past the 5
                 nodes read directly this session (each VRRoomNode's
                 target[5] pointers reach further nodes not yet read),
                 FUN_0043c1c0 (installed as a per-frame callback at
                 DAT_00588730+0x88 throughout), FUN_00437df0/
                 FUN_004394d0/FUN_00494b50 (per-entry/exit room setup,
                 called every room transition)
  <- depended on by: RunMissionBriefingScreen (CONFIRMED this session —
                 sets DAT_0051d478 to one of the two root nodes right
                 before what must be a call into this loop, resolving
                 the earlier "caller not yet traced" gap; the exact
                 call instruction itself wasn't pinpointed, but the
                 handoff of state is unambiguous)

RunMissionBriefingScreen (0x437010, RunMenuScreenLoop screen ID 7)
  -> depends on: EnsureCorrectCDMounted (called directly), SafeFormatString,
                 ReportAssertionFailureEx, FUN_004c83f0 (resource search),
                 the campaign-pair VRRoomNode roots (0x50b2b8/0x506ad0)
                 which it selects between and hands off to
  -> depends on (NOT YET IN DB): FUN_0043eaf0, FUN_00441aa0, FUN_004620d0,
                 FUN_00442720, FUN_00442cc0, FUN_004433c0 (per-frame
                 "briefing complete" poll) — the screen's own internal
                 mechanics beyond the mission-index-driven movie/speech
                 selection and VR handoff
  <- depended on by: RunMenuScreenLoop (screen ID 7); also called
                 directly by name from elsewhere in WinMain's state
                 machine when DAT_00562dc8==0x1d (mission 29 special case)

Ship-interior room graph (COMPLETE walk, ~145 nodes read 2026-09-08)
  -> structural facts confirmed by direct traversal:
     - EVERY roomType!=0 node is a hard jump to its hub pair; the node's
       own target[5] array is vestigial once that fires (frequently
       self-referential or left NULL despite numTargets claiming an
       entry)
     - Multiple physically-distinct "twin" doors lead to the same hub
       with identical data (3 separate roomType=5 doors -> 0x50b678
       found at 0x50b378/0x50b6a8/0x50acb8, for example)
     - The graph is ONE connected structure, not 6 disjoint per-hub
       trees — subtrees discovered from different hubs repeatedly
       converge on the same nodes (e.g. 0x50af28, reached from the
       ITAC/ROT hub, points back to 0x50aef8/0x50b288/0x50b348 — the
       entry room's own direct children)
     - Early-campaign (DAT_00562dc8 < 0x13) subgraph is a tiny ~7-8
       node loop shared across 4 of 5 special hubs (only the briefing
       hub differs) — a deliberate progression gate, not coincidence
  -> COMPLETE: every target address discovered resolves to an
     already-visited node — no leaves remain unread as of this session
  <- depended on by: RunShipInteriorVRLoop's per-frame hit-testing and
     roomType dispatch (both already documented)

Ship-interior room map (roomType -> hub pair)
  -> depends on: VRRoomNode.roomType values read directly in
                 RunShipInteriorVRLoop's dispatch, cross-referenced
                 against the 6 root-node pairs' own moviePath strings
                 (read via read_memory this session)
  roomType 1 -> RunMenuScreenLoop (no room hub — exits VR loop entirely)
  roomType 2 -> hub pair 0x50aec8/0x506c80 ("itac2rot.bik")
  roomType 5 -> hub pair 0x50b678/0x506d10 ("pod2rot2.bik")
  roomType 6 -> hub pair 0x50b3a8/0x506f20 ("lockzomo.bik")
  roomType 7 -> hub pair 0x50b318/0x506e30 ("tv2brd.bik")
  roomType 9 -> hub pair 0x50b168/0x506dd0 ("cd_cd2d.bik")
  entry pair 0x50b2b8/0x506ad0 ("b2iloop.bik" / "rel_ladd_bunk.bik")
                 <- depended on by: RunMissionBriefingScreen (sets this
                 as the VR loop's starting point after a briefing)

EnsureCorrectCDMounted (0x42fe00)
  -> depends on: OpenBigFile, CloseBigFile, SafeFormatString,
                 ReportAssertionFailureEx, LoadInstallPathsFromRegistry's
                 DAT_005d62c4 flag (skips disc-swap UI entirely when set)
  -> depends on (NOT YET IN DB): FUN_004ac6c0 (returns currently-mounted
                 CD number), FUN_0043eb30 (disc-present poll / "please
                 insert disc N" UI, called in a retry loop)
  <- depended on by: WinMain calls this directly (`FUN_0042fe00(...)`
                 appears at several points in WinMain's post-bootstrap
                 body, e.g. right before mission loads)
```

## Coverage note

This cluster is intentionally shallow — it covers the program's literal
entry sequence, window bring-up, and the SurrenderLib diagnostics/assertion
primitives, not any real game subsystem (rendering, physics, mission
scripting, networking) yet. Every "NOT YET IN DB" edge above is a
legitimate, visible gap, not a rounding error: this project has 2434
functions total and roughly two dozen have been examined so far (up from
~12 after the second pass, 2026-09-08). The SurrenderLib diagnostics
cluster (`SR_printf`/`ReportAssertionFailure(Ex)`) is a strong candidate
for wide fan-in from elsewhere in the binary once other subsystems are
explored — worth re-checking `get_function_callers` on it periodically as
coverage grows, rather than assuming its current "callers not yet
enumerated" note stays small.
