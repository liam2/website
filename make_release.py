#!/usr/bin/python
# coding: utf-8
# Release script for LIAM2
# Licence: GPLv3
# Requires:
# * git, pscp and outlook in PATH
# * all tools used for building the doc & exe in PATH
from __future__ import print_function

import errno
import fnmatch
import os
import re
import stat
import subprocess
import sys
# import tempfile
import urllib
import zipfile

from os import chdir, makedirs
from os.path import exists, getsize, abspath, dirname
from shutil import copy2, rmtree as _rmtree
from subprocess import check_output, STDOUT, CalledProcessError

WEBSITE = 'liam2.plan.be'
TMP_PATH = r"c:\tmp\liam2_new_release"
# not using tempfile.mkdtemp to be able to resume an aborted release
# TMP_PATH = os.path.join(tempfile.gettempdir(), "liam2_new_release")

# TODO:
# - different announce message for pre-releases
# - announce RC on the website too
# ? create a download page for the rc
# - create a conda environment to store requirements for the release
#   create -n liam2-{release} --clone liam2
#   or better yet, only store package versions:
#   conda env export > doc\bundle_environment.yml

# TODO: add more scripts to implement the "git flow" model
# - hotfix_branch
# - release_branch
# - feature_branch
# - make_release, detects hotfix or release


# ------------- #
# generic tools #
# ------------- #

def size2str(value):
    unit = "bytes"
    if value > 1024.0:
        value /= 1024.0
        unit = "Kb"
        if value > 1024.0:
            value /= 1024.0
            unit = "Mb"
        return "%.2f %s" % (value, unit)
    else:
        return "%d %s" % (value, unit)


def generate(fname, **kwargs):
    with open('%s.tmpl' % fname) as in_f, open(fname, 'w') as out_f:
        out_f.write(in_f.read().format(**kwargs))


def _remove_readonly(function, path, excinfo):
    if function in (os.rmdir, os.remove) and excinfo[1].errno == errno.EACCES:
        # add write permission to owner
        os.chmod(path, stat.S_IWUSR)
        # retry removing
        function(path)
    else:
        raise


def rmtree(path):
    _rmtree(path, onerror=_remove_readonly)


def call(*args, **kwargs):
    try:
        return check_output(*args, stderr=STDOUT, **kwargs)
    except CalledProcessError, e:
        print(e.output)
        raise e


def echocall(*args, **kwargs):
    print(' '.join(args))
    return call(*args, **kwargs)


def branchname(statusline):
    """
    computes the branch name from a "git status -b -s" line
    ## master...origin/master
    """
    statusline = statusline.replace('#', '').strip()
    pos = statusline.find('...')
    return statusline[:pos] if pos != -1 else statusline


def yes(msg, default='y'):
    choices = ' (%s/%s) ' % tuple(c.capitalize() if c == default else c
                                  for c in ('y', 'n'))
    answer = None
    while answer not in ('', 'y', 'n'):
        if answer is not None:
            print("answer should be 'y', 'n', or <return>")
        answer = raw_input(msg + choices).lower()
    return (default if answer == '' else answer) == 'y'


def no(msg, default='n'):
    return not yes(msg, default)


def do(description, func, *args, **kwargs):
    print(description + '...', end=' ')
    func(*args, **kwargs)
    print("done.")


def allfiles(pattern, path='.'):
    """
    like glob.glob(pattern) but also include files in subdirectories
    """
    return (os.path.join(dirpath, f)
            for dirpath, dirnames, files in os.walk(path)
            for f in fnmatch.filter(files, pattern))


def zip_pack(archivefname, filepattern):
    with zipfile.ZipFile(archivefname, 'w', zipfile.ZIP_DEFLATED) as f:
        for fname in allfiles(filepattern):
            f.write(fname)


def zip_unpack(archivefname, dest=None):
    with zipfile.ZipFile(archivefname) as f:
        f.extractall(dest)


def short(release_name):
    return release_name[:-2] if release_name.endswith('.0') else release_name


def long_release_name(release_name):
    """
    transforms a short release name such as 0.8 to a long one such as 0.8.0

    >>> long_release_name('0.8')
    '0.8.0'
    >>> long_release_name('0.8.0')
    '0.8.0'
    >>> long_release_name('0.8rc1')
    '0.8.0rc1'
    >>> long_release_name('0.8.0rc1')
    '0.8.0rc1'
    """
    dotcount = release_name.count('.')
    if dotcount >= 2:
        return release_name
    assert dotcount == 1, "%s contains %d dots" % (release_name, dotcount)
    pos = pretag_pos(release_name)
    if pos is not None:
        return release_name[:pos] + '.0' + release_name[pos:]
    return release_name + '.0'


def pretag_pos(release_name):
    """
    gives the position of any pre-release tag
    >>> pretag_pos('0.8')
    >>> pretag_pos('0.8alpha25')
    3
    >>> pretag_pos('0.8.1rc1')
    5
    """
    # 'a' needs to be searched for after 'beta'
    for tag in ('rc', 'c', 'beta', 'b', 'alpha', 'a'):
        match = re.search(tag + '\d+', release_name)
        if match is not None:
            return match.start()
    return None


def strip_pretags(release_name):
    """
    removes pre-release tags from a version string

    >>> strip_pretags('0.8')
    '0.8'
    >>> strip_pretags('0.8alpha25')
    '0.8'
    >>> strip_pretags('0.8.1rc1')
    '0.8.1'
    """
    pos = pretag_pos(release_name)
    return release_name[:pos] if pos is not None else release_name


def isprerelease(release_name):
    """
    tests whether the release name contains any pre-release tag

    >>> isprerelease('0.8')
    False
    >>> isprerelease('0.8alpha25')
    True
    >>> isprerelease('0.8.1rc1')
    True
    """
    return pretag_pos(release_name) is not None


def send_outlook(to, subject, body):
    subprocess.call('outlook /c ipm.note /m "%s&subject=%s&body=%s"'
                    % (to, urllib.quote(subject), urllib.quote(body)))


def send_thunderbird(to, subject, body):
    # preselectid='id1' selects the first "identity" for the "from" field
    # We do not use our usual call because the command returns an exit status
    # of 1 (failure) instead of 0, even if it works, so we simply ignore
    # the failure.
    subprocess.call("thunderbird -compose \"preselectid='id1',"
                    "to='%s',subject='%s',body='%s'\"" % (to, subject, body))

# -------------------- #
# end of generic tools #
# -------------------- #

# ------------------------- #
# specific helper functions #
# ------------------------- #


def rst2txt(s):
    """
    translates rst to raw text

    >>> rst2txt(":ref:`matching() <matching>`")
    'matching()'
    >>> # \\n needs to be escaped because we are in a docstring
    >>> rst2txt(":ref:`matching()\\n  <matching>`")
    'matching()\\n  '
    >>> rst2txt(":PR:`123`")
    'pull request 123'
    >>> rst2txt(":pr:`123`")
    'pull request 123'
    >>> rst2txt(":issue:`123`")
    'issue 123'
    >>> rst2txt("::")
    ''
    """
    s = s.replace("::", "")
    # first replace :ref:s which span across two lines (we want to *keep* the
    # blanks in those) then those on one line (where we kill the spaces)
    s = re.sub(":ref:`(.+ *[\n\r] *)<.+>`", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(":ref:`(.+) +<.+>`", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(":pr:`(\d+)`", r"pull request \1", s, flags=re.IGNORECASE)
    return re.sub(":issue:`(\d+)`", r"issue \1", s, flags=re.IGNORECASE)


def relname2fname(release_name):
    short_version = short(strip_pretags(release_name))
    return r"version_%s.rst.inc" % short_version.replace('.', '_')


def release_changes(context):
    directory = r"doc\usersguide\source\changes"
    fname = relname2fname(context['release_name'])
    with open(os.path.join(context['build_dir'], directory, fname)) as f:
        return f.read().decode('utf-8-sig')


def release_highlights(context):
    fname = relname2fname(context['release_name'])
    with open(os.path.join(context['webbuild_dir'], "highlights", fname)) as f:
        return f.read().decode('utf-8-sig')


# -------------------------------- #
# end of specific helper functions #
# -------------------------------- #


# ----- #
# steps #
# ----- #

def check_local_repo(context):
    # releasing from the local clone has the advantage I can prepare the
    # release offline and only push and upload it when I get back online
    branch = context['branch']

    s = "Using local repository at: {repository} !".format(**context)
    print("\n", s, "\n", "=" * len(s), "\n", sep='')

    status = call('git status -s -b')
    lines = status.splitlines()
    statusline, lines = lines[0], lines[1:]
    curbranch = branchname(statusline)
    if curbranch != branch:
        print("%s is not the current branch (%s). "
              "Please use 'git checkout %s'." % (branch, curbranch, branch))
        exit(1)

    if lines:
        uncommited = sum(1 for line in lines if line[1] in 'MDAU')
        untracked = sum(1 for line in lines if line.startswith('??'))
        print('Warning: there are %d files with uncommitted changes '
              'and %d untracked files:' % (uncommited, untracked))
        print('\n'.join(lines))
        if no('Do you want to continue?'):
            exit(1)

    ahead = call('git log --format=format:%%H origin/%s..%s' % (branch, branch))
    num_ahead = len(ahead.splitlines())
    print("Branch '%s' is %d commits ahead of 'origin/%s'"
          % (branch, num_ahead, branch), end='')
    if num_ahead:
        if yes(', do you want to push?'):
            do('Pushing changes', call, 'git push')
    else:
        print()


def clone_repository(context):
    chdir(context['tmp_dir'])

    # make a temporary clone in /tmp. The goal is to make sure we do not
    # include extra/unversioned files. For the -src archive, I don't think
    # there is a risk given that we do it via git, but the risk is there for
    # the bundles (src/build is not always clean, examples, editor, ...)

    # Since this script updates files (update_changelog and build_website), we
    # need to get those changes propagated to GitHub. I do that by updating the
    # temporary clone then push twice: first from the temporary clone to the
    # "working copy clone" (eg ~/devel/liam2) then to GitHub from there. The
    # alternative to modify the "working copy clone" directly is worse because
    # it needs more complicated path handling that the 2 push approach.
    do('Cloning repository',
       call, 'git clone -b {branch} {repository} webbuild'.format(**context))


def check_clone(context):
    # check release highlights
    print(release_highlights(context))
    if no('Does the release highlights look right?'):
        exit(1)


def build_website(context):
    chdir(context['tmp_dir'])

    release_name = context['release_name']

    # XXX: should we announce pre-release on the website?
    if isprerelease(release_name):
        return

    fnames = ["LIAM2Suite-{}-win32.zip", "LIAM2Suite-{}-win64.zip",
              "LIAM2-{}-src.zip"]
    fpaths = [fname.format(release_name) for fname in fnames]
    s32b, s64b, ssrc = [size2str(getsize(fpath)) for fpath in fpaths]

    chdir(context['webbuild_dir'])

    generate(r'conf.py', version=short(release_name))
    generate(r'pages\download.rst',
             version=release_name, short_version=short(release_name),
             size32b=s32b, size64b=s64b, sizesrc=ssrc)
    generate(r'pages\documentation.rst',
             version=release_name, short_version=short(release_name))

    title = 'Version %s released' % short(release_name)
    # strip is important otherwise fname contains a \n and git chokes on it
    fname = call('tinker --filename --post "%s"' % title).strip()

    # for (intersphinx) links to documentation in release notes
    copy2('{tmp_dir}\htmldoc\objects.inv'.format(**context), '.')
    call('tinker --build')

    call('start ' + abspath(r'blog\html\index.html'), shell=True)
    call('start ' + abspath(r'blog\html\pages\download.html'), shell=True)
    call('start ' + abspath(r'blog\html\pages\documentation.html'), shell=True)

    if no('Does the website look good?'):
        exit(1)

    call('git add master.rst')
    call('git add %s' % fname)
    call('git commit -m "announce version %s"' % short(release_name))


def final_confirmation(context):
    msg = """Is the release looking good? If so the website will be uploaded
to the production server and the release will be announced.
"""
    if no(msg):
        exit(1)


def upload(context):
    # pscp is the scp provided in PuTTY's installer
    base_url = '%s@%s:%s' % ('cic', WEBSITE, WEBSITE)

    # 3) website
    if not isprerelease(context['release_name']):
        chdir(context['webbuild_dir'])
        chdir(r'blog\html')
        subprocess.call(r'pscp -r * %s' % base_url)


def pull(context):
    # pull the changelog commits to the branch (usually master)
    # and the release tag (which refers to the last commit)
    chdir(context['repository'])
    do('Pulling changes in {repository}'.format(**context), call,
       'git pull --ff-only --tags {webbuild_dir} {branch}'.format(**context))


def push(context):
    chdir(context['repository'])
    do('Pushing website changes to GitHub', call,
       'git push origin {branch} --follow-tags'.format(**context))


def announce(context):
    chdir(context['build_dir'])

    release_name = context['release_name']

    # ideally we should use the html output of the rst file, but this is simpler
    changes = rst2txt(release_changes(context))
    body = """\
I am pleased to announce that version %s of LIAM2 is now available.

%s

More details and the complete list of changes are available below.

This new release can be downloaded on our website:
http://liam2.plan.be/pages/download.html

As always, *any* feedback is very welcome, preferably on the liam2-users
mailing list: liam2-users@googlegroups.com (you need to register to be
able to post).

%s
""" % (short(release_name), release_highlights(context), changes)

    send_outlook('liam2-announce@googlegroups.com',
                 'Version {} released'.format(short(release_name)),
                 body)


# ------------ #
# end of steps #
# ------------ #

steps_funcs = [
    (check_local_repo, ''),
    (clone_repository, ''),
    (check_clone, ''),
    (build_website, 'Building website'),
    (final_confirmation, ''),
    # We used to push from /tmp to the local repository but you cannot push
    # to the currently checked out branch of a repository, so we need to
    # pull changes instead. However pull (or merge) add changes to the
    # current branch, hence we make sure at the beginning of the script
    # that the current git branch is the branch to release. It would be
    # possible to do so without a checkout by using:
    # git fetch {tmp_path} {branch}:{branch}
    # instead but then it only works for fast-forward and non-conflicting
    # changes. So if the working copy is dirty, you are out of luck.
    (pull, ''),
    # >>> need internet from here
    (push, ''),
    (upload, 'Uploading'),
    (announce, 'Announcing'),
    # (cleanup, 'Cleaning up')
]


def make_release(release_name='dev', steps=':'):
    func_names = [f.__name__ for f, desc in steps_funcs]
    if ':' in steps:
        start, stop = steps.split(':')
        start = func_names.index(start) if start else 0
        # + 1 so that stop bound is inclusive
        stop = func_names.index(stop) + 1 if stop else len(func_names)
    else:
        # assuming a single step
        start = func_names.index(steps)
        stop = start + 1

    if release_name == 'dev':
        raise ValueError("cannot update website for 'dev' releases")

    if 'pre' in release_name:
        raise ValueError("'pre' is not supported anymore, use 'alpha' or "
                         "'beta' instead")
    if '-' in release_name:
        raise ValueError("- is not supported anymore")

    release_name = long_release_name(release_name)

    build_dir = os.path.join(TMP_PATH, 'build')
    if not exists(build_dir):
        exit(1)

    context = {'branch': 'master', 'release_name': release_name,
               'repository': (abspath(dirname(__file__))),
               'tmp_dir': TMP_PATH,
               'build_dir': build_dir,
               'webbuild_dir': os.path.join(TMP_PATH, 'webbuild')}
    for step_func, step_desc in steps_funcs[start:stop]:
        if step_desc:
            do(step_desc, step_func, context)
        else:
            step_func(context)

if __name__ == '__main__':
    argv = sys.argv
    if len(argv) < 2:
        print("Usage: %s release_name|dev [step|startstep:stopstep]"
              % argv[0])
        print("steps:", ', '.join(f.__name__ for f, _ in steps_funcs))
        sys.exit()

    make_release(*argv[1:])
