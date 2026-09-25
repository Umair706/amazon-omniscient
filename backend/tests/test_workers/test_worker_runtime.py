import asyncio

from app.workers import tasks


def test_session_factory_is_cached_per_process():
    tasks._reset_runtime_for_tests()
    assert tasks._get_session_factory() is tasks._get_session_factory()


def test_run_async_reuses_one_loop():
    tasks._reset_runtime_for_tests()

    async def loop_id():
        return id(asyncio.get_running_loop())

    assert tasks._run_async(loop_id()) == tasks._run_async(loop_id())
