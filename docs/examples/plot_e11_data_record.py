"""
Data Records
============

Data records are a tool for managing time series data collected
over the course of a measurement. They store aligned time series data
and meta data about the file in multiple csv files.

An ActiveRecord is a context manager that will automatically dump
any data in the memory to the target directory in the event of
an exception or error.
"""

from rminstr.data_structures import ActiveRecord, ExistingRecord
import time

with ActiveRecord(
    ['column_1', 'column_2'], output_dir='outputs', maxlen=100, minlen=10
) as rec:
    # add a single sample. Time stamps can be applied automatically
    # or through the timestamp keyword.
    rec.update('column_1', 0.1)

    # add multiple samples all at once, time stamps need to be
    # provided in this case
    samples = []
    timestamps = []
    for i in range(50):
        samples.append(i)
        timestamps.append(time.time())
    rec.array_update('column_2', samples, timestamps)

    # The most recent sample in a column can be accessed via indexing

    last_sample = rec['column_2']

    # Columns can be indexed into by their timestamps

    time_series = rec.get_time_series(
        'column_2', t_min=timestamps[5], t_max=timestamps[7]
    )

# %%
# To read the data back in, point the ``ExistingRecord`` class to
# the metadata file produced by the ``ActiveRecord``.
opened = ExistingRecord(f'outputs/{rec.metadata_file_name}')

# Read each line in the record one at a time
# and index into it like you would an active record
while opened.read_next_line():
    pass
last_sample = opened['column_1']


# Read the entire record at once into a
# dictionary of ``TimeSeries`` objects.
columns = opened.batch_read()
