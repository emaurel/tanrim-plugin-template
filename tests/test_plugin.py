"""What must be true of this plugin before it is worth running.

Nothing here touches a model, a network or the ledger. It boots the plugin in
isolation and asks the environment what it ended up with — which catches the
whole class of mistakes that otherwise surface on a real dispatch: a job at a
stage no bench works, a transition to a stage that does not exist, a prompt
declared and never written.

    .venv/bin/python -m pytest plugins/<your_plugin>/tests -q

They also run with the environment's own suite: its `pytest.ini` collects
`plugins/*/tests`, so a plugin's tests travel with the plugin and still run by
default. A test that only runs when you remember it rots the first time the
core changes underneath it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Importable whether this is run from the environment's suite (where
# `pytest.ini` already puts `backend` and `plugins` on the path) or on its own.
REPO = Path(__file__).resolve().parents[3]
for extra in (REPO / "backend", REPO / "plugins"):
    if extra.is_dir() and str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from tanrim import discovery, environment                   # noqa: E402

HERE = Path(__file__).resolve().parents[1]

#: Imported exactly as the server imports it, rather than by file path — so a
#: plugin whose `plugin.py` does `from .agents import scout` is tested through
#: the same machinery that will run it.
PLUGIN = discovery.load(HERE)

#: The same module object, so a test can reach the job functions and stub the
#: `run_agent` the plugin imported. `discovery.load` registers it under
#: `tanrim_plugins.<directory>`, which is where the server finds it too.
plugin_module = sys.modules[f"tanrim_plugins.{HERE.name}"]


@pytest.fixture
def env():
    """This plugin, booted alone.

    Alone on purpose: a test that boots everything installed asserts against
    whatever else happens to be in `plugins/`, and then fails for a good
    reason the day a second plugin arrives.

    `boot` invalidates every derived cache itself, as its last step, so this
    needs nothing else. Reaching into the core's privates to do it again is
    the habit this template exists NOT to teach.
    """
    environment.reset()
    made = environment.boot([PLUGIN])
    yield made
    environment.reset()


def test_it_boots(env):
    """Booting is most of the validation.

    `boot` refuses a job at a stage no bench in that room declares, a room
    patch with no target, two plugins claiming one gate or tool name, and a
    misspelt hook. Getting here means none of those are true.
    """
    assert PLUGIN.id in {p.id for p in env.plugins}


def test_every_transition_names_a_stage_that_exists(env):
    """A typo here is a record that can never leave the stage it is on.

    `advance_record` refuses an undeclared edge, so a misspelt target is not a
    crash — it is a record that quietly stops moving, which is worse.
    """
    for pipeline in PLUGIN.pipelines():
        known = {s.id for s in pipeline.stages}
        assert pipeline.entry in known, f"entry {pipeline.entry!r} is not a stage"
        for t in pipeline.transitions:
            assert t.frm in known, f"{t.frm} -> {t.to}: {t.frm!r} is not a stage"
            assert t.to in known, f"{t.frm} -> {t.to}: {t.to!r} is not a stage"


def test_every_job_is_worked_somewhere(env):
    """An agent's job at a stage no bench declares is never dispatched.

    Boot refuses this, so the test is really a statement of what the refusal
    means: benches are the routing table, and declaring a stage on one is what
    makes that stage reachable.
    """
    for spec in PLUGIN.agents():
        stages = getattr(spec, "jobs", {}) or {}
        for stage in stages:
            assert stage in env.stages_for_role(
                getattr(spec, "role", None) or spec.extends), (
                f"{spec} has a job at {stage!r} that no bench in its room works")


def test_each_stage_a_bench_works_is_a_real_stage(env):
    """The other direction: a bench listing a stage nobody ever reaches."""
    known = {s for p in PLUGIN.pipelines() for s in (x.id for x in p.stages)}
    for room in env.rooms():
        for bench in room.workbenches:
            for stage in bench.stages:
                assert stage in known, (
                    f"{room.id}/{bench.id} works {stage!r}, which is not a "
                    f"stage in any pipeline this plugin declares")


def test_every_declared_prompt_is_on_disk():
    """A missing prompt does not fail an agent — it improvises.

    This is the one failure a fresh checkout actually hits, and it surfaces
    mid-run rather than at boot unless something asks.
    """
    assert PLUGIN.check() == []


def test_a_gated_stage_is_declared_on_a_bench(env):
    """A step gate at a stage no bench works is never raised.

    The orchestrator asks `role_for_stage` BEFORE it asks whether the move is
    the operator's, and that answers from bench declarations alone. With no
    bench naming the stage it answers None, the loop moves on, and the record
    sits there for ever with no error anywhere — which is exactly what this
    template shipped until a review caught it.
    """
    worked = {s for r in env.rooms() for b in r.workbenches for s in b.stages}
    for step in PLUGIN.step_gates():
        assert step.stage in worked, (
            f"step gate at {step.stage!r} is on no bench, so "
            f"role_for_stage({step.stage!r}) is None and the card never "
            f"appears")


def test_a_gate_exists_for_every_gate_that_is_raised(env):
    """A `StepGate` naming a kind no `Gate` defines raises a card that nothing
    knows how to resolve."""
    defined = set(env.gates().keys())
    for step in PLUGIN.step_gates():
        assert step.gate in defined, (
            f"step gate at {step.stage!r} raises {step.gate!r}, which no "
            f"Gate() defines")


def test_the_job_runs_and_moves_the_record(env, tmp_path, monkeypatch):
    """The agent's job, actually CALLED, with the model stubbed out.

    Every other test here reads what the plugin DECLARES. This one runs it —
    and it is the cheapest test in the file, because the job is four lines of
    plumbing around one model call.

    It is here because the template shipped for a while calling
    `state.get_lead` and `state.advance_lead`, neither of which exists. The
    plugin booted perfectly, the whole suite was green, and it died with an
    `AttributeError` the first time anyone pressed Run. Nothing that only
    reads a manifest can catch that.
    """
    import asyncio

    from tanrim import agent_helpers, state

    # A ledger of its own. Without this the test writes into the real
    # `state/leads.json`, which is somebody's actual work.
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    monkeypatch.setattr(state, "RECORDS_FILE", tmp_path / "leads.json")
    monkeypatch.setattr(state, "EVENTS_FILE", tmp_path / "events.json")

    async def no_model(*a, **k):
        """What `run_agent` would have returned, without spending anything."""
        return agent_helpers.RunResult(
            data={"greeting": "Good morning, Ada.", "why": "she is up early"})

    monkeypatch.setattr(plugin_module, "run_agent", no_model, raising=False)
    monkeypatch.setattr(agent_helpers, "run_agent", no_model)

    record = state.add_record("Ada", kind="greeting", recipient="Ada")
    out = asyncio.run(plugin_module.write_greeting(None,
                                                  {"record_id": record["id"]}))

    assert out["ok"] is True, out
    moved = state.get_record(record["id"])
    assert moved["stage"] == "written"
    assert moved["greeting"] == "Good morning, Ada."
