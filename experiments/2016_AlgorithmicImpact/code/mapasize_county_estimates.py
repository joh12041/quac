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
                    help='CSV file (*_wholookslikeSF.csv) containing tweet estimates by county as output by model_test.py'
                    )
    ap.add_argument('output_csv',
                    help='CSV file to output the counts matrix (# of counties x # of counties)')

    args = ap.parse_args()

    with open(args.counties_geojson, 'r') as fin:
        counties_gj = json.load(fin)

    data = {}
    with open(args.tweet_estimates_by_county, 'r') as fin:
        csvreader = csv.reader(fin)
        assert next(csvreader) == ['FIPS','breakdown_of_estimated_locations']
        for line in csvreader:
            estimates = ast.literal_eval(line[1])
            data[line[0]] = {'county_fips' : line[0]}
            for estimate in estimates:
                data[line[0]][estimate] = estimates[estimate]

    columns = []
    for county in counties_gj['features']:
        columns.append(int(county['properties']['FIPS']))
    del(counties_gj)
    columns.sort()
    columns = ['county_fips'] + columns

    with open(args.output_csv, 'w') as fout:
        csvwriter = csv.DictWriter(fout, fieldnames=columns, restval=None)
        csvwriter.writeheader()
        for fips in data:
            csvwriter.writerow(data[fips])


if __name__ == "__main__":
    main()