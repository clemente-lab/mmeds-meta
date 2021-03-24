# MMEDS Testing Guide

## Setup
I have an alias for the pytest command I use
`alias pt='pytest --cov=./ -W ignore::DeprecationWarning -W ignore::FutureWarning -s --durations=0'`
this runs pytest with the code coverage extension and the option to show the test durations.

## Unit Tests
There are 'unit' test files for most of the python files in mmeds. Many of these require the same data to be uploaded into the database for the tests to run. To avoid having uploads run multiple times there is a script that handles the setup, running, and teardown of the unit tests.
The file is `mmeds/tests/unit/test.py`. To use it run `python mmeds/tests/unit/test.py`. This will perform the setup, run all the tests, and perform the cleanup. It also accepts arguments. For example. If you only want to run `mmeds/tests/unit/test_database.py` you can execute `python mmeds/tests/unit/test.py database`. You can run any combo of the different tests.
If a test is failing the additional layer of python that `test.py` creates can make it more difficult to find the issue. For this reason you can specify that `test.py` only perform the setup by passing in `setup` to `test.py` and then run the test directly. For `test_database.py` this would look like:
1) `python mmeds/tests/unit/test.py database setup`
2) `pt mmeds/tests/unit/test_database.py --pudb` (`--pudb` adds the pudb3 extension to pytest so it'll drop you into the debugger when a test fails)
3) `python mmeds/tests/unit/test.py database cleanup`

Note: If a test fails, it can often leave things in either the mysql or mongodb database which may cause other tests to fail so it's important to run cleanup. If that doesn't resolve the issue you can use the script `python scripts/wipe_database.py 1`. This will delete everything in both the mongo and mysql databases. The `1` indicates to this script that it's running under the 'testing' setup (i.e. not on Minerva). You can also pass a username to the script if you only want to delete data for a particular use (e.g. `python scripts/wipe_database.py 1 David`)


Note:
For `test_spawn.py` to pass, the watcher needs to be running as it tests the watcher's behavior. So be sure to start the watcher before running this test (or all the tests if you're running the full suite). When `test_spawn.py` finishes it'll send a signal to the watcher for it to terminate, so you'll need to start it again for the next test run.

## Server Tests
The server tests are simpler. There is a single pytest file `mmeds/tests/server/test_server.py` that contains the current server tests.
To run the server tests, start the watcher then execute `pt mmeds/tests/server/test_server.py`.

Note:
One of the most common errors from these tests is having a page that doesn't match what's expected. If this happens the test window will output the html from each page to the terminal and say they don't match. This is very hard to read as a human, so I setup the tests to write the html to a file when it's comparing the pages. While the tests are still stopped at the pages that don't match run the command `vim -d /tmp/good_page.html /tmp/bad_page.html`. This will open both the desired html (good_page.html) and the actual html produced by the server (bad_page) in vim with the differences between them highlighted.
