# 15. Running code happens in a container, and here is which claim that makes

- Status: accepted
- Date: 2026-08-28

## Context

Half of Anthropic's published skills shell out to Python. `pptx`, `docx` and `xlsx` are not
reference-heavy skills that happen to ship a script — the script *is* the skill, and
[ADR 14](0014-skill-resources-are-readable.md) makes their reference files readable without making
them work. A skill that says *run `ooxml.py unpack deck.pptx`* against a system with no way to run
anything is a skill that fails strangely rather than honestly.

More generally, she cannot check her own work. Asked for a program she writes one, and neither of
us finds out whether it runs.

[`tooling.md`](../tooling.md) § 3 set the condition this record has to meet, and it is the reason
the sandbox was deferred rather than built:

> `hera_sandbox` is the one with a real question in it: it is the only component in this project
> that would run code somebody else wrote, and "small sandbox for testing" and "safe" are not the
> same claim. […] It should not be built until somebody has written down which of those two it is.

The v0.2 plan originally answered by not building it. That answer is being reversed here, so the
question has to be answered instead.

## Decision

**One new package, `hera-sandbox-mcp`**, offering exactly one tool: `sandbox__run(command,
timeout)`. It is a **separate MCP server with its own namespace**, not four more tools inside
`hera_mcp` — the boundary `tooling.md` § 3 asked to be preserved before it could be got wrong. A
deployment that does not want a sandbox does not mount it, and her prompt then describes no tool
she does not have.

**One tool, because she already has the files.** The container mounts the chat's scratchpad
([ADR 12](0012-a-chat-has-a-scratchpad.md)) at `/work` and works there, so reading and writing are
`hera__scratch_*` and stay available on a machine with no Docker at all. A sandbox server with its
own `read`, `write` and `list` would be three descriptions overlapping three that already exist,
and the model would choose between them at random.

### The claim it makes

**It isolates the host filesystem, the network, and everything in `~/.hera` that is not this
conversation's scratchpad. It is not a defence against a container escape.**

Said the other way round: it is the *"small sandbox for testing"* of § 3, built carefully, and it
is not the other thing. The kernel is shared. A local privilege-escalation bug in the runtime or
the kernel defeats it, and nothing about the configuration below changes that. What it does defeat
is the ordinary failure it exists for — a script from a skill you downloaded reading `~/.ssh`,
posting a file somewhere, filling the disk, or spinning forever.

What would upgrade the claim is gVisor, a virtual machine, or rootless Docker with user
namespaces. Each is a project rather than a flag, and each can land behind the same `Sandbox` port
without any of this changing.

### What that means concretely

Every run gets: `--network none`, a read-only root filesystem, `--tmpfs /tmp` with a size cap,
`--cap-drop ALL`, `--security-opt no-new-privileges`, a non-root user, memory, pid and cpu
ceilings, `--rm`, and a host-side wall-clock timeout that kills the container when it expires. The
only writable path that survives the run is `/work`. The Docker socket is never mounted, and there
is no argument that would let one be.

**The image is pinned configuration**, in `config.toml`. A run that needs a library the image does
not have fails saying which one — with the network off, `pip install` is not a repair the model
can reach for, and that is the correct shape: what is installed is a decision about the deployment
and not one the model gets to make mid-turn.

**The port is in the same package as its Docker adapter**, which is a deliberate divergence from
`hera_mcp`. There, the ports exist because search and memory are decisions about the deployment
and the package must not know them. Here, running a container *is* the package's reason to exist,
and a package with the port and no implementation would be an empty gesture. The port is still
there, because the runtime genuinely is replaceable and a remote runner is the obvious second
implementation.

### Permission, and switching it off

**Every run asks.** `sandbox__run` is not `hera__*`, so `DEFAULT_POLICY`'s `fallback=ASK` already
puts a permission card in front of it, with the command on the card. This is not new machinery and
it is not a special case — it is the default a foreign tool gets, applied to the one tool in this
repository that most deserves it. Someone who wants it to stop asking writes one rule, which is
the same sentence as for anybody else's server, and they will have read the command a few dozen
times first.

**It is absent rather than broken when Docker is not there.** The application probes for a daemon
at startup and mounts nothing if there is none, so a machine without Docker has no sandbox tool in
the catalogue and no sentence about one in the prompt. A daemon that dies later fails as a tool
error naming the reason.

## Consequences

- **`pptx`, `docx` and `xlsx` work**, and the file they produce becomes an artifact through
  `from_scratch` ([ADR 13](0013-artifacts-are-tool-calls-with-versions.md)) without its bytes ever
  passing through the model. That path is the reason artifacts had to land first.
- **Hera now has a hard dependency it can do without.** Docker is required for one tool and for
  nothing else. That is a defensible place to put it and it does move the answer to *what do I
  need to run Hera* — which is worth stating in the README rather than discovering.
- **`hera_tools` mounts more than one in-process server.** `builtin` becomes a sequence. Small,
  and it is the change that keeps the three-servers boundary real instead of aspirational.
- **`sandbox__run` is the first tool where a permission card is the everyday case.** ADR 3's
  argument against a card per emotion does not apply and is not being reopened: a run is rare,
  deliberate, and exactly the thing a person should see once each time.
- **Nothing here is `hera_code_mcp`.** Reading and editing a tree, running a build, reading
  diagnostics — still later, still a separate server, and this record does not smuggle any of it
  in. `sandbox__run` runs a command over one directory and knows nothing about a repository.
- **The honest failure is a timeout, and it will happen.** A model writing a script that waits on
  input hangs until the ceiling, and the turn pays for it. The ceiling is low by default for that
  reason, and raising it is an argument on the call rather than a setting.
