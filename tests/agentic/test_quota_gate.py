"""The quota hold never starts inference or completes an accepted intent early."""

import asyncio

from the_framework.agent import Agent
from the_framework.agent.models.events import Event
from the_framework.agent.runtime.bridge import ApplicationError
from the_framework.agent.runtime.protocol import PromptRequest
from the_framework.agent.runtime.worker import Worker
from the_harness.quota_gate import wait_for_quota


def test_gate_waits_keeps_identity_and_rechecks_owner_admission():
    async def run():
        agent = Agent(client=object())
        worker = Worker(agent, None, None, command_middleware=(wait_for_quota,))
        command = PromptRequest(id="held", prompt="keep this", admission="owner")
        blocked = asyncio.Event()
        release = False
        stale = False
        calls, ran = [], []

        async def bridge(request):
            calls.append(request.capability)
            if request.capability == "quota":
                blocked.set()
                return {"allowed": release}
            return {"allowed": not stale}

        async def stream(prompt, **options):
            ran.append(prompt)
            yield Event.from_dict({"type": "agent.step.start"})

        agent.bridge.bind(bridge)
        agent.astream = stream
        await worker.commands.enqueue(command)
        task = asyncio.create_task(worker.commands.run_command(command))
        await asyncio.wait_for(blocked.wait(), 2)
        assert command.status == "waiting"
        assert agent.session.command_status(command.id) == "waiting"
        assert not ran and not command.future.done()
        assert not worker.can_steer(PromptRequest(id="human", prompt="new"))
        # Goal was suspended while waiting: do NOT execute its stale continuation.
        stale, release = True, True
        await asyncio.wait_for(task, 3)
        assert not ran
        assert calls[-1] == "owner"
        assert command.status == "completed"
    asyncio.run(run())


def test_interrupt_held_command_never_runs_model():
    async def run():
        agent = Agent(client=object())
        command = PromptRequest(id="stop", prompt="keep")
        checked = asyncio.Event()
        ran = []

        async def bridge(request):
            checked.set()
            return {"allowed": False}

        async def execute(command):
            ran.append(command.id)
            if False:
                yield

        agent.bridge.bind(bridge)
        async def collect():
            return [event async for event in wait_for_quota(agent, command, execute)]
        task = asyncio.create_task(collect())
        await asyncio.wait_for(checked.wait(), 2)
        command.status = "interrupted"
        await asyncio.wait_for(task, 3)
        assert not ran and command.status == "interrupted"
    asyncio.run(run())


def test_initial_bridge_outage_does_not_prevent_local_repair():
    async def run():
        agent = Agent(client=object())
        ran = []
        async def offline(request):
            raise ApplicationError("offline")
        async def execute(command):
            ran.append(command.prompt)
            if False:
                yield
        agent.bridge.bind(offline)
        command = PromptRequest(id="repair", prompt="repair")
        assert [event async for event in wait_for_quota(agent, command, execute)] == []
        assert ran == ["repair"]
    asyncio.run(run())


def test_held_prompt_survives_worker_restart(tmp_path):
    from the_framework.agent.context.session import Session
    from the_framework.agent.runtime.protocol import CommandCompleted, ShutdownRequest

    async def run():
        path = tmp_path / "session.json"
        session = Session.open(path)
        command = PromptRequest(id="held-restart", prompt="preserve intention", admission="owner")
        first = Agent(client=object(), session=session)
        entered = asyncio.Event()
        async def blocked(request):
            entered.set()
            return {"allowed": False}
        first.bridge.bind(blocked)
        async def unused(command):
            raise AssertionError("model must not run before restart")
            yield
        async def hold():
            return [event async for event in wait_for_quota(first, command, unused)]
        task = asyncio.create_task(hold())
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        recovered = Session.open(path)
        assert recovered.commands[command.id].deferred["prompt"] == command.prompt
        second = Agent(client=object(), session=recovered)
        incoming, ran, admissions = asyncio.Queue(), [], []
        worker = None
        async def send(output):
            if isinstance(output, CommandCompleted):
                await incoming.put(ShutdownRequest(id="done"))
        worker = Worker(second, incoming.get, send, command_middleware=(wait_for_quota,))
        async def allowed(request):
            admissions.append(request.capability)
            return {"allowed": True}
        second.bridge.bind(allowed)
        async def stream(prompt, **options):
            ran.append(prompt)
            yield Event.from_dict({"type": "agent.step.start"})
        second.astream = stream
        await asyncio.wait_for(worker.run(), 5)
        assert ran == ["preserve intention"]
        assert admissions == ["quota", "owner"]
        final = Session.open(path).commands[command.id]
        assert final.status == "completed" and final.deferred is None
    asyncio.run(run())
