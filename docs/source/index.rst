Welcome to Rocky Mountain Instrument's documentation!
=====================================================
This package is a library of instrument control and data collection code.
Instruments capable of providing the same service have control classes with
a shared syntax, allowing similar instruments to be easily swapped into
experiment scripts. 

For example, suppose you have a nanavoltmeter (an HP 34420A in this example) and an a
digital multi-meter (HP 3458A in this example). While these instruments are slightly different, they
can both be configured to behave like a voltmeter in an experiment. In this package, both instruments
have a measurement functionality called ``voltmeter`` defined. This means that interacting with the digital
multi-meter's ``voltmeter`` measurement functionality

.. code-block:: python

   from rminstr.instruments.HP3458A import voltmeter
   vm = voltmeter('GPIB::16::INSTR')
   vm.initial_setup()
   vm.setup(vrange = 1, nplc = 1)
   vm.arm()
   vm.trigger()
   vm.wait_until_data_available(timeout = 10)
   data = vm.fetch_data()

is identical to the code to interact with a nanovoltmeter's ``voltmeter`` measurement functionality.

.. code-block:: python

   from rminstr.instruments.HP34420A import voltmeter
   vm = voltmeter('GPIB::16::INSTR')
   vm.initial_setup()
   vm.setup(v_range = 1, nplc = 1)
   vm.arm()
   vm.trigger()
   vm.wait_until_data_available(timeout = 10)
   data = vm.fetch_data()


The basic idea of the package, is that any instruments which share a measurement functionality - this could be
``voltmeter``, ``ammeter``, ``signal_generator``,  etc - can be swapped at the import statement and still function. This makes
it very easy to develop readable, straight forward flow control scripts that can be very quickly adapted to
support multiple instrument models that provide similar functionalities.

Finally, the package provides some additional features for managing experiments like
``experiment_parameters`` - a method of defining Python dictionaries via CSV files for configuring experiments - and ``data_record`` -
a structure for storing timeseries measurements of multiple instruments taken through out an experiment to CSV
and prevents the programs memory from filling up.

..
   uncomment this if I add examples back in
   .. include::
      auto_examples/index.rst


Table of Contents
=================

.. toctree::
   :maxdepth: 4

   get_started/index.rst
   auto_examples/index.rst
   for_contributors/index.rst


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _GUM: https://jcgm.bipm.org/vim/en/2.41.html
.. _FAIR: https://www.go-fair.org/fair-principles/
