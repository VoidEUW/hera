# 30. Git is bundled with the desktop app, not assumed

- Status: proposed
- Date: 2026-10-28

## Context

The mind is a real git repository, and `hera_profiles` drives it with the `git` binary rather than
a library binding (`mind.py`). That was a deliberate choice: the binary is what anyone inspecting
`~/.hera/mind` by hand will use, and a binding would be a second implementation of the same history
format. `MindRepository.ensure()` runs at boot, so without git Hera does not start.

On a server or in the Docker image (`apt-get install git`) that is a non-issue. On a desktop it is
the first thing that fails:
- Windows has no `git`.
- A stock Mac has `/usr/bin/git`, which is a stub that opens the Command Line Tools installer.
- Most Linux desktops have git, but an AppImage may not assume it.

The other answer was a pure-Python git (dulwich). It would remove the binary and replace a
recorded decision with a dependency that has to agree with real git about every repository a person
might also touch by hand.

## Decision

**The desktop sidecar carries its own portable git, and `hera_profiles` finds it through
`HERA_GIT`.**

- Windows uses MinGit. macOS and Linux use a relocatable build placed beside the frozen `hera`.
- `HERA_GIT` names the binary, and an unset variable means `git` on `PATH`, as today. Only the
  desktop shell sets it.
- The missing-git error stays what it is (`MindError("git is not installed…")`), and now names
  `HERA_GIT` as well.

## Consequences

- The installers grow by the size of a minimal git, a few tens of MB on Windows and less elsewhere.
- Updating git becomes part of updating the app, and a git security release is an app release.
- The freeze spike ([#239](https://github.com/VoidEUW/hera/issues/239)) checks this on all three systems before the shell is built on top of it.
