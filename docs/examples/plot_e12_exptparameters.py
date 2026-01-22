"""
Experiment Parameters
=====================

Experiment Parameters are a type safe markup language
that utilizes CSV files to described arbitrarily nested
dictionaries. Experiment parameters are always a dictionary,
but may contain lists and other dictionaries.

Experiment parameters support ``bool``, ``str``, ``int``,
and ``float`` types. The string stored int he csv is cast
into this type when read in. The type must be declared.

A header line is required of the form ``key_1,value,type,comment``.
For nested dictionaries, add additional key columns. The key values
proceeding the value column designate the path to access the
value in the dictionary.

Single comment lines with a leading ``#`` can be inserted to organize related
blocks of parameters.
"""

from rminstr.data_structures import ExptParameters
from pathlib import Path

# lets create a csv file
# and write it to a file
my_csv_1 = """key_1,value,type,comment
name,reader,str,name of person
age,1,int,age of read
# comment lines can be added for clarity
height,5.11,float,height of person
truthy,True,bool,is this person truthy"""

file_path = Path('outputs/parameters_0.csv')

with open(file_path, 'w') as f:
    f.write(my_csv_1)

# we can read it back in
parameters = ExptParameters(file_path)

assert parameters['height'] == 5.11

# %%
# Nested Keys
# ---------
# Create more key columns in the header
# to create nested structures.

my_csv_1 = """key_1,key_2,value,type,comment
object,attribute,value,str,some nested value"""

file_path = Path('outputs/parameters_1.csv')

with open(file_path, 'w') as f:
    f.write(my_csv_1)

# we can read it back in
parameters = ExptParameters(file_path)

assert parameters['object']['attribute'] == 'value'

# %%
# Lists
# -----
# Repeating a key will create a list ordered
# from top to bottom.


# this creates a list of length two
# under the key ``item``
my_csv_1 = """key_1,value,type,comment
item,value,str,index 0
item,another_value,str,index 1"""

file_path = Path('outputs/parameters_2.csv')

with open(file_path, 'w') as f:
    f.write(my_csv_1)

# we can read it back in
parameters = ExptParameters(file_path)

assert len(parameters['item']) == 2

# %%
# File Composition
# ----------------
# Dictionaries can be composed of multiple
# files, and will be recursively merged in the order
# provided.

files = [
    'outputs/parameters_0.csv',
    'outputs/parameters_1.csv',
    'outputs/parameters_2.csv',
]

parameters = ExptParameters(file_path)


# %%
# Run Settings
# ------------
# In addition to configuration files, ``ExperimentParameters``
# can take in a csv of settings that defines a set
# iterable parameters (like a frequency list). The
# object can be iterated over to track your position in a
# measurement. Unless specified, run_settings are assumed
# to be float values.

my_run_settings = """frequency (GHz),voltage (V)
1.0, 0.1
2.0, 0.2
3.0, 0.3"""

run_settings = Path('outputs/my_run_settings.csv')
with open(run_settings, 'w') as f:
    f.write(my_run_settings)

parameters = ExptParameters(files, run_settings_file=run_settings)

# %%
# The columns of the run settings are accesible
# inside the parameters as if they were
# part of the configuration, adjusted as you advance
# through the loop.
parameters.advance()

# iterate till complete
while not parameters.complete():
    this_voltage = parameters['voltage (V)']

    # advance to next step
    parameters.advance()


# %%
# Saving
# ------
# Parameters and run settings can be saved for record purposes.
# Config files will be saved to a single file.
# Comments are no preserved.
parameters.save_config('outputs/config_copy.csv')
parameters.save_run_settings('outputs/run_settings_copy.csv')
