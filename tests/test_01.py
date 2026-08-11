"""
run from the command line with:
    pytest --disable-pytest-warnings -vvv
"""

import subprocess as sp
from os.path import dirname, join


def test_lint():
    base = dirname(dirname(__file__))
    sp.check_output(
        f'black {join(base, "st3")} {join(base, "tests")} {join(base, "main.py")}',
        shell=True,
    )
    sp.check_output(
        "isort --overwrite-in-place --profile black --conda-env requirements.yaml "
        + f'{join(base, "st3")} {join(base, "tests")} {join(base, "main.py")}',
        shell=True,
    )
