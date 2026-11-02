---
description: Create a spec file for the next Spendly feature
argument-hint: "Step number and feature name e.g. 2 registration"
allowed-tools: Read, Write, Glob
---

You are a senior developer planning a new feature for the Spendly expense tracker. Always follow the rules in CLAUDE.md.

User input: $ARGUMENTS

## Step 1 — Parse the arguments
From $ARGUMENTS extract:

1. `step_number` — zero-padded to 2 digits: 2 → 02, 11 → 11

2. `feature_title` — human readable title in Title Case
   - Example: "Registration" or "Login and Logout"

3. `feature_slug` — file safe slug
   - Lowercase, kebab-case
   - Only a-z, 0-9 and -
   - Max 40 characters
   - Example: "registration", "login-and-logout"

If the step number or feature name is missing, stop and say:
"Usage: /create-spec <step_number> <feature name>
Example: /create-spec 2 registration"

## Step 2 — Check existing specs
Use Glob to list files in `.claude/specs/`.

- If a spec with the same step number already exists, stop and say:
  "Spec for step <step_number> already exists: <filename>. Choose a different step number."
- Read the previous specs to understand what has already been built, so this spec builds on them and does not repeat work.

## Step 3 — Understand the current codebase
Read these files before writing anything:
- `CLAUDE.md` — project rules and conventions
- `app.py` — existing routes
- `database/db.py` — database schema and helpers
- Any templates in `templates/` that are relevant to this feature

Do not guess. Base the spec on what actually exists in the code.

## Step 4 — Write the spec
Create the file `.claude/specs/<step_number>-<feature_slug>.md` using exactly this structure:

```
# Spec: <feature_title>

## Overview
One short paragraph: what this feature does and why the user needs it.

## Depends on
Which previous steps/specs must be completed before this one.

## Routes
Every new or changed route:
- `METHOD /path` — what it does — login required? (yes/no)

## Database changes
New tables, columns or helper functions in database/db.py.
Write "None" if no changes are needed.

## Templates
- Create: list of new templates
- Modify: list of existing templates and what changes

## Files to change
List every existing file that will be modified.

## Files to create
List every new file.

## New dependencies
Any new pip packages. Write "None" if none are needed.

## Rules for implementation
- Follow all rules in CLAUDE.md
- Use parameterized SQL queries only
- Hash passwords with werkzeug (if passwords are involved)
- Keep business logic out of templates
- Reuse existing styles from static/ — no new CSS frameworks

## Definition of done
A checklist of specific, testable behaviours:
- [ ] ...
- [ ] ...
```

Keep the spec focused on this one feature. Do not include features planned for later steps.

## Step 5 — Confirm
After saving, tell the user:
- The path of the spec file created
- A 2–3 line summary of the feature
- "Review the spec, then ask Claude to implement it."

## Rules
- Only create the spec file. Do not write or change any application code.
- Do not modify any existing spec files.