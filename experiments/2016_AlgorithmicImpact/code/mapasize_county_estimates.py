__author__ = 'joh12041'

import argparse
import json
import csv
import ast

def main():
    ap = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument('counties_geojson',
                default='../geometries/USCounties_bare.geojson',
                help='GeoJSON file containing the counties that will be each row')
    ap.add_argument('tweet_estimates_by_county',
                    help='CSV file (*_wholookslikeSF.csv) containing tweet estimates by county as output by model_test.py')
    ap.add_argument('csv_with_number_correct_guesses',
                    help="CSV file output by model_test (e.g. test_tweets_0.csv) with number of tweets correctly guessed in the county.")
    ap.add_argument('output_csv',
                    help='CSV file to output the counts matrix (# of counties x # of counties)')
    ap.add_argument('--include_correct_guesses',
                    action='store_true',
                    default=True,
                    help="Process csv_with_number_correct_guesses (T) or just leave those cells as None (F).")

    args = ap.parse_args()

    with open(args.counties_geojson, 'r') as fin:
        counties_gj = json.load(fin)

    columns = []
    for county in counties_gj['features']:
        columns.append(int(county['properties']['FIPS']))
    del(counties_gj)

    rows = {}
    for fips in columns:
        rows[fips] = {'county_fips' : fips}
    with open(args.tweet_estimates_by_county, 'r') as fin:
        csvreader = csv.reader(fin)
        assert next(csvreader) == ['FIPS','breakdown_of_estimated_locations']
        for line in csvreader:
            estimates = ast.literal_eval(line[1])
            for estimate in estimates:
                rows[estimate][int(line[0])] = estimates[estimate]
    if args.include_correct_guesses:
        with open(args.csv_with_number_correct_guesses, 'r') as fin:
            csvreader = csv.reader(fin)
            assert next(csvreader)[:3] == ['FIPS','count_tweets','within_county']
            for line in csvreader:
                rows[int(line[0])][int(line[0])] = int(line[2])

    columns.sort()
    columns = ['county_fips'] + columns

    with open(args.output_csv, 'w') as fout:
        csvwriter = csv.DictWriter(fout, fieldnames=columns, restval=None)
        csvwriter.writeheader()
        for fips in rows:
            csvwriter.writerow(rows[fips])


if __name__ == "__main__":
    main()