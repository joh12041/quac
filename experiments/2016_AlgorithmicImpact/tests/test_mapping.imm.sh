#!/bin/bash

# This is the basic configuration

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 1000 \
    --start $START \
    --end $END \
    --training P2D \
    --testing P3D \
    --stride P5D \
    --cores $CORE_CT \
    --skip-small-tests 0 \
    --limit 1 \
    --verbose \
    --ses pop_pct \
    --how_filter balanced \
    $GEODB $JOBDIR/model_testing

