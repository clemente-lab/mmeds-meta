from subprocess import run, Popen
from pathlib import Path
import sys
import coverage

from mmeds.authentication import add_user, remove_user
from mmeds.util import setup_environment
from mmeds.spawn import Watcher

import mmeds.config as fig
import mmeds.secrets as sec

"""
- To run all the tests: python test.py
- To run a specific set of test: python test.py test_name1 test_name2 etc
  - possible test names: authentication, database, documents, spawn, snakemake, tools, util, validate
- To run all tests with the pudb pytest plugin python test.py pudb
"""

testing = True
coverage.process_startup()


def add_users(tests):
    # Add users as needed
    # users_added keeps track of the number of users added so they can all be removed at the end
    users_added = 0
    if {'database', 'documents', 'util', 'spawn', 'tools', 'formatter', 'adder', 'analysis'}.intersection(tests):
        add_user(fig.TEST_USER, sec.TEST_PASS, fig.TEST_EMAIL, testing=testing)
        users_added += 1
    # database and spawn tests require a second user
    if 'database' in tests or 'spawn' in tests or 'tools' in tests or 'analysis' in tests:
        add_user(fig.TEST_USER_0, sec.TEST_PASS, fig.TEST_EMAIL, testing=testing)
        users_added += 1
    return users_added


def setup_tests(tests):
    # Add test setups as needed:
    test_studies = []
    test_metadata = []
    test_setup = []
    if {'documents', 'util', 'tools', 'formatter', 'adder', 'analysis'}.intersection(tests):
        test_studies.append(('create-study',
                             'Test_Single_Short',
                             'human',
                             fig.TEST_USER,
                             False,
                             False))
        test_studies.append(('create-study',
                             'Test_Paired',
                             'human',
                             fig.TEST_USER,
                             False,
                             False))
        test_metadata.append(("upload-metadata",
                              None,
                              fig.TEST_SUBJECT_SHORT,
                              fig.TEST_SPECIMEN_SINGLE_SHORT,
                              "human",
                              fig.TEST_USER,
                              False,
                              False,
                              False))
        test_metadata.append(("upload-metadata",
                              None,
                              fig.TEST_SUBJECT_SHORT,
                              fig.TEST_SPECIMEN_PAIRED,
                              "human",
                              fig.TEST_USER,
                              False,
                              False,
                              False))
        if 'tools' in tests or 'analysis' in tests:
            test_studies.append(('create-study',
                                 'Test_Demuxed',
                                 'human',
                                 fig.TEST_USER,
                                 False,
                                 False))
            test_studies.append(('create-study',
                                 'Test_MIXED_17',
                                 'mixed',
                                 fig.TEST_USER_0,
                                 False,
                                 False))
            test_metadata.append(("upload-metadata",
                                  None,
                                  fig.TEST_SUBJECT_SHORT,
                                  fig.TEST_SPECIMEN_DEMUXED,
                                  "human",
                                  fig.TEST_USER,
                                  False,
                                  False,
                                  False))
            test_metadata.append(("upload-metadata",
                                  None,
                                  fig.TEST_MIXED_SUBJECT,
                                  fig.TEST_MIXED_SPECIMEN,
                                  "mixed",
                                  fig.TEST_USER_0,
                                  False,
                                  False,
                                  False))
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
    if test_studies:
        watcher = Watcher()
        watcher.connect()
        queue = watcher.get_queue()
        pipe = watcher.get_pipe()

    study_docs = []
    for study in test_studies:
        print(study)
        queue.put(study)
        doc_pipe_out = pipe.recv()
        study_docs.append(doc_pipe_out["access_code"])
        exit_code_pipe_out = pipe.recv()
        assert exit_code_pipe_out == 0

    assert len(study_docs) == len(test_metadata)
    for metadata, doc in zip(test_metadata, study_docs):
        metadata = list(metadata)
        metadata[1] = doc
        metadata = tuple(metadata)
        print(metadata)
        queue.put(metadata)
        doc_pipe_out = pipe.recv()
        exit_code_pipe_out = pipe.recv()
        assert exit_code_pipe_out == 0


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
    # Start the watcher as a subprocess if we're on github actions
    if Path("/home/runner").exists():
        Popen(['python', './mmeds/host/manager.py'], env=setup_environment("mmeds-stable"))
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
            'tools',
            'util',
            'validate',
            'formatter',
            'adder',
            'uploader',
            'error',
            'snakemake'
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
