#!/bin/bash

# Train on random 30k, test on random 120k as baseline

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --fields tx ln lo tz ds \
    --test-tweet-limit 120000 \
    --train-tweet-limit 30000 \
    --start $START \
    --end $END \
    --training P4D \
    --testing P6D \
    --gap P1D \
    --stride P10D \
    --cores $CORE_CT \
    --limit 1 \
    --skip-small-tests 0 \
    --verbose \
    --ses random \
    --how_filter random \
    --filter_testing 0 \
    $GEODB $JOBDIR/tr_rand30k_te_rand120k