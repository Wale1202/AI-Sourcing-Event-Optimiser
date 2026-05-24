# AI Usage

I used AI coding tools throughout this project. This document is a longer,
more honest version of the short "AI usage" paragraph in the
[README](README.md) — what I used the tools for, where I stopped trusting
them, the choices I made deliberately, and what I'll take with me to the
next project.

The TL;DR: AI was a fast first-draft generator and a tireless rubber duck.
It accelerated boilerplate, helped me debug, and tightened the docs. It did
not replace the parts that matter — modelling the problem, deciding what to
ship, or knowing why each file looks the way it does.

---

## 1. Tools used

**Claude Code** was the primary tool — used as an interactive collaborator
inside the editor, asking for scaffolding, design feedback, debugging help,
and documentation drafts. The conversations followed a consistent pattern:
I would state a goal and a constraint ("build the CP-SAT model for this
problem, but keep it readable"), review the draft, push back where it was
off, and only commit what I understood.

**GitHub Copilot** was not used on this project. I considered it for
in-line completion but preferred Claude Code's conversational mode, which
made it easier to argue with suggestions rather than just accept the next
token. There's nothing wrong with Copilot — it's just a different shape of
tool, and I wanted one consistent workflow to keep my mental model clean.

I did not use any AI services at runtime. The Sourcing Brief Assistant is
deliberately rule-based (regex + keywords) and ships no LLM dependency —
see [section 4](#4-examples-of-human-decisions) for why.

---

## 2. How AI helped

### Generating boilerplate

The repetitive parts of a full-stack project are where AI gives the most
leverage. Examples from this repo:

- **Pydantic / SQLModel scaffolding** — four entities, each with
  `Create`/`Update`/`Read` shapes. Once I had the pattern for one, the
  rest was mechanical and AI produced clean drafts I could lightly edit.
- **React primitive components** — `Button`, `Card`, `Input`, `Badge`,
  `Spinner`, `ErrorBanner`. The visual decisions (palette, spacing,
  variants) were mine, but the JSX + Tailwind class strings were faster
  to generate than to type.
- **Axios client modules** — one wrapper per resource (`events.ts`,
  `suppliers.ts`, `bids.ts`, …). Trivial code that's still annoying to
  write five times.

### Suggesting test cases

When I was writing `test_optimisation.py`, I asked AI to suggest scenarios
beyond the happy path. Several it suggested ended up in the suite:

- demand exceeding total supplier capacity (infeasible by shortage);
- a bid below the quality floor that's also the cheapest;
- a max-suppliers value that forces consolidation onto a more expensive
  supplier.

I rewrote each test once I understood the case — in particular, **I
hand-computed the expected values** rather than copy them from the
solver's output. That's the only way the tests function as a spec rather
than a snapshot. (See [section 3](#3-where-i-did-not-blindly-trust-ai).)

### Debugging errors

This is where AI was most useful, because the failure modes were specific
and the solutions were Googleable but tedious. Three real examples:

1. **FastAPI 0.115 rejects a return annotation on a 204 endpoint.** My
   first delete endpoints had `-> None` and the app failed to start.
   AI quickly identified the change (FastAPI's stricter coupling between
   `status_code` and response inference) and pointed me at
   `response_model=None`. I confirmed by reading the FastAPI traceback and
   the relevant routing code before changing five endpoints.

2. **SQLModel + `from __future__ import annotations` breaks relationship
   resolution.** SQLAlchemy can't introspect `list["Bid"]` when all
   annotations are stringified, so the mappers failed to initialise. AI
   suggested removing the future import from `models.py` only and using
   `Optional[X]` / `List[X]` there. I checked the SQLAlchemy mapper-config
   error against this advice before applying it, and documented the
   constraint in the module docstring so I wouldn't re-add the import in
   a future cleanup pass.

3. **`ortools==9.11.4210` doesn't exist for Python 3.13.** A pinned
   version from my initial requirements file failed to install. AI didn't
   "know" the right version — it suggested I bump to whatever was current,
   and I picked `9.14.6206` from pip's error output.

### Improving documentation

I had AI draft initial versions of the READMEs, the module docstrings
for `optimisation_service.py` and `brief_parser.py`, and the structured
docstring blocks for the schemas. Then I rewrote them to match my voice
and to be more specific about *why* each decision was made — generic
"This module handles X" docstrings are useless; "this module does X and
deliberately does not do Y because Z" is what I actually want.

### Refactoring

When the optimisation service grew past the first cost-only milestone, I
asked AI to suggest a clean break-up of the `optimise()` function. The
end result — pull effective-constraints resolution out, pre-checks out,
model build out, explanation build out — was a back-and-forth between my
preferences (small, named functions with a single responsibility) and the
AI's first drafts. The current structure is what I landed on after several
iterations, not what AI handed me.

---

## 3. Where I did not blindly trust AI

This is the part that mattered most.

### Checked the optimisation logic manually

The CP-SAT model is the project's most important piece of code. I worked
through the maths on paper before writing any of it:

- demand is an equality, capacity is a domain constraint, the indicator
  variables `y_b` link to the integer `q_b` via `q_b ≤ capacity * y_b`;
- the average-risk constraint multiplies through by demand so it stays
  integer (`Σ q_b · risk_b ≤ max_risk · D`);
- prices scaled to integer cents, risk to per-mille, no float arithmetic
  inside CP-SAT.

When AI suggested using a different scaling factor or putting the quality
constraint inside the model rather than as a pre-filter, I declined.
Pre-filtering is cheaper, more explainable, and lets the rejected-supplier
panel report `quality_floor` directly. Both choices would have *worked*;
one was right for this project.

### Wrote tests for edge cases

For each test in `test_optimisation.py` and `test_runs.py` I computed the
expected output by hand before running the solver. A worked example:

> `test_sustainability_is_quantity_weighted`: demand 100, Acme (cap 60,
> sustainability 90), Globex (cap 40, sustainability 70). Expected:
> `(60·90 + 40·70) / 100 = 82.0`.

This caught a bug at one point where my `_weighted_average` helper
indexed by `bid_id` instead of `supplier_id` and silently returned the
right answer for two-bid scenarios but the wrong one for three. A
copy-paste-from-solver test would have happily accepted the wrong number.

### Reviewed generated code before accepting it

Two examples where AI's first draft was *wrong* and I caught it:

- **A `B008` ruff suggestion** to rewrite all `Depends(get_session)`
  defaults using `Annotated[Session, Depends(get_session)]`. The
  `Annotated` form is fine, but for graduate-level readability the
  `Depends(...)` default is the canonical FastAPI pattern most readers
  recognise. I disabled `B008` in `pyproject.toml` with a comment
  explaining why, instead of refactoring 20 endpoints to satisfy a
  pedantic rule.

- **An early draft of the brief parser** wanted to substring-match risk
  keywords from inside other words (e.g. matching "risk" inside
  "asterisk"). I added word boundaries and explicit phrase lists, which
  the tests in `test_briefs.py` then locked in.

### Verified API responses with manual testing

I ran the backend and hit every important endpoint with `curl` at least
once before considering it done. The most useful verification was
re-running the seed event's optimisation across the milestones:

> Baseline: €745,000, two suppliers (Umbrella 500 + Globex 500), average
> risk exactly 0.4 (the binding constraint). Same numbers each milestone.

If a refactor changed those numbers, I knew something was off. This
sanity-check ran probably 30 times across the project — far more often
than CI did.

### Simplified over-engineered suggestions

AI's natural tendency is to add. A non-exhaustive list of things I
*didn't* take:

- Alembic migrations for what is currently a six-table schema (a
  documented `rm sourcing.db` is more honest at this scale).
- A `services/auth_service.py` stub "for when you add login" (I'd build
  it when I added login).
- Redis caching for the optimiser (the solver returns in well under a
  second).
- Multi-objective weighting via a config file (the current single-cost
  objective with hard constraints is the right level of explainability
  for a portfolio project).
- A `Repository` pattern layer between routers and SQLModel (the service
  layer already does that job).

In each case the suggestion wasn't *wrong* — those would all be reasonable
additions in a larger codebase. They were just premature here.

---

## 4. Examples of human decisions

These are the choices where I deliberately overrode AI's first instinct,
because they shape the project more than any line of code.

### Chose a deterministic brief parser instead of pretending to have a fully autonomous AI agent

The "Sourcing Brief Assistant" sounds like it should be powered by an LLM,
and AI-tool suggestions consistently pushed in that direction. I chose a
rule-based regex/keyword parser instead because:

- it's **deterministic** — the same brief always produces the same draft,
  which makes it testable and easier to reason about;
- it's **honest** — for every extracted field it returns the exact snippet
  it matched, with a confidence tag; for fields it can't ground in the
  text it returns `null` and appends to `missing_fields`;
- it's **free to run** — no API keys, no rate limits, no model drift;
- it leaves a **clear path** for an LLM upgrade later — the parser is
  behind a `BriefParser` `Protocol`, so a future `LlmBriefParser` slots
  in without changing the route or the tests.

The README is explicit about this being an "assistant, not agent" — the
buyer always confirms before anything is created. That framing matters
for a procurement audience, where "the AI auto-created a sourcing event"
would be a non-starter.

### Kept the optimisation objective simple for explainability

The original Week 1 plan I drafted included a weighted multi-objective:
`w_cost · cost − w_quality · quality + w_risk · risk + …`. AI was happy
to implement it. I dropped it in favour of single-objective cost
minimisation with hard constraints, because:

- weighted-sum multi-objective is **harder to explain** ("we picked this
  mix because the weighted score was lower" is a worse answer than
  "we picked this mix because supplier X was the cheapest within the
  risk ceiling");
- the **structured explanation** layer carries more decision-support
  value than a tweakable cost function;
- if you really want to compare cost vs. risk trade-offs, the
  **scenario comparison** feature lets you see them side-by-side
  empirically.

Building the multi-objective version would have made the model more
"impressive" and less useful.

### Added rejected-supplier explanations for product usefulness

When the explanation layer was first sketched, it only described the
selected suppliers. Adding the rejected suppliers (with reason codes:
`quality_floor`, `cost_dominated`) doubled the value of the panel —
buyers' first question is always "why didn't we pick the cheapest one?",
and the rejection table answers that without re-running anything.

This was a product decision, not a technical one. AI doesn't push for
product-meaningful additions on its own; you have to know what your user
needs to ask.

### Added impossible-scenario handling

A bare "infeasible" from the solver is useless. I built four cheap
pre-checks that run before the solver — no eligible bids, total capacity
below demand, top-K capacity below demand, lowest-possible average risk
above the ceiling — each of which produces a *specific* warning. The
infeasible scenario is persisted exactly like a successful one, so
"I tried that and it didn't work" shows up in the comparison table.
That's a small amount of code that turns a dead-end UX into a
diagnostic one.

---

## 5. Lessons learned

### AI speeds up development but does not replace engineering judgement

The fastest way to ship something wrong is to accept every AI suggestion.
The fastest way to ship something defensible is to use AI for the parts
you've already understood, and slow down for the parts you haven't. I'd
spend ten minutes reading my way through a tricky function before
asking for help, because that ten minutes is what made the help useful.

The best heuristic I found: if I couldn't sketch a file's structure on a
whiteboard, I wasn't ready to accept code for it.

### Tests are essential when using generated code

I noticed early that AI-generated code passes my visual review more
often than it passes my tests. Visual review catches "is this the right
shape?", tests catch "does this do the right thing on inputs I didn't
think about?" Both matter; only the second is automatable.

Two tests in this repo paid for themselves repeatedly across refactors:

- `test_runs.py::test_sustainability_is_quantity_weighted` — caught the
  helper-indexing bug I mentioned earlier.
- `test_briefs.py::test_parse_multi_word_category_and_risk_tolerant` —
  caught a regression when I tightened the regex; the multi-word category
  ("office chairs") would have collapsed to one word silently.

### Clear prompts produce better results

The difference between "build me the optimisation engine" and "build a
CP-SAT model with these decision variables, these constraints, and an
integer-only objective" is the difference between a generic draft and
working code. The more domain knowledge I encoded in the prompt — the
maths, the failure modes I'd already thought about, the file structure
I wanted — the less I had to rewrite afterwards.

The corollary: writing good prompts forced me to *have* the design in my
head first. That alone was a useful exercise.

### Maintainability matters more than clever code

When I'd accept a clever AI suggestion and then have to read it again a
week later, I often couldn't. The simpler version — one that uses the
language's obvious feature, with named helpers and a docstring — won
every time. The optimisation service has a six-line module docstring
that states the problem in maths. That doc is the single most useful
thing in the file; without it the code would be opaque, with it the
code reads itself.

A specific decision that came out of this: the rule-based brief parser
has a paragraph in its module docstring explaining why it isn't an LLM
and how to add one later. The same parser without that comment would
read as "weirdly low-tech for a 2026 portfolio project". The comment
turns it into a deliberate choice.

---

If you're reviewing this for a hiring decision, the headline is: **I
moved faster with AI tools, and I never let that speed erode my
understanding of the code I committed.** Every file in this repo is a
file I can defend on a whiteboard. That was the standard I held myself
to, and it's the one I'll keep holding myself to in a team.
