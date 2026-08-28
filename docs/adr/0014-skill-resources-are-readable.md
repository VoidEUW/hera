# 14. Skill resources are readable

- Status: accepted
- Date: 2026-08-28

## Context

`hera_skillsets.render` tells the model a lie. Every selected skill that has files beside it
arrives carrying the sentence:

> This skill has further files beside it in `<path>`. Read one if this skill tells you to.

She has no tool that can read a file. The sentence has been in the prompt since v0.1 and there has
never been a way to act on it.

This is the actual reason Anthropic's reference-heavy skills do not work here. `brand-guidelines`,
`canvas-design`, `dataviz`, `frontend-design` and `web-artifacts-builder` are all the same shape:
a short `SKILL.md` that says *read `references/palette.md` before choosing colours*, and a
directory of material beside it. Selected, they arrive as an instruction to consult something
unreachable — which is worse than not having the skill, because a model told to read a file it
cannot read either invents its contents or stalls.

A general file-reading tool would fix it and is the wrong fix. Reading arbitrary paths is a
different capability with a different permission story, and it belongs to `hera_code_mcp`
whenever that exists. What is needed here is narrow: a skill can read *its own* directory.

## Decision

**One tool, `hera__read_resource(skill, path)`**, behind an optional `ResourceReader` port in
`hera_mcp`, resolving against `~/.hera/skills/<skill>/` and nothing else.

**The traversal guard is the feature.** `..` in any segment, an absolute path, and a resolved path
that escapes the skill's directory are each refused with a message written for the model. A
symlink pointing outside is refused by the same check, because the comparison is made after
resolution rather than on the string. This gets a test of its own — a comment saying the path is
validated is not a validation.

**A binary file is refused with its name and size** rather than decoded badly. The mojibake
problem from the attachment work, in a new coat: a tool that returns replacement characters for a
PNG has told the model something false about the file.

**The sentence in the prompt becomes true**, which is the whole point, and `hera_skillsets` does
not change to make it so — it already reports the path, and the tool resolves against the skills
directory it was given.

## Consequences

- **The reference-heavy half of Anthropic's published skills works**, unmodified, dropped into
  `~/.hera/skills/`. That is a real capability arriving for one small tool.
- **The script-running half still does not**, and it is a separate decision with its own record —
  [ADR 15](0015-running-code-in-a-container.md). This record deliberately does not claim
  otherwise: reading a reference and executing a program somebody else wrote are not the same act,
  and bundling them would have made the safe one wait for the dangerous one.
- **It stays allowed by default.** It reads inside a directory whose contents a person put there,
  and the trust marks in `~/.hera/trusted.json` are the existing answer to *whose skill is this*.
- **It is not a file reader and must not become one.** The `skill` argument is not a path prefix
  the model may vary; there is no `hera__read_file`, and the day one is wanted it belongs to a
  different server with a different default permission.
