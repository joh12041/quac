#!/bin/bash

# Train on T14, Test on T15

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 120000 \
    --train-tweet-limit 30000 \
    --start $START \
    --end $END \
    --training P1D \
    --testing P3D \
    --gap P224D \
    --stride P227D \
    --cores $CORE_CT \
    --limit 1 \
    --skip-small-tests 0 \
    --verbose \
    --ses random \
    --how_filter random \
    --filter_testing 0 \
    $GEODB $JOBDIR/rand_te120k_testacrossDBs
