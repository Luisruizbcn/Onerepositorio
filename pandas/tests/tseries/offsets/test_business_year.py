"""
Tests for the following offsets:
- BYearBegin
- BYearEnd
"""
from datetime import datetime

import pytest

import pandas as pd
from pandas.tests.tseries.offsets.common import (
    Base,
    assert_is_on_offset,
    assert_offset_equal,
)

from pandas.tseries.offsets import (
    BYearBegin,
    BYearEnd,
)


@pytest.mark.parametrize("n", [-2, 1])
@pytest.mark.parametrize(
    "cls",
    [
        BYearBegin,
        BYearEnd,
    ],
)
def test_apply_index(cls, n):
    offset = cls(n=n)
    rng = pd.date_range(start="1/1/2000", periods=100000, freq="T")
    ser = pd.Series(rng)

    res = rng + offset
    assert res.freq is None  # not retained
    assert res[0] == rng[0] + offset
    assert res[-1] == rng[-1] + offset
    res2 = ser + offset
    # apply_index is only for indexes, not series, so no res2_v2
    assert res2.iloc[0] == ser.iloc[0] + offset
    assert res2.iloc[-1] == ser.iloc[-1] + offset


class TestBYearBegin(Base):
    _offset = BYearBegin

    def test_misspecified(self):
        msg = "Month must go from 1 to 12"
        with pytest.raises(ValueError, match=msg):
            BYearBegin(month=13)
        with pytest.raises(ValueError, match=msg):
            BYearEnd(month=13)

    offset_cases = []
    offset_cases.append(
        (
            BYearBegin(),
            {
                datetime(2008, 1, 1): datetime(2009, 1, 1),
                datetime(2008, 6, 30): datetime(2009, 1, 1),
                datetime(2008, 12, 31): datetime(2009, 1, 1),
                datetime(2011, 1, 1): datetime(2011, 1, 3),
                datetime(2011, 1, 3): datetime(2012, 1, 2),
                datetime(2005, 12, 30): datetime(2006, 1, 2),
                datetime(2005, 12, 31): datetime(2006, 1, 2),
            },
        )
    )

    offset_cases.append(
        (
            BYearBegin(0),
            {
                datetime(2008, 1, 1): datetime(2008, 1, 1),
                datetime(2008, 6, 30): datetime(2009, 1, 1),
                datetime(2008, 12, 31): datetime(2009, 1, 1),
                datetime(2005, 12, 30): datetime(2006, 1, 2),
                datetime(2005, 12, 31): datetime(2006, 1, 2),
            },
        )
    )

    offset_cases.append(
        (
            BYearBegin(-1),
            {
                datetime(2007, 1, 1): datetime(2006, 1, 2),
                datetime(2009, 1, 4): datetime(2009, 1, 1),
                datetime(2009, 1, 1): datetime(2008, 1, 1),
                datetime(2008, 6, 30): datetime(2008, 1, 1),
                datetime(2008, 12, 31): datetime(2008, 1, 1),
                datetime(2006, 12, 29): datetime(2006, 1, 2),
                datetime(2006, 12, 30): datetime(2006, 1, 2),
                datetime(2006, 1, 1): datetime(2005, 1, 3),
            },
        )
    )

    offset_cases.append(
        (
            BYearBegin(-2),
            {
                datetime(2007, 1, 1): datetime(2005, 1, 3),
                datetime(2007, 6, 30): datetime(2006, 1, 2),
                datetime(2008, 12, 31): datetime(2007, 1, 1),
            },
        )
    )

    @pytest.mark.parametrize("case", offset_cases)
    def test_offset(self, case):
        offset, cases = case
        for base, expected in cases.items():
            assert_offset_equal(offset, base, expected)


class TestBYearEnd(Base):
    _offset = BYearEnd

    offset_cases = []
    offset_cases.append(
        (
            BYearEnd(),
            {
                datetime(2008, 1, 1): datetime(2008, 12, 31),
                datetime(2008, 6, 30): datetime(2008, 12, 31),
                datetime(2008, 12, 31): datetime(2009, 12, 31),
                datetime(2005, 12, 30): datetime(2006, 12, 29),
                datetime(2005, 12, 31): datetime(2006, 12, 29),
            },
        )
    )

    offset_cases.append(
        (
            BYearEnd(0),
            {
                datetime(2008, 1, 1): datetime(2008, 12, 31),
                datetime(2008, 6, 30): datetime(2008, 12, 31),
                datetime(2008, 12, 31): datetime(2008, 12, 31),
                datetime(2005, 12, 31): datetime(2006, 12, 29),
            },
        )
    )

    offset_cases.append(
        (
            BYearEnd(-1),
            {
                datetime(2007, 1, 1): datetime(2006, 12, 29),
                datetime(2008, 6, 30): datetime(2007, 12, 31),
                datetime(2008, 12, 31): datetime(2007, 12, 31),
                datetime(2006, 12, 29): datetime(2005, 12, 30),
                datetime(2006, 12, 30): datetime(2006, 12, 29),
                datetime(2007, 1, 1): datetime(2006, 12, 29),
            },
        )
    )

    offset_cases.append(
        (
            BYearEnd(-2),
            {
                datetime(2007, 1, 1): datetime(2005, 12, 30),
                datetime(2008, 6, 30): datetime(2006, 12, 29),
                datetime(2008, 12, 31): datetime(2006, 12, 29),
            },
        )
    )

    @pytest.mark.parametrize("case", offset_cases)
    def test_offset(self, case):
        offset, cases = case
        for base, expected in cases.items():
            assert_offset_equal(offset, base, expected)

    on_offset_cases = [
        (BYearEnd(), datetime(2007, 12, 31), True),
        (BYearEnd(), datetime(2008, 1, 1), False),
        (BYearEnd(), datetime(2006, 12, 31), False),
        (BYearEnd(), datetime(2006, 12, 29), True),
    ]

    @pytest.mark.parametrize("case", on_offset_cases)
    def test_is_on_offset(self, case):
        offset, dt, expected = case
        assert_is_on_offset(offset, dt, expected)


class TestBYearEndLagged(Base):
    _offset = BYearEnd

    def test_bad_month_fail(self):
        msg = "Month must go from 1 to 12"
        with pytest.raises(ValueError, match=msg):
            BYearEnd(month=13)
        with pytest.raises(ValueError, match=msg):
            BYearEnd(month=0)

    offset_cases = []
    offset_cases.append(
        (
            BYearEnd(month=6),
            {
                datetime(2008, 1, 1): datetime(2008, 6, 30),
                datetime(2007, 6, 30): datetime(2008, 6, 30),
            },
        )
    )

    offset_cases.append(
        (
            BYearEnd(n=-1, month=6),
            {
                datetime(2008, 1, 1): datetime(2007, 6, 29),
                datetime(2007, 6, 30): datetime(2007, 6, 29),
            },
        )
    )

    @pytest.mark.parametrize("case", offset_cases)
    def test_offset(self, case):
        offset, cases = case
        for base, expected in cases.items():
            assert_offset_equal(offset, base, expected)

    def test_roll(self):
        offset = BYearEnd(month=6)
        date = datetime(2009, 11, 30)

        assert offset.rollforward(date) == datetime(2010, 6, 30)
        assert offset.rollback(date) == datetime(2009, 6, 30)

    on_offset_cases = [
        (BYearEnd(month=2), datetime(2007, 2, 28), True),
        (BYearEnd(month=6), datetime(2007, 6, 30), False),
    ]

    @pytest.mark.parametrize("case", on_offset_cases)
    def test_is_on_offset(self, case):
        offset, dt, expected = case
        assert_is_on_offset(offset, dt, expected)
