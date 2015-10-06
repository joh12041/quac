__author__ = 'isaac'

import argparse
import os
import u
import csv
import json
from shapely.geometry import shape
import numpy
#from django.contrib.gis import geos

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('results_folders',
                    nargs='+',
                    help='folder containing pickled results objects')
    ap.add_argument('output_user_csv',
                    help='path to csv containing users from this model, their cae, and predication area')
    ap.add_argument('compare_user_confidence',
                    type=int,
                    default=0,
                    help='folder containing pickled results objects')
    args = ap.parse_args()

    geometries_fn = "/export/scratch2/isaacj/geometries/county_ct_mapping"
    counties = generate_counties_to_ct_dict(geometries_fn)

    if args.compare_user_confidence:
        assert len(args.results_folder) == 2, "If comparing model results, can only compare between two models right now"
        filenames = []
        for folder in args.results_folder:
            folder_fns = []
            fns = os.listdir(folder)
            for fn in fns:
                if u.PICKLE_SUFFIX in fn and 'results' in fn:
                    folder_fns.append(folder + fn)
            filenames.append(folder_fns)
        compare_user_confidence_results(filenames)

    for folder in args.results_folder:
        fns = os.listdir(folder)
        for fn in fns:
            users = []
            if u.PICKLE_SUFFIX in fn and 'results' in fn:
                tweets = u.pickle_load(folder + fn)
                for tweet_result in tweets:
                    username = tweet_result.tweet.user_screen_name
                    tid = tweet_result.tweet.id
                    pa95 = tweet_result.location_estimate.pred_area
                    sae = tweet_result.sae
                    users.append([username, tid, pa95, sae])

def compare_user_confidence_results(filenames):
    users = {}
    for fn in filenames[0]:
        tweets = u.pickle_load(fn)
        for tweet_result in tweets:
            username = tweet_result.tweet.user_screen_name
            tid = tweet_result.tweet.id
            pa95 = tweet_result.location_estimate.pred_area
            sae = tweet_result.sae
            if (username, tid) in users:
                if sae < users[(username, tid)][1]:
                    users[(username, tid)] = (pa95, sae)
            else:
                users[(username, tid)] = (pa95, sae)
    agreed = 0
    disagreed = 0
    distance_disagreed = []
    for fn in filenames[1]:
        tweets = u.pickle_load(fn)
        for tweet_result in tweets:
            username = tweet_result.tweet.user_screen_name
            tid = tweet_result.tweet.id
            if (username, tid) in users:
                pa95_smaller = tweet_result.location_estimate.pred_area < users[(username, tid)][0]
                sae_smaller = tweet_result.sae < users[(username, tid)][1]
                if pa95_smaller and sae_smaller:
                    agreed += 1
                elif not pa95_smaller and not sae_smaller:
                    agreed += 1
                else:
                    disagreed += 1
                    distance_disagreed.append(abs(tweet_result.sae - users[(username, tid)][1]))
    print("{0} tweets lined up with a smaller 95% prediction area = smaller sae between models and {1} disagreed.".format(agreed, disagreed))
    print("{0} median difference in SAE for disagreements.".format(numpy.median(distance_disagreed)))
    print("{0} average difference in SAE for disagreements.".format(numpy.average(distance_disagreed)))
    print("{0} 1st quartile difference in SAE for disagreements.".format(numpy.percentile(distance_disagreed, 0.25)))
    print("{0} 3rd quartile difference in SAE for disagreements.".format(numpy.percentile(distance_disagreed, 0.75)))

def generate_counties_to_ct_dict(geometries_fn):
    if not os.path.exists(geometries_fn + u.PICKLE_SUFFIX):
        counties_gj_fn = "/export/scratch2/isaacj/geometries/USCounties_bare.geojson"
        with open(counties_gj_fn, 'r') as fin:
            counties_gj = json.load(fin)

        ct_to_atts = {}
        ct_hmi_fn = "/export/scratch2/isaacj/geometries/ct_hmi.csv"
        with open(ct_hmi_fn, 'r') as fin:
            csvreader = csv.reader(fin)
            assert next(csvreader) == ['ID','County_FIPS','Name','HMI_ACS5YR2013']
            for line in csvreader:
                ct = line[0]
                try:
                    hmi = int(line[3])
                except:
                    hmi = None
                ct_to_atts[ct] = {'hmi': hmi}
        print("{0} census tracts loaded.".format(len(ct_to_atts)))

        ct_race_pop_fn = "/export/scratch2/isaacj/geometries/us_ct_raceetc.geojson"
        with open(ct_race_pop_fn, 'r') as fin:
            ct_gj = json.load(fin)
        # NOTE: hisp_lat and white are no exclusive - we test hisp_lat first and so favor a CT = hisp_lat over that CT = white
        race_cols = [('hisp_lat','DP0100002'), ('white','DP0080003'), ('black','DP0080004'), ('asian','DP0080006')]
        count_predomraces = {'white':0, 'black':0, 'asian':0, 'hisp_lat':0, 'total':0}
        for ct in ct_gj['features']:
            fips = ct['properties']['GEOID10']
            if fips in ct_to_atts:
                totalpop = int(ct['properties']['DP0010001'])
                predom_race = None
                count_predomraces['total'] += 1
                for race in race_cols:
                    try:
                        if float(ct['properties'][race[1]]) / totalpop >= 0.9:
                            predom_race = race[0]
                            count_predomraces[race[0]] += 1
                            break
                    except:
                        continue
                ct_to_atts[fips]['pop'] = totalpop
                ct_to_atts[fips]['predom_race'] = predom_race
        print('CTs assigned a race: {0}'.format(count_predomraces))

        ct_geog_fn = "/export/scratch2/isaacj/geometries/us_ct.geojson"
        with open(ct_geog_fn, 'r') as fin:
            ct_gj = json.load(fin)

        counties = {}
        count_skipped = 0
        count_processed = 0
        for county in counties_gj['features']:
            fips = county['properties']['FIPS']
            counties[fips] = {'shape':shape(county['geometry']), 'ct':[]}
            for ct in ct_gj['features']:
                ct_county = ct['properties']['STATE_FIPS'] + ct['properties']['CNTY_FIPS']
                ct_fips = ct['properties']['FIPS']
                if ct_county == fips:
                    try:
                        counties[fips]['ct'].append({'shape' : shape(ct['geometry']),
                                                     'pop' : ct_to_atts[ct_fips]['pop'],
                                                     'hmi' : ct_to_atts[ct_fips]['hmi'],
                                                     'race' : ct_to_atts[ct_fips]['predom_race']})
                    except:
                        count_skipped += 1
                        continue
            count_processed += 1
            if count_processed % 100 == 0:
                print("{0} counties processed.".format(count_processed))

        u.pickle_dump(geometries_fn, counties)
        print("{0} skipped out of {1}".format(count_skipped, len(ct_gj['features'])))
        return counties
    else:
        return u.pickle_load(geometries_fn)


if __name__ == "__main__":
    compare_user_confidence_results([['data/geo/tr_urbanonly30k_te_rand120k/results.0.pkl.gz'],['data/geo/tr_ruralonly30k_te_rand120k/results.0.pkl.gz']])