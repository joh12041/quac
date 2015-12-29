#!/bin/bash

# Train only urban (1-2)

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 2 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 60000 \
    --train-tweet-limit 30000 \
    --start $START \
    --end $END \
    --training P2D \
    --testing P3D \
    --gap P1D \
    --stride P2D \
    --cores $CORE_CT \
    --limit 3 \
    --skip-small-tests 0 \
    --verbose \
    --ses random \
    --how_filter random \
    --filter_testing 0 \
    $GEODB $JOBDIR/tr_random30kalltokens_te_rand60k
