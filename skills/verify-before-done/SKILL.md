---
name: verify-before-done
description: Use when you are about to tell the user that an implementation, bug fix, refactor, or config change is "done", "fixed", "working", or "passing". Turns the request into checkable acceptance criteria, executes an actual check per criterion, and reports verified, failed, and not-verified items separately instead of claiming success from reading the code. Pairs with baseline-first-fix, which runs at the start of a fix.
license: MIT
---

# Verify before you claim "done"

A completion claim is only as good as the checks behind it.
This skill makes the claim and the evidence arrive together.

## Workflow

1. **List the acceptance criteria.**
   Derive them from what the user asked for, nothing more.
   Rewrite each vague criterion until a command could decide it.
   "Search works" becomes "a query for `foo` returns the 3 seeded rows".

2. **Run one real check per criterion.**
   Prefer the project's own test command, scoped to what you changed.
   Keep the project's test configuration as it is.
   If no test touches the behavior, drive it for real: call the CLI, hit the endpoint, load the page.
   Reading the diff is not a check.

3. **Classify every criterion.**
   - Verified: the command ran and the output matched.
   - Failed: the output did not match. Fix it before reporting.
   - Not verified: you could not run the check. Name the blocker.

4. **Report in three sections.**
   - What changed (files and the gist).
   - What you ran, with a one-line result for each command.
   - What you did not check, and why.

## Red lines

- Weakening, skipping, or deleting a test to get a green run.
- Saying "tests pass" after running only some of them without saying which.
- Closing with "should work" or "looks fine".
- Dropping a not-verified item from the report.
