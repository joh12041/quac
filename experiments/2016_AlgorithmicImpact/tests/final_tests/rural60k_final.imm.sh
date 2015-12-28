#!/bin/bash

# Train only rural (5-6)

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 60000 \
    --train-tweet-limit 60000 \
    --start $START \
    --end $END \
    --training P6D \
    --testing P4D \
    --gap P1D \
    --stride P2D \
    --cores $CORE_CT \
    --limit 3 \
    --skip-small-tests 0 \
    --verbose \
    --ses urban \
    --how_filter ruralf \
    --filter_testing 0 \
    $GEODB $JOBDIR/tr_ruralonly60k_te_rand60k
