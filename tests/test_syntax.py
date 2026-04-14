# -*- coding: utf-8 -*-
"""
Created on Sat Apr 12 07:34:10 2025

@author: dcg2
"""

from rminstr.utilities.importer import instrument_iterator


def test_naming():
    for impl in instrument_iterator():
        iname = impl.impl.__name__
        abcname = impl.abc.__name__.replace('ABC_', '')
        if iname != abcname:
            print(impl.model, impl.impl.__name__, ' failed')
        assert iname == abcname


def test_measurement_functionality_common_syntax():
    implementations = []
    methods = []
    reports = []
    print('Checking Instrument Syntax Conventions :')
    for impl in instrument_iterator():
        abstract_methods = list(impl.abc.__abstractmethods__)
        print('  ',impl.model)
        for am in abstract_methods:
            print('    ',am)
            try:
                report = impl.impl._check_method_syntax(am)
                print('     ',report)
                reports.append(report)
                methods.append(am)
                implementations.append(impl)
                
            except Exception as e:
                print(
                    'Error in generating syntax report for ',
                    impl.model,
                    am,
                    impl.abc.__name__,
                )
                raise e

    all_passed = True

    titles = []
    for i, r, m in zip(implementations, reports, methods):
        titles.append(i.model + '.' + i.impl.__name__ + '.' + m)
    # max_sec_title = max([len(t) for t in titles])
    titles = [t.rjust(0) for t in titles]
    failed_count = 0
    for i, r, m, title in zip(implementations, reports, methods, titles):
        if not r.passed:
            all_passed = False
            failed_count += 1
            print(title, ' FAILED')
            print('  All abc args :', i.abc.acceptable_args[m])
            print('  not defined in abc :', r.undefined_in_abc)
            print('  missing_in_imp :', r.missing_in_impl)
            print('  has_positional_args :', r.contains_position)
            print(len(title) * '-' + '-' * 6)
    print('TOTAL FAILED METHODS :', failed_count)
    assert all_passed


if __name__ == '__main__':
    test_measurement_functionality_common_syntax()
