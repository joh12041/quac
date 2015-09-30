#!/bin/bash

# Test mapping on 200 tweets (fast)

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 200 \
    --train-tweet-limit 1000 \
    --start $START \
    --end $END \
    --training P1D \
    --testing P1D \
    --gap P1D \
    --stride P2D \
    --cores $CORE_CT \
    --limit 1 \
    --skip-small-tests 0 \
    --verbose \
    --ses random \
    --how_filter random \
    --filter_testing 0 \
    $GEODB $JOBDIR/testing_temp_delete
