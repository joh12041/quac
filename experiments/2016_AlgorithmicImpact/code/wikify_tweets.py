__author__ = 'joh12041'

import csv
import urllib.parse
import urllib.request
import json
import os


def main():

    spatial_articles_en_fn = '/Users/joh12041/GraduateSchool/wikipedia_parser/wikipedia-parsing/resources/talk_page_ids_counties.csv'
    spatialArticleIDs = {}
    with open(spatial_articles_en_fn, 'r') as fin:
        csvreader = csv.reader(fin)
        header = ['LOCAL_ID','TITLE','TALK_ID','TALK_TITLE','GEOMETRY','county_fips']
        assert next(csvreader) == header
        for line in csvreader:
            spatialArticleIDs[line[header.index('TITLE')]] = True

    tweets_json_folder = '/Users/joh12041/GraduateSchool/Geolocation/quac_fork/data/geo/sample_tweets/'
    files = os.listdir(tweets_json_folder)
    for fn in [f for f in files if '.json' in f]:
        with open(tweets_json_folder + fn, 'r') as fin:
            print("\nProcessing {0}.".format(fn))
            count_spatial = 0
            count_all = 0
            count_skipped = 0
            title_counts = {}
            i = 0
            for line in fin:
                i += 1
                tweet = json.loads(line.strip().replace(r'\\"', r'\"'))
                try:
                    urlencoded_text = urllib.parse.quote(tweet['text'] + ' ' + tweet['user']['location'] + ' ' + tweet['user']['description'])
                except TypeError:
                    try:
                        urlencoded_text = urllib.parse.quote(tweet['text'] + ' ' + tweet['user']['description'])
                    except TypeError:
                        try:
                            urlencoded_text = urllib.parse.quote(tweet['text'] + ' ' + tweet['user']['location'])
                        except TypeError:
                            urlencoded_text = urllib.parse.quote(tweet['text'])
                try:
                    query = 'http://como.macalester.edu/wikibrain/wikify?lang=en&text={0}'.format(urlencoded_text)
                    response = urllib.request.urlopen(query)
                    str_response = response.readall().decode('utf-8')
                    json_response = json.loads(str_response)
                    for item in json_response['references']:
                        if item['title'] in spatialArticleIDs:
                            count_spatial += 1
                        count_all += 1
                        if item['title'] in title_counts:
                            title_counts[item['title']] += 1
                        else:
                            title_counts[item['title']] = 1
                except Exception:
                    count_skipped += 1
                    continue
        print('{0} entities of which {1} were spatial out of {2} articles'.format(count_all, count_spatial, i - count_skipped))
        print('{0} total entities per tweet, {1} spatial entities per tweet.'.format(round(count_all / (i - count_skipped), 3), round(count_spatial / (i - count_skipped), 3)))
        with open(tweets_json_folder + fn.replace('.json', '_wikiconceptcounts.csv'), 'w') as fout:
            csvwriter = csv.writer(fout)
            csvwriter.writerow(['wikipedia_title','count'])
            for article in title_counts:
                csvwriter.writerow([article, title_counts[article]])

def update_spatial_counts():
    articles_processed = {'female':956, 'male':931, 'rural':931, 'urban': 940}
    spatial_articles_en_fn = '/Users/joh12041/GraduateSchool/wikipedia_parser/wikipedia-parsing/resources/talk_page_ids_counties.csv'
    spatialArticleIDs = {}
    with open(spatial_articles_en_fn, 'r') as fin:
        csvreader = csv.reader(fin)
        header = ['LOCAL_ID','TITLE','TALK_ID','TALK_TITLE','GEOMETRY','county_fips']
        assert next(csvreader) == header
        for line in csvreader:
            spatialArticleIDs[line[header.index('TITLE')]] = True

    tweets_json_folder = '/Users/joh12041/GraduateSchool/Geolocation/quac_fork/data/geo/sample_tweets/first_round/'
    files = os.listdir(tweets_json_folder)
    for fn in [f for f in files if '.csv' in f]:
        if 'female' in fn:
            sample = 'female'
        elif 'male' in fn:
            sample = 'male'
        elif 'rural' in fn:
            sample = 'rural'
        else:
            sample = 'urban'
        count_spatial = 0
        count_all = 0
        sum_spatial = 0
        sum_all = 0
        print("Processing {0}".format(fn))
        with open(tweets_json_folder + fn, 'r') as fin:
            csvreader = csv.reader(fin)
            assert next(csvreader) == ['wikipedia_title','count']
            for line in csvreader:
                count_all += 1
                sum_all += int(line[1])
                if line[0] in spatialArticleIDs:
                    count_spatial += 1
                    sum_spatial += int(line[1])
        print("Out of {0} articles: {1} spatial out of {2} entities and {3} sum spatial out of {4} total.".format(articles_processed[sample], count_spatial, count_all, sum_spatial, sum_all))
        print("{0}: {1} total entities per tweet, {2} spatial entities per tweet".format(sample, round(sum_all/articles_processed[sample], 3), round(sum_spatial/articles_processed[sample], 3)))


if __name__ == "__main__":
    main()
