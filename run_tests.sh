#!/bin/bash

# Run unit tests and create a coverage report.
#
# To run the test suite for the entire package, don't specify any options:
#
#    $ ./run_tests.sh
#
# To run all tests in a specific test file, use the module path or file path:
#
#    $ ./run_tests.sh topowiz.tests.test_utils
#
#        or
#
#    $ ./run_tests.sh topowiz/tests/test_utils.py
#
# To run just one test case from the test file, add the class name:
#
#    $ ./run_tests.sh topowiz/tests/test_utils.py:TestBasic
#

rm .coverage*    # cover-erase with multiprocessing seemed to cause issues
                 # (warning messages or some lines not shown as covered)
                 # so deleting old cover files manually instead

nosetests -v --config=nose.cfg --exclude=lambda_test_run.py $@

echo "@@@ Coverage report: file:///tmp/topowiz-coverage/index.html"
echo
