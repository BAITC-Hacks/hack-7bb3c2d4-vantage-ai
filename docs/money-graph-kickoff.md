# Money Graph — case selection and initial requirements

Recorded on 23 September 2026 following the team's selection of Money Graph.

## Selected case

**Money graph: reconstructing the financial structure of an organized group from a transaction network**

Task owner: **Freedom**. Track: **Finance**. Team: **Vantage AI**.

## Requirements confirmed by the supplied case description

An AML analyst sees the bottom of a transaction chain and needs to reconstruct the financial structure above it. The described tool must:

- Turn four hops of transfers into a transaction graph.
- Assign a role to each node.
- Rank entities for investigation.

These are requirements, not claims of implemented functionality. Investigation priorities and inferred roles are analytical leads, not proof of wrongdoing.

## Technical specification and data to review

- https://docs.google.com/document/d/1JPLU-G6R25Ge2hVaY2J9cqvrx7FGExj87XKwJPaMz3o/edit
- https://drive.google.com/file/d/1ro-SiY042jv7De0h7tXBDyY8ZKdHz_US/view
- https://drive.google.com/file/d/1yHdWaSb6gwPAUrqco-KrwR2U_YhzFQFT/view
- https://drive.google.com/file/d/1EnMGG22jSH7Mvgt396kKRi3bjAobsomN/view

The full technical specification and linked datasets have not yet been verified for this checkpoint. Confirm the exact scoring rubric, input schema, graph direction, hop semantics, role taxonomy, required outputs, and technology constraints before implementation decisions are final.

## Proposed implementation checkpoints (not official scoring criteria)

1. Inspect provided data and document identifiers, transfer direction, amount, currency, timestamps, and missing values actually present.
2. Implement ingestion and validation with explicit errors for unsupported input.
3. Reconstruct the required graph from selected starting entities using the task's hop rules.
4. Compute transparent role hypotheses and investigation priorities with supporting transfers and paths.
5. Display the graph, ranked entities, and evidence for a selected entity.
6. Test the full input-to-result path, including malformed input and disconnected entities.
7. Verify a clean-clone launch and document dependencies, configuration, test steps, and limitations.

## Submission checklist from the supplied participant guide

- Use an AI agent in the development workflow.
- Keep final code in the team repository supplied by the platform.
- Never publish API keys.
- Document implemented features truthfully; distinguish planned work from running functionality.
- Include purpose, features, user flow, technologies, architecture, launch steps, reproducible test, data/services, limitations, and deployment link if available in the final README.
- Push the final version before the deadline and complete **Submit Solution** on the platform.

## Existing repository mismatch

At this checkpoint the incoming scaffold, README, and AGENTS.md describe **Track 11 / Kazakhtelecom / organisational regulation comparison**. They do not describe the newly selected Money Graph case. The scaffold is preserved; case-specific instructions and implementation must be reconciled with the team's confirmed selection and full Money Graph specification. No Money Graph functionality is claimed by this document.
