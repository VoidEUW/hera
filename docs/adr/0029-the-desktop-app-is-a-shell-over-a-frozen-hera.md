# 29. The desktop app is a Tauri shell over a frozen `hera`

- Status: proposed
- Date: 2026-10-28

## Context

#24 asks for a desktop app: an AppImage, a macOS app and a Windows `.exe`. It has to work two
ways. One is a local Hera for one person on one machine. The other is a window onto a Hera running
somewhere else.

Hera is a Python server with a SvelteKit interface it serves itself, same-origin, from
`hera_core/static` ([ADR 6](0006-spa-over-json-sse-api.md)). Its runtime needs Python 3.12, SQLite,
and the `git` binary (see [ADR 30](0030-git-is-bundled-not-assumed.md)). Node is needed only to
build the interface. CI builds a Docker image and nothing else.

The candidates were:
- **Electron.** Identical Chromium everywhere and the most mature passkey story, at 150 MB or more
  per install.
- **pywebview with PyInstaller.** Python only, but with no updater, signing or deep-link story.
- **Tauri.** A Rust shell over the system webview. Small, with an updater, deep links and signing
  built in.

## Decision

**`apps/desktop/` is a Tauri v2 shell. In local mode it runs Hera as a PyInstaller-built sidecar;
in client mode it loads the host's own address.**

- **The sidecar is `hera serve`, frozen**, with the built interface inside it, built natively on
  each operating system. `hera serve --port 0 --announce` binds a free loopback port and prints it
  for the shell to read.
- **Local mode shares `~/.hera` with a CLI install.** `~/.hera/server.lock` records a running
  server's pid and port, and the shell attaches to it rather than starting a second process on the
  same SQLite file and git repository.
- **Local mode signs itself in.** The shell mints a one-time `launch` token through the sidecar's
  stdin and opens `/auth/launch?token=…`. The window gets a session and the first launch runs the
  setup wizard without a setup code ([ADR 27](0027-an-account-is-a-session-and-a-role.md)). A
  local install never shows a password screen it does not need.
- **Client mode loads the host's origin.** The interface is the server's own, same-origin as
  ADR 6 requires. There is no bundled copy, no CORS and no API change, and the sign-in screen is the
  server's.
- **A passkey from inside the app goes through the system browser.** WKWebView and WebKitGTK do not
  offer WebAuthn for an arbitrary self-hosted domain. The app opens the browser, and the browser
  returns through `hera://` with a one-time token. A password works everywhere.
- **The release matrix is native:**
  - `ubuntu-22.04` builds the AppImage and `.deb`.
  - `macos-14` builds a universal `.dmg`.
  - `windows-latest` builds an NSIS `.exe`.

  The builds run on an app tag and are attached to the GitHub release, together with the updater's
  manifest.
- **Unsigned first.** The signing steps run only when their secrets exist. The updater key, which
  is free, is set up from the first build.

## Consequences

- `apps/desktop/` is Rust and not a uv member, so the layering guard and `test_workspace.py` do not
  see it. It gets its own CI job.
- System webviews differ: WebKit on macOS and Linux, Chromium-based WebView2 on Windows. The e2e
  suite's WebKit project, already in use for the phone, is the nearest check.
- Freezing is the largest unknown in v0.3.0, so it is a spike ([#239](https://github.com/VoidEUW/hera/issues/239)) before anything else depends on
  it.
- Unsigned builds need a right-click → Open on macOS and pass a SmartScreen warning on Windows.
  Both are in the install notes until certificates exist.
