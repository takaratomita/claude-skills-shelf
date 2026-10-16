---
name: handoff-prompt
description: Use for handoffs - when the user wants a prompt for another session or agent, a task brief for a subagent, or when the context window is running out and work has to continue in a fresh session. Writes a self-contained prompt that someone who has never seen the project can run without causing damage, and returns it in the chat as a single block the user can copy.
license: MIT
---

# Write a prompt a stranger can run safely

The reader of a handoff prompt has none of your context.
Anything you leave implicit, they will guess.

## Delivery

- Put the prompt in the chat as a single copyable block. Write a file only if the user asks for one.
- Mark the start and the end of the block on their own lines, outside the block.
- If the prompt contains code fences, use a longer fence on the outside than on the inside.
- Never send a truncated block. Shorten it, or split it into numbered parts with their own markers.

## Contents, in this order

1. **What must not happen.** Files to leave alone, commands not to run, parallel work to avoid,
   and no commits or pushes unless the user asks. It goes first so a skimming reader still stays safe.
2. **Goal.** One to three lines.
3. **Current state.** Absolute paths, `file:line` references, and numbers.
   Pair every number with the command that measured it, so the reader can measure again.
4. **Decision rights.** What the reader may decide alone, and what goes back to the user.
5. **Done means.** A measurable end state, not "tests pass".
6. **Known pitfalls.** Mistakes already made, so they are not repeated.
7. **Pace.** Ask the reader to finish in one go instead of pausing for confirmation.

## Check before sending

- No references like "the above" or "as discussed".
- Every path is absolute.
- The block is closed and the markers are outside it.
