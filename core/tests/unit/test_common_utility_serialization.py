from __future__ import annotations

from coyote.domain.common.reporting import nl_join


def test_nl_join_does_not_mutate_the_caller_list():
    values = ["A", "B", "C"]

    assert nl_join(values, "och") == "A, B och C"
    assert values == ["A", "B", "C"]
    assert nl_join([], "och") == ""
