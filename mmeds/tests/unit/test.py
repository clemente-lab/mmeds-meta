from subprocess import run
import sys
import os

from mmeds.authentication import add_user, remove_user
from mmeds.database import upload_metadata, upload_otu

import mmeds.config as fig
import mmeds.secrets as sec

testing = True 

def main():
    tests = set_tests(sys.argv)
    users_added = add_users(tests)
    setup_tests(tests)
    run_tests(tests)
    remove_users(users_added)

def set_tests(sys_args):
    tests = sys.argv[1:]
    # if there are no specific tests passed, then run all of them
    if len(tests) == 0:
        tests = ['authentication', 'database', 'documents', 'spawn', 'tool', 'tools', 'util', 'validate']
    return tests

def add_users(tests):
    # add users as needed
    # users_added keeps track of the number of users added so they can all be removed at the end
    users_added = 0 
    if ('database' in tests) or ('documents' in tests) or ('spawn' in tests) or ('tool' in tests) or ('tools' in tests):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing = testing)
        users_added += 1
    # database and spawn tests require a second user
    if ('database' in tests) or ('spawn' in tests):
        add_user(fig.TEST_USER_0, sec.TEST_PASS, fig.TEST_EMAIL, testing = testing)
        users_added += 1
    return users_added

def setup_tests(tests):
    # add test setups as needed:
    test_setup = []
    if ('database' in tests) or ('documents' in tests) or ('tool' in tests) or ('tools' in tests):
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
        if 'database' in tests:
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
        if 'tools' in tests:
            test_setup.append((fig.TEST_SUBJECT,
                               fig.TEST_SPECIMEN,
                               fig.TEST_DIR,
                               fig.TEST_USER,
                               'Test_Paired',
                               'paired_end',
                               'single_barcodes',
                               fig.TEST_READS,
                               fig.TEST_REV_READS,
                               fig.TEST_BARCODES,
                               fig.TEST_CODE_PAIRED))
            test_setup.append((fig.TEST_SUBJECT,
                               fig.TEST_SPECIMEN,
                               fig.TEST_DIR,
                               fig.TEST_USER,
                               'Test_Demuxed',
                               'single_end',
                               'single_barcodes',
                               fig.TEST_DEMUXED,
                               None,
                               fig.TEST_BARCODES,
                               fig.TEST_CODE_DEMUX))
            test_otu = (fig.TEST_SUBJECT,
                        fig.TEST_SPECIMEN,
                        fig.TEST_DIR,
                        fig.TEST_USER,
                        'Test_SparCC',
                        fig.TEST_OTU,
                        fig.TEST_CODE_OTU)
            assert 0 == upload_otu(test_otu)
    for setup in test_setup:
        assert 0 == upload_metadata(setup)

def run_tests(tests):
    test_class = []
    for test in tests:
        test_class.append(test.capitalize() + 'Test')
    test_directory = os.path.dirname(os.path.abspath(__file__))
    run(['pytest', test_directory, '-k', ' or '.join(test_class)])

def remove_users(users_added):
    #remove users when done
    if users_added >= 1:
        remove_user(fig.TEST_USER, testing = testing)
        if users_added == 2:
            remove_user(fig.TEST_USER_0, testing = testing)

main()
