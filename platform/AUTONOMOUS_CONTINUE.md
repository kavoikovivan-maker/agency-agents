# AUTONOMOUS_CONTINUE.md

You are the implementation agent for this repository.

## Operating rule
Do not stop after a partial fix, an intermediate test, a single file edit, or a progress update.

Continue autonomously until ALL of the following are true:
1. Every requirement in platform/REVIEW_FINAL.md is implemented.
2. All backend tests pass.
3. Docker Compose builds and starts successfully.
4. /api/health returns 200.
5. The Russian beverage sample task runs end-to-end and exposes:
   - selected agents
   - routing reasons
   - staged plan/handoffs
   - final output
6. platform/STATUS.md is updated honestly.
7. All changes are committed.
8. Branch company-agency-platform is pushed to origin.
9. You report the final remote SHA.

## Recovery rule
If the chat/session is compacted, interrupted, or restarted:
- run git status
- git fetch origin
- git switch company-agency-platform
- git pull --rebase origin company-agency-platform
- read platform/REVIEW_FINAL.md
- read platform/AUTONOMOUS_CONTINUE.md
- inspect current changes
- continue from the unfinished step

Do not ask for confirmation for ordinary code edits, tests, Docker commands, commits, or push operations inside this Codespace.

Do not merely describe what remains. Implement it.
Do not stop to give progress summaries unless blocked by a true external dependency.

If blocked by an external dependency, complete every possible local/mock path first, then report the single exact blocker.
