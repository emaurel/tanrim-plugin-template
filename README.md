# Tanrim plugin template

A complete, working [Tanrim](https://github.com/emaurel/agent_environment)
plugin, small enough to read in one sitting. Clone it, rename it, replace the
contents.

It does something trivial — takes a name, has an agent write a greeting, and
asks you before it counts as done — but it exercises every part of the
contract: a pipeline, a room with a bench, an agent with a job, a gate, a
hook, a record schema, prompts and a self-check.

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
cd /path/to/agent_environment
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

> **Rename the kind before you install this next to real work.** A record with
> no explicit `kind` falls back to the first pipeline alphabetically. Installed
> unchanged as `example`, this one wins that race, and every transition in an
> existing ledger is then refused for being off `greeting`'s table.

## Reading it in the right order

1. **`pipelines()`** — the states your work passes through and the legal moves
   between them. This is the spine; everything else hangs off it.

   The table is **law, not documentation**. `advance_record` refuses an
   undeclared edge and logs what WAS allowed from there. In the project this
   came from, a table nothing checked had 23 declared edges against 44
   actually taken and 182 transitions off it entirely.

   A move whose only role is `operator` is a **gate**: the environment raises
   a card and waits rather than dispatching anyone.

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
   streaming, the token accounting, and a per-agent lock. Pass `schema=` if
   your agent has side effects — without it, a retry re-sends the original
   prompt, and an agent told again to "write the files now" writes them again.

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

Declare `requires = ("their_id",)`, which orders you second and lets you win
where you overlap. Then **patch rather than restate**:

- `RoomPatch` adds a bench to a room they own.
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
