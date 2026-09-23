import { z } from "zod";

// A numbered clause from one edition of the regulation.
export const Clause = z.object({
  edition: z.enum(["before", "after"]),
  number: z.string().describe("e.g. '5.5.3'"),
  heading: z.string().nullable(),
  text: z.string(),
  path: z.array(z.string()).describe("ancestor clause numbers, outermost first"),
});
export type Clause = z.infer<typeof Clause>;

// One duty extracted from a clause: who does what to what.
export const OrgFunction = z.object({
  owner: z.string(),
  verb: z.string(),
  object: z.string(),
  quote: z.string().describe("verbatim text from the source clause"),
  sourceRef: z.string().describe("e.g. 'before 5.5.3'"),
});
export type OrgFunction = z.infer<typeof OrgFunction>;

export const DeltaKind = z.enum(["unchanged", "moved", "weakened", "lost", "duplicated", "new"]);
export type DeltaKind = z.infer<typeof DeltaKind>;

export const Finding = z.object({
  id: z.string(),
  kind: DeltaKind,
  before: z.array(OrgFunction),
  after: z.array(OrgFunction),
  ruleId: z.string(),
  explanation: z.string(),
  outcome: z.enum(["asserted", "needs_review"]),
  verifierNote: z.string().nullable(),
});
export type Finding = z.infer<typeof Finding>;

export const TraceEvent = z.object({
  actor: z.enum(["parser", "aligner", "Extractor", "rules", "Explainer", "Verifier"]),
  event: z.string(),
  detail: z.string(),
  atMs: z.number(),
});
export type TraceEvent = z.infer<typeof TraceEvent>;
