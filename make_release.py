#!/usr/bin/python
# Release script for Liam2
# Licence: GPLv3
from __future__ import print_function

import errno
import os
import stat

from os import chdir, makedirs
from os.path import exists
from shutil import copytree, copy2, rmtree as _rmtree
from subprocess import check_output, STDOUT


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
    return check_output(*args, stderr=STDOUT, **kwargs)


def git_remote_last_rev(url, branch=None):
    """
    url of the remote repository
    branch is an optional branch (defaults to 'refs/heads/master')
    """
    if branch is None:
        branch = 'refs/heads/master'
    output = call('git ls-remote %s %s' % (url, branch))
    for line in output.splitlines():
        if line.endswith(branch):
            return line.split()[0]
    raise Exception("Could not determine revision number")


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
    print(description, end=' ')
    func(*args, **kwargs)
    print("done.")


def copy_release(release_name):
    chdir('..')
    copytree(r'build\bundle\editor', r'win32\editor')
    copytree(r'build\bundle\editor', r'win64\editor')
    copytree(r'build\tests\examples', r'win32\examples')
    copytree(r'build\tests\examples', r'win64\examples')
    copytree(r'build\src\build\exe.win32-2.7', r'win32\liam2')
    copytree(r'build\src\build\exe.win-amd64-2.7', r'win64\liam2')
    copytree(r'build\doc\usersguide\build\html',
             r'win32\documentation\html')
    copytree(r'build\doc\usersguide\build\html',
             r'win64\documentation\html')
    copy2(r'build\doc\usersguide\build\latex\LIAM2UserGuide.pdf',
          r'win32\documentation')
    copy2(r'build\doc\usersguide\build\latex\LIAM2UserGuide.pdf',
          r'win64\documentation')
    # standalone docs
    copy2(r'build\doc\usersguide\build\latex\LIAM2UserGuide.pdf',
          'LIAM2UserGuide-%s.pdf' % release_name)
    copy2(r'build\doc\usersguide\build\htmlhelp\LIAM2UserGuide.chm',
          'LIAM2UserGuide-%s.chm' % release_name)
    copytree(r'build\doc\usersguide\build\html',
             'html\\%s' % release_name)


def create_bundles(release_name):
    chdir('win32')
    call('7z a -tzip ..\Liam2Suite-%s-win32.zip *' % release_name)
    chdir('..')
    chdir('win64')
    call('7z a -tzip ..\Liam2Suite-%s-win64.zip *' % release_name)
    chdir('..')


def cleanup():
    rmtree('win32')
    rmtree('win64')
    rmtree('build')


def make_release(release_name=None, branch=None):
    # Since git is a dvcs, we could make this script work locally, but it would
    # not be any more useful because making a release is usually to distribute
    # it to someone, and for that I need network access anyway.
    # Furthermore, cloning from the remote repository makes sure we do not
    # include any untracked file

    # git config --get remote.origin.url
    repository = 'https://github.com/liam2/liam2.git'
    if branch is None:
        branch = 'master'

    status = call('git status -s')
    lines = status.splitlines()
    if lines:
        uncommited = sum(1 for line in lines if line.startswith(' M'))
        untracked = sum(1 for line in lines if line.startswith('??'))
        print('Warning: there are %d files with uncommitted changes '
              'and %d untracked files:' % (uncommited, untracked))
        print(status)
        if no('Do you want to continue?'):
            exit(1)

    ahead = call('git log --format=format:%%H origin/%s..%s' % (branch, branch))
    num_ahead = len(ahead.splitlines())
    print("Branch '%s' is %d commits ahead of 'origin/%s'"
          % (branch, num_ahead, branch), end='')
    if num_ahead:
        if yes(', do you want to push?'):
            do('Pushing changes...', call, 'git push')
    else:
        print()

    rev = git_remote_last_rev(repository, 'refs/heads/%s' % branch)

    if release_name is None:
        # take first 7 digits of commit hash
        release_name = rev[:7]

    if no('Release version %s (%s)?' % (release_name, rev)):
        exit(1)

    chdir('c:\\tmp')
    if exists('liam2_new_release'):
        rmtree('liam2_new_release')
    makedirs('liam2_new_release')
    chdir('liam2_new_release')

    do('Cloning...', call, 'git clone -b %s %s build' % (branch, repository))

    chdir('build')

    print()
    print(call('git log -1').decode('utf8'))
    print()

    if no('Does that last commit look right?'):
        exit(1)

    do('Creating source archive...', call,
       'git archive --format zip --output liam2-%s-src.zip %s'
       % (release_name, rev))
    do('Building everything...', call, 'buildall.bat')
    do('Moving stuff around...', copy_release, release_name)
    do('Creating bundles...', create_bundles, release_name)

    if release_name != rev[:7]:
        if no('Is the release looking good (if so, the tag will be '
              'created and pushed)?'):
            exit(1)

        do('Tagging release...', call,
           'git tag -a %{name}s -m "tag release %{name}s"'
           % {'name': release_name})
        do('Pushing tag...', call, 'git push')

    do('Cleaning up...', cleanup)


if __name__=='__main__':
    from sys import argv

    # if len(argv) < 2:
    #     print "Usage: %s [version] [branch]" % (argv[0],)
    #     exit(2)

    make_release(*argv[1:])
