#!/bin/bash

# This is the basic configuration

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 120000 \
    --start $START \
    --end $END \
    --training P10D \
    --testing P18D \
    --stride P28D \
    --cores $CORE_CT \
    --skip-small-tests 0 \
    --verbose \
    --ses random \
    --how_filter expected \
    $GEODB $JOBDIR/pop_random_120k_t60k

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 120000 \
    --start $START \
    --end $END \
    --training P10D \
    --testing P18D \
    --stride P28D \
    --cores $CORE_CT \
    --skip-small-tests 0 \
    --verbose \
    --ses pop_pct \
    --how_filter balanced \
    $GEODB $JOBDIR/pop_balanced_120k_t60k

