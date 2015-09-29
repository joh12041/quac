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
    --training P1D \
    --testing P1D \
    --stride P28D \
    --cores $CORE_CT \
    --skip-small-tests 0 \
    --verbose \
    --ses random \
    --how_filter random \
    --filter_testing True \
    $GEODB $JOBDIR/rand_te120k_fulldbT14
