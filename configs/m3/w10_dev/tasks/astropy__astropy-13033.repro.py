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
    assert "found 'time'" not in message
    assert 'flux' in message
