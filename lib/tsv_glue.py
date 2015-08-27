'''This module offers a simple interface to the TSV files we want to store.

   You will note that it doesn't use the csv module. This is because that
   module has a number of annoying habits, the most significant one being that
   it completely does not support unicode. (There are wrappers which solve
   this, but I'd prefer to keep dependencies, particularly those that don't
   come with the OS, to a minimum.) However, the final straw was the fact that
   it wanted to escape quote characters even though I specified no quoting.

   It's really a very simple format. We'll be OK.

   WARNING: Keep the TSV dialect consistent with README.

   See http://docs.python.org/library/io.html for the meaning of the buffering
   parameter. '''

# Copyright (c) Los Alamos National Security, LLC, and others.

import collections
import io
import csv

import u


class Reader(object):

   '''Read rows are returned as lists. Empty strings are converted to None.
      Converting to numbers, etc., is the responsibility of the caller.'''

   __slots__ = ('fp', 'separator')

   def __init__(self, file_, buffering=-1, separator='\t', mode='t'):
      '''Open a TSV file for reading and return the reader object; the file
         can be either a filename or an open integer file descriptor. If it's
         a filename which does not exist, raise an exception.'''
      self.separator = separator
      mode = 'r' + mode
      self.fin = open(file_, mode='r', buffering=buffering)
      #self.fp = io.open(file_, mode=mode, buffering=buffering)
      self.fp = csv.reader(self.fin)

   def __iter__(self):
      return self

   def close(self):
      self.fin.close()
       #self.fp.close()

   def __next__(self):
      return next(self.fp)
      # line = self.fp.readline()
      # line = line.rstrip('\n')
      # if (line == ''):
      #    raise StopIteration
      # return [(col if col != '' else None)
      #         for col in line.split(self.separator)]


class Writer(object):

   __slots__ = ('filename', 'fp')

   def __init__(self, file_, fp=None, buffering=-1, clobber=False):
      '''Open a TSV file for writing and return the writer object. file_ can
         be either an open integer file descriptor or a filename. In the
         latter case, create a new file if one does not already exist. If
         clobber is True, overwrite any existing contents, if False (the
         default), append.'''
      if (isinstance(file_, str)):
         self.filename = file_
      if (clobber or file_ == 1):
         # io.open() on file descriptor 1 (stdout) with mode='at' crashes with
         # "IOError: [Errno 29] Illegal seek". That's very odd; perhaps a
         # Python bug (e.g., <http://bugs.python.org/issue6236>)? Anyway, we
         # work around it by forcing mode='wt', since mode='at' isn't
         # meaningful in that context anyway.
         mode = 'w'
      else:
         mode = 'a'
      self.fout = open(file_, mode=mode, buffering=buffering, encoding='utf8')
      self.fp = csv.writer(self.fout)

   def close(self):
      self.fout.close()
      #self.fp.close()

   def flush(self):
      self.fout.flush()
      #self.fp.flush()

   def writerow(self, row):
      self.fp.writerow(row)
      # def _unicodify(s):
      #    if s is None:
      #       return ''
      #    else:
      #       return str(s)
      # self.fp.write('\t'.join([_unicodify(i) for i in row]) + '\n')


class Dict(collections.defaultdict):
   '''A lazy-loading dictionary of open TSV files. Essentially:

      >>> t = tsv_glue.Dict('/tmp/foo_')
      >>> d['bar'].writerow([1,2,3])

      In the second line, if t['bar'] isn't already an open TSV file, it will
      magically become one (stored in "/tmp/foo_bar.tsv").'''

   def __init__(self, prefix, class_=Writer, buffering=-1, clobber=False):
      self.prefix = prefix
      self.class_ = class_
      self.buffering = buffering
      self.clobber = clobber

   def __missing__(self, key):
      filename = self.filename_from_key(key)
      self[key] = self.class_(filename, buffering=self.buffering,
                              clobber=self.clobber)
      u.l.debug('lazy opened %s' % (filename))
      return self[key]

   def close(self):
      for f in self.values():
         f.close()

   def filename_from_key(self, key):
      return (self.prefix + key + '.csv')

   def iterfiles(self):
      return [self.filename_from_key(i) for i in self.keys()]

