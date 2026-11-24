import asyncio
from dataclasses import dataclass, field


@dataclass
class FakeTx:
    open: bool = True
    committed: bool = False
    rolled_back: bool = False
    operations: list[str] = field(default_factory=list)

    def write(self, op: str) -> None:
        if not self.open:
            raise RuntimeError("transaction already closed")
        self.operations.append(op)

    def commit(self) -> None:
        if not self.open:
            raise RuntimeError("transaction already closed")
        self.committed = True
        self.open = False

    def rollback(self) -> None:
        if self.open:
            self.rolled_back = True
            self.open = False


@dataclass
class FakeFileHandle:
    path: str
    closed: bool = False
    lines: list[str] = field(default_factory=list)

    def write_line(self, line: str) -> None:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        self.lines.append(line)

    def close(self) -> None:
        self.closed = True


async def _cleanup(tx: FakeTx, fh: FakeFileHandle) -> None:
    """
    Runs on cancellation or failure.
    Avoids unguarded awaits that could be interrupted mid-cleanup;
    rolls back uncommitted work and always closes the file handle.
    """
    try:
        if tx.open and not tx.committed:
            tx.rollback()
    finally:
        if not fh.closed:
            fh.close()


async def process_reservation_with_audit(
    tx: FakeTx,
    fh: FakeFileHandle,
    started: asyncio.Event,
    release_io: asyncio.Event,
) -> str:
    try:
        tx.write("RESERVE sku=widget qty=2")
        fh.write_line("attempt: sku=widget qty=2")

        # Signal test that both tx and file handle are open and mid-flight
        started.set()

        # Simulate slow I/O where cancellation arrives mid-flight
        await release_io.wait()

        fh.write_line("committed: sku=widget qty=2")
        tx.commit()
        fh.close()
        return "committed"
    except asyncio.CancelledError:
        # Shield cleanup so a second cancellation signal cannot abort rollback/close
        await asyncio.shield(_cleanup(tx, fh))
        raise
    except Exception:
        await asyncio.shield(_cleanup(tx, fh))
        raise