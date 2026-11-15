#!/usr/bin/env python
"""
Run the test suite.

    python runtests.py                       # all tests
    python runtests.py tests.test_bootstrap  # a module, class or method
    python runtests.py -v 2                  # more verbose output

See "Using the Django test runner to test reusable applications":
https://docs.djangoproject.com/en/stable/topics/testing/advanced/#using-the-django-test-runner-to-test-reusable-applications
"""
import argparse
import os
import sys

import django
from django.conf import settings
from django.test.utils import get_runner


def main():
    parser = argparse.ArgumentParser(description="Run the django-htmx-datatable test suite.")
    parser.add_argument("labels", nargs="*", default=["tests"], help="test labels (default: tests)")
    parser.add_argument("-v", "--verbosity", type=int, default=1, choices=[0, 1, 2, 3])
    args = parser.parse_args()

    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=args.verbosity)
    failures = test_runner.run_tests(args.labels)
    sys.exit(bool(failures))


if __name__ == "__main__":
    main()
