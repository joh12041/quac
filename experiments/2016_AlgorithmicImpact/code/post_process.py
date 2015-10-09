__author__ = 'isaac'

import argparse
import os
import u
import csv
import json
from shapely.geometry import shape
import numpy
import collections
#from django.contrib.gis import geos
import traceback

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

def compare_user_confidence_results():
    groups = [['rural','urban'],['male','female']]
    for to_compare in groups:
        folders = ['/export/scratch2/isaacj/Johnson_quac/data/geo/tr_{0}only30k_te_rand120k'.format(tc) for tc in to_compare]
        first = [os.path.join(folders[0], f) for f in os.listdir(folders[0]) if 'results' in f and u.PICKLE_SUFFIX in f]
        second = [os.path.join(folders[1], f) for f in os.listdir(folders[1]) if 'results' in f and u.PICKLE_SUFFIX in f]
        users = {}
        print("Loading in {0} results.".format(to_compare[0]))
        for fn in first:
            tweets = u.pickle_load(fn)
            for tweet_result in tweets:
                if tweet_result.location_estimate:
                    username = tweet_result.tweet.user_screen_name
                    tid = tweet_result.tweet.id
                    pa95 = tweet_result.location_estimate.pred_area
                    sae = tweet_result.cae
                    if (username, tid) in users:
                        if sae < users[(username, tid)][1]:
                            users[(username, tid)] = (pa95, sae)
                    else:
                        users[(username, tid)] = (pa95, sae)
        agreed = 0
        disagreed = 0
        distance_disagreed = []
        print("Loading in {0} results.".format(to_compare[1]))
        for fn in second:
            tweets = u.pickle_load(fn)
            for tweet_result in tweets:
                username = tweet_result.tweet.user_screen_name
                tid = tweet_result.tweet.id
                if (username, tid) in users:
                    if tweet_result.location_estimate:
                        pa95_smaller = tweet_result.location_estimate.pred_area < users[(username, tid)][0]
                        sae_smaller = tweet_result.cae < users[(username, tid)][1]
                        if pa95_smaller and sae_smaller:
                            agreed += 1
                        elif not pa95_smaller and not sae_smaller:
                            agreed += 1
                        else:
                            disagreed += 1
                            distance_disagreed.append(abs(tweet_result.cae - users[(username, tid)][1]))
        print("{0} tweets lined up with a smaller 95% prediction area = smaller sae between models and {1} disagreed.".format(agreed, disagreed))
        print("{0} median difference in SAE for disagreements.".format(numpy.median(distance_disagreed)))
        print("{0} average difference in SAE for disagreements.".format(numpy.average(distance_disagreed)))
        print("{0} 1st quartile difference in SAE for disagreements.".format(numpy.percentile(distance_disagreed, 25)))
        print("{0} 3rd quartile difference in SAE for disagreements.".format(numpy.percentile(distance_disagreed, 75)))

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
                if len(ct) == 10:
                    ct = '0' + ct
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
        cts_added = 0
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
                        cts_added += 1
                    except Exception:
                        count_skipped += 1
            count_processed += 1
            if count_processed % 100 == 0:
                print("{0} counties processed and {1} CTs skipped and {2} added.".format(count_processed, count_skipped, cts_added))

        u.pickle_dump(geometries_fn, counties)
        print("{0} skipped out of {1} and {2} added".format(count_skipped, len(ct_gj['features']), cts_added))
        return counties
    else:
        return u.pickle_load(geometries_fn)


def aggregate_results():
    ap = argparse.ArgumentParser()
    ap.add_argument('results_folders',
                    nargs='+',
                    help='folder containing pickled results objects')
    args = ap.parse_args()

    for folder in args.results_folders:
        files = os.listdir(folder)
        binned_test_fns = [os.path.join(folder, f) for f in files if 'binned.csv' in f and 'failed' not in f and 'test' in f]
        binned_training_fns = [os.path.join(folder, f) for f in files if 'binned.csv' in f and 'failed' not in f and 'training' in f]
        county_test_fns = [os.path.join(folder, f) for f in files if '.csv' in f and 'test' in f and 'failed' not in f and 'b' not in f]
        county_training_fns = [os.path.join(folder, f) for f in files if '.csv' in f and 'training' in f and 'failed' not in f and 'b' not in f]

        counties = {}
        # aggregate testing counts for each county
        for county_test_fn in county_test_fns:
            with open(county_test_fn, 'r') as fin:
                csvreader = csv.reader(fin)
                header = next(csvreader)
                fips_idx = header.index('FIPS')
                count_idx = header.index('count_tweets')
                wicounty_idx = header.index('within_county')
                wi100km_idx = header.index('within_100km')
                for line in csvreader:
                    fips = line[fips_idx]
                    count = int(line[count_idx])
                    wicounty = int(line[wicounty_idx])
                    wi100km = int(line[wi100km_idx])
                    if fips in counties:
                        counties[fips]['count_testing'] += count
                        counties[fips]['count_wi_county'] += wicounty
                        counties[fips]['count_wi_100km'] += wi100km
                    else:
                        counties[fips] = {'fips':fips, 'count_testing':count,
                                          'count_wi_county':wicounty, 'count_wi_100km':wi100km}
        # add in amount of training data for each county
        for county_training_fn in county_training_fns:
            with open(county_training_fn, 'r') as fin:
                csvreader = csv.reader(fin)
                header = next(csvreader)
                fips_idx = header.index('FIPS')
                count_idx = header.index('count_tweets')
                for line in csvreader:
                    fips = line[fips_idx]
                    count = int(line[count_idx])
                    if 'count_training' in counties[fips]:
                        counties[fips]['count_training'] += count
                    else:
                        counties[fips]['count_training'] = count
        # compute percentages for each county
        for fips in counties:
            for stat in ['county','100km']:
                try:
                    counties[fips]['pct_wi_{0}'.format(stat)] = round(counties[fips]['count_wi_{0}'.format(stat)] / counties[fips]['count_testing'], 3)
                except ZeroDivisionError:
                    counties[fips]['pct_wi_{0}'.format(stat)] = 0
            for phase in ['training','testing']:
                try:
                    counties[fips]['avg_{0}'.format(phase)] = round(counties[fips]['count_{0}'.format(phase)] / len(county_test_fns), 3)
                except ZeroDivisionError:
                    counties[fips]['avg_{0}'.format(phase)] = 0
        # write summarized output
        with open(os.path.join(folder, 'summarized_county_stats.csv'), 'w') as fout:
            header = ['fips','count_training','count_testing','avg_training','avg_testing',
                      'count_wi_county','count_wi_100km','pct_wi_county','pct_wi_100km']
            csvwriter = csv.DictWriter(fout, fieldnames=header)
            csvwriter.writeheader()
            od = collections.OrderedDict(sorted(counties.items()))
            for fips in od:
                csvwriter.writerow(od[fips])

        bins = {}
        bin_headers_idx0 = ['age','race','urban','gender']
        current_bin = None
        bin_idx = 0
        for binned_test_fn in binned_test_fns:
            with open(binned_test_fn, 'r') as fin:
                csvreader = csv.reader(fin)
                for line in csvreader:
                    if line[bin_idx] in bin_headers_idx0:
                        current_bin = line[bin_idx]
                        header = line
                        count_idx = header.index('count_tweets')
                        wicounty_idx = header.index('within_county')
                        wi100km_idx = header.index('within_100km')
                        if current_bin not in bins:
                            bins[current_bin] = {'header':[current_bin,'count_training','avg_training','count_testing','avg_testing',
                                                           'count_wi_county', 'count_wi_100km', 'pct_wi_county', 'pct_wi_100km']}
                    else:
                        category = line[bin_idx]
                        count = int(line[count_idx])
                        wicounty = int(line[wicounty_idx])
                        wi100km = int(line[wi100km_idx])
                        if category in bins[current_bin]:
                            bins[current_bin][category]['count_testing'] += count
                            bins[current_bin][category]['count_wi_county'] += wicounty
                            bins[current_bin][category]['count_wi_100km'] += wi100km
                        else:
                            bins[current_bin][category] = {current_bin:category, 'count_testing':count,
                                                                'count_wi_county':wicounty, 'count_wi_100km':wi100km}
        for binned_training_fn in binned_training_fns:
            with open(binned_training_fn, 'r') as fin:
                csvreader = csv.reader(fin)
                for line in csvreader:
                    if line[bin_idx] in bin_headers_idx0:
                        current_bin = line[bin_idx]
                        header = line
                        count_idx = header.index('count_tweets')
                    else:
                        count = int(line[count_idx])
                        category = line[bin_idx]
                        if 'count_training' in bins[current_bin][category]:
                            bins[current_bin][category]['count_training'] += count
                        else:
                            bins[current_bin][category]['count_training'] = count
        # compute percentages/averages for each bin
        for bin in bins:
            for category in bins[bin]:
                if category == 'header':
                    continue
                for stat in ['county','100km']:
                    try:
                        bins[bin][category]['pct_wi_{0}'.format(stat)] = round(bins[bin][category]['count_wi_{0}'.format(stat)] / bins[bin][category]['count_testing'], 3)
                    except ZeroDivisionError:
                        bins[bin][category]['pct_wi_{0}'.format(stat)] = 0
                for phase in ['training','testing']:
                    try:
                        bins[bin][category]['avg_{0}'.format(phase)] = round(bins[bin][category]['count_{0}'.format(phase)] / len(binned_test_fns), 3)
                    except ZeroDivisionError:
                        bins[bin][category]['avg_{0}'.format(phase)] = 0
        # write summarized output
        with open(os.path.join(folder, 'summarized_binned_stats.csv'), 'w') as fout:
            for bin in bins:
                csvwriter = csv.DictWriter(fout, fieldnames=bins[bin]['header'])
                csvwriter.writeheader()
                for category in bins[bin]:
                    if category == 'header':
                        continue
                    csvwriter.writerow(bins[bin][category])
                csvwriter.writerow({})
                fout.flush()



if __name__ == "__main__":
    #generate_counties_to_ct_dict("/export/scratch2/isaacj/geometries/county_ct_mapping")
    print("Aggregating results.")
    aggregate_results()
    print("Comparing opposite models.")
    compare_user_confidence_results()