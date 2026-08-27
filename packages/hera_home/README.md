# hera-home

One question, one answer: **where is `~/.hera`?**

```python
from hera_home import home, mind_dir, skills_dir

home()        # $HERA_HOME, or ~/.hera
mind_dir()    # $HERA_HOME/mind
skills_dir()  # $HERA_HOME/skills
```

This exists because four packages need the same answer and two of them may not import each
other. It was `hera_tools.settings.hera_home()` while `hera_tools` was the only caller; the
moment `hera_profiles` needed the mind directory, a copy would have been two places that can
disagree about an environment variable name — the kind of drift that produces an empty mind
repository and no error message.

It has no dependencies and holds no state. Every function reads the environment on each call,
so a test that sets `HERA_HOME` with `monkeypatch.setenv` takes effect immediately and nothing
has to be reset.

Nothing here creates a directory. Asking where something is and deciding to make it are
different decisions, and the second one belongs to whoever owns the contents.
