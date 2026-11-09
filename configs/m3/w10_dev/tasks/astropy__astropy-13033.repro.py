"""Issue: removing a required TimeSeries column gives a misleading message
("expected 'time' as the first columns but found 'time'") instead of saying required columns are missing."""
import numpy as np
import pytest

from astropy.time import Time
from astropy.timeseries import TimeSeries


def test_missing_required_column_message_names_the_column():
    time = Time(np.arange(100000, 100003), format='jd')
    ts = TimeSeries(time=time, data={'flux': [99.9, 99.8, 99.7]})
    ts._required_columns = ['time', 'flux']
    with pytest.raises(ValueError) as error:
        ts.remove_column('flux')
    message = str(error.value)
    expected, separator, found = message.partition(' but found ')
    assert separator
    # The actual remaining column really is time. The issue is that the
    # expected required-column list must also name the missing flux column.
    assert "'time'" in expected
    assert "'flux'" in expected
    assert "'time'" in found
