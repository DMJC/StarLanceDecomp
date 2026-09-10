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
  -> depends on: GetShieldFacingIndex (hit-facing resolver, itself a
                 thin wrapper over unopened FUN_00463ca0), ApplyShieldDamage
                 (the real damage-application function), ApplyComponentDamage
                 (grouped-hitbox subsystem damage — resolved this session)
  -> depends on (NOT YET IN DB): FUN_00479940/FUN_00479b30 (hit-
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
  -> depends on: PropagateAlertToChildren, ApplyComponentDamage
  -> NOT decoded in full detail this session
```

## Shield/component damage resolution (thirteenth session)

```
GetShieldFacingIndex (0x463d30)
  -> depends on: ComputeHitQuadrant (the real facing-index computation
                 this function wraps — resolved this session)
  <- depended on by: ProcessProjectileImpact

ApplyShieldDamage (0x463ee0)
  -> depends on: ship-object +0x5f0..+0x5fc shield-quadrant floats
                 (damage committed here), _DAT_0051cf34/_DAT_0051cf78,
                 ScaleDamageForDifficulty, HasDamageAuthority
  -> depends on (NOT YET IN DB): FUN_004641f0... resolved as
                 ApplyHullDamage this session (see below — NOT actually
                 called from ApplyShieldDamage's own overflow path in
                 the code read so far; the two are siblings under
                 ProcessProjectileImpact, not caller/callee — corrected
                 from the tentative "hull-damage spillover" dependency
                 guessed last session), FUN_00474c80 (scoring/kill-
                 credit), FUN_00456dd0/FUN_00463e10 (local-player hit
                 feedback)
  <- depended on by: ProcessProjectileImpact

ApplyComponentDamage (0x4645c0)
  -> depends on: ship-object +0xf8/+0x100 child list (component-group
                 lookup), ReportAssertionFailureEx (attackerSlot bounds
                 check — confirms general-purpose assert usage outside
                 bootstrap code), ScaleDamageForDifficulty, HasDamageAuthority
  -> depends on (NOT YET IN DB): FUN_00474e00 (component-
                 destroyed reaction), FUN_00415270 (wingman/comm
                 chatter trigger), FUN_0047d1f0 (per-turret hit mark)
  <- depended on by: ProcessProjectileImpact, HandleComponentDestroyedEvent
```

## Difficulty/authority/hull/destruction (fourteenth session)

```
ScaleDamageForDifficulty (0x463d70)
  -> depends on: DAT_00582e8c (deathmatch flag), DAT_00562f14
                 (difficulty level 0/1/2)
  <- depended on by: ApplyShieldDamage, ApplyComponentDamage,
                 ApplyHullDamage (shared difficulty curve across all
                 three defense tiers)

HasDamageAuthority (0x4b5590)
  -> depends on: DAT_0058832c (player count), DAT_005dc1e8 (host
                 flag), a per-client NPC-ownership offset table
                 (DAT_005dccc4) and modulo divisor (DAT_005db8e0) for
                 the distributed co-op NPC-authority scheme
  <- depended on by: ApplyShieldDamage, ApplyComponentDamage (shared
                 multiplayer-authority gate)

ApplyHullDamage (0x4641f0)
  -> depends on: ship-object +0x600 hull-section float array (a THIRD
                 defense tier, sibling to the +0x5f0 shield array, NOT
                 nested under it), ScaleDamageForDifficulty,
                 HasDamageAuthority, SetShipDestroyedState (called on
                 hull depletion)
  <- depended on by: (caller not directly traced — reached via the
                 same ProcessProjectileImpact-driven damage dispatch
                 as the other two tiers, exact call site not pinpointed)

ComputeHitQuadrant (0x463ca0)
  -> depends on: ship-object bounding-box extents (+0x5a0/+0x5a8/
                 +0x5ac/+0x5b4), a local-space hit-point input
  <- depended on by: GetShieldFacingIndex

SetShipDestroyedState (0x401f30)
  -> depends on: object+0x684 (CORRECTED this session — an AI
                 command/state structure, not a "current target"
                 reference as described in 3 earlier sessions; see
                 confidence_db.md's correction note), TrySetAiState
  <- depended on by: ApplyHullDamage (on hull depletion)

TrySetAiState (0x40ca50)
  -> depends on: PTR_DAT_004e06e0 (AI state-definition table: OnExit
                 callback, flags, display name, priority per state —
                 CONTENTS now read directly, see below), object+0x680
                 (AI-initialized flag), object+0x688 (mid-transition
                 busy flag), ReportAssertionFailureEx (rejected-
                 transition logging)
  <- depended on by: SetShipDestroyedState, and (by design, though not
                 individually traced) presumably every other AI
                 behavior-change call site in the game
```

## AI state catalog (sixteenth session)

```
PTR_DAT_004e06e0 (3-pointer array: group0/1/2 state tables)
  group0 -> 0x4e0050 (~20 entries read: Find Scoop Up, Jump Out, Jump
            In, Slow Rotate, Ship Follow Curve, Toggle Cloak, Patrol
            Route, Formation Regroup, Object Attack, "Ripper grabs
            target object", Explode, Find New Target, Escort, Land,
            Run Away, Fly, Warp Out, Warp In, Launch Missile, Fly
            Aimlessly, Do Nothing — string pool at 0x4e0a80)
  group1 -> 0x4e04a0 (~20 entries read: Fight(truncated), "Make
            capship list left", Disrupted, "Eject fighter attack",
            "Ripper attach cargo pod to Mammoth", "Ripper end drop
            object", "Dark reign shoot", Dock, Eject Spin, Scoop Up,
            Fight, Launch, Torpedo, Avoid Target, Multiplayer Control,
            Player Control, "Fly ship backwards", "Immediately set
            ship to zero velocity and rotation", "Huuuuuuuuge
            explosion", "Turns object lights off", "Make ripper drop
            what it's carrying" — string pool at 0x4e0780)
  group2 -> 0x4e06c8 (read this session: essentially empty — one
                 placeholder entry whose name points to the shared
                 "empty string" global DAT_00515d70; no state IDs
                 observed anywhere fall in the 200+ range this group
                 would cover)
  <- depended on by: TrySetAiState (the whole priority-gated FSM this
                 table drives)

state 33 ("Dark Reign shoot", group0) -> HandleDarkReignAttackState
  -> depends on: HasDamageAuthority, deathmatch team array (DAT_005db650),
                 ScanForTargetCandidate, QueueAiEvent
  <- confirms user-supplied claim: this is a deathmatch superweapon
                 attack state, tied to the "Deathmatch Dark Reign
                 target" objective (string at 0x4e06ec)

state 110 ("dark reign shoot", group1) -> HandleDarkReignExitState
  -> depends on (NOT YET IN DB): FUN_0040e8a0 (cleanup)
```

## AI perception/event queue — a second AI subsystem (eighteenth session)

```
ScanForTargetCandidate (0x401cb0)
  -> depends on: object+0x684 (AI command struct, mode selector at +2),
                 DAT_005267cc (mission-scripted candidate list, one of
                 LoadMissionFile's 27 directory tables — direct link
                 between AI targeting and mission-authored data),
                 GetObjectIndexFromPointer (candidate iterator helper),
                 ScanNavigationGraphTarget (mode-2 delegate)
  <- depended on by: HandleDarkReignAttackState (and presumably other
                 AI target-search call sites, not individually traced)

ScanNavigationGraphTarget (0x401d80)
  -> depends on: DAT_005294fc/DAT_00529500/DAT_00529520 (mission
                 navigation-graph node array — 3 previously-separate
                 LoadMissionFile directory tables now understood as
                 ONE structure), DAT_005267c0 (per-node type byte),
                 DAT_00538c90 (type-1 node sub-candidate-list, same
                 shape as ScanForTargetCandidate's own mode-1 table)
  -> depends on (NOT YET IN DB): FUN_00453070 (type-2 recursion prep),
                 FUN_0045a440 (invalid node-type fallback)
  <- depended on by: ScanForTargetCandidate (mode 2)

GetObjectIndexFromPointer (0x4531c0)
  -> depends on: DAT_0052951c (base of a 76-byte-stride mission-object
                 array)
  <- depended on by: ScanForTargetCandidate, ScanNavigationGraphTarget

GetNavGraphNodeIndexFromPointer (0x453070)
  -> depends on: DAT_005294fc (nav-graph node array base, cross-
                 confirmed a second way — same global ScanNavigationGraphTarget
                 uses directly)
  <- depended on by: ScanNavigationGraphTarget (type-2 recursive case)

HandleFatalMissionError (0x45a440)
  -> depends on: FUN_0045a460 (NOT YET IN DB, actual emergency-dump
                 writer), FUN_004d04ed (CRT exit, identified session 1)
  <- depended on by: ScanNavigationGraphTarget (invalid node-type
                 fallback)

BeginNetworkMessage (0x4b9920) / WriteMessageBits (0x4b9830)
  -> depends on: two parallel per-player buffer sets (DAT_005db674/
                 DAT_005db678 vs DAT_005db67c/DAT_005db680, selected by
                 a flags bit — reliable/unreliable channel guess),
                 DebugLog_Stub, the full DPMessage name table
                 (PTR_s_DPMESSAGE_END_0050ca94, READ IN FULL — see
                 below, ~80 real message names), DAT_0050ca88
                 (trailing-bit mask table)
  <- depended on by: BroadcastAiEventPacket, and (by design, given the
                 generic bit-packed-message shape) presumably most/all
                 of the game's DirectPlay traffic — confirms "DP" =
                 DirectPlay throughout the codebase (see confidence_db.md)
```

## The full DirectPlay message catalog (twenty-first session)

```
PTR_s_DPMESSAGE_END_0050ca94 (message-name pointer table, indexed by
                               message type ID, used by BeginNetworkMessage)
  -> ~52 DPGMESSAGE_* entries (gameplay sync): confirms SUBOBJHIT/
     SUBOBJSTRENGTH as the real name for ApplyComponentDamage's model;
     reveals PROXMINE (real separate mine mechanic, distinct from the
     "huge gun" 0xd/0xe correction), IONCANNONSTATE/IONCANNONROTATION
     (a new weapon, Ion Cannon), TAGBOMBEXPLODES/TAGBOMBOWNER (Tag
     Bomb), TRIGGERNUKE, SPECTRALSHIELDSACTIVE (a shield mechanic
     distinct from the quadrant system), ECMACTIVE, CHAFF (matches
     the "chaff exit" debug tag from RunMissionGameplay), CLOAKACTIVE
     (matches "Toggle Cloak" AI state), KILLEDBYSHADOW/SETSHADOW (an
     unexplained "Shadow" mechanic), DEATHSPEWBEACONS,
     DROPPEDCOMMSRELAY, a pickup/powerup system (DROPPICKUP/
     PICKEDUP_OBJECT/RESPAWN_PICKUP/POWERUP_TRIGGERED), deathmatch
     resync machinery (DM_SEND_RESYNC/DM_REQUEST_RESYNC/
     RESYNC_DMSCENARIO), and DPGMESSAGE_DISEASED (unexplained)
  -> ~28 DPIMESSAGE_* entries (lobby/session): full matchmaking
     protocol — host migration, ready-check, team colors, world-state/
     mission-spec sync for late joiners, custom ping (cPing/sPing)
  <- depended on by: BeginNetworkMessage (name lookup for debug
                 logging), and implicitly the message-type-ID space
                 every DirectPlay send in the game uses
```

## The "Shadow" (spectator) system (twenty-second session)

```
HandleSetShadowMessage (0x4b49f0, DPGMESSAGE_SETSHADOW = message ID 50)
  -> depends on: DAT_005db538 (current shadow/spectate-target slot),
                 &DAT_005db654 (60-byte-stride per-player name array),
                 FUN_00491030 (resource-string lookup, used throughout
                 the UI, still not decompiled), ship-object
                 +0x5f0..+0x600 shield-quadrant array (zeroed when the
                 LOCAL player becomes the shadow), SendSetShadowMessage
                 (broadcast)
  <- depended on by: (network dispatch on message ID 50, not
                 individually traced)

HandleKilledByShadowMessage (0x4b4b30, DPGMESSAGE_KILLEDBYSHADOW = message ID 51)
  -> depends on: ship-object +0x694 ("last attacker" field, documented
                 several sessions ago — written here with sentinel
                 -2 instead of a real attacker slot), same name-array/
                 resource-lookup pattern as HandleSetShadowMessage,
                 SendKilledByShadowMessage (broadcast)
  <- depended on by: (network dispatch on message ID 51, not
                 individually traced)

SendSetShadowMessage (0x4bb030) / SendKilledByShadowMessage (0x4bb060)
  -> depends on: BeginNetworkMessage, WriteMessageBits (confirmed via
                 exact `mov edx, 50`/`mov edx, 51` immediate-value
                 byte-pattern search, not guessed)
```

## "Spectral Shields" — temporary invulnerability (twenty-third session)

```
SetSpectralShieldsActive (0x415430, DPGMESSAGE_SPECTRALSHIELDSACTIVE = message ID 67)
  -> depends on: DAT_0057bf20 (availability gate), ship-object +8 flags
                 (bit 0x8000000 = the invulnerability flag itself —
                 confirms user-supplied documentation claim directly),
                 the weapon-type-definition table's +0x64 field (type
                 ID, shared with FireWeapon) and a NEW +0xb-stride
                 sibling field DAT_00500cec ("threat weight" per type,
                 alongside DAT_00500ce0/ce4/ce8 documented earlier),
                 ship-object +0x670 (NEW field: most-threatening-
                 nearby-weapon-type result), SendSpectralShieldsMessage
  <- depended on by: (activation call site not traced — presumably a
                 player input/ability-hotkey handler)

SendSpectralShieldsMessage (0x4babc0)
  -> depends on: BeginNetworkMessage, WriteMessageBits (confirmed via
                 exact `mov edx, 0x43` immediate-value byte-pattern
                 search)

ProcessNetworkMessage (0x4b6f80) [master incoming-message dispatcher]
  -> DPGMESSAGE_SPECTRALSHIELDSACTIVE case (0x4b90b0-0x4b9113):
     depends on: ReadMessageBits, ship-object +8 flags (0x8000000 bit),
                 ship-object +0x670 (receives the network-synced
                 "blocked weapon type" value here — SECOND confirmed
                 write site for this field, alongside
                 SetSpectralShieldsActive's own local computation)
  -> the other ~79 cataloged message cases NOT individually examined
  <- depended on by: incoming DirectPlay traffic (not individually
                 traced to a specific receive-loop caller)

ReadMessageBits (0x4b6e50)
  -> depends on: DAT_005dcce8 (incoming message buffer), DAT_005dcc9c
                 (bit cursor), DAT_0050ca88/DAT_0050ca7c (trailing-bit
                 mask tables) — structurally symmetric to WriteMessageBits
  <- depended on by: ProcessNetworkMessage
```

QueueAiEvent (0x402660)
  -> depends on: object+0xb8c/+0xb90 (event queue count/buffer, lazily
                 allocated 720 bytes), ReportAssertionFailureEx
                 (overflow guard, "DPStack Overflow on %s"),
                 DAT_005883b0 (tick counter, for expiry timestamps),
                 HasDamageAuthority (multiplayer broadcast gate)
  -> depends on: BroadcastAiEventPacket (multiplayer AI-event
                 broadcast — resolved this session)
  <- depended on by: HandleDarkReignAttackState; presumably a wide
                 range of other AI decision-making call sites given
                 its generic "push a perceived event with TTL" shape
                 — relationship to TrySetAiState's state machine not
                 directly traced

BroadcastAiEventPacket (0x4ba560)
  -> depends on (NOT YET IN DB): FUN_004b9920 (begin packet),
                 FUN_004b9830 (write one packet field — called
                 4-8 times per broadcast depending on event type)
  <- depended on by: QueueAiEvent
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

## Single-player campaign structure (2026-09-08, twenty-fifth session)

```
InitializeMissionGameplay (0x4934f0)
  -> depends on: DAT_0050c2e8 (SP prev-mission-outcome code),
                 DAT_00588400[slot*0x54] (MP prev-mission-outcome code, per-player array),
                 DAT_005883c0 (resolved cutscene/debrief ID, 0x106-0x11e range),
                 FUN_004a44d0 (resolves DAT_005883c0/DAT_0057e048 into a loadable resource, not decompiled),
                 DAT_00566f8c / DAT_00579990 (ship-class-keyed eject-eligibility-shaped flags)
  <- depended on by: campaign mission-to-mission flow (caller not re-traced this session)

Mission-scripting command table (data, ~0x4f31xx-0x4f33xx+, exact bounds unknown)
  -> depends on: (nothing -- static data table)
     entries reference: description strings ("TerminateMission" @0x4f4074,
       "End the mission, and drop to death sequence" @0x4f4048,
       "Sets a Mission Objective's status" @0x4f43dc),
       handler function pointers (0x459bb0, 0x459bd0, 0x459c90, ... range,
       none decompiled this session)
  <- depended on by: presumably the .dte mission script interpreter (not yet located)
     and/or shared with SLEdit.exe (mission editor, gamedata/StarLancer/) -- not confirmed

mission.cpp API (source-confirmed via debug strings, code not newly traced this session)
  init_mission / process_mission / destroy_mission
  -> depends on: gMissionBuffer, Mission_TriggerCount / MAX_TRIGGERLIST (trigger-list
     system referenced in an assert string, not yet located in code)
  <- matches structurally to: LoadMissionFile / RunMissionGameplay / UnloadMission
     (already documented in an earlier session under different working names)
```

## Mission-scripting command handlers (2026-09-08, twenty-sixth session)

```
MissionScript_WaitForKey (0x459ae0)
  -> depends on: DAT_005799bc (current key-wait index, global),
                 DAT_004e2380 (0x4e-byte-stride per-key condition table),
                 DAT_00595c68 / DAT_00595c92 / DAT_00595c9e / DAT_00595c85 / DAT_00595d05
                   (condition-flag bytes/arrays checked per condition-type case),
                 DAT_004e23cc (0x27-stride secondary index table),
                 DAT_00588370 (flag array indexed by the above)
  <- depended on by: mission-scripting command dispatch table (entry for "WaitForKey")

MissionScript_TerminateMission (0x459bb0)
  -> depends on: DAT_00588338 (incremented counter, not otherwise characterized)
  <- depended on by: mission-scripting command dispatch table (entry associated with
                 name "TerminateMission", exact table-slot alignment uncertain)

MissionScript_EndMissionDeathSequence (0x459bd0)
  -> depends on: FUN_0045d460 -> depends on: DAT_00537418, DAT_00537575 (reset to 0),
                 FUN_0045d480 (label/state-jump primitive, not decompiled)
  <- depended on by: mission-scripting command dispatch table (entry association
                 uncertain -- behaviorally the best fit for "drop to death sequence")
```

## TurretSetTarget investigation (2026-09-08, twenty-seventh session)

```
MissionScript_SetAnyTriggerState (0x45d3a0)
  -> depends on: FUN_00453200 (resolves implicit target entity),
                 DAT_005267c0 (per-entity trigger array, stride 8, inner records stride 0x30),
                 FUN_0045b2d0 (applies the resolved trigger-state change, not decompiled)
  <- depended on by: mission-scripting command table ("SetAnyTriggerState" slot, confirmed)

MissionScript_0x459bd0_ResetAndScan (0x459bd0)
  -> depends on: ResetTriggerGlobalsAndResolveTarget (0x45d460)
       -> depends on: DAT_00537418, DAT_00537575 (reset to 0),
                       ResolveObjectRangeAndInvokeCallback (0x45d480, called with callback=NULL)
            -> depends on: DAT_0052951c/DAT_00529504 (nav-graph node range),
                            DAT_005267cc/DAT_005267c8 (trigger-table range),
                            DAT_005294fc/DAT_005294f0/DAT_00529500/DAT_00529520/DAT_00538c90/DAT_005267c0
                              (navigation/waypoint graph, shared with ScanNavigationGraphTarget @ 0x401d80),
                            InvokeTargetMatchCallback (0x45d700) -> calls FUN_0045d720, then (*callback)()
  <- depended on by: mission-scripting command table (slot association UNRESOLVED --
                 table position implies "TurretSetTarget" but behavior does not match)
```

## Resource file / BigFile TOC loader (2026-09-08, twenty-eighth session)

```
OpenBigFile (0x4c7e20)
  -> depends on: FUN_004d02ef (fopen-style wrapper, "rb" mode),
                 ReadSwappedUint32 (0x4c7df0, magic+tocEntryCount+tocSizeBytes),
                 FUN_004d0c17 (rewind()-equivalent),
                 FUN_004cfeec (locking fread wrapper)
  <- depended on by: (caller not re-traced this session -- likely a startup
                 archive-mount routine alongside EnsureCorrectCDMounted)

HOG_BigRead / HOG_bigread (0x4c7f60)
  -> depends on: FindBigFileTocEntry (0x4c8370),
                 DecompressBigFileEntry (0x4c8480) [compressed path],
                 HOG_file_read (0x4c5be0) [TOC-miss fallback],
                 ReportAssertionFailureEx, FUN_004c36d0 (sprintf-style formatter)
  <- depended on by: LoadNamedResource (0x4c5bd0, trivial passthrough)
                 <- LoadResourceFileBuffer (0x45a300)

FindBigFileTocEntry (0x4c8370)
  -> depends on: FUN_004dae20 (_stricmp-style case-insensitive compare),
                 ReadSwappedUint32 (offset/size fields),
                 FUN_004d0407 (fseek wrapper, seeks archive FILE* to resolved offset)
  <- depended on by: HOG_BigRead, HOG_bigsize (0x4c81f0)

DecompressBigFileEntry (0x4c8480)
  -> depends on: ReadSwappedUint32 (2-byte marker peek via FUN_004cfeec, not itself),
                 SR_MEM_allocate, FUN_004cc350 (actual decompressor, NOT decompiled),
                 SR_MEM_free
  <- depended on by: HOG_BigRead (compressed-entry path)

LoadResourceFileBuffer (0x45a300)
  -> depends on: FileExistsOnDisk (0x4ad6e0) [mod/dev override check],
                 ReadLooseResourceFile (0x45a3e0) [loose-file path, calls HandleFatalMissionError on flagged failure],
                 LoadNamedResource -> HOG_BigRead [archive path]
  <- depended on by: (mission/resource loading callers, not re-traced this session)

HOG_file_read (0x4c5be0)
  -> depends on: HOG_file_size (0x4c5b90), SR_MEM_allocate_named,
                 FUN_004d02ef (fopen), FUN_004cfeec (fread), FUN_004d013c (fclose),
                 ReportAssertionFailureEx
  <- depended on by: HOG_BigRead (TOC-miss fallback)
```

## BigFile decompressor identified as RefPack; .ut suffix explained (2026-09-08, twenty-ninth session)

```
DecompressBigFileEntry (0x4c8480)
  -> depends on: DecompressRefPackBlock (0x4cc350, was FUN_004cc350) -- EA RefPack/QFS LZ77 decoder,
                 identified via control-byte structural match, triggered by the 0x10FB magic

HOG_BigRead (0x4c7f60)
  -> depends on: (unchanged from Pass 28) -- extension-stripping rule now understood as reconciling
                 a hardcoded ".ut" suffix used by many callers (e.g. RunMissionBriefingScreen's
                 "ms_speech\enrbr_tag%02d.ut") against bare-basename BigFile TOC entries

SR_CCB_load (0x4cb9d0, was FUN_004cb9d0)
  -> depends on: HOG_BigRead, LoadNamedResource, SR_MEM_allocate, FUN_004cb540 (scalar field reader,
                 not decompiled), FUN_004d0333 (free)
  <- depended on by: (not traced this session -- found only as a HOG_BigRead caller)
```

## The .ccb loader: a master-palette resource format (2026-09-08, thirtieth session)

```
SR_CCB_load (0x4cb9d0)
  -> depends on: HOG_BigRead (0x4c7f60), FUN_004cb540 (native-endian cursor read),
                 SR_MEM_allocate (5 allocations: struct, blockA, blockB, scalarC, payload),
                 FUN_004d0333 (free), SR_MEM_free
  <- depended on by: InitializeGraphicsDevice (was FUN_004acbe0, graphics-device init --
                 stores result at rendererState+0x1606), InitializeLoadoutScreen (was
                 FUN_00441aa0, asset-preload sequence -- stores result in DAT_005246d0).
                 CORRECTED in Pass 61: +0x1602 (read by the RGB-to-native-pixel-format
                 packing loop, "Block A") is NOT this function's result -- it's populated
                 by a separate SR_TGA_allocate_palette() call in the same branch (see
                 below). The .ccb file's own real content (Block A/B as originally
                 described) is unconfirmed; only the RGB-palette attribution was wrong.
                 Pass 53's per-screen-not-per-image finding is unaffected: it's still true
                 that InitializeLoadoutScreen restores the pre-screen +0x1602 pointer
                 before returning, and Palette scope = per-screen, not per-image.
```

## The REAL master-palette source: standard 8-bit color-mapped .tga files, not .ccb (2026-09-09, Pass 61)

```
SR_TGA_allocate_palette (0x4cacb0, was FUN_004cacb0) / SR_TGA_get_palette (0x4ca9b0, was
  FUN_004ca9b0) -- self-named via their own ReportAssertionFailureEx strings
  -> loads a named .tga file whole (SR_FileAlloc), asserts bpp==8, reads its STANDARD
     256-entry embedded BGR color map (TGA spec: imageType 1 or 9, colorMapType != 0,
     color map starts at offset 18+idLength) into a 768-byte RGB buffer
  <- depended on by:
       InitializeGraphicsDevice: SR_TGA_allocate_palette("softpal.tga"/"palette.tga") ->
         rendererState+0x1602 (the REAL master RGB palette, read by the packing loop
         previously mis-attributed to SR_CCB_load's result -- see correction above),
         in the SAME if/else branch as the SR_CCB_load("softpal.ccb"/"palette.ccb") call
       InitializeLoadoutScreen: SR_TGA_allocate_palette("palette3.tga") alongside
         SR_CCB_load("palette3.ccb")
       a large HUD-init function (source-tagged hud.cpp): SR_TGA_allocate_palette
         ("oldpalette.tga") for a HUD-local gradient-icon palette copy

Resolves 2 of Pass 53's 3 unexplained "extracted" palette dumps:
  extracted/PALETTE_N  <- palette.tga's color map (byte-exact match, confirmed)
  out_softpal/SOFTPAL_N <- softpal.tga's color map (byte-exact match, confirmed)
  out_palettes/POWER_N  <- still unresolved; not any color-mapped .tga in RESOURCE/
    (powerball.TGA, the name's obvious candidate, is 24bpp truecolor -- no color map)
```

## Palette-to-image mapping: there mostly isn't one (2026-09-09, Pass 53)

```
Palette assignment granularity in this engine: per render-context (screen), not per image.
  -> confirmed: 8583/8583 shapes across all 337 .spr files in gamedata/ have paletteOffset=0
                (the per-shape PaletteOverrideRecord mechanism, Pass 39/41, is unused in
                the shipped game)
  -> confirmed: LoadSquadronRoster (0x4a44d0) -- the generic .sro/.SHP structured-text
                object parser (renamed from its .sro-only usage; also loads all 438 .SHP
                ship/turret/pod models in InitializeLoadoutScreen as "roster of one") --
                contains no CCB/RGB/palette code anywhere
  -> gamedata/'s extracted/out_palettes/out_softpal dumps (2771 numbered entries each,
     third-party tool output, not this project's) do not correspond to any per-image
     mechanism found in Lancer.exe; index>0 in each mostly degrades to flat-gray noise
     runs, consistent with a heuristic byte-scanner rather than a principled extractor
```

## Mission trigger-type catalog discovered (2026-09-08, thirty-first session)

```
DumpMissionTriggerListOverflow (0x45b330)
  -> depends on: DAT_005373e4 (Mission_TriggerCount, confirmed real name),
                 DAT_0052abe0 (trigger record array, stride 0x30, byte 0 = type code),
                 GetObjectIndexFromPointer, FUN_004024e0 (object display name, not decompiled),
                 DebugLog_Stub, ReportAssertionFailureEx
  <- depended on by: (not traced -- likely called from the per-tick trigger-add path)

FUN_004843a4 (HUD per-frame render, NOT the script interpreter -- ruled out this session)
  -> depends on: DAT_005799bc (WaitForKey's key-wait index; also drives the on-screen
                 "press key to continue" prompt rendered here), DAT_004e2380 (per-key
                 condition/display table, shared with MissionScript_WaitForKey)
  <- depended on by: (not traced)
```

## THE MISSION SCRIPT INTERPRETER FOUND: a stack-based bytecode VM (2026-09-08, thirty-second session)

```
UpdateMissionFrame (0x4924b0)
  -> ProcessMissionTriggerQueue (0x45b840)
       -> depends on: DAT_005373e4 (Mission_TriggerCount), DAT_0052abe0 (trigger array, stride 0x30),
                       GetObjectIndexFromPointer, DAT_00529504 (nav-graph node count, validity check)
       -> DispatchMissionTriggerMatch (0x45ce70)
            -> MatchTriggerAgainstWaitingScripts (0x45cea0)
                 -> depends on: DAT_005294e0+idx*0x30 (== MissionScript_SetAnyTriggerState's array,
                                confirmed same array this session), DAT_005267c0 (trigger-type lookup,
                                shared with ResolveObjectRangeAndInvokeCallback / SetAnyTriggerState),
                                FindMissionScriptThreadSlot (0x45b960)
                                  -> walks linked list rooted at PTR_DAT_004f6348 (node stride 0xB8/0x2e dwords)
                                FUN_0045d810, FUN_0045d0d0, FUN_0045b8d0 (not decompiled)

ResumeMissionScriptThread (0x45ba30)
  -> depends on: DAT_00537570 (VM eval stack ptr), DAT_005373f0 (VM instruction cursor),
                 DAT_00537578 (current-thread global), DAT_00537415 (active-thread count),
                 RunMissionScriptVM (0x45c980)
  <- depended on by: (per-tick script scheduler driver, not traced this session)

RunMissionScriptVM (0x45c980)
  -> depends on: DAT_004f6350 (opcode jump table, ~84 entries), per-thread instruction cursor at
                 threadStruct+0x10
  -> dispatches to (confirmed 3 of ~84 opcodes):
       MissionVM_OpEquals (0x45bad0, opcode 2) -> DAT_00537570 (eval stack)
       MissionVM_OpNotEquals (0x45bb00, opcode 3) -> DAT_00537570
       opcode 20 (0x45bbf0) -> FUN_0045cb20 (push game-state value, not decompiled) -> DAT_00537570
  <- depended on by: ResumeMissionScriptThread

Relationship to the Pass 25-27 named-command metadata table (adjacent in memory, immediately
after DAT_004f6350's jump table ends): UNRESOLVED -- flagged as open, not assumed either way.
```

## VR ship-interior system: closing open questions (2026-09-08, thirty-third session)

```
WinMain
  -> RunShipInteriorVRLoop (0x439fb0)
       -> depends on: VRRoomNode graph (145 nodes, complete), HOG_BigRead,
                       DAT_0051d478 (current room), DAT_0051db34/DAT_0051dacc (mouse x/y),
                       roomType 3/4 hover-prop path -> "move_a.bik" (literal) / LoadNamedResource
                       -> DAT_0051d9cc (shared overlay-content slot)
       -> RunMenuScreenLoop (0x4289d0)   [roomType==1 exit transition, direct call]
       -> RunMissionSelectMapScreen (0x44f3d0)   [roomType==5 hub, already documented]
  -> RunMenuScreenLoop (0x4289d0)   [also called directly by WinMain's own state machine]
```

## `CheckKeyEdgeState` decoded; the "CTRL+POTATO" cheat code confirmed (2026-09-08, thirty-fourth session)

```
CheckKeyEdgeState (0x4bd570)
  -> depends on: DAT_00595c68 (raw per-key down-state array, shared with MissionScript_WaitForKey),
                 DAT_005d54ec (per-key edge-latch array),
                 DAT_00595c92/DAT_00595c9e (Shift L/R), DAT_00595c85/DAT_00595d05 (Ctrl L/R),
                 DAT_00595ca0/DAT_00595d20 (Alt L/R),
                 DAT_005d5744/DAT_005d5634/DAT_00595d80 (per-modifier combo-latch flags)
  <- depended on by: RunMainMenuScreen (0x428b60, Ctrl+Potato cheat + post-cheat debug/mission-select
                 input), RunShipInteriorVRLoop, MissionScript_WaitForKey (via DAT_00595c68 only,
                 not this function directly), and other menu screens (not re-audited this session)

RunMainMenuScreen (0x428b60)
  -> depends on: CheckKeyEdgeState (cheat sequence + post-cheat input),
                 DAT_005d5641 (cheat-armed flag), DAT_00562dc8 (mission index, set by digit entry),
                 _DAT_00588400 (debug destination code, consumer not traced)

## `_DAT_00588400`'s consumer traced: 12 debug codes = 12 real squadron-roster files (2026-09-08, thirty-fifth session)

```
RunMainMenuScreen (Ctrl+Potato + F1-F12/Enter combos)
  -> writes: _DAT_00588400 (unindexed = slot 0)
       -> read by: InitializeMissionGameplay
            iVar6 = DAT_0050c2e8; if (DAT_00582e8c==0) iVar6 = DAT_00588400[slot*0x54];
            -> outcome-code switch (0-0xb aliases 0xf4-0xff, Pass 25) -> DAT_005883c0 (id) +
               a literal roster filename (e.g. "wolv_frm_shp")
            -> LoadSquadronRoster (0x4a44d0, was FUN_004a44d0)
                 -> depends on: srofiles.cpp-tagged parser, DAT_0057e048 (loaded roster handle,
                                consumed later in the same function for ship/wing setup)

## More hidden key bindings revealed via CheckKeyEdgeState's prototype (2026-09-08, thirty-sixth session)

```
RunShipInteriorVRLoop
  -> CheckKeyEdgeState(1,0,1)   [Esc, exit VR loop]
  -> CheckKeyEdgeState(0x39,0,1) [Space, activate hovered hotspot]

UpdateMissionFrame
  -> CheckKeyEdgeState(1,0,1)   [Esc, exit mission]
  -> CheckKeyEdgeState(0xb,0,1) [0 key] -> SaveScreenshotTga (0x4adc20)

RunControlsOptionsScreen (0x42b690)
  -> depends on: DAT_004e5cd0 (control-descriptor table, stride 0x24, ~51 entries),
                 DAT_004e2380 (live runtime key-binding table, shared with MissionScript_WaitForKey),
                 DAT_004e23cc, DAT_004e23ae (per-control mode/device-name fields),
                 CheckKeyEdgeState (used to detect "which key did the user just press to rebind")

## .bik loading/playback pipeline decoded; DAT_004e5cd0 corrected (2026-09-08, thirty-seventh session)

```
RunShipInteriorVRLoop / RunMissionBriefingScreen / etc.
  -> FindBinkMovieInArchive (0x4c83f0)
       -> depends on: DAT_005202d4 (current BigFile* archive, same struct as OpenBigFile's return,
                       shared between resource loads and movie streaming),
                       FUN_004dae20 (case-insensitive compare), ReadSwappedUint32,
                       SetFilePointer (raw Win32 HANDLE seek, +4 field of the BigFile struct)
  -> _BinkOpen_8 / _BinkSetFrameRate_8 / _BinkSetSoundSystem_8 / _BinkDoFrame_4 /
     _BinkCopyToBuffer_28 / _BinkWait_4 / _BinkGoto_12 / _BinkClose_4  (public Bink 1.x SDK)

RunControlsOptionsScreen (0x42b690)
  -> depends on: DAT_004e5cd0 (KeyScanCandidate table, 89 entries, stride 0x24 --
                 CORRECTED from Pass 36: candidate scancodes, not control names),
                 CheckKeyEdgeState (scanned across scancode x 3 modifier modes),
                 DAT_004e2380 (runtime binding table, stride 0x4e) with sub-fields
                 DAT_004e23ac (control name -> GetLanguageString index),
                 DAT_004e23ae (bound device/joystick name string),
                 DAT_004e23cc (mode/type field),
                 GetLanguageString (0x491030, was FUN_00491030)

## THE COMPLETE DEFAULT FLIGHT CONTROL SCHEME (2026-09-09, thirty-eighth session)

```
DAT_004e2380 (now typed ControlBinding[74], 78-byte stride)
  -> read by: CheckKeyEdgeState-driven flight/gameplay input code (UpdateMissionFrame and others,
              not individually cross-referenced this session -- table content itself was read
              directly rather than traced from a consumer),
              MissionScript_WaitForKey (Pass 26, shares this table for scripted key-wait conditions),
              RunControlsOptionsScreen (Pass 36/37, rebind UI reads/writes this table directly)
  -> depends on (per-entry): GetLanguageString(langStringIndex) for the real localized display name
  <- documents: the complete 74-binding default keyboard control scheme (cameras, targeting,
              flight, weapons, ship-system windows, Spectral Shields, wingman commands, menu)

## .fnt/.spr assets identified as WinVFX resource formats (2026-09-09, thirty-ninth session)

```
InitializeWinVfxLibrary (0x4a26d0)
  -> depends on: LoadLibraryA("winvfx8.dll" or "winvfx16.dll", by color depth),
                 GetProcAddress x ~27 (VFX_shape_draw, VFX_shape_translate_draw, VFX_shape_transform,
                   VFX_buffer_transform, VFX_window_construct, VFX_pane_construct, VFX_pane_wipe,
                   VFX_shape_lookaside, VFX_shape_multilookaside, VFX_shape_draw_filtered,
                   VFX_shape_draw_tinted, VFX_return_global_palette, VFX_shape_draw_mirrored,
                   VFX_string_draw, VFX_character_width, VFX_pane_copy, VFX_pixel_write,
                   VFX_window_destroy, VFX_pane_destroy, VFX_shape_bounds, VFX_assign_window_buffer,
                   VFX_shape_scan, VFX_init_global_palette, VFX_line_draw, VFX_triplet_value,
                   VFX_shape_origin, VFX_shape_resolution),
                 DAT_00588730+0x1602 (RGB palette source, shared with SurrenderLib's palette init, Pass 25/30)
  <- depended on by: WinMain (bootstrap, not re-traced this session)

BuildFontWidthCache (0x480d70, was FUN_00480d70)
  -> depends on: LoadNamedResource (.fnt resource handle), VFX_character_width (via DAT_005959e0)
  <- depended on by: FUN_004288e0 and other .fnt-loading call sites

DrawShapeJittered (0x48c6e0, was FUN_0048c6e0)
  -> depends on: VFX_shape_bounds, VFX_shape_draw / VFX_shape_draw_mirrored (via DAT_005959e4/DAT_005957a8),
                 DAT_00588700 / DAT_00588724 (jitter intensity, not independently confirmed)

.fnt / .spr resources
  -> loaded via: LoadNamedResource (Pass 28's generic resource path)
  -> consumed via: winvfx8.dll / winvfx16.dll's VFX_* API (opaque -- binary layout not in Lancer.exe)

## WINVFX8.DLL present in gamedata: the real .spr/.fnt formats decoded (2026-09-09, fortieth session)

```
WINVFX8.DLL (gamedata/StarLancer/WINVFX8.DLL, loaded as a second Ghidra program this session)
  VFX_shape_draw (0x100031d9)
    -> depends on: ShapeSet/ShapeRecord layout, VFX_shape_blit_unclipped (0x100035fc, renamed)
  VFX_shape_bounds (0x1000925d) / VFX_shape_count (0x100093f7) / VFX_shape_list (0x1000940c)
    -> depend on: same ShapeSet layout (shapeCount @+4, 8-byte {recordOffset,paletteOffset} pairs @+8)
  VFX_shape_palette (0x10009308) / VFX_shape_colors (0x10009361)
    -> depend on: paletteOffset sub-records (structured RGB entries vs. flat int list, respectively)
  VFX_font_height (0x10008798) / VFX_character_width (0x100087ad) / VFX_character_draw (0x100087cf)
    -> depend on: FontResource layout (lineHeight @+8, glyphOffset[256] @+0x10, raw glyph bitmaps)

Lancer.exe's InitializeWinVfxLibrary (Pass 39) -> loads this exact DLL and resolves these exact exports

## ShapeRecord.headerField1 resolved as origin point (2026-09-09, forty-first session)

```
VFX_shape_origin (0x10009281, WINVFX8.DLL)
  -> depends on: ShapeSet.shapes[idx].recordOffset, ShapeRecord+0x04 (origin/hotspot point)
VFX_shape_minxy (0x100092dc) / VFX_shape_resolution (0x100092a6)
  -> depend on: ShapeRecord+0x08/+0x0C/+0x10/+0x14 (bbox X1/Y1/X2/Y2, confirms Pass 40 layout)

gamedata/StarLancer/RESOURCE/FONT.FNT, gamedata/StarLancer/cd1/*.SPR
  -> RefPack-compressed on disk (Pass 29 magic 10 FB), even as loose files --
     must decompress before FontResource/ShapeSet structs (Pass 40) apply

## RefPack decoder built and verified byte-exact against real assets (2026-09-09, forty-second session)

```
reversing/tools/refpack_decompress.py (new project tool)
  -> ports: DecompressRefPackBlock (Lancer.exe, 0x4cc350, Pass 29)
  -> verified against: gamedata/StarLancer/RESOURCE/FONT.FNT (-> FontResource, Pass 40)
                        gamedata/StarLancer/cd1/YOVB.SPR (-> ShapeSet/ShapeRecord, Pass 40)
  -> confirms: 5-byte RefPack header (2 magic + 3-byte BE size), full 4-form opcode algorithm

## Mission briefing / weapons loadout / debriefing: the full flow (2026-09-09, forty-third session)

```
RunMissionBriefingScreen (0x437010)
  -> InitializeLoadoutScreen (0x441aa0)     [stage 1: setup, skipped for mission 0x1d]
       -> depends on: DAT_00523e84/e74/aa4 (fighter/missile/gunship counts),
                       .ccb master palette (Pass 30), loadout lighting rig
  -> FindBinkMovieInArchive + _BinkOpen_8   [stage 2a: normal mission briefing video]
     OR HOG_BigRead("enddebriefing.ut")     [stage 2b: mission 0x1d = campaign epilogue]
  -> per-frame loop -> UpdateLoadoutSelection (0x443760)   [stage 3: interactive loadout]
       -> depends on: FUN_004394d0 (confirm/cancel dialog), FUN_00446180 (tooltip builder,
                       not decompiled), mission-0x17-specific hidden-object rule
  -> HOG_BigRead("ms_speech_enrbr_tag_%02d.ut") + FUN_00461d80  [stage 4: closing narration]
  -> DAT_0051d478 = campaign-stage-appropriate VRRoomNode hub   [stage 5: hand-off to RunShipInteriorVRLoop]

## VR ship interior: what happens when a .bik clip finishes (2026-09-09, forty-fourth session)

```
FUN_0043c1c0 (per-frame VR-loop callback, installed at DAT_00588730+0x88)
  -> depends on: _BinkWait_4/_BinkDoFrame_4/_BinkCopyToBuffer_28/_BinkNextFrame_4/_BinkGoto_12,
                 DAT_0051d9e4 (1=just-transitioned, 2=steady-state),
                 DAT_00520298 (completion flag, read by RunShipInteriorVRLoop's outer dispatch, Pass 33)
  -> roomType==3 completion path: FindBinkMovieInArchive + _BinkOpen_8 on a NEW clip from
       PTR_s_move_a__004e8138 (14-entry table -> move_a_/move_b_/move_c_/move_d_.bik),
       DAT_0051dac0 (cycling index), DAT_0051d9d8 (shared hover-prop overlay buffer, Pass 33)
  -> other-room arrival-clip completion path: _BinkGoto_12(bink, 2, 1) -- loops near-start,
       no new file opened

## The briefing-hub "news report" TV, and tracing the path to mission briefing (2026-09-09, forty-fifth session)

```
RunShipInteriorVRLoop, roomType==7 transition
  -> RunBriefingHubNewsReport (0x43ba40)
       -> depends on: DAT_00562dc8 (mission index, selects news clip from ~27-28-entry table @0x4e90d0-0x4e91a8),
                       FindBinkMovieInArchive, _BinkOpen_8 (rel_tv_in_loop.bik / b_tv_news_.bik / tv_cald_.bik)
  -> (after RunBriefingHubNewsReport returns) settles into briefing-hub room (tv2brd.bik, Pass 5)

RunMissionBriefingScreen callers: RunMenuScreenLoop (screen ID 7) AND WinMain directly (0x4aa027, 0x4aa6f2)
  -> WinMain-level triggering condition: under investigation (forked)

## THE MISSING LINK FOUND: roomType 1 leads to mission briefing, not the main menu (2026-09-09, forty-sixth session)

```
RunShipInteriorVRLoop, roomType==1 door
  -> RunMenuScreenLoop(7)   [literal argument -- corrects Pass 4/5's "exit to menu" mislabel]
       -> RunMissionBriefingScreen (Pass 43's full 5-stage sequence)
            -> DAT_0051d4b4==1 (confirmed) -> VR loop reopens fresh at bunkroom entry hub
            -> DAT_0051d4b4==0 or 2 (declined/cancelled) -> unwinds toward main menu

WinMain (0x4aa027, 0x4aa6f2)
  -> RunMissionBriefingScreen()   [only when DAT_00562dc8==0x1d, mission-29 epilogue]
       -> FUN_004ac620 (ending cutscene/credits, not decompiled) -> DAT_00562dc8 reset to 1

RunMissionSelectMapScreen (roomType==5 hub)
  -> InitializeMissionGameplay -> RunMissionGameplay -> UnloadMission   [direct, no briefing hop]

## Menu asset position data decoded: the mission-select star map's hotspot table (2026-09-09, forty-seventh session)

```
RunMissionSelectMapScreen (0x44f3d0)
  -> depends on: DAT_004ebb38 / PTR_DAT_004ebb3c (MapScreenState[] table, stride 0x58,
                 {hotspotCount, MenuHotspotRect* rects, ...} per state -- states 0 (3 rects,
                 0x4ebaf8) and 1 (5 rects, 0x4ebb10) read directly),
                 DAT_004ebb60 (state-transition table, [state][hotspotIndex] -> nextState, stride 0x16 dwords)

## Hotspot layouts documented for all 12 menu screens (2026-09-09, forty-eighth session)

```
HitTestRectArray (0x43eb30, was FUN_0043eb30) -- shared hotspot hit-test utility
  -> depends on: caller-supplied {rectArray ptr, count, mouseX, mouseY}
  <- depended on by (hidden-arg technique exposed all at once via set_function_prototype):
       RunOptionsMenuScreen (6-entry stack table)
       RunSoundOptionsScreen (DAT_004e76a0[6] buttons + DAT_004e76d0[4] sliders, contiguous)
       RunNewGameSetupScreen (8-entry main row @stack[unresolved, see Pass 50 -- decompiler's
         PTRSUB(ESP,-0xa4) offset has no confirmed backing writes] + 10-entry name-picker @local_64[confirmed])
       RunVideoOptionsScreen (DAT_004e76f0[17] + DAT_004e7778[1] gamma handle)
       RunMultiplayerSetupScreen (38-record contiguous table[confirmed Pass 52], 5 windows:
         main row+sessions[16], connecting panel[4], host-setup[4], difficulty row[8], join[6])
       RunMultiplayerLobbyScreen (3-entry exit cluster + 40-entry(0x28) main table[confirmed
         Pass 52]; one 3-entry host-mode checkbox row still unresolved, same class as Pass 50)
       RunSaveLoadScreen (19-record contiguous table[confirmed Pass 51]: load=slice[1:6],
         save=slice[6:19] -- adjacency directly confirmed via base-pointer arithmetic)
       RunSaveGameBrowserScreen (17-record table[confirmed Pass 51]: 10 slots + 4 actions in one
         window, 2 scroll arrows + 1 confirm-dialog rect in two more)
       RunControlsOptionsScreen (local tables)

RunMainMenuScreen -- uses its OWN inline hit-test (not HitTestRectArray), DAT_004e5b90[5],
  stride 12 bytes {x,y,w,h,target,extra}. target field is a loop-continue gate, not a
  destination ID (Pass 51) -- index 0/1/2 -> New Game/Multiplayer/Options, index 4 -> hidden
  "watch ending" mission-0x1d trigger, index 3 -> inert (never reaches the action switch).

RunNetworkDisconnectScreen (0x43ca30, screen 8) -- confirmed zero hotspots, non-interactive

## Which palette is used for the menus (2026-09-09, Pass 54)

```
SR_CCB_load (0x4cb9d0) -- exactly 2 call sites total, revealed via set_function_prototype:
  <- InitializeGraphicsDevice (0x4acbe0, was FUN_004acbe0, renamed this pass) --
       runs ONCE at startup (called 4x from FUN_004a8600's device try/fallback loop):
         rendererState+0x1ac == 0  -> SR_CCB_load("softpal.ccb")
         rendererState+0x1ac != 0  -> SR_CCB_load("palette.ccb")
       result stored persistently at rendererState+0x1606/+0x1602
       -> THIS is the palette every menu screen renders through -- no menu
          screen calls SR_CCB_load itself
  <- InitializeLoadoutScreen (0x441aa0) -- loads "palette3.ccb" separately into
       DAT_005246d0 for its own 3D ship-preview rendering, then restores the
       original rendererState+0x1602/+0x1606 before returning (Pass 53) --
       palette3.ccb never reaches the menu system
```

## The `.SHP`/`.sro` 3D object format: a generic tagged-chunk container (2026-09-09, Pass 55)

```
SR_FileAlloc (0x4cb420, was FUN_004cb420)
  -> depends on: FUN_004c8110 (resource cache lookup), GetBigFileEntrySize,
                 SR_MEM_allocate_named, LoadNamedResource
  -> loads a named resource WHOLE into memory, returns raw byte buffer

ReadTaggedChunk (0x4a2eb0, was FUN_004a2eb0) -- {tag:u16,stride:u16,count:u16}+payload
  scanner over SR_FileAlloc's buffer, forward-only cursor (DAT_005959f8)
  <- depended on by: LoadSquadronRoster (0x4a44d0) -- EVERY field read, tags 0,1,2,3,4,
       6,7,8,9,0xa,0xb,0xc,0xd,0xe,0xf,0x10 (see reverse_engineered_functions.md Pass 55
       for the full per-tag catalog). Shared by both .sro (squadron roster) and .SHP
       (438 ship/turret/pod model files) -- confirmed same loader, same chunk format.
  -> tag 1 = named parts array (part name = null-padded ASCII at record start,
       confirmed directly: "Gren frame", "arms")
  -> tag 0xf = the actual renderable polygon/face list (triangle/quad flag +
       live cross-product face-normal computation from referenced vertex data)
  -> tag 0xa = hardpoint/socket records (embedded "startup"/"deploy" keyword string)
  -> tag 0x10 = file-scope array read once after all parts. Pass 55 guessed
       "materials/textures table"; Pass 56 CORRECTS this after sampling 73 real files
       with populated tag-0x10 data -- it's a unit-normal + adjacency-bitmask record
       (collision/bounding-plane table, confidence 2), definitely NOT texture data
       (confidence 5 -- no strings, no small-index pattern anywhere sampled)
  -> texture/material assignment mechanism: UNRESOLVED, and now confidence-3 that it's
     external to .SHP entirely (every tag in the catalog checked, none carries a texture
     filename or index-into-materials pattern). Next lead: FUN_004a3040/FUN_004a3cb0
     (per-hardpoint post-processing in LoadSquadronRoster, not yet decompiled).
```

## `.SHP` tags decoded further: vertices, normals, hardpoint names/transforms (2026-09-09, Pass 56)

```
tag 4 (per tag-2 item) = per-vertex record: {position:float3, normal:float3(unit), 2xint32}
  -- confirmed: every sampled normal has magnitude 1.0, positions match real ship-scale coords

tag 6 (per tag-2 item) = named socket/hardpoint string label -- confirmed directly: "cpit0\0..."
  (a cockpit-socket name; resolves the stray "cpit0" fragment noted in Pass 55)

tag 3 (per tag-2 item) = per-triangle-fan record: 3 leading header int32s (constant across a
  fan run, e.g. {0,22,0}), then 3 sliding-window vertex-index int32s (a clean triangle-fan
  encoding: [2,3,20]->[3,20,19]->[20,19,8]->...), then 9 trailing floats (plausible per-vertex
  UV/shading, unconfirmed) -- likely the ACTUAL rendered mesh surface for most ships, since
  tag 0xf (Pass 55's confirmed face list) turns out to appear in only 2 chunks total across
  all 438 shipped .SHP files -- essentially unused despite having fully working consumer code
  (same class of surprise as Pass 53's unused per-shape palette overrides)

tag 9 (per-part) = plausible hardpoint attach transform: {count:int32, position:float3,
  2x orientation float3(unit), scalars incl. -400.0/1000.0} -- one real record decoded,
  not confirmed against a consumer

tag 0xa (per-part) numeric field = plausible range/distance value (16000 in samples checked)
```


## Spectral Shields enforcement: exhaustively searched, not found anywhere (2026-09-09, Pass 57)

```
object+0x670 / ship-flags bit 0x8000000 -- WRITTEN in exactly 2 places (both already
  known: SetSpectralShieldsActive's local computation, ProcessNetworkMessage's network
  write) and READ NOWHERE ELSE in the entire binary. Confirmed via:
    - full-binary search_byte_patterns for the 0x670 displacement encoding (2 hits total)
    - flag-constant 0x8000000 search restricted to the combat code range (2 hits, both
      inside the same 2 functions above)
    - direct inspection of ApplyShieldDamage / ApplyComponentDamage / ProcessProjectileImpact
      (none reference either the field or the flag)
  -> Confidence 5 negative finding: nothing in Lancer.exe reads this value/flag back to
     actually block, reduce, or redirect damage. Recommended next step per METHODOLOGY:
     live-debugging, not further static search.
```

## Combat-damage helper functions decoded (2026-09-09, Pass 57)

```
TrackFriendlyFireWarning (0x474c80, was FUN_00474c80) -- CORRECTS a prior "scoring/
  kill-credit" guess. Real behavior: accumulates damage dealt to a friendly target,
  escalates a 3-stage voice-warning ("ff_001/005/009.ut" -- "friendly fire") once a
  damage threshold + cooldown are met. Called from ApplyShieldDamage/ApplyComponentDamage
  when attacker==local player and target's team flag==0 (friendly).
  <- depended on by: ApplyShieldDamage, ApplyComponentDamage

SetComponentDestroyedNotification (0x474e00, was FUN_00474e00)
  -> sets local-player-ship+0x678 = 1 (or 2 + network broadcast via FUN_004bb920 when
     hosting) -- a "you lost a subsystem" notification flag; UI/HUD consumer not traced
  <- depended on by: ApplyComponentDamage

QueueCommChatterEvent (0x415270, was FUN_00415270)
  -> depends on: FUN_00402860 (event-slot allocator, not decompiled -- may or may not be
     the same queue as QueueAiEvent/0x402660), FUN_0048c580, FUN_004bb980 (network broadcast)
  <- depended on by: ApplyShieldDamage, ApplyComponentDamage (fired on friendly-fire and
     wingman-component-hit events)
```

## Do `.bik` files contain/set a palette? No (2026-09-09, Pass 58)

```
Lancer.exe's Bink imports (12 total, full import table checked): _BinkOpen@8,
  _BinkOpenMiles@4, _BinkClose@4, _BinkWait@4, _BinkDoFrame@4, _BinkNextFrame@4,
  _BinkCopyToBuffer@28, _BinkGoto@12, _BinkPause@8, _BinkSetFrameRate@8,
  _BinkSetSoundSystem@8, _BinkSetVolume@8 -- NO BinkGetPalette/BinkSetPalette import

DAT_0051dab4 (_BinkCopyToBuffer's flags arg, 4 write sites: FUN_00438d50,
  RunShipInteriorVRLoop x2, FUN_0043efc0) = (rendererState+0x162e != 0x03E0) ? 4 : 3
  -> 0x03E0 = RGB555 green-channel bitmask; +0x162e is among the already-documented
     pixel-format bit-shift constants (Pass 25/30) -- this is an RGB555-vs-RGB565
     output-format selector, NOT a palette mode. (0x80000000, the only other bit ever
     OR'd in, is a separate reverse-playback flag.)

Conclusion: Bink video is a completely separate RGB color pipeline from the game's
  .ccb-driven 8-bit master-palette system (Pass 30/54) used by .spr/.fnt/menus --
  the two never intersect.
```

## `.spr` RLE format decoded + medal sprites verified against a real screenshot (2026-09-09, Pass 59)

```
VFX_shape_blit_unclipped (WINVFX8.DLL, 0x100035fc)
  -> per-row RLE opcode format, fully decoded (see reverse_engineered_functions.md
     Pass 59): control byte CB, mode=CB&1, count=CB>>1
       CB==0x00        -> end of row
       mode==0,count>0 -> repeat-fill run (1 color byte + count)
       mode==1,count>0 -> literal run (count raw bytes)
       CB==0x01        -> skip run (1 distance byte, transparent)
  -> implemented in reversing/tools/decode_spr.py

MEDAL1-6.SPR (gamedata/StarLancer/cd1/) -- the 6 medal-case UI images
  -> each: ShapeSet with a fake "shape 0" = 768-byte embedded {R,G,B} palette
     (6-bit VGA precision), NOT a real ShapeRecord -- distinct from the
     confirmed-unused per-shape PaletteOverrideRecord mechanism (Pass 53)
  -> real shapes (1..N) = 7-9 animation frames per medal, building up a
     white/red hover-select border in the last couple of frames
  -> VERIFIED: decode_spr.py's output for all 6 files, arranged in a 2x3 grid,
     exactly matches a real user-supplied screenshot of the medal case
```

## `INTERFACE\*.bik` menu-transition videos: full call map (2026-09-09, Pass 60)

```
RunInGameOptionsScreen (0x4394d0, was FUN_004394d0) -- mid-mission pause menu
  <- called from: RunMissionBriefingScreen, RunShipInteriorVRLoop
  -> calls: RunSaveGameBrowserScreen, RunSoundOptionsScreen, RunControlsOptionsScreen,
     RunVideoOptionsScreen
  -> plays: igofade.bik (x5, <-> its own sub-screens), igo2mm.bik (-> Main Menu, quit mission)

RunMultiplayerDebriefScreen (0x4296a0, was FUN_004296a0) -- post-mission MP results screen
  <- called from: WinMain (3x)
  -> calls: RunSaveGameBrowserScreen
  -> loads: interface\mpdebr.spr, itacbig.fnt, itacsml.fnt

Shared options sub-screens get TWO parallel transition-clip sets depending on caller:
  RunControlsOptionsScreen / RunSoundOptionsScreen / RunVideoOptionsScreen:
    from RunOptionsMenuScreen (main menu path)  -> optfade2.bik / opfad2mm.bik
    from RunInGameOptionsScreen (in-game path)  -> igofade2.bik / igof2mm.bik
  RunSaveGameBrowserScreen:
    from RunNewGameSetupScreen (single-player path) -> sinfade2.bik / sifad2mm.bik
    from RunInGameOptionsScreen (in-game path)       -> igofade2.bik / igof2mm.bik

Other direct transitions:
  RunMainMenuScreen -> main2opt.bik / main2mul.bik / main2sin.bik
  RunOptionsMenuScreen -> opt2main.bik (exit), optfade.bik x3 (-> its sub-screens)
  RunNewGameSetupScreen -> sin2main.bik x2, sinfade.bik
  RunMultiplayerSetupScreen -> mul2main.bik x2, mulfade.bik x5
  RunSaveLoadScreen -> mulfade2.bik

NOT referenced anywhere in Lancer.exe (checked exhaustively): FADIGOPT.BIK, IGOPTFAD.BIK
  (only the .tga backdrop variant exists), MUL2OPT.BIK, MULFA2OPT.BIK, MULTI2MM.BIK,
  OLDOPFAD2MM.BIK, SIN2OPT.BIK, SINFA2OP.BIK -- unused/leftover assets
```

## Campaign pilot setup decoded; corrects a mislabel (2026-09-09, Pass 62)

```
RunNewGameSetupScreen (0x430490)
  case 0/1 -> g_wPilotGenderIsFemale / g_dwNewPilotGenderIsFemaleUI (was DAT_00562f16/
    DAT_0051da54) -- CORRECTED from Pass 46's "difficulty A/B": this is pilot gender
    (0=male picks "mp%s" format/assets, nonzero=female picks "fp%s", confirmed via
    FUN_004536d0 and FUN_00441100's pilot-record-screen setup)
  case 2 -> exit to RunSaveGameBrowserScreen (screen 0xd) -- Load Existing Pilot
  case 3 -> RunDifficultySelectDialog (was FUN_00430300) -> on confirm, LoadPlayerProfile
  case 4 -> exit to main menu
  case 5 -> "Reset" (mechanism only: re-arms cursor-blink flag)
  case 6 -> options dialog
  case 7 -> toggle recent-name list panel (DAT_005202b8, Pass 48)

RunDifficultySelectDialog (0x430300, was FUN_00430300) -- the REAL 3-tier difficulty picker
  -> g_wCampaignDifficulty (was DAT_00562f14), cycled 0(Easy)/1(Normal)/2(Hard)
  <- depended on by: ScaleDamageForDifficulty (reads g_wCampaignDifficulty directly)

LoadPlayerProfile (0x4751b0)
  -> depends on: FUN_004d02ef (fopen-style), FUN_004d0003 (fread/fwrite-style, 0xd0=208
     bytes), GetLanguageString (default pilot name, string 0xbf)
  -> tries to read "profile.bin" from the current (per-callsign) directory; on failure,
     zeroes/defaults the profile (mission index = 1, stats zeroed) and WRITES a fresh
     profile.bin -- this is the actual new-pilot-creation path, not a separate step
  <- depended on by: RunNewGameSetupScreen case 3 (after RunDifficultySelectDialog confirms)
```

## `profile.bin`'s field layout decoded and verified against a real save (2026-09-09, Pass 63)

```
PlayerProfile struct (208 bytes, base DAT_00562cf8) -- session-global mirror, written by
  AdvanceCampaignMissionAndSaveProfile (0x475a90, was FUN_00475a90), defaulted by
  LoadPlayerProfile (0x4751b0) when profile.bin doesn't exist yet:
    +0x00 currentMissionIndex        <- DAT_00562dc8
    +0x04 callsign[32]               <- DAT_00562dcc (variable-length copy, NOT null-padded --
                                          real sample file has a genuine uninitialized leftover
                                          byte right after a short name)
    +0x24 highestRankTierReached     <- DAT_00562dec (high-water mark into a 9-entry short
                                          threshold table, DAT_005009f4)
    +0x28 perMissionSpecialFlag      <- DAT_00562df0 (per-mission lookup, DAT_005009d7-indexed)
    +0x2c cumulativeScore            <- DAT_00562df4 (compared against DAT_005009f4's thresholds)
    +0x30 reserved1[6 dwords]        <- DAT_00562dfc (unidentified)
    +0x48 reserved2[6 dwords]        <- DAT_00562e14 (unidentified)
    +0x60 perMissionRankSnapshot[28] <- DAT_00562e2c (int16, 0xFFFF sentinel = unplayed)
    +0x98 perMissionScoreSnapshot[28]<- DAT_00562e64 (int16, 0 = untouched)

  <- verified against gamedata/StarLancer/profile.bin (real player save, callsign "DMJC"):
     currentMissionIndex=3, highestRankTierReached=0, cumulativeScore=30,
     perMissionRankSnapshot=[4,4,-1,...], perMissionScoreSnapshot=[0,9,21,0,...]

RefreshActiveCallsignFromProfile (0x475390, was FUN_00475390) -- re-reads profile.bin, copies
  ONLY the callsign field into the active-session DAT_00562dcc global; does not unpack any
  other PlayerProfile field into separate globals
```

## `profile.bin`'s remaining fields resolved (2026-09-09, Pass 64)

```
RenderBriefingHubFrame (0x436b20, was FUN_00436b20) -- briefing-hub room per-frame
  Bink-decode-and-render callback (sibling to FUN_0043c1c0)
  -> reads DAT_00562dfc/DAT_00562e14 (PlayerProfile's reserved1/reserved2 mirrors) as two
     parallel 6-entry boolean arrays -> gates which hub-room hotspots/props render+respond
     this frame; switches lookup-table sets on DAT_00562dc8 < 0x13 (early vs late campaign,
     matches the Pass ~33 "two parallel ship-layout graphs" finding)

BuildMissionDebriefText (0x424cf0, was FUN_00424cf0) -- post-mission debrief text builder
  -> reads DAT_0050099f / DAT_005009d7 / DAT_005009bb (indexed by the Pass-25 mission-
     outcome-branch value) as boolean gates for optional extra debrief paragraphs
  -> one gate additionally requires (&DAT_00562e2c)[missionIndex]==4, i.e.
     PlayerProfile.perMissionRankSnapshot==4 -- independent confirmation of Pass 63's
     "rank" interpretation for that field
  <- depended on by: FUN_00425240 (sibling, not separately decompiled this pass)
```

## CONFIRMED: mission-19 threshold = ANS Reliant -> ANS Yamato transfer (2026-09-10, Pass 65)

```
WinMain (~0x4a9fd5, ~0x4aa53f) -- cutscene/asset selection, both keyed on DAT_00562dc8 < 0x13:
  site 1: DAT_00562dc8 < 0x13 && DAT_0052a470 != 0 (default from LoadPlayerProfile)
            -> PlayMovie("new_reliant_transfer.bik")   -- the transfer story beat, shown once
          else -> PlayMovie("new_a_y_trans.bik")        -- generic filler (already seen / post-transfer)
  site 2: DAT_00562dc8 < 0x13 -> "new_rel_exec.bik" (Reliant variant)
          else                -> "new_y_exec.bik"       (Yamato variant)

-> CONFIRMS (user-supplied narrative context): mission index 19 is exactly where the
   player transfers from the ANS Reliant (destroyed) to the ANS Yamato for the rest of
   the campaign. This is the SAME threshold already found independently in:
     - RenderBriefingHubFrame (Pass 64): early/late hub-room hotspot table switch
     - the "two parallel ship-layout graphs" note (circa Pass 33)
   All three are now understood as the same underlying event, not three coincidental
   mission-19 checks.

Real asset confirmation: reliant.shp / yamato.shp (carrier 3D models), reliant_hang.shp
  (Reliant hangar), reliant_destback.shp / "Yamato DestBack.shp" (destruction backdrops
  for BOTH ships), "reliant_induction" (Reliant-specific onboarding sequence, role
  unconfirmed beyond its error string).
```

## The missing AI link found: UpdateShipAiTick + the real AI state stack (2026-09-10, Pass 66)

```
UpdateShipAiTick (0x40c5f0, was FUN_0040c5f0) -- per-object AI tick
  <- depended on by: ProcessMissionSimulationTick (confirmed call site), FUN_00457cd0,
     FUN_0040c8f0, FUN_00416450 (other callers, not individually traced)
  -> drains object+0xb90/+0xb8c (QueueAiEvent's perception queue, Pass 20), promoting an
     eligible event (expiry passed AND priority >= current top-of-stack state's priority,
     via PTR_DAT_004e06e0 catalog lookup) into the active AI-state record
  -> runs object+0x684's TOP-OF-STACK state catalog entry's slot-0 (OnEnter, once via the
     object+0x688 "fresh" flag) and slot-4 (OnUpdate, every tick) callbacks
  -> if the state catalog flags have bit 0x20 ("unconditional transition"): runs OnUpdate,
     FUN_0040ce70, then RECURSES into itself (immediate same-tick re-evaluation)

PushAiState (0x40cc10, was FUN_0040cc10) -- CORRECTS Pass 17's "AI command structure" model:
  object+0x684 (base ptr) / object+0x680 (depth) = a real 20-entry (0x208=520 byte, 26
    bytes/entry) PUSHDOWN STACK of AI states, not a single current-state slot
  -> depends on: TrySetAiState (priority gate), SR_MEM_allocate (lazy 520B stack +
     144B/0x90 scratch buffer @ object+0x68c, source-tagged aigeneric.cpp)
  -> move-to-front dedup: if the new state+params already exist deeper in the stack,
     removes that entry and re-pushes at top instead of duplicating
  -> on real push: shifts stack up, writes new top entry, zeroes 4 payload fields (the
     same fields UpdateShipAiTick fills FROM a queued event), sets object+0x688 "fresh"
     flag unless the state is an unconditional-transition type, zeroes the scratch buffer,
     tags with an incrementing generation ID (DAT_005185a8) when DAT_005185b1 is set
  <- depended on by: UpdateShipAiTick, SetShipDestroyedState (Pass 17)
  -> first gate: FUN_0040ca00 (semantics not confidently determined, confidence 1)
```

## 14 specific `.tga` images mapped to their call sites (2026-09-10, Pass 67)

```
LoadGenericSplashBackdrop (0x4ab3f0, was FUN_004ab3f0) -- loads splash.tga
  <- called by: ShowMissionLoadingScreen (0x4ad0a0, was FUN_004ad0a0)
       <- called by: WinMain (3x), RunMissionSelectMapScreen, RunMainMenuScreen

LoadStartupSplashBackdrop (0x4ab4b0, was FUN_004ab4b0) -- loads sl_splash.tga /
  sl_splash800.tga / sl_splash1024.tga via an unrecovered jump table
  <- called once, from InitializeGraphicsDevice (startup)

RunMainMenuScreen -> sl_splash2.tga (separate from the startup selection above)
RunNewGameSetupScreen -> sinfade.tga, main2sin.tga
RunOptionsMenuScreen -> main2opt.tga, optfade.tga (3 sites)
RunSaveLoadScreen (3 sites) + RunMultiplayerLobbyScreen (1 site) -> mulfade.tga
RunInGameOptionsScreen -> igofade.tga, ingameop.tga (5 sites), igoptfad.tga (4 sites)
RunMultiplayerDebriefScreen -> igoptfad.tga (shared with RunInGameOptionsScreen, Pass 60)

RunMissionBriefingScreen (0x437129) -- "briefdoor" texture, TWO variants selected by
  DAT_00562dc8 > 0x12 -- the same ANS Reliant/ANS Yamato mission-19 transfer threshold
  confirmed in Pass 65 (now a third independent site using it)
```

CORRECTION (user-supplied): each screen's .tga is its real persistent background (loaded
once at screen entry, before the per-frame render callback installs -- confirmed against
RunOptionsMenuScreen's real disassembly), not a poster-frame placeholder. The matching
.bik is the click-triggered transition animation the DEPARTING screen plays on its way to
that background -- which button triggers which video was already mapped per-screen in
Pass 60; this pass's .tga mapping is the destination-background half of the same
(video, destination) pair for each menu click.

## CONFIRMED: shipboard VR interfaces use the identical background system (2026-09-10, Pass 68)

```
SetActiveBackgroundImage (0x494b50, was FUN_00494b50) -- ONE shared function for every
  background swap in the game, menu AND shipboard alike
  -> no-ops if filename == DAT_00588744 (already active); else updates it and calls
     FUN_00494a70 (the real load/display routine, not decompiled)
  <- called by: every menu screen right before installing its per-frame callback
     (RunOptionsMenuScreen/main2opt.tga, Pass 67), AND by shipboard VR interior props:

RunCdPlayerPropScreen (0x437fc0, was FUN_00437fc0) -- the ship interior's jukebox/CD-player
  prop (loads cdplay.spr, play/pause/stop/skip/volume/repeat mini-UI)
  -> DAT_00562dc8 <= 0x12 -> SetActiveBackgroundImage("rel_bunk2cd.tga")   (ANS Reliant)
     DAT_00562dc8 >  0x12 -> SetActiveBackgroundImage("brd2cd.tga")        (ANS Yamato)
  -- 4th independent site using the exact Reliant/Yamato mission-19 threshold (Pass 64/65/67)
```

## `DisplayActiveBackgroundImage` decoded: the real TGA display pipeline (2026-09-10, Pass 69)

```
DisplayActiveBackgroundImage (0x494a70, was FUN_00494a70)
  -> if DAT_00588740 (callback ptr) set: call it directly, bypass everything below
  -> else if active filename set: SR_FileAlloc (load whole file) -> read width/height from
     the real TGA header (offsets 0xc/0xe) -> ComputePixelFormatFromMasks(ARGB8888 masks)
     -> allocate width*height*bpp buffer -> SR_TGA_rle_uncompress (decode) ->
     rendererState+0x50 (blit, not traced) -> free buffers
  -> else: rendererState+0x50 with no new image (redraw as-is)
  <- called by: SetActiveBackgroundImage, SetActiveBackgroundCallback (indirectly, via the
     callback it installs)

SR_TGA_rle_uncompress (0x4cad60, was FUN_004cad60) -- self-named via its own assertion
  strings. Complete real TGA RLE decoder: skips header+colormap correctly, handles both
  orientation flags (image descriptor bits 0x10/0x20), real RLE packet format (top bit =
  repeat vs raw run, low 7 bits = run length - 1)

SetActiveBackgroundCallback (0x494bb0, was FUN_00494bb0) -- sibling to
  SetActiveBackgroundImage: installs DAT_00588740 (dynamic/non-image background), clears
  the active filename. No caller located yet.
```

## The renderer +0x50/+0x40 blit-target write sites: searched exhaustively, not found (2026-09-10, Pass 70)

```
DAT_00588730+0x50 (DisplayActiveBackgroundImage's blit call) and +0x40 (called directly
  from InitializeGraphicsDevice) -- NO write site found anywhere in the program despite:
    - search_instructions checked every store to +0x50/+0x40 program-wide
    - every plausible graphics/device/backend init function checked individually:
      InitializeGraphicsDevice, SR_init (was FUN_004c3830), FUN_004c9a40, FUN_004ab290,
      FUN_004a8600, FUN_004ad2e0, FUN_004c22b0, FUN_004c3000, FUN_004cc5a0,
      InitializeWinVfxLibrary, WinMain (full)
    - InitializeWinVfxLibrary decoded in full: resolves ~28 VFX_* exports into SEPARATE
      named globals (DAT_005959e4 etc.), none into DAT_00588730 -- rules out a sequential
      WinVFX-export-table hypothesis
    - DAT_00588730 itself is assigned exactly once in the whole program (from SR_init's
      return value) -- no second "reconfigure" call site exists
  -> +0x50 confirmed heavily reused by UNRELATED structs elsewhere (a real DirectX COM
     vtable call in DetectDirectXVersion, gameplay object fields in FUN_00404040/
     FUN_00412390) -- not unique to the renderer state
  -> honest negative finding, consistent with the earlier Spectral Shields (+0x670) dead
     end (Pass 57): likely populated via a computed/loop offset or an unlocated bulk copy,
     not a literal per-field store. Live-debugging recommended as the next step.
```

## The ITAC interface (2026-09-10, Pass 71)

```
RunItacScreen (0x43efc0, was FUN_0043efc0)  [source: C:\lancer\game\itac.cpp]
  <- called by: WinMain, RunShipInteriorVRLoop
  -> setup: 5x SR_MEM_allocate (itac.cpp-tagged) incl. screen buffer DAT_00520314,
     LoadNamedResource(itacsnd.fat / itacbig.fnt / itacsml.fnt)
  -> eye-recognition gate (DAT_00523088 == 0):
       DAT_00562dc8 < 0x13 (Reliant, missions 1-18) -> chdir -> PlayBinkMovieFromArchiveByName -> chdir back
       else (Yamato, missions 19+)                  -> PlayBinkMovieFromHandle
     [5th confirmed Reliant/Yamato mission-19 threshold site, after RenderBriefingHubFrame,
      WinMain's cutscene selection, RunMissionBriefingScreen's briefdoor,
      RunCdPlayerPropScreen's room background]
  -> starting category: 1 (News Reports) if eye-recog gate played, else 0 (Debrief)
  -> main loop: on hover->active change, runs category-switch sequence (below);
     on category 8 (Exit) or DAT_00520840, tears down and returns
  -> room-transition-out (DAT_005251dc != 0, set elsewhere/not traced): hide background,
     EnsureCorrectCDMounted, chdir, strchr(+0x18,'\\') path trim, FUN_004abb80 (not
     decompiled) -> chdir back -> install DAT_00588730+0x88 callback -> FUN_0043eaf0

PlayBinkMovieFromArchiveByName / PlayBinkMovieFromHandle (0x4ab9d0 / 0x4ab6e0,
  was FUN_004ab9d0 / FUN_004ab6e0) -- GENERIC Bink player utilities, not ITAC-specific.
  Reused by ITAC's eye-recog gate and exit sequence with different args:
    ...ByName: FindBinkMovieInArchive(name) -> BinkOpen(archiveData, 0x800000)
    ...FromHandle: BinkOpen(param_1 directly, 0x1000)

9-category catalog (three parallel 9-entry tables, all read directly:
  0x4e9288 callback ptrs x5/cat, 0x4e9340 hotspot rects x4/cat, 0x4e9418 string ptrs x3/cat):

  0 Debrief       ItacEnterDebriefCategory      (0x4246c0)  BuildMissionDebriefText
  1 News Reports  ItacEnterNewsReportsCategory  (0x44dd90)  inter\itac\newsrep.spr
  2 Video Reports ItacEnterVideoReportsCategory (0x450540)  inter\itac\vidrep.spr
  3 Fighters      ItacEnterFightersCategory     (0x425910)  inter\itac\fighters.spr
  4 Capital Ships ItacEnterCapShipsCategory     (0x423870)  inter\itac\capships.spr
  5 Squadrons     ItacEnterSquadronsCategory    (0x44faa0)  inter\itac\squads.spr
  6 Personnel     ItacEnterPersonnelCategory    (0x44e4c0)  inter\itac\persons.spr
  7 Kills         ItacEnterKillsCategory        (0x441100)  inter\itac\kills.spr
  8 Exit ITAC     (none -- all-zero table row)

  CORRECTION: bik "f" suffix (e.g. itacdebf.bik vs itacdeb.bik) means EXIT-line, not
  gender -- first impression (by analogy with g_wPilotGenderIsFemale's mp/fp system,
  Pass 62) was wrong; disproved by reading the code before it was written down anywhere.
  Confirmed for all 9 categories via the 0x4e9418 string table.

Category-switch sequence (in RunItacScreen's main loop):
  play click sound -> [if old category active: format+pump exit-line bik -> call old
  category's table field 1 (exit callback)] -> set new active category -> [if new != Exit
  and has field 0: call ItacEnter*Category] -> format+pump new enter-line bik + trans-line
  token -> [new == Exit(8): special-cased, plays PlayBinkMovieFromHandle only if
  DAT_00562dc8 > 0x12, then straight to teardown] -> else: ItacShowCategoryTransitionAndEnter

ItacShowCategoryTransitionAndEnter (0x43fca0, was FUN_0043fca0)
  -> formats inter\itac\itactrans_NNNNN.tga from category's trans-line token
  -> SR_FileAlloc -> SR_TGA_rle_uncompress -> memcpy directly into *DAT_00520314
     [a DIFFERENT, working blit path -- bypasses the still-unresolved rendererState+0x50
      vtable call from Pass 70 entirely]
  -> calls category's table field 2 ("content setup") callback if non-null

Table field 2 callbacks:
  shared stub FUN_0044de90 (News/VideoReports/Fighters/CapShips) -> DAT_0052032c=1 +
    FUN_00440b10 (generic 4-entry list-selection reset, 0x520334..0x52036c)
  Debrief (0x4247a0) -> shared reset + FUN_00424be0 (BuildMissionDebriefText + text layout)
  Squadrons (0x44fb60) -> DAT_00523058=0 + shared reset
  Personnel (0x44e520) -> own hotspot/callback (FUN_0044ed00, not decompiled) + shared reset
  Kills (0x4411c0) -> renders live 3D scene via DAT_00588730+0x78/+0x7c (begin/end frame),
    memcpy's rendered frame into *DAT_00520314 same as ItacShowCategoryTransitionAndEnter
    [qualitatively different: rotating 3D display, not a flat list]

  <- open: table fields 3/4 (per-category, called from undecompiled FUN_004404a0)
  <- open: DAT_00523088's set-site
  <- open: ITAC's room-graph exits (rel_itac2X.bik/itac2X.bik clips) not mapped to hotspots
```

## Room-transition-out internals + remaining itac.cpp functions (2026-09-10, Pass 72)

```
RunItacScreen's room-transition-out (DAT_005251dc != 0), continued from Pass 71:
  ... chdir back -> DAT_00588730+0x88 = &ItacRoomTransitionFrameCallback -> ...
  -> SafeFormatString(trans-line token) -> PlayBinkMovieFromArchiveWithVolume
     (0x4abb80, was FUN_004abb80) -> ActivateItacTransitionBackground (0x43eaf0)
  -> DAT_005251dc = 0

PlayBinkMovieFromArchiveWithVolume (0x4abb80) -- a 3RD generic Bink-player variant,
  alongside PlayBinkMovieFromArchiveByName/PlayBinkMovieFromHandle (Pass 71). Same
  FindBinkMovieInArchive lookup + 0x800000-byte open as ...ByName, but adds
  _BinkSetVolume_8(handle, 0x8000) and checks DAT_00588730+0x1ac == 0|2 (render-mode)
  instead of +0x15f8. Confirmed generic via get_xrefs_to: 11x WinMain, x1
  AdvanceCampaignMissionAndSaveProfile, 4x other VR-room helpers (FUN_0048b6b0,
  FUN_004abd40 x2, FUN_004abde0, FUN_004ac620), + exactly 1x RunItacScreen.

ItacRoomTransitionFrameCallback (0x4403f0, was FUN_004403f0/LAB_004403f0)
  -> chains DAT_00588730+0x80 if set -> *DAT_00594544 = time/frame counter
  -> FUN_0043fe90(DAT_0052082c) [fade amount] -> if !DAT_0052308c (not waiting) and
     DAT_00522f54: FUN_0043fe00 -> draw mouse cursor via (*DAT_005959e4)(cursor sprite,
     DAT_0051db34, DAT_0051dacc)  [same hover-position globals as the hotspot hit-test]

ActivateItacTransitionBackground (0x43eaf0, was FUN_0043eaf0)
  -> SafeFormatString("%s.tga", param) -> renderer +0x78 (begin frame) ->
     SetActiveBackgroundImage
  [final step of room-transition-out: swaps in the destination room's background]

DynamicList_GetByIndex (0x4406a0, was FUN_004406a0) -- generic singly-linked-list
  node walker, self-named via its own "DynamicList::GetByIndex" assertion string.
  <- called by (get_xrefs_to): every ITAC record-browser category's list helpers:
       Kills:        FUN_00441320, FUN_00441540
       Capital Ships: FUN_00423cb0, FUN_00424130
       Fighters:     FUN_00425b70, FUN_00426030
       Personnel:    FUN_0044e0a0, FUN_0044ea50, FUN_0044ed00
       Squadrons:    FUN_0044fde0, FUN_00450180, FUN_004508d0, FUN_00450cc0
  -> confirms every list-style ITAC category shares this one traversal primitive,
     indexed by scroll position

InitializeItacLanguageStrings (0x440770, was FUN_00440770)  [itac.cpp]
  -> LoadLibraryA(itaclang.dll) [asserts "language_init: Can't find ITACLANG.DLL"]
  -> pass 1: LoadStringA(id=1,2,3,...) until 0 -> count (DAT_00520828) + total bytes
     (DAT_00520838)
  -> SR_MEM_allocate flat buffer (DAT_00520830) + pointer table (DAT_005231ac)
  -> pass 2: re-load each string by id -> copy into flat buffer, record start ptr

RegisterItacTooltip (0x440bd0, was FUN_00440bd0)
  -> appends param to &DAT_00520368[DAT_005231b4++], bounded at 30 slots
     (asserts "Too many tooltips" past slot 29)

  <- open: DAT_00588730+0x1ac's render-mode values not independently mapped
```

## FUN_004404a0, g_dwItacSkipEyeRecognition's set-site, and ITAC's room-graph exits (2026-09-10, Pass 73)

```
UpdateMouseCursorState (0x4404a0, was FUN_004404a0) -- CORRECTION: generic mouse-input
  helper, NOT a category-table dispatcher (Pass 71/72 speculated wrongly).
  <- called by: RunItacScreen, RunMissionSelectMapScreen, FUN_00440010, FUN_00440170
  -> applies mouse delta -> re-centers OS cursor -> clamps to screen bounds -> derives
     click/button edge-detection flags (DAT_00520138/DAT_0051dab0/DAT_00520820/_DAT_00520824)
     from packed input state DAT_005231a4

Category table field 3 = per-frame update (called directly from RunItacScreen's main
  loop, NOT from UpdateMouseCursorState):
  ItacDebriefPerFrameUpdate (0x4247c0, was FUN_004247c0) -- Debrief's field 3
    -> if (DAT_0052032c) { if (g_dwItacSkipEyeRecognition != 0) g_dwItacSkipEyeRecognition = 0;
       FUN_00424be0(); ... }  [THE set-site's consumer]
  ItacVideoReportsPerFrameUpdate (0x450630, was FUN_00450630) -- Video Reports' field 3
    -> on click: ItacSelectVideoReportRecord (field 4)

  ItacSelectVideoReportRecord (0x450cc0, was FUN_00450cc0) -- field 4 (Video Reports)
    -> waits for button release -> DAT_005251dc = DynamicList_GetByIndex(selected index)

  CORRECTION: DAT_005251dc is ITAC's "play the selected Video Report record" trigger,
    not a room-exit mechanism (Pass 71 assumed the latter from its plumbing alone).
    It reuses the room-transition bink-playing machinery (background-hide/CD-check/
    chdir) because playing a clip needs the same sequence a real room change does.

g_dwItacSkipEyeRecognition (0x523088, was DAT_00523088) -- both write sites traced:
  SET (=1): WinMain, immediately before the post-mission-debrief RunItacScreen() call
    (right after AdvanceCampaignMissionAndSaveProfile, non-end-of-campaign path)
  CLEAR (=0): ItacDebriefPerFrameUpdate, on the first per-frame tick after landing on
    the Debrief tab
  -> one-shot "skip eye-recognition for this specific post-mission entry" flag; any
     LATER re-entry via the normal VR room graph requires eye-recognition again

ITAC's room-graph exits (VRRoomNode graph, RunShipInteriorVRLoop @ 0x439fb0):
  ITAC has NO internal room-exit hotspot table -- RunShipInteriorVRLoop dispatches on
  the CURRENT node's nRoomType; nRoomType==2 launches RunItacScreen() directly instead
  of a normal still-image hotspot screen.

  VRRoomNode struct (44 bytes, pre-existing type): nHotspotX/Y/W/H (4x i16), pMoviePath,
    pMoviePathAlt (char* x2), nUnk10 (i16), nNumTargets (i16), pTarget0-4 (void* x5),
    nRoomType (i16), nSoundFlag (i16)

  Reliant graph (confirmed via read_memory):
    0x506c50 = ITAC room itself: hotspot(150,100,150,300), enter clip
      "bunk2itac_no_eye_recog.bik", nRoomType=2, nNumTargets=1 -> pTarget0=0x506c80
    0x506c80 = fixed post-ITAC room (bunkroom): enter clip "rel_itac2bunk.bik",
      alt "rel_doorloop.bik", nRoomType=0
      [RunShipInteriorVRLoop hardcodes the jump to 0x506c80 after RunItacScreen()
       returns, rather than reading pTarget0 back out -- same destination either way]
    0x506b30 = corridor-junction waypoint just outside ITAC's door: enter clip
      "rel_t2itac.bik", nRoomType=0, 3 targets:
        -> 0x506c50 (into ITAC, "bunk2itac_no_eye_recog.bik")
        -> 0x506e60 (back down corridor, "rel_itac2t.bik")
        -> 0x506cb0 (back to pod bay, "rel_itac2pod.bik")

  Yamato graph (partially confirmed):
    0x50aec8 = fixed post-ITAC room: enter clip "itac2rot.bik", alt "itac_dl.bik"
      -> lands in the "rot" (rotation) room, NOT bunk/pod -- confirms Reliant and
         Yamato VR room graphs are laid out differently
    Yamato's exact ITAC room node (nRoomType==2, counterpart to Reliant's 0x506c50):
      NOT located -- traced 0x50aec8 -> 0x50ae98 -> 0x50ae68 -> 0x50ace8 (none are it);
      get_xrefs_to on pod2itac.bik/lock2itac.bik string addresses returned no
      references (unindexed by Ghidra)

  <- open: DAT_00588730+0x1ac's render-mode values not independently mapped
```

## Remaining clip names/nodes + every category's fields 3/4 (2026-09-10, Pass 74)

```
Remaining itac2X/X2itac VRRoomNodes (found via search_byte_patterns on the string
  address's LE bytes -- get_xrefs_to found nothing, same blind spot as Pass 73's
  pod2itac.bik/lock2itac.bik):

  0x506f50 (Reliant) -- pMoviePath="rel_cap2itac.bik", hotspot=0x0/0x0, nNumTargets=0,
    nRoomType=0. TRUE TERMINAL: nothing else points to 0x506f50 either (searched for
    it as a raw pointer, zero hits) -- reached via scripted code, not the room graph.
    Consistent with the one-time capital-ship-transfer cutscene (Pass 65's "cap").

  0x50acb8 (Yamato) -- pMoviePath="itac2pod_hud.bik", hotspot(260,220,80,100),
    nNumTargets=1 -> pTarget0=0x50b678, nRoomType=5 (launches RunMissionSelectMapScreen
    directly). pTarget0 matches RunShipInteriorVRLoop's hardcoded "next room after
    mission map" for Yamato -- confirms the connection.

  0x50ab08 (Yamato) -- pMoviePath="itac2dor.bik", hotspot(220,0,200,480), nNumTargets=3
    -> 0x50a958, 0x50a9e8, 0x50aad8. nRoomType=0 (the "door" room).

  0x50ada8 (Yamato) -- pMoviePath="itac2itac.bik", hotspot(181,150,340,150),
    nNumTargets=0, nRoomType=2  <-- THIS IS YAMATO'S ITAC ROOM NODE, the counterpart
    to Reliant's 0x506c50 that Pass 73 failed to locate via graph traversal.
    Confirmed 2 incoming edges (found via search_byte_patterns on 0x50ada8 itself):
      0x50ab68 (lock-room junction, movie "ir_l2i.bik", alt "itac_itacl.bik")
        -> pTarget0=0x50ae08, pTarget1=0x50ab38, pTarget2=0x50ada8(ITAC)
      0x50ae34 (2nd junction, movie "ir_f2i.bik", alt "itac_itacl.bik")
        -> pTarget0=0x50ad78, pTarget1=0x50ada8(ITAC), pTarget2=0x50ae08
    Mirrors the Reliant "corridor junction fans out to ITAC + 2 other destinations"
    pattern from Pass 73. Confirms >=2 physical approaches to Yamato's ITAC.

Every category's field 3 (per-frame update) + field 4 (hover-preview render), decoded:
  cat0 Debrief:      field4 = ItacDebriefRenderTransferSummary (0x424930)
                      [renders rank/callsign transfer summary; distinct "continue"
                       prompt on the player's most-recent mission]
  cat1 News:         field3 = ItacNewsReportsPerFrameUpdate (0x44dea0)
                      field4 = ItacNewsReportsRenderPreview (0x44dfe0)
  cat2 VideoReports: field4 = ItacVideoReportsRenderPreview (0x450760)
                      [temp thumbnail of selected record, distinct from full playback]
  cat3 Fighters:     field3 = ItacFightersPerFrameUpdate (0x425980)
                      field4 = ItacFightersRenderPreview (0x425a70) [icon from record+0x3c]
  cat4 CapShips:     field3 = ItacCapShipsPerFrameUpdate (0x423930)
                      field4 = ItacCapShipsRenderPreview (0x423ac0) [icon from record+0x1e,
                        via a 19-case switch whose cases all decompile identically --
                        not confirmed as real vs. decompilation artifact]
  cat5 Squadrons:    field3 = ItacSquadronsPerFrameUpdate (0x44fb80)
                      field4 = ItacSquadronsRenderPreview (0x44fd10) [squads.spr portrait,
                        0x1c-byte/entry record array]
  cat6 Personnel:    field3 = ItacPersonnelPerFrameUpdate (0x44e590)
                      field4 = ItacPersonnelRenderPreview (0x44e720) [persons.spr portrait
                        from record+0x1e]
  cat7 Kills:        field3 = ItacKillsPerFrameUpdate (0x441280) [no redraw-gate, no
                        sub-tabs, just scroll bounds-check]
                      field4 = ItacKillsRenderPreview (0x441300) [trivial: caption flush
                        only -- Kills is driven by its Pass 71 live-3D field 2 instead]

  NEW: Fighters/CapShips/Squadrons/Personnel (cat 3/4/5/6) each poll a SECOND hotspot
    row (shared table ~0x4e96c4-0x4e96d0, indexed by shared global DAT_00523058) to
    switch roster sub-tabs (class/rank filter, exact semantics not mapped). News/
    VideoReports/Debrief/Kills do not have this.

Shared per-frame primitives used by every category and the main tab bar:
  FindHotspotIndexAtCursor (0x43fe40, was FUN_0043fe40) -- generic rect-array hit-test
    against cursor position
  IsClickConfirmEdge (0x441060, was FUN_00441060) -- click debounce (fires once per press)
  DrawFadingTextCaptions (0x43ff50, was FUN_0043ff50) -- renders the 6-slot floating-
    caption array (DAT_005202fc+) with optional fade-in
  UpdateHoverAnimationWidget (0x4409f0, was FUN_004409f0) -- generic hover "wiggle"
    animation updater for a small widget struct (float @+0x14, counter @+0x18,
    redraw callback @+0x20); widget identity not resolved

  <- open: rel_cap2itac.bik/itac2pod_hud.bik/itac2dor.bik not connected to a gameplay trigger
```

## All 4 remaining open items resolved (2026-09-10, Pass 75)

```
Sub-tab table (0x4e96c4-0x4e96d3, 16 bytes) -- exactly 2 sub-tabs, 4 parallel
  2-entry short arrays:
    0x4e96c8: [0, 1]      hotspot-click-index -> sub-tab ID (identity)
    0x4e96c4: [25, 24]    icon sprite index per sub-tab
    0x4e96cc: [551, 478]  draw X per sub-tab
    0x4e96d0: [59, 59]    draw Y per sub-tab (same row)
  <- open: click-rect array for these 2 buttons not located (0x4e96b0-c3 doesn't
     cleanly parse as one); semantic meaning of the 2 tabs not determined

ItacCapShipsRenderPreview's switch -- CONFIRMED REAL via disassemble_function
  (not a decompilation artifact as Pass 74 left open):
  56-byte lookup table @ 0x423c74: (classID-1) -> group value, pattern
    "groupN, groupN, 19(default)" repeating for N=0..18 (~19 groups of 3 classes)
  -> selected group*3 (0,3,...,54) used ONLY for a first color/tint-setting draw
     call; the actual icon draw right after uses the RAW class ID directly
  -> genuine per-ship-class tint/highlight-group system, semantics of the
     groups (faction? hull tier?) not determined

UpdateHoverAnimationWidget's widget -- generic (also called from 0x42a4f2,
  outside ITAC). Each ITAC call site passes a hardcoded literal address in
  ECX -- one static widget instance per category, not a shared/parameterized
  one. Debrief's instance (0x51d2e8) initialized in FUN_00424730 (called from
  ItacEnterDebriefCategory):
    +0x00 = sprite-surface handle (DAT_0052305c, one of RunItacScreen's setup
            buffers)
    +0x14 = float wiggle offset (already known)
    +0x18 = direction counter (already known)
    +0x20 = redraw callback = &LAB_00425220 (not decompiled)
  Used alongside a category-specific 2nd hotspot table with LITERAL args
  visible in disassembly (Debrief: ECX=0x4e4928, EDX=2 -- the prev/next-
  mission page-turn buttons) -- likely animates hover feedback for these
  small nav buttons, distinct from the main list-scroll hotspots.

DAT_00588730+0x1ac -- RESOLVED: not a scalar render-mode flag, but the FIRST
  FIELD of a bulk-copied 1299-dword (0x513, 5196-byte) video-mode descriptor
  record. InitializeGraphicsDevice:
    puVar6 = DAT_00588730 + 0x1ac
    puVar5 = (&DAT_00595da0) + param_4 * 0x513   [device/mode table from
                                                    EnumDisplayCardsFromDriver]
    for i in 0x513: *puVar6++ = *puVar5++         [the SAME 1299-dword copy
                                                     Pass 70 found, unplaced]
  *(int*)(DAT_00588730+0x1ac) read back afterward: values 0/1/2 each call
  LoadRendererBackendDriver (0x4cc470, was FUN_004cc470, self-identified via
  its own "SR_driver_init" GetProcAddress string -- LoadLibraryA + call that
  export) to load a renderer backend DLL; any other value skips the load
  (true hardware acceleration, no driver DLL needed).
  -> the 47 program-wide "+0x1ac" search_instructions hits were a RED HERRING:
     almost all belong to unrelated structs at the same coincidental offset,
     same lesson as Pass 70's "+0x50" investigation.
  <- open: per-mode-value driver DLL name (implicit register arg, not traced)
```

## Sub-tab click-rects, hover-widget callback, tint-group semantics (2026-09-10, Pass 76)

```
Sub-tab click-rects (found via disassemble_function on ItacFightersPerFrameUpdate --
  the literal args MOV EDX,0x2 / MOV ECX,0x4e5460 don't survive decompilation):
  0x4e5460: [{X=551,Y=59,W=64,H=41}, {X=478,Y=59,W=64,H=61}]
  -> X/Y match Pass 75's confirmed draw-position table (0x4e96cc/0x4e96d0) exactly

UpdateHoverAnimationWidget's Debrief callback chain, resolved:
  DAT_00588730... no -- 0x51d2e8+0x20 (_DAT_0051d308) = &RefreshDebriefSummaryText
    (0x425220, was LAB_00425220/FUN_00425220)
  RefreshDebriefSummaryText -> BuildDebriefSummaryText(1, 1.0)
  BuildDebriefSummaryText (0x425240, was FUN_00425240) -- assembles the mission-
    debrief narrative paragraph:
    -> checks per-mission outcome-flag arrays (DAT_00562e2c/e9c/ed6, DAT_0050099f,
       DAT_005009d7) indexed by the currently-viewed mission
    -> selects a template from local_14[] (4 pointers + 1 default) by outcome class
       (0-4 or -1), and/or GetLanguageString fragments (0x53f/0x540/0x541/0x566,
       gated on mission-end-reason DAT_00588394)
    -> concatenates matching fragments (separator &DAT_004e5440) into a buffer,
       final pointer stored to _DAT_0051d304
  CORRECTION: this is NOT a "wiggle" redraw for Debrief -- UpdateHoverAnimationWidget's
    generic periodic-refresh-on-tick-change mechanism is reused here to periodically
    rebuild the debrief text. Its other call site (0x42a4f2, outside ITAC) not traced,
    so unclear whether it's ever used for an actual wiggle effect anywhere.

Tint-group semantics -- partially resolved:
  PopulateCapShipsRosterForSubTab (0x424410, was FUN_00424410, called from
    ItacEnterCapShipsCategory) takes sub-tab index (0/1):
    param==0 -> walks 0x4e42c0..0x4e4560 (21 x 32-byte records)
    param==1 -> walks 0x4e4560..0x4e48c0 (27 x 32-byte records)
    each record -> FUN_00440710 (DynamicList insert)
  -> CONFIRMS: CapShips' 2 sub-tabs = 2 distinct ship rosters (21 vs 27 entries,
     plausibly per-faction, not confirmed)
  -> each 32-byte record holds ~7-8 consecutive GetLanguageString IDs (e.g. record0:
     1262-1269) + 1-2 small numeric fields -- consistent with a name/description/
     stat card per ship class
  <- UNBLOCKED in Pass 77 (see below) -- LANGUAGE.DLL exists on disk and its
     RT_STRING resources are directly readable without Ghidra
```

## Tint-group semantics unblocked via direct LANGUAGE.DLL extraction (2026-09-10, Pass 77)

```
reversing/tools/extract_language_strings.py (new tool) -- generic Win32 PE
  RT_STRING resource reader (16-strings-per-block STRINGTABLE format), reads
  gamedata/StarLancer/LANGUAGE.DLL directly, no Ghidra required. Also works
  on ITACLANG.DLL (identical PE resource format).

CORRECTION: Capital Ships' 32-byte records (0x4e42c0 x21, 0x4e4560 x27) hold
  8 PERSON names/callsigns each, NOT ship-class name/stat data as Pass 74-76
  assumed:
    ID 1262 "General Makin", 1263 "Sean Oliver", ... (record 0, all real names)
    ID 1277 "Jester" (record 1's 8th name -- a callsign mixed into real names)
    ID 1278 "Zero", 1279 "Ace", 1280 "Link", 1281 "Sundown", ... (record 2,
      ALL callsigns -- likely an embarked fighter squadron roster)
  Context check (IDs 1200-1261): 1200-1244 = the game's own END CREDITS
    (dev names, "Quality Assurance Warthog", "Localization" section headers);
    1245-1253 = mission objective text for a specific mission (the "Saladin"
    raid); 1254-1261 = that mission's named NPCs/callsigns ("Admiral Petrov",
    "Rasputin", "Hangman", "Electra"...)
  -> CONFIRMS this ID range is the shared campaign/credits/NPC text pool, not
     a dedicated per-ship-class table. Capital Ships category = named capital
     ships + their commanding officers/bridge crew (or embarked squadron).

Tint groups (Pass 75's 56-byte lookup @ 0x423c74) -- RESOLVED pairing pattern:
  FUN_00440710 (record-insert helper) links the raw 32-byte records into the
  DynamicList BY REFERENCE (no copy) -> record+0x1e IS the record's own
  trailing 2-byte field, read directly by the tint switch.

  All 21 sub-tab-0 classIDs:  1,2,4,5,7,14,8,2,11,10,13,14,16,17,19,20,22,
                              23,25,25,26
  All 27 sub-tab-1 classIDs:  28,29,31,32,35,37,38,40,46,41,41,29,56,43,40,
                              44,46,47,49,40,50,52,53,56,44,56,56

  -> Every value used lands on a "group" slot of the lookup table's
     groupN,groupN,default(19) triplets -- the DEFAULT slot (classID
     3,6,9,12,...,57) is NEVER assigned to any of the 48 real records on
     EITHER sub-tab.
  -> Several classIDs repeat across multiple distinct records (2 appears
     twice, 14 twice, 25 twice, 40 three times, 56 four times) -- confirms
     classID is a shared category value, not a unique per-ship ID.
  -> CONCLUSION (confidence 4): the ~19 tint groups each reserve exactly 2
     "populated" classID slots (36 of 57 total slots used) -- most plausibly
     2 named variants/marks/ships per hull class or faction grouping, sharing
     one UI accent color; the 3rd slot per group is an unused fallback that
     no real record ever exercises.
  <- open: which hull class/faction each group actually represents -- would
     need capships.spr's icon art decoded and compared (not attempted; the
     record text is person-names, not a self-describing class label)
```

## capships.spr decoded: tint groups are per-class-pair palettes (2026-09-10, Pass 78)

```
CAPSHIPS.SPR (RefPack-compressed, gamedata/StarLancer/RESOURCE/): shapeCount=57
  = 19 groups x {1 palette block, 2 ship images} -- EXACTLY explains Pass 77's
  "default classID slot never assigned to a real record" pattern: those aren't
  missing/reserved ships, they're each group's own dedicated palette block.

  shape indices 0,3,6,9,...,54 (19 total) -- 768-byte palette blocks, each
    immediately preceding its group's 2 real ship-image shapes
  shape indices 1,2 / 4,5 / 7,8 / .../ 55,56 -- the 2 ship images per group

BUG FOUND + FIXED in decode_spr.py: only ever used the FIRST palette block
  in a file for every shape (fine for single-palette files like the medal-
  case sprites -- re-verified unaffected by the fix). CAPSHIPS.SPR has 19
  separate palette blocks; using only the first produced geometrically-
  correct but color-scrambled "TV static" ship images for every group past
  the first. Fixed to track the nearest-preceding palette block per shape.

Visual confirmation after the fix: groups pair 2 GENUINELY DIFFERENT hull
  designs (not marks/variants of one ship) sharing one palette:
    group 1 (shapes 4,5): boxy dual-runway platform + separate sleek cruiser
    group 6 (shape 20): white-star-on-blue + red/white stripes (Alliance/US-
      style insignia)
    group 18 (shape 55): red Soviet-style star (Coalition-style insignia)
  -> CONFIRMS: each palette group = a faction/national color scheme shared
     by 2 distinct ships, not "2 marks of one class"

GetShapeRecordPointer (0x480c40, was FUN_00480c40):
  return spriteSetBase + shapes[index].recordOffset
  -- matches decode_spr.py's own documented ShapeSet.shapes[i].recordOffset
     format (Pass 39/41), now independently confirmed against game code

ActivateShapePalette (0x428410, was FUN_00428410):
  takes (paletteBlockPtr, brightness) -> converts 6-bit-VGA {R,G,B} triplets
  to native pixel format (shift/mask fields matching ComputePixelFormatFromMasks,
  Pass 69) -> uploads via WinVFX lock/unlock pair (DAT_005957c0/DAT_005957d0)
  brightness=1.0 -> full; other values -> dimmed (fade support)

  => ItacCapShipsRenderPreview's full sequence now understood end to end:
     GetShapeRecordPointer(capships.spr, group*3) -> ActivateShapePalette(_, 1.0)
     -> draw icon by raw classID
     [group*3 = the shape index of that group's palette block, NOT an
      arbitrary tint constant -- retroactively explains the unexplained
      "color-setting calls" preceding every icon draw across Pass 74's
      RenderPreview functions]

  <- open: real-world label per group (hull class/faction name) -- needs
     matching against official reference art
  <- open: whether Fighters/Squadrons/Personnel/Kills/News/VideoReports'
     .spr files use the same multi-palette-per-group layout -- not checked
```

## Player creation / campaign start (2026-09-10, Pass 79)

```
Main Menu "New Game" (DAT_0051dac4=0xc) -> RunNewGameSetupScreen (0x430490)
  case 0/1: set pilot gender (g_wPilotGenderIsFemale / g_dwNewPilotGenderIsFemaleUI)
  case 2: Load Existing Pilot -> screen 0xd (RunSaveGameBrowserScreen)
  case 3: Confirm New Pilot -> RunDifficultySelectDialog (3-tier g_wCampaignDifficulty)
    -> on confirm: SR_MEM_free(bg sprite) -> LoadPlayerProfile (Pass 62: loads or
       silently creates profile.bin, currentMissionIndex=1 for a fresh pilot)
    -> FUN_0049cd20 (fills a 260-byte array @ PTR_DAT_005047d2..0x5048d6 with value 2,
       resets a small struct @ 0x58a958 -- transient session state, NOT in profile.bin;
       only called for a genuinely new pilot, not Load Existing)
    -> returns 1 up through RunMenuScreenLoop to WinMain
  case 4: Exit to main menu
  case 5: cancel callsign edit (DAT_0052019c=1, re-runs FUN_004aada0) -- NOT a field-clear
  case 6: Options dialog
  case 7: toggle recent-name list panel

WinMain's main loop, first pass through after New Game (bVar1 true):
  EnsureCorrectCDMounted()
  if DAT_00562dc8 == 1 EXACTLY (brand-new pilot, never a resumed one):
    PlayBinkMovieFromArchiveWithVolume("new_intro.bik")   [campaign opening cinematic]
    RunReliantInductionTour (0x438d50, was FUN_00438d50)
  else:
    straight to RunShipInteriorVRLoop

RunReliantInductionTour -- 5-stage new-pilot orientation walkthrough, narrated by "Enriq":
  stage 0: locker room   (loop single_rel_c2lock.bik, narration enr_locker_box.bik)
  stage 1: sim pod        (loop rel_podmon_loop.bik,   narration enr_simpod_box.bik)
  stage 2: cargo deck     (loop rel_cdloop.bik,         narration enr_cd_box.bik)
  stage 3: ITAC           (loop rel_itacloop.bik,       narration enr_itac_box.bik)
  stage 4: outro          (loop rel_tv_enriq.bik,       narration enr_outro_box.bik)
  -> each stage: play ambient loop, advance on input/timeout -> play narration clip -> next
  -> returns exit stage (0-5); WinMain picks a follow-up transition clip via a per-stage
     jump table (ESI*4+0x4aa8c8, only partially read: 0x506bf0, 0x4e8d08="rel_pod2itac.bik")
  -> then RunShipInteriorVRLoop begins normal free-roam VR navigation aboard the Reliant,
     eventually reaching mission 1's briefing via the existing room-graph navigation
     (documented across the ITAC passes)

  <- open: FUN_0049cd20's array/struct role not traced to a consumer
  <- open: whether the tour can be aborted entirely vs. exited early at a stage
  <- open: the post-tour transition-clip jump table not fully mapped
```
