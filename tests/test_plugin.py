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


@pytest.fixture
def env():
    """This plugin, booted alone.

    Alone on purpose: a test that boots everything installed asserts against
    whatever else happens to be in `plugins/`, and then fails for a good
    reason the day a second plugin arrives.
    """
    environment.reset()
    environment._invalidate_derived()
    made = environment.boot([PLUGIN])
    yield made
    environment.reset()
    environment._invalidate_derived()


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


def test_a_gate_exists_for_every_gate_that_is_raised(env):
    """A `StepGate` naming a kind no `Gate` defines raises a card that nothing
    knows how to resolve."""
    defined = set(env.gates())
    for step in PLUGIN.step_gates():
        assert step.gate in defined, (
            f"step gate at {step.stage!r} raises {step.gate!r}, which no "
            f"Gate() defines")
