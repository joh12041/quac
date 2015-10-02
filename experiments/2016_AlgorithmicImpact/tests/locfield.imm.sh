#!/bin/bash

# Train on tweets considered local via geometric median only, test on random

. $(dirname $0)/parseargs.sh

model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 120000 \
    --train-tweet-limit 30000 \
    --start $START \
    --end $END \
    --training P6D \
    --testing P8D \
    --gap P1D \
    --stride P14D \
    --cores $CORE_CT \
    --limit 1 \
    --skip-small-tests 0 \
    --verbose \
    --ses localness \
    --how_filter random \
    --filter_testing 0 \
    $GEODB $JOBDIR/tr_locfieldonly30k_te_rand120k


model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 120000 \
    --train-tweet-limit 30000 \
    --start $START \
    --end $END \
    --training P6D \
    --testing P8D \
    --gap P1D \
    --stride P14D \
    --cores $CORE_CT \
    --limit 1 \
    --skip-small-tests 0 \
    --verbose \
    --ses pop_pct \
    --how_filter random \
    --filter_testing 0 \
    $GEODB $JOBDIR/tr_popbalanced30k_te_rand120k


model-test \
    --min-instances 3 \
    --model geo.gmm.Token \
    --model-parms weight_f:wt_inv_error_sae \
    --test-tweet-limit 120000 \
    --train-tweet-limit 30000 \
    --start $START \
    --end $END \
    --training P6D \
    --testing P8D \
    --gap P1D \
    --stride P14D \
    --cores $CORE_CT \
    --limit 1 \
    --skip-small-tests 0 \
    --verbose \
    --ses senate \
    --how_filter random \
    --filter_testing 0 \
    $GEODB $JOBDIR/tr_senate30k_te_rand120k