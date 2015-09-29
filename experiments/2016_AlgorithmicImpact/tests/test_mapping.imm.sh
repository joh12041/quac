#!/bin/bash

# This is the basic configuration

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 200 \
    --start $START \
    --end $END \
    --training P1D \
    --testing P1D \
    --stride P2D \
    --cores $CORE_CT \
    --skip-small-tests 0 \
    --limit 1 \
    --verbose \
    --ses pop_pct \
    --how_filter balanced \
    $GEODB $JOBDIR/model_testing

