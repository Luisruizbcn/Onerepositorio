# -*- coding: utf-8 -*-

import numpy as np
import pytest

import pandas.util.testing as tm
from pandas import date_range
from pandas._libs.tslib import iNaT
from pandas._libs.tslibs import conversion, timezones


class TestTslib(object):

    @pytest.mark.parametrize('tz', ['UTC', 'Asia/Tokyo',
                                    'US/Eastern', 'Europe/Moscow'])
    def test_tslib_tz_convert(self, tz):
        def compare_utc_to_local(tz_didx, utc_didx):
            f = lambda x: conversion.tz_convert_single(x, 'UTC', tz_didx.tz)
            result = conversion.tz_convert(tz_didx.asi8, 'UTC', tz_didx.tz)
            result_single = np.vectorize(f)(tz_didx.asi8)
            tm.assert_numpy_array_equal(result, result_single)

        def compare_local_to_utc(tz_didx, utc_didx):
            f = lambda x: conversion.tz_convert_single(x, tz_didx.tz, 'UTC')
            result = conversion.tz_convert(utc_didx.asi8, tz_didx.tz, 'UTC')
            result_single = np.vectorize(f)(utc_didx.asi8)
            tm.assert_numpy_array_equal(result, result_single)

        # US: 2014-03-09 - 2014-11-11
        # MOSCOW: 2014-10-26  /  2014-12-31
        tz_didx = date_range('2014-03-01', '2015-01-10', freq='H', tz=tz)
        utc_didx = date_range('2014-03-01', '2015-01-10', freq='H')
        compare_utc_to_local(tz_didx, utc_didx)
        # local tz to UTC can be differ in hourly (or higher) freqs because
        # of DST
        compare_local_to_utc(tz_didx, utc_didx)

        tz_didx = date_range('2000-01-01', '2020-01-01', freq='D', tz=tz)
        utc_didx = date_range('2000-01-01', '2020-01-01', freq='D')
        compare_utc_to_local(tz_didx, utc_didx)
        compare_local_to_utc(tz_didx, utc_didx)

        tz_didx = date_range('2000-01-01', '2100-01-01', freq='A', tz=tz)
        utc_didx = date_range('2000-01-01', '2100-01-01', freq='A')
        compare_utc_to_local(tz_didx, utc_didx)
        compare_local_to_utc(tz_didx, utc_didx)

    def test_tz_convert_empty(self):
        # Check empty array
        arr = np.array([], dtype=np.int64)
        result = conversion.tz_convert(arr,
                                       timezones.maybe_get_tz('US/Eastern'),
                                       timezones.maybe_get_tz('Asia/Tokyo'))
        tm.assert_numpy_array_equal(result, arr)

    def test_tz_convert_nat(self):
        # Check all-NaT array
        arr = np.array([iNaT], dtype=np.int64)
        result = conversion.tz_convert(arr,
                                       timezones.maybe_get_tz('US/Eastern'),
                                       timezones.maybe_get_tz('Asia/Tokyo'))
        tm.assert_numpy_array_equal(result, arr)
