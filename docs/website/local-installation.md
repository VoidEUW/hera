# Local Installation

Three ways to run Hera on your own machine:

- **Docker Installation** — one container, built from the repository. Easiest to keep updated.
- **Source Installation** — run the Python application and the web interface directly, with
  `uv` and Node. For development or for machines where Docker isn't an option.
- **App Install** — a packaged desktop app. Not available yet.

All three store data in the same place, `~/.hera` (see **Configuration**), and none of them
needs an account or a cloud service. Hera always talks to a model endpoint you run yourself,
never a hosted one.
