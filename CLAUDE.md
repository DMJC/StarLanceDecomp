# Lancerremake — project instructions

This project reverse-engineers Star Lancer's `Lancer.exe` and reimplements it as `neoLancer`.

## Reverse-engineering methodology (read before any Ghidra/decompile work)

Full methodology: `reversing/METHODOLOGY.md`. Read it before starting any
reverse-engineering task — the summary below is not a substitute.

**Non-negotiable rules, in brief:**

- **Semantic equivalence is the goal, not byte-level match.** Byte/assembly
  comparison is a *confidence tool*, not the completion criterion.
  Completion = 100% understood/reimplemented behavior.
- **Every claim carries an explicit confidence level (0-5)** — see the scale
  in `reversing/METHODOLOGY.md`. Never state a low-confidence guess as fact.
  Never silently upgrade a guess's confidence without new evidence.
- **Don't let algorithmic-tier assumptions launder structural-tier guesses
  into facts.** Keep "what a function does" separate from "why it's shaped
  that way" in write-ups.
- **Unit of work is the subsystem, not the individual function.** Recover
  the structs/globals a function's whole cluster uses together. Before
  declaring a subsystem done, check whether a richer pre-existing analysis
  layer already covers it (`search_functions`/`search_data_types` first) —
  this project has repeatedly re-derived things a previous pass had already
  named correctly, simply because nobody searched first.
- **Update `reversing/confidence_db.md` and `reversing/dependency_graph.md`**
  whenever a function/struct/global is newly identified, reinterpreted, or
  changes confidence. This is what prevents "skipped huge swathes of the
  executable" — a subsystem with dependencies pointing at unrated entries is
  a visible, honest gap, not something to paper over.
- **Don't backfill confidence ratings you haven't actually re-verified.** The
  pre-existing `reversing/reverse_engineered_functions.md` (827 entries) is
  NOT yet indexed in the confidence database — treat anything from it not
  listed in `confidence_db.md` as unrated legacy content, not as Confidence 2
  just because it's written in prose with conviction.

## Session memory

A separate, cross-session Claude memory store (outside this repo) holds the
narrative history of past investigations — what was tried, what was ruled
out, live-playtest findings, user corrections. It's useful context but is
NOT a substitute for `reversing/confidence_db.md`, which is the structured,
in-repo record any contributor (human or AI) should be able to read.

## Live debugging

This codebase's own history (see `reversing/reverse_engineered_functions.md`
and the confidence database) shows static code reading alone has repeatedly
reached wrong conclusions ("this should work") on bugs that only became
clear via actual live playtesting with debug instrumentation. When
investigating a reported runtime bug, prefer adding targeted, throttled
`printf` debug output and running the actual game over pure static tracing,
once static reading stops producing a confident, checkable hypothesis.
