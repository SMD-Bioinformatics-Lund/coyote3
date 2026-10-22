"""Bounded-memory stable sorting of internally produced table rows."""

import heapq
import pickle
from contextlib import ExitStack
from itertools import islice
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, BinaryIO, Callable, Iterable, Iterator

SORT_CHUNK_ROWS = 1000
MERGE_FAN_IN = 32


def _read_rows(stream: BinaryIO) -> Iterator[dict[str, Any]]:
    """Read only spool records written by this invocation in its private directory.

    Pickle preserves internal BSON and datetime values. No uploaded file or caller
    path is accepted; the temporary directory is created with owner-only access.

    Args:
        stream: Binary run file opened by this invocation's merge operation.

    Yields:
        Original internal row dictionaries in their persisted run order.
    """
    while True:
        try:
            yield pickle.load(stream)
        except EOFError:
            return


def _merge(paths: list[Path], key: Callable) -> Iterator[dict[str, Any]]:
    """Merge contiguous stable runs with bounded open descriptors.

    Args:
        paths: At most MERGE_FAN_IN ordered runs in this invocation's private directory.
        key: Existing table comparator used to create the sorted runs.

    Yields:
        Sorted rows, preserving input-run order for equal keys.
    """
    with ExitStack() as stack:
        streams = [stack.enter_context(path.open("rb")) for path in paths]
        yield from heapq.merge(*(_read_rows(stream) for stream in streams), key=key)


def sorted_page(
    items: Iterable[dict[str, Any]], *, key: Callable, start: int, end: int
) -> list[dict[str, Any]]:
    """Return a stable sorted slice using bounded chunks and a private temporary spool.

    Args:
        items: Internal rows, consumed completely to preserve caller match counts.
        key: Existing clinical table comparator key.
        start: Inclusive zero-based offset.
        end: Exclusive offset.

    Returns:
        The requested rows, preserving equal-key input order and original value types.

    Raises:
        OSError: Temporary storage is unavailable or full. Temporary files are removed
            on both successful and failed requests; no partial page is returned.
    """
    with TemporaryDirectory(prefix="coyote-table-") as directory:
        root = Path(directory)
        runs = []
        source = iter(items)
        sequence = 0
        while chunk := list(islice(source, SORT_CHUNK_ROWS)):
            path = root / str(sequence)
            sequence += 1
            with path.open("xb") as stream:
                for row in sorted(chunk, key=key):
                    pickle.dump(row, stream, protocol=pickle.HIGHEST_PROTOCOL)
            runs.append(path)
        while len(runs) > MERGE_FAN_IN:
            merged = []
            for offset in range(0, len(runs), MERGE_FAN_IN):
                batch = runs[offset : offset + MERGE_FAN_IN]
                path = root / str(sequence)
                sequence += 1
                with path.open("xb") as stream:
                    for row in _merge(batch, key):
                        pickle.dump(row, stream, protocol=pickle.HIGHEST_PROTOCOL)
                for old in batch:
                    old.unlink()
                merged.append(path)
            runs = merged
        iterator = _merge(runs, key)
        try:
            return list(islice(iterator, start, end))
        finally:
            iterator.close()
