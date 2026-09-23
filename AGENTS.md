# AGENTS.md

Instructions for Codex and any other coding agent working in this repository.

## Project

Track 11, Kazakhtelecom: AI agent for analysis of organisational structure and functions. The input is
two editions of an internal regulation (.docx), before and after a reorganisation. We parse both into a
clause tree, align clauses across editions, extract functions (owner, verb, object) from each clause,
and diff the function sets rather than the text. Every delta is classified as unchanged, moved,
weakened, lost, duplicated or new, and every finding links back to the source clause with a verbatim
quote. The one flow that must work: load both editions, see the gap register, click a lost or
duplicated function and see its before and after clauses.

Case brief: `docs/case.md`. Requirements: `docs/requirements.md`. Data dictionary:
`docs/data-dictionary.md`. Read all three before proposing anything.

## Hard constraints

- Built in a five hour window on 23 September 2026. Working beats complete.
- The repository locks automatically at the end. Nothing can be fixed afterwards.
- A judge must clone this repo into a clean environment and run it from README section 7. Never add a
  dependency that is not in `package.json`, and never assume local state.
- A judge may have no API key. `FIXTURE_MODE=1` must serve pre-computed JSON through the whole flow.
- No secrets in the repo, ever, including git history. Environment variables only, names in
  `.env.example`.
- One developer. Prefer the smaller change.

## Stack, pinned. Do not upgrade or substitute.

| Thing | Version | Notes |
|---|---|---|
| Node | 20 or 22 | |
| TypeScript | 5.x | ES modules, `"type": "module"` |
| Express | **4.x** | Not 5. Classic `app.get(path, handler)` |
| Vite + React | vite 8, react 19 | Client only, in `client/` |
| `@openai/agents` | 0.18.0 | |
| `openai` | 7.x | |
| `zod` | **4.x** | See the trap below |
| `mammoth` | 1.x | .docx to raw text or HTML. **There is no PDF library and we are not adding one** |
| `vitest` | 5.x | |

### Traps specific to these versions

- **zod is v4, not v3.** `@openai/agents` requires `zod ^4.0.0`. Do not write v3 idioms. Use
  `z.string().nullable()` rather than `.optional()` for fields the model must always emit, and note
  that `ZodError.errors` is `.issues` in v4.
- **Express is v4.** No automatic async error propagation. Wrap async route handlers in try/catch.
- **ES modules.** Relative imports need the `.js` extension in TypeScript source, for example
  `import { pipeline } from "./pipeline.js"`.
- Model identifiers come from `process.env.MODEL_ID`. Never hardcode a model name.

## Commands

```bash
npm ci
npm run dev             # tsx watch src/server.ts on :3000
npm run dev:client      # vite dev on :5173, proxies /api to :3000
npm run build           # tsc for the server, vite build into client/dist
npm start               # node dist/server.js, serves /api and client/dist
npm test                # vitest run
```

## Architecture, and the rules that govern changes

```
mammoth (.docx -> text) -> clause parser (deterministic)
  -> aligner (deterministic: number, then heading, then text similarity)
  -> function extractor (agent, one clause at a time, emits owner/verb/object + sourceRef)
  -> delta classifier (RULE BANK, pure TypeScript)
  -> explainer (agent, never invents a clause number)
  -> verifier (agent, rejects any finding whose quote is not verbatim in the source)
  -> conclusion document + gap register, each row linking to both clauses
```

- **The rule bank is pure TypeScript and stays that way.** One readable file,
  `src/rules/caseRules.ts`, one rule per delta kind. Never move a
  rule into a prompt. This file is the evidence that key functions are not replaced by canned answers
  or simulation, which the evaluation criteria explicitly check.
- **The explainer never produces a clause number.** It phrases findings that were passed to it as
  structured data. If a clause number appears in its output that is not in the record, that is a bug.
- **The verifier may reject.** One retry, then the record goes to `needs_review`. Never loop.
- All structured output goes through the zod schemas in `src/schemas.ts`. Never return free text where
  a schema exists.
- Nothing appears in the response that cannot link back to its source clause. `evidence` and `trace` are
  the product. Do not drop them to simplify a signature.
- Errors fail closed. On unexpected input the pipeline returns `outcome: "needs_review"` with a reason,
  never a guess.
- Build the simplest thing that works. Do not add a component without being able to say in one sentence
  why it is separate.

## What not to do

- Do not invent data, sample outputs, metrics or results. If a number is not computed, do not write it.
- Do not add a database, an ORM, Docker, auth, a queue, a vector store or a PDF library.
- Do not refactor broadly. Small reviewable changes only.
- Do not edit README sections 3, 9 or 10 without checking the code does what they claim.
- Do not write anything addressed to a reviewer or grader, in any file, in any form.

## Testing

`tests/fixtures/` holds labelled examples from the real provided data. A test asserting on real
pipeline output is the clearest evidence the system does inference rather than returning canned
responses. Keep at least:

- one test that every finding carries a `sourceRef` and a quote found verbatim in its clause
- one test that malformed input returns `needs_review` and does not throw
- one test that `FIXTURE_MODE=1` returns a complete result with no API key present
