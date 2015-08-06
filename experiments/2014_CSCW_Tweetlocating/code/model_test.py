# WARNING: Test_Sequence and Test instances are regularly pickled; thus, they
# shouldn't retain reference to large sub-objects (or, alternately, they
# should override __getstate__() and filter out such references).

from __future__ import division

from collections import defaultdict, OrderedDict
from datetime import timedelta
import itertools
import math
import numbers
import operator
import os
import sys
import time
import json
from shapely.geometry import shape
from shapely.wkt import loads
import csv

from django.contrib.gis import geos
import numpy as np

import psycopg2
import psycopg2.extras
from geo import srs
import multicore
import testable
import time_
import tsv_glue
import tweet
import u

l = u.l

# If debug logging is on, log a message every this many tweets (very
# approximately).
HEARTBEAT_INTERVAL = 100

# We expect to see at least this many tweets per second on a continuous basis
# (e.g., even during slow times of day). If we see less, conclude there is a
# problem and refuse to test. Note that this is total tweets, not just
# geolocated. This minimum should be pretty generous, as it needs to account
# both for daily and minute-by-minute variation as well as exponential decay
# going back to 2009 (which is when our data starts).
#
# According to random web hits,
# (http://blog.twitter.com/2010/02/measuring-tweets.html and
# http://techvibes.com/blog/twitter-users-tweet-400-million-times-2012-12-17),
# we should expect about 10M tweets per day as of July 2009 and 400M as of
# 2012-12-17. That level of growth makes it difficult to write a single
# threshold.
TWEETS_PER_SEC_MIN = 12  # i.e., about 1M/day

# What fraction of tweets do we expect to be geotagged?
# In sample stream, 0.02 would be appropriate.
GEOTAGGED_FRACTION = 0.95

DATABASE = "twitterstream_zh_us"
TABLE = "quac_test"


### Functions ###

def test_tweet(model, fields, tw):
    # joblib can't call methods, so this is a function.
    assert (tw.geom.srid == model.srid)
    if (tw.id % HEARTBEAT_INTERVAL == 0):
        l.debug('testing tweet id %d' % (tw.id))
    r = Metrics_Tweet(tweet=tw, fields=fields, region_id = tw.region_id)
    le = model.locate(tw.tokens, 0.50)
    r.location_estimate = le
    if (le is None):
        r.success_ct = 0
        r.cae = float('inf')  # we sort on this later; put fails last
    else:
        r.success_ct = 1
        r.ntokens = len(le.explanation)
        r.ncomponents = le.n_components
        r.npoints = le.n_points
        r.cae = le.cae(tw.geom)
        r.sae = le.sae(tw.geom)
        r.contour = le.contour(tw.geom)
        r.covt50 = int(le.coverst_p(tw.geom))
        r.pra50 = le.pred_area
        le.populate_pred_region(0.90)
        r.covt90 = int(le.coverst_p(tw.geom))
        r.pra90 = le.pred_area
        le.populate_pred_region(0.95)
        r.covt95 = int(le.coverst_p(tw.geom))
        r.pra95 = le.pred_area
        le.unprepare()  # save a bunch of memory
    return r


### Classes ###

class Metrics(object):

    '''The point of this class is to hold random attributes, with some
       convenience functionality: it knows how to add itself to another Metrics
       object (numeric attributes are summed), divide by real numbers (numeric
       attributes are divided by the number), etc. Note that after such
       operations, the non-numeric attributes are lost.'''

    def __init__(self, **kwargs):
        for k in kwargs:
            setattr(self, k, kwargs[k])

    def __add__(self, other):
        kwargs = { k: getattr(self, k) + getattr(other, k)
                   for k in vars(self).keys()
                   if isinstance(getattr(self, k), numbers.Real) }
        return self.__class__(**kwargs)

    def __radd__(self, other):
        # This method is needed by sum(), which initializes the running sum to
        # zero. Accordingly, we make it only work with zero.
        if (other != 0):
            return NotImplemented
        return self

    def __str__(self):
        return str(vars(self))

    def __truediv__(self, other):
        if (not isinstance(other, numbers.Real)):
            return NotImplemented
        kwargs = { k: getattr(self, k) / other
                   for k in vars(self).keys()
                   if isinstance(getattr(self, k), numbers.Real) }
        return self.__class__(**kwargs)

    @property
    def keys_as_list(self):
        return sorted(self.numeric_vars.keys())

    @property
    def numeric_vars(self):
        return OrderedDict((k, v) for (k, v) in sorted(vars(self).items())
                           if isinstance(v, numbers.Real))

    @property
    def as_list(self):
        return [getattr(self, k) for k in self.keys_as_list]


class Metrics_Tweet(Metrics):

    @property
    def summary_dict(self):
        d = OrderedDict()
        d['tweet_id'] = self.tweet.id
        d['region_id'] = self.tweet.region_id

        for f in sorted(self.fields):
            d[f] = getattr(self.tweet, f)
        if (self.location_estimate is None):
            d['explanation'] = None
        else:
            expll = sorted(self.location_estimate.explanation.items(),
                           key=operator.itemgetter(1), reverse=True)
            d['explanation'] = ", ".join(((u'%s (%g)' % i) for i in expll))
        d.update(self.numeric_vars)
        return d


class Test(object):

    @property
    def end(self):
        return self.testing_end

    @property
    def parms(self):
        'An OrderedDict of some relevant parameters for this test.'
        od = OrderedDict()
        for a in ('training_start', 'training_end',
                  'testing_start', 'testing_end'):
            od[a] = getattr(self, a)
        return od

    @property
    def testing_end(self):
        return self.testing_start + self.testing_duration

    @property
    def testing_start(self):
        return self.training_end + self.gap

    @property
    def training_end(self):
        return self.training_start + self.training_duration

    @property
    def training_start(self):
        return self.start

    def __init__(self, start, training_d, gap, testing_d):
        self.start = start
        self.training_duration = training_d
        self.gap = gap
        self.testing_duration = testing_d
        
    def __str__(self):
        return str(self.start)

    def do_test(self, m_class, cur, args, i):
        self.i = i
        # create tokenizer
        tzer = u.class_by_name(args.tokenizer)(args.ngram)
        # load training & testing tweets from database
        exu = None if args.dup_users else set()
        (tr_tweets, _) = self.fetch(cur, args.srid, 'training', tzer,
                                           args.fields, args.unify_fields, exu)
        tr_tweets = self.filter_geometry(tr_tweets, args.ses, cur, args.how_filter, 30000)  # downsample to 30000 per Reid's paper
        tr_users = set()
        for tweet in tr_tweets:
            tr_users.add(tweet.user_screen_name)
        self.map_tweets(tr_tweets, "{0}/training_tweets_{1}.csv".format(args.output_dir, i),
                            geojsonfn="/export/scratch2/isaacj/geometries/USCounties_bare.geojson")
        exu = None if args.dup_users else tr_users
        (te_tweets, _) = self.fetch(cur, args.srid, 'testing', tzer,
                                    args.fields, args.unify_fields, exu)
        if (not args.skip_small_tests):
            self.attempted = True
        else:
            l.info('insufficient data, skipping test %s ' % (self))
            self.attempted = False
            self.results = []
            return
        # tokenize training tweets
        tr_tokens = self.group_tokens(tr_tweets,
                                      args.trim_head, args.min_instances)
        self.train_tweet_ct = len(tr_tweets)
        self.train_token_ct = len(tr_tokens)
        # downsample test tweets
        if (len(te_tweets) > args.test_tweet_limit):
            te_tweets = u.rand.sample(te_tweets, args.test_tweet_limit)
            l.info('sampled %d test tweets per --test-tweet-limit'
                   % (args.test_tweet_limit))
        self.test_tweet_ct = len(te_tweets)
        # build model
        self.model = m_class(tr_tokens, args.srid, tr_tweets)
        l.debug('starting model build')
        t_start = time.time()
        self.model.build()
        l.info('built model in %s' % (u.fmt_seconds(time.time() - t_start)))
        t_start = time.time()
        # test 'em
        self.results = multicore.do(test_tweet,
                                (self.model, args.fields), te_tweets)
        l.info('tested tweets in %s' % (u.fmt_seconds(time.time() - t_start)))

    def dump(self, dir_):
        u.pickle_dump('%s/model.%d' % (dir_, self.i), self.model)
        u.pickle_dump('%s/results.%d' % (dir_, self.i), self.results)

    def enough_data_p(self, train_ct, test_ct):
        '''Return True if the number of training and testing tweets seem
           reasonable in relation to the corresponding durations; otherwise,
           return False. For example:

           >>> from time_ import iso8601_parse
           >>> from isodate import parse_duration
           >>> start = iso8601_parse('2012-04-01')
           >>> tr = parse_duration('P1D')
           >>> gap = parse_duration('P0D')
           >>> te = parse_duration('PT1H')
           >>> test = Test(start, tr, gap, te)
           >>> test.enough_data_p(10369, 433)
           True
           >>> test.enough_data_p(0, 0)
           False
           >>> test.enough_data_p(10367, 433)
           False
           >>> test.enough_data_p(10369, 431)
           False'''
        def threshold(duration):
            return (duration.total_seconds()
                    * TWEETS_PER_SEC_MIN * GEOTAGGED_FRACTION)
        enough = True
        tr_t = threshold(self.training_duration)
        te_t = threshold(self.testing_duration)
        if (train_ct < tr_t):
            enough = False
            l.debug('need %g tweets per %s to train, but have %d'
                    % (tr_t, self.training_duration, train_ct))
        if (test_ct < te_t):
            enough = False
            l.debug('need %g tweets per %s to test, but have %d'
                    % (te_t, self.testing_duration, test_ct))
        return enough

    def fetch(self, cur, srid, phase, tzer, fields, unify, excluded=None):
    # fetch tweets
        try:
            cur.execute(
                "SELECT tweet_id as tweet_id, created_at as created_at, day as day, \
                    hour as hour, text as text, user_screen_name as user_screen_name, \
                    user_description as user_description, user_lang as user_lang, \
                    user_location as user_location, user_time_zone as user_time_zone, \
                    lat as lat, lon as lon, geotagged as geom_src, county_fips as region_id \
                FROM {0} WHERE {1}".format(TABLE, self.where(phase, 'created_at')))
            rows = cur.fetchall()
        except:
            l.info("tweet selection from db failed")
            raise Exception
        l.debug('fetched %d rows' % (len(rows)))
        tweets_raw = [tweet.Tweet.from_dict(row) for row in rows]
        l.debug('fetched %d tweets' % (len(tweets_raw)))
        # filter out duplicate users
        users = set()
        tweets = list()
        for tw in tweets_raw:
            if (excluded is None or (tw.user_screen_name not in excluded
                                     and tw.user_screen_name not in users)):
                users.add(tw.user_screen_name)
                tweets.append(tw)
        # if phase == "training":
            # self.filter_geometry(tweets,"urban",cur,"balance")
        l.info('%s on %d tweets by %d users'
               % (phase, len(tweets), len(users)))
        # tokenize tweets
        t = time.time()
        for tw in tweets:
            # FIXME: This could be refactored to run in parallel
            tw.tokenize(tzer, fields, unify)
        l.debug('tokenized in %s' % (u.fmt_seconds(time.time() - t)))
        # done
        return (tweets, users)

    def filter_geometry(self, tweets, ses, cur, how, limit):
        # TODO: update to match this: https://docs.google.com/spreadsheets/d/1-rqwtsATqAuhRMk7_O4a5DDr8lVyjBMuGotALCH430g/edit#gid=394314015
        potential_ses = ['urban', 'income']
        if ses == 'urban':
            weights = { 'balance' : {1:0.305, 2:0.248, 3:0.206, 4:0.092, 5:0.088, 6:0.062},
                       'expected' : {1:0.396, 2:0.237, 3:0.195, 4:0.081, 5:0.063, 6:0.028},
                          'urban' : {1:0.534, 2:0.372, 3:0.044, 4:0.020, 5:0.019, 6:0.013},
                          'rural' : {1:0.273, 2:0.222, 3:0.184, 4:0.083, 5:0.131, 6:0.108}}
        elif ses == 'income':
            weights = { 'balance' : {},
                       'expected' : {},
                         'wealthy': {},
                            'poor': {}}

        if ses not in potential_ses:
            l.warning("filtering randomly because {0} not in {1}.".format(ses, potential_ses))
            return u.rand.sample(tweets, limit)
        if how not in weights:
            l.warning("filtering randomly because {0} not an option.".format(how))
            return u.rand.sample(tweets, limit)
        cur.execute("SELECT fips as fips, {0} as {0} from quac_ses".format(ses))

        tweet_bins = {}

        for category in weights[how]:
            weights[how][category] = math.ceil(weights[how][category] * limit)
            tweet_bins[category] = []

        counties = {}
        for county in cur:
            counties[county[0]] = county[1]

        for tweet in tweets:
            if tweet.region_id in counties:
                tweet_bins[counties[tweet.region_id]].append(tweet)

        final_tweets = []
        for category in tweet_bins:
            while len(tweet_bins[category]) > weights[how][category]:
                index = u.rand.randrange(0, len(tweet_bins[category]))
                tweet_bins[category].pop(index)
            if len(tweet_bins[category]) < weights[how][category]:
                l.warn('insufficient tweets in category {0}. only have {1} of {2}.'.format(category,
                                                                                           len(tweet_bins[category]),
                                                                                           weights[how][category]))
            final_tweets.extend(tweet_bins[category])

        return final_tweets

    def group_tokens(self, tweets, trim_head_frac, min_instance_ct):
        # list of (token, point) pairs
        tps = []
        for tw in tweets:
            for tok in tw.tokens:
                tps.append((tok, tw.geom))
        tps.sort(key=operator.itemgetter(0))
        # grouped
        tokens = list()
        for (key, group) in itertools.groupby(tps, key=operator.itemgetter(0)):
            tokens.append((key, [i[1] for i in group]))
        l.debug('%d tokens total' % (len(tokens)))
        # remove infrequent
        tokens = list(filter(lambda t: len(t[1]) >= min_instance_ct, tokens))
        l.debug('%d tokens appear >= %d times' % (len(tokens), min_instance_ct))
        # convert to multipoint
        tokens = [(tok, geos.MultiPoint(pts, srid=tweets[0].geom.srid))
                  for (tok, pts) in tokens ]
        l.info('created %d multipoint token groups, %d total points'
               % (len(tokens), sum(len(t[1]) for t in tokens)))
        # remove frequent
        assert (0 <= trim_head_frac < 1)
        tokens.sort(key=lambda i: len(i[1]), reverse=True)
        tokens = tokens[int(round(trim_head_frac * len(tokens))):]
        l.debug('%d tokens after head trim' % (len(tokens)))
        assert (len(tokens) > 0)
        # done
        return dict(tokens)

    def increment(self, duration):
        return Test(self.start + duration, self.training_duration,
                    self.gap, self.testing_duration)

    def map_tweets(self, tweets, outputname, geojsonfn="USCounties_bare.geojson", properties=[]):
        try:
            with open(geojsonfn, 'r') as fin:
                geography = json.load(fin)
        except IOError as e:
            l.warning(e)
            l.warning("mapping will not occur because geojson {0} does not exist".format(geojsonfn))
            return
        except ValueError as e:
            l.warning(e)
            l.warning("mapping will not occur because geojson {0} is an invalid json object".format(geojsonfn))
            return

        ID_FIELD = "FIPS"

        count_matched = 0
        distribution = {}
        for region in geography['features']:
            distribution[region['properties'][ID_FIELD]] = {'count' : 0}
            for property in properties:
                distribution[region['properties'][ID_FIELD]][property] = []
        for tweet in tweets:
            for region in distribution:
                if tweet.region_id == region:
                    count_matched += 1
                    distribution[region]['count'] += 1
                    for property in properties:
                        distribution[region][property].append(getattr(tweet, property))
        l.info('{0} out of {1} tweets matched via region_id.'.format(count_matched, len(tweets)))

        for region in distribution:
            for property in properties:
                if distribution[region]['count'] > 0:
                    distribution[region]['mean_' + property] = np.mean(distribution[region][property])
                    distribution[region]['med_' + property] = np.median(distribution[region][property])
                else:
                    distribution[region]['mean_' + property] = -1
                    distribution[region]['med_' + property] = -1


        # Backup method if region_ids are not populated at high rate, but this shouldn't be needed and complicates
        #  the procedure so commented out for now. Would need to be updated to support properties_dict.
        # if count < 0.95*len(tweets):  # loose metric for whether most of the region ids are populated
        #     count_matched = 0
        #     l.warning('switching to slower geojson containment method')
        #     shapes = {}
        #     for region in geography['features']:
        #         distribution[region['properties'][ID_FIELD]] = 0
        #         shapes[region['properties'][ID_FIELD]] = shape(region['geometry'])
        #     for tweet in tweets:
        #         try:
        #             pt = loads('POINT ({0} {1})'.format(tweet.geom.x, tweet.geom.y))
        #             for region in shapes:
        #                 if shapes[region].contains(pt):
        #                     distribution[region] += 1
        #                     count_matched += 1
        #                     continue
        #         except:
        #             continue
        #     l.info('{0} out of {1} tweets matched via containment.'.format(count_matched, len(tweets)))

        with open(outputname, 'w') as fout:
            csvwriter = csv.writer(fout)
            header = [ID_FIELD, 'count_tweets']
            for property in properties:
                header.append('mean_' + property)
                header.append('med_' + property)
            csvwriter.writerow(header)
            for region in distribution:
                line = [region, distribution[region]['count']]
                for property in properties:
                    line.append(distribution[region]['mean_' + property])
                    line.append(distribution[region]['med_' + property])
                csvwriter.writerow(line)
        l.info("Output geo stats to {0}".format(outputname))

    def meanmedian(self, robj, validp, source, success_attr, attrs):
        'This is a convoluted method to compute means and medians.'
        u.zero_attrs(robj, ([success_attr]
                            + ['m' + a for a in attrs]
                            + ['d' + a for a in attrs]))
        if (validp):
            wins = list(filter(lambda x: getattr(x, success_attr), source))
            setattr(robj, success_attr, len(wins))
            if (len(wins) == 0):
                l.warning('test had zero successes')
                return
            for attr in attrs:
                vals = [getattr(i, attr) for i in wins]
                setattr(robj, 'm' + attr, np.mean(vals))
                setattr(robj, 'd' + attr, np.median(vals))

    def shrink(self):
        self.model = u.Deleted_To_Save_Memory()
        self.results = u.Deleted_To_Save_Memory()

    def shrink_to_disk(self, dir_):
        self.dump(dir_)
        self.shrink()

    def summarize(self, outputdir=None):
        # Some metrics should be summed, others averaged, and others ignored.
        assert (self.attempted == 0 or len(self.results) > 0)
        self.summary = Metrics()
        self.summary.test_ct = 1
        self.summary.attempted_ct = int(self.attempted)
        if (self.attempted):
            self.summary.train_tweet_ct = self.train_tweet_ct
            self.summary.train_token_ct = self.train_token_ct
            self.summary.test_tweet_ct = self.test_tweet_ct
        else:
            self.summary.train_tweet_ct = 0
            self.summary.train_token_ct = 0
            self.summary.test_tweet_ct = 0
        self.meanmedian(self.summary, self.attempted, self.results,
                        'success_ct', ['ntokens', 'ncomponents', 'npoints',
                                       'cae', 'sae',
                                       'contour', 'pra50', 'pra90', 'pra95',
                                       'covt95', 'covt90', 'covt50', ])
        self.summarize_by_geo('success_ct', outputdir)

    def summarize_by_geo(self, success_attr, outputdir):
        wins = list(filter(lambda x: getattr(x, success_attr), self.results))
        losses = list(filter(lambda x: getattr(x, success_attr) == 0, self.results))
        if wins:
            self.map_tweets(wins, "{0}/test_tweets_{1}.csv".format(outputdir, self.i),
                            geojsonfn="/export/scratch2/isaacj/geometries/USCounties_bare.geojson",
                            properties=['ntokens', 'ncomponents', 'npoints',
                                        'cae', 'sae',
                                        'contour', 'pra50', 'pra90', 'pra95',
                                        'covt95', 'covt90', 'covt50'])
        if losses:
            self.map_tweets(losses, "{0}/test_tweets_{1}.csv".format(outputdir, self.i),
                            geojsonfn="/export/scratch2/isaacj/geometries/USCounties_bare.geojson",
                            properties=['ntokens', 'ncomponents', 'npoints',
                                        'cae', 'sae',
                                        'contour', 'pra50', 'pra90', 'pra95',
                                        'covt95', 'covt90', 'covt50'])


    def where(self, phase, column):
        # NOTE: No SQL injection bug because the datetimes we test against are
        # stringified from real objects, not strings provided by the user.
        return ("(%s >= '%s' AND %s < '%s')"
                % (column, getattr(self, phase + '_start'),
                   column, getattr(self, phase + '_end')))

    def unshrink_from_disk(self, dir_, model=False, results=False):
        assert (model or results)
        if (model and isinstance(self.model, u.Deleted_To_Save_Memory)):
            self.model = u.pickle_load('%s/model.%d' % (dir_, self.i))
        if (results and isinstance(self.results, u.Deleted_To_Save_Memory)):
            self.results = u.pickle_load('%s/results.%d' % (dir_, self.i))


class Test_Sequence(object):

    def __init__(self, args):
        self.args = args
        self.conn = psycopg2.connect("dbname={0}".format(DATABASE))
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)
        l.info('opened database {0}'.format(self.args.database_file))

    @property
    def first_good_test(self):
        # Any attempted test will give us what we need, but an arbitrary
        # number of tests might not have been attempted.
        return next(itertools.ifilter(lambda t: t.attempted, self.schedule))

    def main(self):
        u.memory_use_log()
        t_start = time.time()
        # Replaced with self.cur in __init__
        # db = db_glue.DB(self.args.database_file)
        # assert (db.metadata_get('schema_version') == '5')
        # normalize start and end times
        if (self.args.start is None):
            sql = 'SELECT min(created_at) AS st FROM {0};'.format(self.table)
            self.cur.execute(sql)
            self.args.start = self.cur.fetchone()[0]
        if (self.args.end is None):
            sql = 'SELECT max(created_at) AS et FROM {0};'.format(self.table)
            self.cur.execute(sql)
            # add one second because end time is exclusive
            self.args.end = self.cur.fetchone()[0] + timedelta(seconds=1)
        self.args.start = time_.as_utc(self.args.start)
        self.args.end = time_.as_utc(self.args.end)
        # print test sequence parameters
        self.log_parameters()
        # set up model parameters
        model_class = u.class_by_name(self.args.model)
        model_class.parms_init(self.args.model_parms, log_parms=True)
        # build schedule
        self.schedule_build(self.args.limit)
        l.info('scheduled %s tests (%s left over)'
               % (len(self.schedule), self.args.end - self.schedule[-1].end))
        if (not os.path.exists(self.args.output_dir)):
            os.mkdir(self.args.output_dir)
        l.info('results in %s' % (self.args.output_dir))
        # testing loop
        for (i, t) in enumerate(self.schedule):
            if (i+1 < self.args.start_test):
                l.info('using saved test %d per --start-test' % (i+1))
                l.warning('token and tweet counts will be incorrect')
                # FIXME: hack.....
                try:
                    t.model = u.Deleted_To_Save_Memory()
                    t.results = u.Deleted_To_Save_Memory()
                    t.i = i
                    t.train_tweet_ct = -1e6
                    t.train_token_ct = -1e6
                    t.test_tweet_ct = -1e6
                    t.unshrink_from_disk(self.args.output_dir, results=True)
                    t.attempted = True
                except (IOError, x):
                    if (x.errno != 2):
                        raise
                    t.attempted = False
            else:
                l.info('starting test %d of %d: %s' % (i+1, len(self.schedule), t))
                t.do_test(model_class, self.cur, self.args, i)
            t.summarize(self.args.output_dir)
            if (t.attempted):
                if (self.args.profile_memory):
                    # We dump a memory profile here because it's the high water
                    # mark; we're about to reduce usage significantly.
                    import meliae.scanner as ms
                    filename = 'memory.%d.json' % (i)
                    l.info('dumping memory profile %s' % (filename))
                    ms.dump_all_objects('%s/%s' % (self.args.output_dir, filename))
                t.shrink_to_disk(self.args.output_dir)
            l.debug('result: %s' % (t.summary))
            u.memory_use_log()
        # done!
        l.debug('computing summary')
        self.summarize()
        l.debug('summary: %s' % (self.summary))
        l.debug('saving TSV results')
        test_indices = u.sl_union_fromtext(len(self.schedule), ':')
        self.tsv_save_tests('%s/%s' % (self.args.output_dir, 'tests.tsv'),
                            test_indices)
        l.debug('saving pickled summary')
        self.memory_use = u.memory_use()
        self.memory_use_peak = "Not implemented"
        self.time_use = time.time() - t_start
        u.pickle_dump('%s/%s' % (self.args.output_dir, 'summary'), self)
        u.memory_use_log()
        l.info('done in %s' % (u.fmt_seconds(self.time_use)))

    def log_parameters(self):
        # note: spacing matches geo.base.Model.parms_init()
        l.info('sequence parameters:')
        l.info('  cores:                %d' % (self.args.cores))
        l.info('  model:                %s' % (self.args.model))
        l.info('  fields:               %s' % (','.join(self.args.fields)))
        l.info('  unify fields:         %s' % (self.args.unify_fields))
        l.info('  SRID:                 %d' % (self.args.srid))
        l.info('  tokenizer:            %s' % (self.args.tokenizer))
        l.info('  ngrams:               %d' % (self.args.ngram))
        l.info('  dup users:            %s' % (self.args.dup_users))
        l.info('  head trim count:      %g' % (self.args.trim_head))
        l.info('  min instances:        %d' % (self.args.min_instances))
        l.info('timing parameters:')
        l.info('  start time:           %s' % (self.args.start))
        l.info('  end time:             %s' % (self.args.end))
        l.info('  training window:      %s' % (self.args.training))
        l.info('  testing window:       %s' % (self.args.testing))
        l.info('  gap:                  %s' % (self.args.gap))
        l.info('  stride:               %s' % (self.args.stride))

    def schedule_build(self, max_test_ct):
        self.schedule = []
        t = Test(self.args.start, self.args.training,
                 self.args.gap, self.args.testing)
        while (t.end < self.args.end
               and (max_test_ct is None or len(self.schedule) < max_test_ct)):
            self.schedule.append(t)
            t = t.increment(self.args.stride)
        assert(len(self.schedule) >= 1)  # FIXME: should error check, not assert

    def summarize(self):
        summaries = [t.summary for t in self.schedule]
        sum_ = sum(summaries)
        if (sum_.attempted_ct <= 0):
            u.abort('%d tests were attempted' % (sum_.attempted_ct))
        # In this case it is mostly OK that we are simply averaging the test
        # results, since counts should be averaged across the tests.
        self.summary = sum_ / sum_.attempted_ct
        self.summary.test_ct = sum_.test_ct
        self.summary.attempted_ct = sum_.attempted_ct
        # standard deviations (FIXME: awkward)
        for attr in ('success_ct', 'mcae', 'msae', 'mpra95', 'mpra90', 'mpra50',
                     'mcontour', 'mcovt95', 'mcovt90', 'mcovt50'):
            setattr(self.summary, 's' + attr,
                    np.std([getattr(i, attr) for i in summaries
                            if i.attempted_ct > 0]))

    def tsv_open(self, filename):
        if (filename == '-'):
            t = tsv_glue.Writer(fp=sys.stdout)
        else:
            t = tsv_glue.Writer(filename, clobber=True)
        return t

    def tsv_save_tests(self, filename, test_indices):
        l.info('writing summary results of tests to %s' % (filename))
        tsv = self.tsv_open(filename)
        tsv.writerow(['test_idx'] + list(self.schedule[0].parms.keys())
                     + self.schedule[0].summary.keys_as_list)
        tsv.writerow(['mean'] + ([None] * len(self.schedule[0].parms))
                     + self.summary.as_list)
        for i in sorted(test_indices):
            t = self.schedule[i]
            tsv.writerow([i] + list(t.parms.values()) + t.summary.as_list)

    def tsv_save_tokens(self, filename, geofiles_p, geoimage_width,
                        test_indices, token_idx, tw_tokens):
        l.info('writing tokens summaries to %s' % (filename))
        if (not geofiles_p):
            tsv = self.tsv_open(filename)
            self.first_good_test.unshrink_from_disk(self.args.output_dir,
                                                    model=True)
            tsv.writerow(['test_idx', 'token_idx']
                         + list(self.first_good_test.model.token_summary_keys))
        for i in sorted(test_indices):
            test = self.schedule[i]
            if (not test.attempted):
                continue
            test.unshrink_from_disk(self.args.output_dir, model=True)
            tokenrows = [test.model.token_summary(token)
                         for token in test.model.tokens]
            tokenrows.sort(key=operator.itemgetter('point_ct'), reverse=True)
            token_indices = u.sl_union_fromtext(len(tokenrows), token_idx)
            for j in xrange(len(tokenrows)):
                tokenrow = tokenrows[j]
                if (not (j in token_indices
                         or i in tw_tokens.get(tokenrow['token'], set()))):
                    continue
                if (not geofiles_p):
                    tsv.writerow([i, j] + tokenrow.values())
                else:
                    assert (geoimage_width > 0)
                    gi_basename = u'%s.%d.%d' % (u.without_ext(filename), i, j)
                    l.debug('writing geofiles %s' % (gi_basename))
                    test.model.dump_geofiles(gi_basename, geoimage_width,
                                             tokenrow['token'])
            test.shrink()

    def tsv_save_tweets(self, filename, include_fails_p, geofiles_p,
                        geoimage_width, test_indices, tweet_idx):
        '''Return value is a mapping from tokens involved in printed tweets to
           a set of test indices in which they appeared.'''
        tokens = defaultdict(set)
        l.info('writing tweet summaries%s to %s'
               % (' and geoimages' if geofiles_p else '', filename))
        if (not geofiles_p):
            tsv = self.tsv_open(filename)
            self.first_good_test.unshrink_from_disk(self.args.output_dir,
                                                    results=True)
            tsv.writerow(['test_idx', 'tweet_idx']
                         + self.first_good_test.results[0].summary_dict.keys())
        for i in sorted(test_indices):
            test = self.schedule[i]
            if (not test.attempted):
                continue
            test.unshrink_from_disk(self.args.output_dir, results=True)
            tweetrows = test.results[:]
            tweetrows.sort(key=operator.attrgetter('cae'))
            for j in sorted(u.sl_union_fromtext(len(tweetrows), tweet_idx)):
                r = tweetrows[j]
                if (not r.success_ct and not include_fails_p):
                    continue
                for token in r.location_estimate.explanation.keys():
                    tokens[token].add(i)
                if (not geofiles_p):
                    tsv.writerow([i, j] + r.summary_dict.values())
                else:
                    assert (geoimage_width > 0)
                    gi_basename = u'%s.%d.%d' % (u.without_ext(filename), i, j)
                    l.debug('writing geofiles %s' % (gi_basename))
                    # FIXME: ugly hack to get PR_90 instead of PR_95
                    import geo.gmm
                    geo.gmm.Token.parms_init({})
                    r.location_estimate.dump_geofiles(gi_basename,
                                                      geoimage_width, 0.90)
                    srs.dump_geojson(gi_basename + '.truth', r.tweet.geom)
            test.shrink()
        return tokens


testable.register('')
