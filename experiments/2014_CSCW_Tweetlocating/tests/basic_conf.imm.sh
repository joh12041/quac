#!/bin/bash

# This is the basic configuration

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --start $START \
    --end $END \
    --training P4D \
    --testing P2D \
    --stride P1D \
    --cores $CORE_CT \
    --skip-small-tests 0 \
    --verbose \
    $GEODB $JOBDIR/test_geo
