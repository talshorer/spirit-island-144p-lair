#! /bin/bash

before=$1
after=$2
shift 2

OUTPUTS="log diff"

for phase in before after; do
    git checkout ${$phase}
    tgt=$phase
    for output in $OUTPUTS; do
        python3 -m lrlr.main "$@" \
            --diff-all --diff-sort-range \
            --output $output --split $tgt-$output
    done
done

for output in $OUTPUTS; do
    diff -urN before-$output after-$output > $output.diff
    code $output.diff
done
