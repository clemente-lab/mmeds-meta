from subprocess import run
from pathlib import Path
import sys
import coverage

from mmeds.authentication import add_user, remove_user
from mmeds.database.database import upload_metadata, upload_otu, upload_lefse

import mmeds.config as fig
import mmeds.secrets as sec

"""
- To run all the tests: python test.py
- To run a specific set of test: python test.py test_name1 test_name2 etc
  - possible test names: authentication, database, documents, spawn, tool, tools, util, validate
- To run all tests with the pudb pytest plugin python test.py pudb
"""

testing = True
coverage.process_startup()


def add_users(tests):
    # Add users as needed
    # users_added keeps track of the number of users added so they can all be removed at the end
    users_added = 0
    if {'database', 'documents', 'util', 'spawn', 'tool', 'tools', 'formatter', 'adder', 'analysis'}.intersection(tests):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=testing)
        users_added += 1
    # database and spawn tests require a second user
    if 'database' in tests or 'spawn' in tests or 'analysis' in tests:
        add_user(fig.TEST_USER_0, sec.TEST_PASS, fig.TEST_EMAIL, testing=testing)
        users_added += 1
    return users_added


def setup_tests(tests):
    # Add test setups as needed:
    test_setup = []
    if {'documents', 'util', 'tool', 'tools', 'formatter', 'adder', 'analysis'}.intersection(tests):
        test_setup.append((fig.TEST_SUBJECT_SHORT,
                           'human',
                           fig.TEST_SPECIMEN_SINGLE_SHORT,
                           fig.TEST_USER,
                           'Test_Single_Short',
                           testing,
                           fig.TEST_CODE_SHORT))
        if 'tools' in tests or 'analysis' in tests:
            test_setup.append((fig.TEST_SUBJECT_SHORT,
                               'human',
                               fig.TEST_SPECIMEN_PAIRED,
                               fig.TEST_USER,
                               'Test_Paired',
                               testing,
                               fig.TEST_CODE_PAIRED))
            test_setup.append((fig.TEST_SUBJECT_SHORT,
                               'human',
                               fig.TEST_SPECIMEN_DEMUXED,
                               fig.TEST_USER,
                               'Test_Demuxed',
                               testing,
                               fig.TEST_CODE_DEMUX))
            test_setup.append((fig.TEST_MIXED_SUBJECT,
                               'mixed',
                               fig.TEST_MIXED_SPECIMEN,
                               fig.TEST_USER,
                               'Test_Mixed',
                               testing,
                               fig.TEST_CODE_MIXED))
            # Upload OTU if running test_tools.py
            # Functionality removed in study-sequencing run split
            """
            test_otu = (fig.TEST_SUBJECT_SHORT,
                        'human',
                        fig.TEST_SPECIMEN_SHORT,
                        fig.TEST_DIR,
                        fig.TEST_USER,
                        'Test_SparCC',
                        fig.TEST_OTU,
                        fig.TEST_CODE_OTU)
            assert 0 == upload_otu(test_otu)
            # Upload Lefse data if running test_tools.py
            test_lefse = (fig.TEST_SUBJECT_SHORT,
                          'human',
                          fig.TEST_SPECIMEN_SHORT,
                          fig.TEST_DIR,
                          fig.TEST_USER,
                          'Test_Lefse',
                          fig.TEST_LEFSE,
                          fig.TEST_CODE_LEFSE)
            assert 0 == upload_lefse(test_lefse)
            """
    if 'database' in tests:
        test_setup.append((fig.TEST_SUBJECT,
                           'human',
                           fig.TEST_SPECIMEN_SINGLE,
                           fig.TEST_USER,
                           'Test_Single',
                           testing,
                           fig.TEST_CODE))
        test_setup.append((fig.TEST_ANIMAL_SUBJECT,
                           'animal',
                           fig.TEST_SPECIMEN_ANIMAL,
                           fig.TEST_USER,
                           'Test_Animal_Single',
                           testing,
                           fig.TEST_CODE))
        test_setup.append((fig.TEST_SUBJECT_ALT,
                           'human',
                           fig.TEST_SPECIMEN_ALT_0,
                           fig.TEST_USER_0,
                           'Test_Single_0',
                           testing,
                           fig.TEST_CODE + '0'))

    for setup in test_setup:
        print(setup)
        assert 0 == upload_metadata(setup)


def run_tests(tests, pudb):
    print("running tests")
    test_class = []
    for test in tests:
        test_class.append(test.capitalize() + 'Test')
    test_directory = Path(__file__).parent.resolve()
    if pudb:
        run(['pytest', '--cov=mmeds', '--pudb', '-W', 'ignore::DeprecationWarning', '-W', 'ignore::FutureWarning',
             '-s', test_directory, '-x', '-k', ' or '.join(test_class), '--durations=0'], check=True)
    else:
        run(['pytest', '--cov=mmeds', '-W', 'ignore::DeprecationWarning', '-W',
             'ignore::FutureWarning', test_directory, '-k', ' or '.join(test_class), '--durations=0'], check=True)


def remove_users(users_added):
    # Remove users when done
    if users_added >= 1:
        remove_user(fig.TEST_USER, testing=testing)
        if users_added == 2:
            remove_user(fig.TEST_USER_0, testing=testing)


def main():
    # Grab the arguments passed to the script, skipping the script itself
    tests = sys.argv[1:]
    pudb = 'log' in tests
    if pudb:
        tests.remove('log')

    setup = 'setup' in tests
    if setup:
        tests.remove('setup')

    cleanup = 'cleanup' in tests
    if cleanup:
        tests.remove('cleanup')

    if not tests:
        tests = [
            'analysis',
            'authentication',
            'database',
            'documents',
            'spawn',
            'demultiplex',
            'tool',
            'tools',
            'util',
            'validate',
            'formatter',
            'adder',
            'uploader',
            'error'
        ]

    users_added = add_users(tests)
    # Logic to allow for setting up or cleaning up tests without running them
    if not cleanup:
        setup_tests(tests)
    if not setup:
        if not cleanup:
            run_tests(tests, pudb)
        remove_users(users_added)


if __name__ == '__main__':
    main()
