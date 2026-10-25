# Issue tracker: Local Markdown

Issues and specs for this repo live as Markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`.
- A feature spec, when maintained in the tracker, lives at `.scratch/<feature-slug>/spec.md`.
- Implementation tickets are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` in dependency order.
- Each ticket records its blockers near the top. Use `Blocked by: None` when it can start immediately.
- Ticket state is recorded in a `Status:` line. New fully specified tickets use `ready-for-agent`.
- Comments and conversation history append under a `## Comments` heading.

When a skill says to publish to the issue tracker, create one Markdown file per ticket in the feature's `issues/` directory. Do not create external tracker labels for this local workflow.
