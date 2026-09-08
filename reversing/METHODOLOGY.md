# Reverse-engineering methodology

This document governs how `Lancer.exe` (and the other RealSpace-engine
executables this project reverse-engineers) get analyzed and reimplemented.
It supersedes any ad-hoc approach used in earlier passes. Every new piece of
work in `reversing/` or informed by Ghidra analysis should follow this.

## Core principle: semantic equivalence first, byte-level match as a validation tool

The end goal is **not** "the rewritten code compiles to the same bytes as the
original." The end goal is **behavioral equivalence** — the reimplementation
does the same observable thing for the same inputs. Byte-for-byte assembly
comparison is one of several tools for *gaining confidence* that a rewrite is
correct, not the definition of correctness itself, and not the completion
criterion.

**Completion criterion for any function/subsystem: 100% understood/
reimplemented behavior, not 100% matching bytes.**

## The three-tier match hierarchy

1. **Structural match** — identify functions, globals, structs, enums,
   vtables, jump tables, state machines, resource formats, and call
   relationships. This is *shape*, not *behavior*: knowing a function exists,
   what it's called, what it touches, and who calls it.
2. **Behavioral match** — the rewritten function produces the same
   externally observable results for the same inputs (return values, modified
   structures, globals, generated events, file output, rendering commands, AI
   decisions, etc.).
3. **Algorithmic match** — control flow and data transformations correspond
   closely to the original. This is the deepest, most expensive tier and is
   only worth pursuing where it actually matters (perf-critical code,
   anything with subtle edge-case behavior that a black-box behavioral test
   wouldn't catch).

**Do not let Tier 3 (algorithmic) assumptions propagate backward into Tier 1
(structural) claims unless they have been proven.** A plausible guess about
*why* code is shaped a certain way is not evidence for *what* a struct field
is named or *what* a function's real boundary is. Keep these tiers honestly
separated in write-ups — don't let a confident-sounding algorithmic narrative
launder an unproven structural guess into an assumed fact.

## The pipeline

```
Original executable
        │
        ▼
 ┌─────────────────────┐
 │ Structural recovery │
 │                     │
 │ Functions           │
 │ Globals             │
 │ Data structures     │
 │ Call graph          │
 │ Jump tables         │
 │ State machines      │
 │ Resource structures │
 └──────────┬──────────┘
            │
            ▼
 ┌─────────────────────┐
 │ Behaviour discovery │
 │                     │
 │ Inputs / outputs    │
 │ Side effects        │
 │ Global state        │
 │ Preconditions       │
 │ Invariants          │
 └──────────┬──────────┘
            │
            ▼
 ┌─────────────────────┐
 │ Function rewrite    │
 │                     │
 │ Clean C/C++         │
 │ Meaningful names    │
 │ Real structures     │
 └──────────┬──────────┘
            │
            ▼
 ┌─────────────────────┐
 │ Differential tests  │
 │                     │
 │ Original vs rewrite │
 └──────────┬──────────┘
            │
            ▼
      Behaviour match
            │
            ▼
 ┌─────────────────────┐
 │ Assembly comparison │
 │ for uncertain code  │
 └──────────┬──────────┘
            │
            ▼
    Modify / improve
```

## The original executable as oracle

Where a differential-test harness is feasible (a function with clean,
capturable inputs/outputs — not a function entangled with global UI/render
state), treat `Lancer.exe` itself as the ground-truth oracle:

```
same input
   │
   ├──── original function ────> result A
   │
   └──── rewritten function ───> result B

             compare A/B
```

Compare return values, modified structures, global variables, generated
events, file output, rendering commands, AI decisions, etc. — whatever the
function's real observable surface is, not just its return value.

This isn't always practical (most of this codebase's interesting behavior is
deeply entangled with global engine state, live rendering, and real user
input, not a clean pure-function boundary) — use it where it's cheap, don't
force it where it isn't. A well-reasoned Confidence 2/3 write-up (see below)
is a legitimate, honest stopping point when a real differential harness isn't
practical.

## Unit of work: subsystems, not individual functions

Change the unit of work from "decompile this function" to "resolve this
subsystem." When investigating a function, recover **all the structures and
globals used by that cluster together**, not just the one function that
happened to be the entry point. 

Before declaring a subsystem investigated, check whether a
richer, previously-existing analysis layer already covers ground your own
pass hasn't looked at (`search_functions`/`search_data_types` for the
subsystem's own naming family) — this project's own history includes more
than one case where hours were spent re-deriving something a completely
different, undocumented-in-memory process had already named correctly.

## Confidence scale

Every claim in this project — a function's real behavior, a struct field's
name/type, a global's role, an algorithmic detail — carries an explicit
confidence level. **Never silently upgrade a lower-confidence guess to a
higher one without new evidence, and never state a Confidence 0/1 claim as
if it were a Confidence 4/5 fact.**

| Confidence | Meaning |
|---:|---|
| **5** | Exact compiler output match — the rewrite, compiled, produces byte-identical (or provably semantically identical at the instruction level) machine code to the original. Rare; reserve for cases this was actually checked. |
| **4** | Assembly substantially equivalent — read the original disassembly/decompilation and the rewrite side by side; the control flow and operations correspond closely, no meaningful divergence found. |
| **3** | Extensive differential tests match — real oracle-vs-rewrite testing (see above) was run across a meaningful input range and matched, but the assembly itself wasn't compared line-by-line. |
| **2** | Static analysis strongly supports the interpretation — a clean Ghidra decompile, cross-referenced against real corpus data (real `.IFF` files, real callers, consistent field usage across multiple independent call sites) supports the claim, but no dynamic/differential test was run. This is where most of this project's existing work currently sits. |
| **1** | Plausible interpretation — a reasonable guess, maybe supported by naming conventions or a single call site, not independently cross-checked. This project's history has many of these; they are useful working hypotheses, not facts. |
| **0** | Unknown — genuinely undetermined; documented as a gap, not guessed at. |

Every write-up (memory file, `reversing/` entry, code comment citing a Ghidra
source) should carry its confidence level, or be treated as unrated legacy
content that needs a confidence pass before being relied on for a new
decision.

## The confidence database and dependency graph

`reversing/confidence_db.md` is the living, structured index of what's known
about which function/struct/global, at what confidence, and what it depends
on. It exists specifically to prevent the failure mode of skipping huge
swathes of the executable while chasing one narrow thread — a per-subsystem
row in the database makes coverage gaps visible instead of implicit.

- **Update it whenever a function/struct/global is newly identified,
  reinterpreted, or has its confidence level change** (up OR down — a
  Confidence 2 guess that a later pass disproves should be marked down, not
  silently dropped).
- **Populate it incrementally, honestly.** Do not backfill confidence ratings
  for previously-documented material (e.g. the existing 827-entry
  `reverse_engineered_functions.md`) without actually re-verifying each entry
  — an unverified blanket rating is worse than no rating, because it looks
  authoritative. Existing entries are implicitly unrated (treat as
  Confidence 1 at best, i.e. "plausible interpretation, not independently
  re-checked under this methodology") until individually revisited.
- **The dependency graph** (`reversing/dependency_graph.md`) records, per
  entry, what other functions/structs/globals it depends on or is depended on
  by — this is what makes "resolve this subsystem" (above) checkable rather
  than aspirational: before marking a subsystem resolved, its dependency
  edges should mostly resolve to entries that are themselves in the database,
  not a wall of unrated references.

## Relationship to `reversing/reverse_engineered_functions.md` and Claude's own memory files

`reverse_engineered_functions.md` remains the prose-form reference for
per-function behavior detail (signatures, field tables, equivalent C
implementations, known compatibility hazards) — the confidence database
doesn't replace it, it indexes it (and everything else: memory-file
findings, code comments) with a confidence level and dependency edges.
Claude's own cross-session memory files (`project_lancer_*.md`, outside this
repo) remain the narrative "how we got here / what was tried and ruled out"
record — useful context, not a substitute for the structured database living
in the project itself, which any contributor (human or AI) should be able to
read without needing Claude's own memory.
