#! /bin/bash

set -xe

mypy .
flake8 .
black --check .
isort --check .
