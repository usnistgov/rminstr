# Rocky Mountain Instruments

> [!NOTE]
> This software is in active and early development by the RF power calibrations service at NIST to support
> RF power calibrations and the development primary RF power standards. Expect breaking breaking changes as the software
> evolves. Instrument interfaces are added and tested as needed for the calibration service. Bugs may
> be present in the instrument interfaces that we are unaware of. Please exercise caution when using interfaces
> presented in this code.

This package is a library of instrument control and data recording code.
Instruments capable of providing the same service have control classes with
a shared syntax, allowing similar instruments to be easily swapped into
experiment scripts.

Read the [pages](https://pages.nist.gov/rminstr-ipages) for code API and examples.

## Usage

For example, suppose you have a nano voltmeter (an HP 34420A in this example) and an a
digital multi-meter (HP 3458A in this example). While these instruments are slightly different, they
can both be configured to behave like a voltmeter in an experiment. In this package, both instruments
have a measurement functionality called `Voltmeter` defined. This means that interacting with one instrument
model that can act as a `Voltmeter`,

```python
from rminstr.instruments.HP3458A import Voltmeter
vm = Voltmeter('GPIB0::16::INSTR')
vm.initial_setup()
vm.setup(v_range = 1)
vm.arm()
vm.trigger()
vm.wait_until_data_available(timeout = 10)
data = vm.fetch_data()
```
is identical to the code to interact with a different model of `Voltmeter`.

```python
from rminstr.instruments.HP34420A import Voltmeter
vm = Voltmeter('GPIB0::16::INSTR')
vm.initial_setup()
vm.setup(v_range = 1)
vm.arm()
vm.trigger()
vm.wait_until_data_available(timeout = 10)
data = vm.fetch_data()
```

The basic idea of the package, is that any instruments which share a measurement functionality - this could be
`Voltmeter`, `Ammeter`, etc - can be swapped at the import statement and still function. This makes
it very easy to develop readable, straight forward flow control scripts that can be very quickly adapted to
support multiple instrument models that provide similar functionalities.

In addition to the library of instruments, the package provides some additional features for managing experiments like the
* `ExperimentParameters` - a type safe csv based markup language for defining configuration files (can be edited in Excel).
* `DataRecord` - a class for recording, managing, and retrieving timeseries data and metadata collected from multiple instruments in human readable csv files.

## Authors

Contributors names and contact info

Daniel C. Gray, Zenn C. Roberts, Aaron M. Hagerstrom


