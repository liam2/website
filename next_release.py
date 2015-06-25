#!/usr/bin/python
# encoding: utf-8
# script to start a new release cycle
# Licence: GPLv3
from os.path import join
from make_release import relname2fname, long_release_name
from shutil import copy

def add_release(release_name):
    fname = relname2fname(long_release_name(release_name))

    # create "empty" highlights for that release
    highlights_dir = 'highlights'
    copy(join(highlights_dir, 'template.rst.inc'),
         join(highlights_dir, fname))

if __name__ == '__main__':
    from sys import argv

    add_release(*argv[1:])
