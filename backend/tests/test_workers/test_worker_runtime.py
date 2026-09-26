import asyncio

import pytest

from app.workers import tasks


@pytest.fixture(autouse=True)
def reset_worker_runtime():
    """Dispose the cached loop/engine after every test so tests don't leak state into each other."""
    yield
    tasks._reset_runtime_for_tests()


def test_session_factory_is_cached_per_process():
    tasks._reset_runtime_for_tests()
    assert tasks._get_session_factory() is tasks._get_session_factory()


def test_run_async_reuses_one_loop():
    tasks._reset_runtime_for_tests()

    async def loop_id():
        return id(asyncio.get_running_loop())

    assert tasks._run_async(loop_id()) == tasks._run_async(loop_id())


def test_run_async_cancels_pending_coroutine_on_interrupt():
    """A BaseException raised mid-run (like Celery's SoftTimeLimitExceeded) must not leave
    the coroutine pending on the shared loop — otherwise it silently resumes on a later,
    unrelated _run_async call.

    NOTE: asyncio only re-raises SystemExit/KeyboardInterrupt out of a callback scheduled
    via call_later — any other BaseException subclass is swallowed and logged by the
    loop's default exception handler instead of propagating. KeyboardInterrupt is the
    closest stand-in we can trigger from a plain callback for the signal-driven
    SoftTimeLimitExceeded that Celery raises in real workers.
    """
    tasks._reset_runtime_for_tests()

    completed = False

    async def slow_coro():
        nonlocal completed
        await asyncio.sleep(10)
        completed = True

    def raise_from_callback():
        raise KeyboardInterrupt("simulated soft time limit")

    loop = tasks._get_loop()
    loop.call_later(0.01, raise_from_callback)

    with pytest.raises(KeyboardInterrupt):
        tasks._run_async(slow_coro())

    # The interrupted coroutine must have been cancelled, not left pending.
    assert len(asyncio.all_tasks(loop)) == 0

    # Running another coroutine on the same loop must not resume the old one.
    tasks._run_async(asyncio.sleep(0))
    assert completed is False
