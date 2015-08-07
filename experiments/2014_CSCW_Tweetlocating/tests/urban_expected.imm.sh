#!/bin/bash

# This is the basic configuration

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 60000 \
    --start $START \
    --end $END \
    --training P8D \
    --testing P12D \
    --stride P20D \
    --cores $CORE_CT \
    --skip-small-tests 0 \
    --verbose \
    --ses urban \
    --how_filter Random \
    $GEODB $JOBDIR/urban_random
