import numpy as np
import pytest

from pandas._libs.tslibs.dtypes import NpyDatetimeUnit

import pandas as pd
from pandas import Timedelta
import pandas._testing as tm
from pandas.core.arrays import (
    DatetimeArray,
    TimedeltaArray,
)


class TestNonNano:
    @pytest.fixture(params=["s", "ms", "us"])
    def unit(self, request):
        return request.param

    @pytest.fixture
    def reso(self, unit):
        if unit == "s":
            return NpyDatetimeUnit.NPY_FR_s.value
        elif unit == "ms":
            return NpyDatetimeUnit.NPY_FR_ms.value
        elif unit == "us":
            return NpyDatetimeUnit.NPY_FR_us.value
        else:
            raise NotImplementedError(unit)

    @pytest.fixture
    def tda(self, unit):
        arr = np.arange(5, dtype=np.int64).view(f"m8[{unit}]")
        return TimedeltaArray._simple_new(arr, dtype=arr.dtype)

    def test_non_nano(self, unit, reso):
        arr = np.arange(5, dtype=np.int64).view(f"m8[{unit}]")
        tda = TimedeltaArray._simple_new(arr, dtype=arr.dtype)

        assert tda.dtype == arr.dtype
        assert tda[0]._reso == reso

    @pytest.mark.parametrize("field", TimedeltaArray._field_ops)
    def test_fields(self, tda, field):
        as_nano = tda._ndarray.astype("m8[ns]")
        tda_nano = TimedeltaArray._simple_new(as_nano, dtype=as_nano.dtype)

        result = getattr(tda, field)
        expected = getattr(tda_nano, field)
        tm.assert_numpy_array_equal(result, expected)

    def test_to_pytimedelta(self, tda):
        as_nano = tda._ndarray.astype("m8[ns]")
        tda_nano = TimedeltaArray._simple_new(as_nano, dtype=as_nano.dtype)

        result = tda.to_pytimedelta()
        expected = tda_nano.to_pytimedelta()
        tm.assert_numpy_array_equal(result, expected)

    def test_total_seconds(self, unit, tda):
        as_nano = tda._ndarray.astype("m8[ns]")
        tda_nano = TimedeltaArray._simple_new(as_nano, dtype=as_nano.dtype)

        result = tda.total_seconds()
        expected = tda_nano.total_seconds()
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize(
        "nat", [np.datetime64("NaT", "ns"), np.datetime64("NaT", "us")]
    )
    def test_add_nat_datetimelike_scalar(self, nat, tda):
        result = tda + nat
        assert isinstance(result, DatetimeArray)
        assert result._reso == tda._reso
        assert result.isna().all()

        result = nat + tda
        assert isinstance(result, DatetimeArray)
        assert result._reso == tda._reso
        assert result.isna().all()

    def test_add_pdnat(self, tda):
        result = tda + pd.NaT
        assert isinstance(result, TimedeltaArray)
        assert result._reso == tda._reso
        assert result.isna().all()

        result = pd.NaT + tda
        assert isinstance(result, TimedeltaArray)
        assert result._reso == tda._reso
        assert result.isna().all()


class TestTimedeltaArray:
    @pytest.mark.parametrize("dtype", [int, np.int32, np.int64, "uint32", "uint64"])
    def test_astype_int(self, dtype):
        arr = TimedeltaArray._from_sequence([Timedelta("1H"), Timedelta("2H")])

        if np.dtype(dtype).kind == "u":
            expected_dtype = np.dtype("uint64")
        else:
            expected_dtype = np.dtype("int64")
        expected = arr.astype(expected_dtype)

        warn = None
        if dtype != expected_dtype:
            warn = FutureWarning
        msg = " will return exactly the specified dtype"
        with tm.assert_produces_warning(warn, match=msg):
            result = arr.astype(dtype)

        assert result.dtype == expected_dtype
        tm.assert_numpy_array_equal(result, expected)

    def test_setitem_clears_freq(self):
        a = TimedeltaArray(pd.timedelta_range("1H", periods=2, freq="H"))
        a[0] = Timedelta("1H")
        assert a.freq is None

    @pytest.mark.parametrize(
        "obj",
        [
            Timedelta(seconds=1),
            Timedelta(seconds=1).to_timedelta64(),
            Timedelta(seconds=1).to_pytimedelta(),
        ],
    )
    def test_setitem_objects(self, obj):
        # make sure we accept timedelta64 and timedelta in addition to Timedelta
        tdi = pd.timedelta_range("2 Days", periods=4, freq="H")
        arr = TimedeltaArray(tdi, freq=tdi.freq)

        arr[0] = obj
        assert arr[0] == Timedelta(seconds=1)

    @pytest.mark.parametrize(
        "other",
        [
            1,
            np.int64(1),
            1.0,
            np.datetime64("NaT"),
            pd.Timestamp("2021-01-01"),
            "invalid",
            np.arange(10, dtype="i8") * 24 * 3600 * 10**9,
            (np.arange(10) * 24 * 3600 * 10**9).view("datetime64[ns]"),
            pd.Timestamp("2021-01-01").to_period("D"),
        ],
    )
    @pytest.mark.parametrize("index", [True, False])
    def test_searchsorted_invalid_types(self, other, index):
        data = np.arange(10, dtype="i8") * 24 * 3600 * 10**9
        arr = TimedeltaArray(data, freq="D")
        if index:
            arr = pd.Index(arr)

        msg = "|".join(
            [
                "searchsorted requires compatible dtype or scalar",
                "value should be a 'Timedelta', 'NaT', or array of those. Got",
            ]
        )
        with pytest.raises(TypeError, match=msg):
            arr.searchsorted(other)


class TestUnaryOps:
    def test_abs(self):
        vals = np.array([-3600 * 10**9, "NaT", 7200 * 10**9], dtype="m8[ns]")
        arr = TimedeltaArray(vals)

        evals = np.array([3600 * 10**9, "NaT", 7200 * 10**9], dtype="m8[ns]")
        expected = TimedeltaArray(evals)

        result = abs(arr)
        tm.assert_timedelta_array_equal(result, expected)

        result2 = np.abs(arr)
        tm.assert_timedelta_array_equal(result2, expected)

    def test_pos(self):
        vals = np.array([-3600 * 10**9, "NaT", 7200 * 10**9], dtype="m8[ns]")
        arr = TimedeltaArray(vals)

        result = +arr
        tm.assert_timedelta_array_equal(result, arr)
        assert not tm.shares_memory(result, arr)

        result2 = np.positive(arr)
        tm.assert_timedelta_array_equal(result2, arr)
        assert not tm.shares_memory(result2, arr)

    def test_neg(self):
        vals = np.array([-3600 * 10**9, "NaT", 7200 * 10**9], dtype="m8[ns]")
        arr = TimedeltaArray(vals)

        evals = np.array([3600 * 10**9, "NaT", -7200 * 10**9], dtype="m8[ns]")
        expected = TimedeltaArray(evals)

        result = -arr
        tm.assert_timedelta_array_equal(result, expected)

        result2 = np.negative(arr)
        tm.assert_timedelta_array_equal(result2, expected)

    def test_neg_freq(self):
        tdi = pd.timedelta_range("2 Days", periods=4, freq="H")
        arr = TimedeltaArray(tdi, freq=tdi.freq)

        expected = TimedeltaArray(-tdi._data, freq=-tdi.freq)

        result = -arr
        tm.assert_timedelta_array_equal(result, expected)

        result2 = np.negative(arr)
        tm.assert_timedelta_array_equal(result2, expected)
