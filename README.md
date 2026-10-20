# claude-skills-shelf

Free [Agent Skills](https://agentskills.io/specification) that make AI coding agents **prove their work**:
check before claiming "done", measure before fixing, and hand off work without losing context.

Written for Claude Code. Each skill is a plain `SKILL.md`, so it also installs into Cursor, Codex, Gemini CLI,
GitHub Copilot, and the other agents supported by [`npx skills`](https://github.com/vercel-labs/skills).

## Skills

| Skill | Use it when | What it changes |
|---|---|---|
| [`verify-before-done`](skills/verify-before-done/SKILL.md) | The agent is about to say "done", "fixed", or "tests pass" | Turns the request into criteria, runs a command per criterion, and reports verified / failed / not-verified separately |
| [`baseline-first-fix`](skills/baseline-first-fix/SKILL.md) | Starting a bug fix or a performance change | Captures a failing reproduction or a metric first, then re-runs the same command and reports before vs. after |
| [`handoff-prompt`](skills/handoff-prompt/SKILL.md) | Writing a prompt for another session, agent, or subagent | Produces a self-contained, copyable prompt with prohibitions first and a measurable end state |

The skills are short on purpose. They describe a workflow, not a framework, and need no MCP server, API key, or account.

## Install

### Any agent, via skills.sh

```bash
npx skills add takaratomita/claude-skills-shelf
```

Install a single skill:

```bash
npx skills add takaratomita/claude-skills-shelf --skill verify-before-done
```

Preview without installing:

```bash
npx skills add takaratomita/claude-skills-shelf --list
```

### Claude Code plugin marketplace

Inside Claude Code:

```text
/plugin marketplace add takaratomita/claude-skills-shelf
/plugin install proof-first-skills@claude-skills-shelf
```

### Manual copy (Claude Code)

```bash
git clone https://github.com/takaratomita/claude-skills-shelf.git
mkdir -p ~/.claude/skills
cp -R claude-skills-shelf/skills/* ~/.claude/skills/
```

Restart Claude Code after installing. The skills load automatically when their description matches the task;
you can also invoke one by name, for example `/verify-before-done`
(`/proof-first-skills:verify-before-done` when installed as a plugin).

## Repository layout

```text
skills/<name>/SKILL.md           # one directory per skill (Agent Skills format)
.claude-plugin/marketplace.json  # Claude Code plugin marketplace
.cursor-plugin/plugin.json       # Cursor plugin manifest
scripts/check_shelf.py           # structure and hygiene checks
```

Run the checks:

```bash
python3 scripts/check_shelf.py
python3 -m unittest discover -s scripts
claude plugin validate . --strict
```

## Contributing

Issues and pull requests are welcome. Keep each skill focused on one workflow, keep the `name` equal to the
directory name, and run `python3 scripts/check_shelf.py` before opening a PR.

## License

[MIT](LICENSE)
