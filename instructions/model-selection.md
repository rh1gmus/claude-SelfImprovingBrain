# Model selection (INSTRUCTION SET: tunable)
Sessions start on `sonnet` at `medium`. [I-001]
Use the cheapest tier that does the work well. [I-002]
Change tiers on a pattern (2+ entries in `observations.local.md`), not one run. [I-003]

| Tier | Model | Work |
|---|---|---|
| T0 | `haiku` | grep/read-and-summarize, log triage, renames, formatting, boilerplate, commit-message drafts [I-004] |
| T1 | `sonnet` (default) | features, bug fixes with a repro, scripts, tests, small refactors, docs [I-005] |
| T2 | `opus` | architecture, many-file or cross-system changes, ambiguous debugging, security/identity/prod changes, rule proposals [I-006] |

- Delegate T2 analysis to `brain-architect`, T0 lookups to `brain-scout`, isolated T1 work to `brain-builder`, and risky multi-file work to `brain-reviewer`. [I-007]
  Below about 3 tool calls, do it inline. [I-008]
- You can't switch the session model. If most remaining work is T2, say once: "Suggest `/model opus`: <reason>". [I-009]
- Escalate a tier after two failures on the same step, on identity/auth/prod/security/deletion work, or when scope grows. [I-010]
  Drop back to T1 once the plan is settled. [I-011]
