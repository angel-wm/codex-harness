# Verification policy

Configure at least one structured command in `harness/config.json` before an SDD
feature enters implementation. Each command step has this shape:

```json
{
  "name": "unit-tests",
  "argv": ["python", "-m", "unittest", "discover"],
  "windows_argv": ["py", "-3", "-m", "unittest", "discover"],
  "posix_argv": ["python3", "-m", "unittest", "discover"],
  "cwd": ".",
  "env": {},
  "timeout_seconds": 600
}
```

The control plane selects the platform-specific argument list when supplied,
executes without a shell, resolves `cwd` inside the Git root, merges configured
non-secret environment values, runs steps sequentially, and stops at the first
failure or timeout.

Persistent evidence contains step names, selected argument fingerprints, exit
codes, durations, timestamps, and the implementation fingerprint. Full output is
shown in the active turn on failure but is not automatically stored.

Completion evidence is valid only while its implementation fingerprint remains
current. Tests should cover observable results, meaningful failure paths, and
every SDD requirement. Native POSIX execution must not be claimed solely from
unit tests of POSIX command selection.
