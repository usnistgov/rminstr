"""
Cant test instruments with pytests, so storing here but it needs
to be run manually while ocnnected to an instrument
"""

import numpy as np


if __name__ == '__main__':
    # Change the VNA type to check if its working
    from rminstr.instruments.KS_PNA import VNA

    VNA = VNA('GPIB0::16::INSTR')

    # Linear Sweep
    VNA.setup(
        power_dBm=0,
        IFBW=1000,
        params=['a11', 'b11'],
        fstart_GHz=0.1,
        fstop_GHz=26.5,
        npoints=100,
        sweep_type='lin',
    )

    VNA.arm()
    VNA.trigger()
    VNA.wait_until_data_available(10)
    data = VNA.fetch_data()

    import matplotlib.pyplot as plt

    plt.close('all')
    fig, ax = plt.subplots(1, 1)
    fig.suptitle('Linear Sweep')
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['b11'])), 'o-', label='b11'
    )
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['a11'])), 'o-', label='a11'
    )
    ax.legend(loc='best')
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('Parameter (dB)')
    fig.show()
    # Logarithmic Sweep
    VNA.setup(
        power_dBm=0,
        IFBW=1000,
        params=['a11', 'b11'],
        fstart_GHz=0.1,
        fstop_GHz=26.5,
        npoints=100,
        sweep_type='log',
    )

    VNA.arm()
    VNA.trigger()
    VNA.wait_until_data_available(10)
    data = VNA.fetch_data()

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1)
    fig.suptitle('Log Sweep')
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['b11'])), 'o-', label='b11'
    )
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['a11'])), 'o-', label='a11'
    )
    ax.legend(loc='best')
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('Parameter (dB)')
    fig.show()

    # Frequency List Sweep
    VNA.setup(
        power_dBm=0,
        IFBW=1,
        params=['a11', 'b11'],
        flist_GHz=np.sort(np.random.random(10)),
    )

    VNA.arm()
    VNA.trigger()
    VNA.wait_until_data_available(10)
    data = VNA.fetch_data()

    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1)
    fig.suptitle('Frequency List')
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['b11'])), 'o-', label='b11'
    )
    ax.plot(
        data['Frequency (GHz)'], 10 * np.log10(np.abs(data['a11'])), 'o-', label='a11'
    )
    ax.legend(loc='best')
    ax.set_xlabel('Frequency (GHz)')
    ax.set_ylabel('Parameter (dB)')
    plt.show()
