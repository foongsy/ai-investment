# Data Directory

Use this directory only for sanitized examples, schemas, derived summaries, or pointers to approved external data sources.

## File Naming Convention

Use lowercase, kebab-case filenames with a type prefix to distinguish file intent:

- `schema-...` for schema proposals and data model specs
- `prompt-...` for reusable system/user prompt assets
- `template-...` for reusable fill-in templates
- `snapshot-...` for point-in-time derived summaries/exports
- `ref-...` for reference notes and source pointers

Recommended pattern:

- `type-topic-purpose.md`

Guidelines:

- Keep prefixes lowercase (do not use uppercase prefixes)
- Use concise, descriptive names
- Prefer `.md` for text documentation and prompt assets
- Do not include version numbers in filenames; use git history to track revisions

## Prompt Asset Convention

Use a consistent section order for reusable prompt files:

1. `# Prompt: <name>`
2. `## Purpose`
3. `## Inputs`
4. `## Task`
5. `## Analysis Requirements`
6. `## Constraints`
7. `## Output Format`
8. `## Quality Bar`
9. `## Missing Context Handling`
10. `## Examples` when useful

Keep prompt files focused on instructions. If an output contract is large or machine-validated, store it in a separate `schema-...json` file and reference it from the prompt.

Do not store:

- Credentials, API keys, access tokens, or seed phrases
- Account numbers, SSNs, tax identifiers, or personal identity documents
- Full brokerage, bank, credit card, or retirement account statements
- Raw CSV, PDF, Excel, or database exports from financial institutions
- Tax forms or tax preparation files

If a workflow needs sensitive source data, keep it outside this workspace and explicitly approve the specific file or service access for that task.