import asyncio
import pytest

from m7.C.service.cancellation_drill import process_reservation_with_audit, FakeFileHandle, FakeTx


def test_cancel_mid_flight_rolls_back_tx_and_closes_file() -> None:
    async def runner() -> tuple[FakeTx, FakeFileHandle]:
        tx = FakeTx()
        fh = FakeFileHandle("/tmp/audit.log")
        started = asyncio.Event()
        release_io = asyncio.Event()

        task = asyncio.create_task(
            process_reservation_with_audit(tx, fh, started, release_io)
        )

        # Wait until both the transaction and file handle are actively open mid-flight
        await started.wait()
        assert tx.open is True
        assert fh.closed is False

        # Cancel mid-flight
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        return tx, fh

    tx, fh = asyncio.run(runner())

    assert tx.open is False
    assert tx.committed is False
    assert tx.rolled_back is True
    assert fh.closed is True