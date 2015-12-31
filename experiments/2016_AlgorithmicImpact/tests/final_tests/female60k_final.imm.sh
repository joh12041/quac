#!/bin/bash

# Train on male-only, Train on female-only

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 60000 \
    --train-tweet-limit 60000 \
    --start $START \
    --end $END \
    --training P3D \
    --testing P3D \
    --gap P1D \
    --stride P3D \
    --cores $CORE_CT \
    --limit 3 \
    --skip-small-tests 0 \
    --verbose \
    --ses gender \
    --how_filter female-only \
    --filter_testing 0 \
    $GEODB $JOBDIR/tr_femaleonly60k_te_rand60k