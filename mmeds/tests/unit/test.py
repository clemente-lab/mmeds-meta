from subprocess import run
from pathlib import Path
import sys

from mmeds.authentication import add_user, remove_user
from mmeds.database import upload_metadata, upload_otu

import mmeds.config as fig
import mmeds.secrets as sec

"""
- To run all the tests: python test.py
- To run a specific set of test: python test.py test_name1 test_name2 etc
  - possible test names: authentication, database, documents, spawn, tool, tools, util, validate
- To run all tests with error log output: python test.py log
  - gives output as wanted for Travis CI
"""

testing = True
log = False


def main():
    global log
    log = 'log' in sys.argv
    tests = set_tests(sys.argv)
    users_added = add_users(tests)
    setup_tests(tests)
    run_tests(tests)
    remove_users(users_added)


def set_tests(sys_args):
    tests = sys.argv[1:]
    if 'log' in tests:
        tests.remove('log')
    # if there are no specific tests passed, then run all of them
    if len(tests) == 0:
        tests = ['authentication', 'database', 'documents', 'spawn', 'tool', 'tools', 'util', 'validate']
    return tests


def add_users(tests):
    # Add users as needed
    # users_added keeps track of the number of users added so they can all be removed at the end
    users_added = 0
    if 'database' in tests or 'documents' in tests or 'spawn' in tests or\
            'tool' in tests or 'tools' in tests:
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=testing)
        users_added += 1
    # database and spawn tests require a second user
    if 'database' in tests or 'spawn' in tests:
        add_user(fig.TEST_USER_0, sec.TEST_PASS, fig.TEST_EMAIL, testing=testing)
        users_added += 1
    return users_added


def setup_tests(tests):
    # Add test setups as needed:
    test_setup = []
    if 'documents' in tests or 'tool' in tests or 'tools' in tests:
        test_setup.append((fig.TEST_SUBJECT_SHORT,
                           fig.TEST_SPECIMEN_SHORT,
                           fig.TEST_DIR,
                           fig.TEST_USER,
                           'Test_Single_Short',
                           'single_end',
                           'single_barcodes',
                           fig.TEST_READS,
                           None,
                           fig.TEST_BARCODES,
                           fig.TEST_CODE_SHORT))
        if 'tools' in tests:
            test_setup.append((fig.TEST_SUBJECT_SHORT,
                               fig.TEST_SPECIMEN_SHORT,
                               fig.TEST_DIR,
                               fig.TEST_USER,
                               'Test_Paired',
                               'paired_end',
                               'single_barcodes',
                               fig.TEST_READS,
                               fig.TEST_REV_READS,
                               fig.TEST_BARCODES,
                               fig.TEST_CODE_PAIRED))
            test_setup.append((fig.TEST_SUBJECT_SHORT,
                               fig.TEST_SPECIMEN_SHORT,
                               fig.TEST_DIR,
                               fig.TEST_USER,
                               'Test_Demuxed',
                               'single_end_demuxed',
                               'single_barcodes',
                               fig.TEST_DEMUXED,
                               None,
                               fig.TEST_BARCODES,
                               fig.TEST_CODE_DEMUX))
            # Upload OTU if running test_tools.py
            test_otu = (fig.TEST_SUBJECT_SHORT,
                        fig.TEST_SPECIMEN_SHORT,
                        fig.TEST_DIR,
                        fig.TEST_USER,
                        'Test_SparCC',
                        fig.TEST_OTU,
                        fig.TEST_CODE_OTU)
            assert 0 == upload_otu(test_otu)
    if 'database' in tests:
        test_setup.append((fig.TEST_SUBJECT,
                           fig.TEST_SPECIMEN,
                           fig.TEST_DIR,
                           fig.TEST_USER,
                           'Test_Single',
                           'single_end',
                           'single_barcodes',
                           fig.TEST_READS,
                           None,
                           fig.TEST_BARCODES,
                           fig.TEST_CODE))
        test_setup.append((fig.TEST_SUBJECT_ALT,
                           fig.TEST_SPECIMEN_ALT,
                           fig.TEST_DIR_0,
                           fig.TEST_USER_0,
                           'Test_Single_0',
                           'single_end',
                           'single_barcodes',
                           fig.TEST_READS,
                           None,
                           fig.TEST_BARCODES,
                           fig.TEST_CODE + '0'))
    for setup in test_setup:
        assert 0 == upload_metadata(setup)


def run_tests(tests):
    test_class = []
    for test in tests:
        test_class.append(test.capitalize() + 'Test')
    test_directory = Path(__file__).parent.resolve()
    if not log:
        run(['pytest', '--cov=mmeds', '-W', 'ignore::DeprecationWarning', '-W',
             'ignore::FutureWarning', test_directory, '-k', ' or '.join(test_class), '--durations=0'])
    else:
        run(['pytest', '--cov=mmeds', '-W', 'ignore::DeprecationWarning', '-W', 'ignore::FutureWarning',
             '-s', test_directory, '-x', '-k', ' or '.join(test_class), '--durations=0'])


def remove_users(users_added):
    # Remove users when done
    if users_added >= 1:
        remove_user(fig.TEST_USER, testing=testing)
        if users_added == 2:
            remove_user(fig.TEST_USER_0, testing=testing)


if __name__ == '__main__':
    main()
