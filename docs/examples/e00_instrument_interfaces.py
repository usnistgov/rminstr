"""
Instrument Interfaces
=====================

Every instrument interfaces inherits a common state model,
and an interface abstraction for a kind of service that instrument
may provide.

Every instrument has it's own submodule by its make and model,
and interfaces for that instrument art imported through
that submodule.

Different instruments can be used for the same measurement
by swapping import statements.
"""

from rminstr.instruments.HP3458A import Voltmeter

# %%
# Every interface in this package adheres to a common state
# model. Flow control often looks like this:
#
# 1. Connect to instrument with the class and a VISA address.
# 2. Bring to a safe initial state ``initial_setup()``.
# 3. Adjust settings with ``setup``.
# 4. Arm the instrument with ``arm``.
# 5. Trigger the instrument with ``trigger``.
# 6. Wait for data to be ready with ``wait_until_data_available``.
# 7. Fetch data with ``fetch_data``.
# 8. Back to step 3.

vm = Voltmeter('GPIB0::16::INSTR')
vm.initial_setup()
vm.setup(v_range=1)
vm.arm()
vm.trigger()
vm.wait_until_data_available(timeout=10)

# Return a dictionary of numpy arrays.
data = vm.fetch_data()

# %%
# Query an instruments state
# as needed
vm.query_state()

# %%
# Close out the connection when you are done.
vm.close()
