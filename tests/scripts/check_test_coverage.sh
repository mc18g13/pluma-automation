#!/bin/bash
this_dir="$(dirname $0)"
test_dir="$(readlink -f $this_dir/..)"
farmcore_dir="$(pip3 show pluma | awk -F': ' '/Location/ {print $2}')"

if [ -z "${farmcore_dir}" ]; then
    echo 'Cannot find pip3 package "pluma". Is it installed?'
    exit 1
fi

if [ ! -z "$1" ]; then
    test_dir="$(readlink -f $this_dir/../$1)"

    if [ ! -e "$test_dir" ]; then
        echo "No such file or directory: $test_dir"
        exit 1
    fi

    echo "Running only tests in $test_dir"
else
    echo "Running all tests in $test_dir"
fi

python3 -m pytest --cov=$farmcore_dir --cov-report=term-missing $test_dir