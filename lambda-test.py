#!/usr/bin/env python3

# Not a unit test, just a small utility that runs our lambda funtion with a
# specific input.

from topowiz import lambda_function

import json
import os
import sys

_PATH = "topowiz/tests/data"

def get_available_tests():
    """
    Return all test data files for Lambda.

    The correct files are recognized by their filename, which starts with
    'lambda'.

    """
    return [f for f in os.listdir(_PATH) if f.startswith("lambda")]

available_tests = get_available_tests()

if not len(sys.argv) == 2 or sys.argv[1] not in available_tests:
    print("Error! Please specify one of the available tests as argument:")
    for at in available_tests:
        print("    - %s" % at)
    sys.exit(1)

chosen_file = "%s/%s" % (_PATH, sys.argv[1])

event = json.loads(open(chosen_file, "r").read())

lambda_function.lambda_handler(event, None)

