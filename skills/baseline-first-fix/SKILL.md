---
name: baseline-first-fix
description: Use at the start of any bug fix, performance or cost improvement, or other change meant to alter existing behavior. Captures a baseline before any edit (a reproduction that fails today, or a metric value), re-runs the identical command after the change, and reports a before/after comparison with a regression check instead of "it should be fixed now". Use verify-before-done at the end, when reporting completion.
license: MIT
---

# Baseline first, then the same measurement again

A fix nobody measured before is a fix nobody can prove.
This skill pins down "before" so that "after" means something.

## Workflow

1. **Capture the baseline before editing anything.**
   - Bug: write a reproduction (a test, or a command if a test is impractical).
     Run it and see it fail now. A reproduction that already passes proves nothing.
   - Improvement: choose one metric and the command that measures it.
     Record the value. Take several samples when the number is noisy.
   - Write down the command, the inputs, and the environment you used.

2. **Change one thing.**
   One cause per change keeps the comparison readable.

3. **Measure again with the identical command and inputs.**
   Confirm two things: the reproduction now passes, and the surrounding tests did not regress.

4. **Report before and after side by side.**
   Show the command, the baseline result, the new result, and the regression run.

## Iterating

Repeat steps 2 and 3 until the target is met or the stop condition is hit.
Set that stop condition before the first attempt, such as a maximum number of tries or a target value.

## Red lines

- Claiming an improvement with no baseline.
- Measuring "after" on easier conditions than "before".
- Calling a bug fixed when it was never reproduced. Say that it was not reproduced.
