# Tanrim plugin template

A complete, working [Tanrim](https://github.com/emaurel/tanrim)
plugin, small enough to read in one sitting. Clone it, rename it, replace the
contents.

It does something trivial — takes a name, has an agent write a greeting, and
asks you before it counts as done — but it exercises the spine of the
contract: a pipeline, a room with two benches, an agent with a job, a gate, a
step gate, two kinds of hook, a record schema, prompts and a self-check.

It does not show `tools()`, `routes()`, `room_handlers()`, `record_view()` or
the patch types; [docs/CONTRACT.md](docs/CONTRACT.md) covers all of them.

```
plugin.py            the manifest — the only required file
rooms/hall.yaml      a room, as YAML
prompts/greeter/     the agent's instructions
tests/test_plugin.py what must be true before it is worth running
docs/CONTRACT.md     the full reference for every question a plugin answers
```

## What a plugin is

Tanrim is a world, a worker pool, a durable ledger, a state machine, an
approval mechanism, an agent runner and an HTTP surface. It knows nothing
about what the work IS. An install with no plugins has no stages, no rooms and
nothing to do — which is the correct empty state, not an error.

A plugin supplies the rest: what a unit of work is, what states it passes
through, which rooms work it, who staffs them, what the operator is asked, and
what any of it means.

**The environment never reads your files.** It asks questions and you answer
them. It never imports your modules on its own and never assumes a layout, so
a plugin can keep its rooms in YAML, in Python, or in a database, and all
three work identically. `yaml_rooms()` and `file_prompts()` are conveniences
your plugin *calls*; they are not the mechanism.

The smallest legal plugin is an id and a name. Every question has a default
that contributes nothing, so you implement only what you have.

## Getting it running

```bash
cd /path/to/tanrim
git clone git@github.com:<you>/tanrim-plugin-template.git plugins/hello
```

Then edit `plugins/hello/plugin.py`:

```python
class ExamplePlugin(Plugin):
    id = "hello"                 # must match the directory name's purpose,
    name = "Hello"               # and be unique across what is installed
```

Restart the server, or reload without one:

```bash
curl -X POST http://127.0.0.1:8765/plugins/reload
```

Reload covers a plugin **appearing or disappearing**. It does not cover a
plugin whose code changed — Python caches modules — so restart while you are
editing.

Boot prints what it found:

```
[boot] 3 plugin(s): hello, web_agency, website_recreation
[boot] built Hello 1 (hello) at ring 1 slot 2
```

A plugin that serves routes prints them on a line of its own; this one serves
none.

A castle for your plugin appears on the map, with The Hall in it.

> **Rename the STAGES too, not just the id.** A record with no explicit `kind`
> is resolved by the STAGE it is sitting at — so a generic stage id makes two
> pipelines fight over the same kind-less records. `written` is already a stage
> in `job_hunt`. (Only when no pipeline owns the stage does it fall back to the
> first-declared kind, which is alphabetical directory order; that fallback is
> the last resort now, and it used to be the only one.)

## Making the first record

A castle on the map with nothing in it does nothing, and the environment has
no generic "create a record" route — what a unit of work IS belongs to your
plugin, so opening one does too. Every real plugin creates its own, either
from a `routes()` endpoint or from a sourcing agent.

The fastest way to see the thing run, with the server stopped:

```bash
cd /path/to/tanrim
PYTHONPATH=backend .venv/bin/python -c "
from tanrim import discovery, state
discovery.boot()
r = state.add_record('Ada', kind='greeting', recipient='Ada')
print(r['id'], r['stage'])
"
```

`add_record` starts it at the pipeline's `entry` stage. Start the server and
the stage sweep dispatches The Hall to it on the next tick; the sprite walks
to the Writing Desk, and when it is done the record is at `written` with a
card waiting for you.

For anything beyond a first look, give your plugin a `routes()` returning an
`APIRouter`, so the app has something to call:

```python
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter()

class NewGreeting(BaseModel):
    # Refuse a body you do not understand, rather than silently ignoring a
    # field somebody meant. A typo in a caller should 422, not no-op.
    model_config = ConfigDict(extra="forbid")
    recipient: str

@router.post("/greetings")
async def open_one(body: NewGreeting):
    from tanrim import state
    return state.add_record(body.recipient, kind="greeting",
                            recipient=body.recipient)
```

## Saving what a job produced

One function, and it is the only way a stage may change:

```python
from tanrim import state

state.get_record(record_id)                  # read
state.update_record(record_id, **fields)     # patch, no stage change
state.advance_record(record_id, "written",   # move AND patch, one write
                     agent="greeter", note="…", **fields)
```

`advance_record` appends to the record's history in the same write, including
which fields the step actually changed, and **refuses an edge your pipeline
does not declare** — logging what WAS allowed from there. It returns `None`
on a refusal rather than raising, so a job that ignores the return value
reports success having moved nothing.

## Reading it in the right order

1. **`pipelines()`** — the states your work passes through and the legal moves
   between them. This is the spine; everything else hangs off it.

   The table is **law, not documentation**. `advance_record` refuses an
   undeclared edge and logs what WAS allowed from there. In the project this
   came from, a table nothing checked had 23 declared edges against 44
   actually taken and 182 transitions off it entirely.

   A move whose only role is `operator` is a **gate** — but three things must
   line up or nothing happens and nothing complains:

   1. a **bench** in some room declares the stage, because the orchestrator
      asks `role_for_stage` before it asks anything else, and with no bench it
      answers `None` and the loop moves on;
   2. every role allowed out of that stage is `operator`;
   3. some plugin declares a `StepGate` for that `(stage, pipeline)`.

   Miss the first and the record sits there for ever. That is why `hall.yaml`
   gives `written` its own Outbox bench even though no agent works there —
   this template shipped without it, and its one gate could never fire.

2. **`rooms()`** — places on the map. A room declares **workbenches**, and a
   bench declares the stages worked at it. That is the routing table: nothing
   else registers a stage as reachable, and a record arriving at a room whose
   benches do not declare its stage is refused.

   Geometry is computed if you leave `position`/`size` off a bench, so you
   never do the tile arithmetic.

3. **`agents()`** — who staffs a room. `jobs` is keyed by **stage**, which is
   what lets another plugin later give your role a job at a stage it invents.

   A room's agent is a **role**, not one worker. `max_workers` in the manifest
   is how many can be hired; the role owns memory and context, the worker owns
   the lock, the sprite and the log line.

4. **The job function** — `async def (world, task) -> dict`. A task dict
   rather than fixed arguments, because not every job is about a record at a
   stage. Read what you need and ignore the rest.

   `run_agent()` owns the turn: the sprite's busy state, the MCP servers, the
   streaming, the token accounting, and a per-agent lock.

   Pass `schema=` so the one retry knows what shape to produce. If the final
   message is not the JSON you asked for, `run_agent` retries once with the
   bad output quoted back — **text-only and single-turn** (`allowed_tools:
   []`), built from the transcript, never from your original prompt. Re-sending
   the prompt is the bug that got fixed: an agent with file tools still
   attached, told again to "write the files now", rebuilt an entire site and
   overwrote work that had already been verified.

5. **`gates()` and `step_gates()`** — what you are asked before something
   irreversible. A `StepGate` is keyed by stage rather than by edge, because
   the operator is asked *before* the room runs, when which edge it will take
   is not yet known.

   `validate` runs **before** the card is resolved, so refusing costs nothing.
   Refusing after it is resolved consumes the card and leaves the work undone.

6. **`hooks()`** — four kinds, because they compose differently:

   | kind | behaviour | example |
   |---|---|---|
   | BROADCAST | every listener is called | `tick`, `startup`, `stage_changed` |
   | VETO | first refusal wins | `before_stage_change` |
   | TRANSFORM | chained, each output feeding the next | normalising a written field |
   | SUPPLIER | the last plugin to answer | |

   Veto and transform run inside a durable write, so an `async def` listener
   is refused at boot.

## Extending someone else's plugin

Declare `requires = ("their_id",)`. That guarantees you load **after** them —
not necessarily second — so their rooms exist for you to patch.

"Later wins" is only half true, and the half that does not is the useful one:
two plugins declaring the same `Gate.kind` or the same `Tool.name` make boot
**refuse**, by name. Later genuinely does win for step gates, hooks, and — in
silence — whole `Room` and `AgentSpec` ids. That silence is the trap:
**patch rather than restate**.

- `RoomPatch` adds a bench to a room they own. A bench with a new id is added;
  one with an existing id has its `stages` and `tasks` unioned. At the room
  level `tools`, `skills` and `mcp_servers` are **unioned** too — only `name`,
  `purpose`, `color`, `position`, `size` and `max_workers` override.
- `AgentPatch` gives an existing role a job at a stage you invented.

Both exist because the obvious alternative — returning a whole `Room` or
`AgentSpec` with the same id — boots perfectly cleanly and **silently drops
everything the original had**.

Their code is importable under the synthetic package plugins are loaded into:

```python
from tanrim_plugins.web_agency import jobs as agency_jobs
```

`prompts.kind_loader` searches the plugins that declare a kind first, so your
`probe/PORT_ROLE` is found for your records and never seen by theirs — with
neither plugin knowing the other exists.

## Testing

```bash
.venv/bin/python -m pytest plugins/hello/tests -q
```

The environment's `pytest.ini` collects `plugins/*/tests`, so a plugin's tests
travel with the plugin and still run by default. A test that only runs when
you remember it rots the first time the core changes underneath it.

`tests/test_plugin.py` boots the plugin **alone** — a test that boots
everything installed asserts against whatever else happens to be in
`plugins/`, and then fails for a good reason the day a second one arrives.

Two habits worth copying:

- **Watch each test fail before you keep it.** A test you have not seen fail
  is a test you do not know the meaning of.
- **Assert provenance, not a fixed list.** A test asserting the environment's
  gates *equal* your exact set fails the moment a second plugin is installed
  — for doing the thing the test exists to encourage.

## Full reference

**[docs/CONTRACT.md](docs/CONTRACT.md)** — every question a plugin can answer,
what each one takes, and what boot refuses.

Real plugins worth reading, if you have access:
[web_agency](https://github.com/emaurel/tanrim-web-agency) (a full pipeline),
[website_recreation](https://github.com/emaurel/tanrim-website-recreation)
(an extension that declares no rooms and no agents of its own), and
[job_hunt](https://github.com/emaurel/tanrim-job-hunt) (a second, unrelated
kind of work on the same machinery).
