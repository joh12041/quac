#!/bin/bash

# This is the basic configuration

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --fields { tx } { ds } { ln } { lo } { tz } \
    --unify-fields { 0 , 1 } \
    --start $START \
    --end $END \
    --training P2D \
    --testing P1D \
    --stride P1D \
    --cores $CORE_CT \
    --verbose \
    $GEODB $JOBDIR/@id
