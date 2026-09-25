# The plugin contract

It lives in the environment's own repository, because a copy is a second
version by the end of the month:

**https://github.com/emaurel/tanrim/blob/main/docs/CONTRACT.md**

In a checkout you already have, it is `docs/CONTRACT.md` next to
`backend/tanrim/`, and the file it describes is `backend/tanrim/contract.py` —
read that one if the two ever disagree.

This template shipped a vendored copy for exactly one commit, and it had
already drifted by the time anyone read it: the core's version had been
corrected and the copy had not. That is the whole argument.

## What it covers

Every question a plugin answers, what each one takes, and what boot refuses:

| | |
|---|---|
| the machine | `pipelines`, `record_model`, `summary_fields`, `bulk_fields` |
| the world | `rooms`, `agents`, `room_handlers`, importing lazily |
| asking the operator | `gates`, `step_gates` |
| reacting | `hooks` — broadcast, veto, transform, supplier |
| talking to models | `prompt`, `declares_prompts`, `run_agent` |
| showing a record | `record_view` and the block vocabulary |
| the rest | `tools`, `routes`, `overseer`, `persist_room`, `setup`, `check` |
| writing it down | `state.add_record` / `advance_record` / `update_record` |

Plus the words — record, room, workbench, role, worker, castle, gate — which
this template's README uses without defining all of them.
