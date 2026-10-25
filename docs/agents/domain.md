# Domain Docs

How engineering skills should consume this repo's domain documentation.

## Before exploring

- Read `CONTEXT.md` at the repo root, or `CONTEXT-MAP.md` if present and the relevant context documents it points to.
- Read relevant architecture decision records in `docs/adr/`.
- If a context document or ADR directory does not exist, proceed without assuming decisions that are not documented.

## Use the project's vocabulary

Use domain terms as defined in context documents. If a needed concept is not documented, use the terminology in the current project specification and call out unresolved naming decisions instead of silently inventing a new term.

## Flag conflicts

Surface conflicts with documented architecture decisions instead of silently overriding them.
