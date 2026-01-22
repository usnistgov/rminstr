"""Importer utilities for calorimeter-python."""

from collections import namedtuple
from pathlib import Path
import importlib.util as _ilutil
import sys as _sys
import os as _os
import rminstr.instruments.measurement_functionalities as meas_funs


def import_instrument(model_name: str, functionality: str) -> type:
    """
    Import an instrument model/functionality by string.

    Parameters
    ----------
    model_name : str
        Name of of instrument model to import.

    functionality : str
        Name of measurement functionality to import.

    Returns
    -------
    type
        Instrument class of given model/functionality.

    """
    mod_str = 'rminstr.instruments.' + model_name
    if (spec := _ilutil.find_spec(mod_str)) is not None:
        # If you chose to perform the actual import ...
        mod = _ilutil.module_from_spec(spec)
        _sys.modules[mod_str] = mod
        spec.loader.exec_module(mod)
        cls = getattr(mod, functionality)
    return cls


def instrument_iterator():
    """
    Iterate over all the instrument implementations available in rminstr.

    Yields
    ------
    namedtuple
        Has fields model, impl, abc, statemodel.
        Field `model` is a str of the model name.
        Field `impl` is the class object of a measurment functionality implementation.
        Field `abc` is the measurement functionality abstraction class object.
        Fiel `statemodel` is the statemodel definition the functionality abstraction uses.

    """
    implementation = namedtuple(
        'InstrImplementationDescriptor', 'model impl abc statemodel'
    )

    abstractions = [getattr(meas_funs, a) for a in dir(meas_funs) if 'ABC_' in a]
    # abstractions  = [a for a in abstractions if issubclass(a,meas_funs.state_models.SetupOnly)]

    instr_path = Path(__file__).parents[1] / 'instruments'
    mods = _os.listdir(instr_path)

    def modpath(p):
        return _os.path.join(instr_path, p)

    mods = [m for m in mods if _os.path.isdir(modpath(m)) and '__' not in m]
    exclude = ['communications', 'measurement_functionalities']
    mods = [m for m in mods if m not in exclude]

    for model in mods:
        mod_str = 'rminstr.instruments.' + model
        spec = _ilutil.find_spec(mod_str)
        mod = _ilutil.module_from_spec(spec)
        _sys.modules['module.name'] = mod
        spec.loader.exec_module(mod)
        functionalities = [a for a in dir(mod) if '__' not in a]
        for f in functionalities:
            impl_cls = getattr(mod, f)
            for abc in abstractions:
                # print(impl_cls.__name__, abc.__name__)
                try:
                    if issubclass(impl_cls, abc):
                        bases = abc.__bases__
                        bases = [
                            b
                            for b in bases
                            if issubclass(b, meas_funs.state_models.SetupOnly)
                        ]
                        assert len(bases) == 1
                        statemodel = bases[0]
                        impl = implementation(model, impl_cls, abc, statemodel)
                        yield impl
                except TypeError:
                    pass

    return mod


if __name__ == '__main__':
    for m in instrument_iterator():
        print(m.model, m.impl.__name__, m.abc.__name__, m.statemodel.__name__)
