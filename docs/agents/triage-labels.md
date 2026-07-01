# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Role                  | Label in tracker | Meaning                                  |
| --------------------- | ---------------- | ---------------------------------------- |
| `needs-triage`        | `needs-triage`   | Maintainer needs to evaluate this issue  |
| `needs-info`          | `needs-info`     | Waiting on reporter for more information |
| `ready-for-agent`     | `ready-for-agent`| Fully specified, ready for an AFK agent  |
| `ready-for-human`     | `ready-for-human`| Requires human implementation            |
| `wontfix`             | `wontfix`        | Will not be actioned                     |

When a skill mentions a role, apply the label via `tools.gogs.replace_labels_on_issue()` (pass label IDs) or `tools.gogs.add_labels_to_issue()`.

Label IDs are fetched from `tools.gogs.list_labels()`.
