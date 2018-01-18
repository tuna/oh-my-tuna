#!/usr/bin/env python
#
#  This file is part of oh-my-tuna
#  Copyright (c) 2018 oh-my-tuna's authors
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import subprocess
import os
import sys
import argparse
from six.moves import input
from contextlib import contextmanager

mirror_root = "mirrors.tuna.tsinghua.edu.cn"
always_yes = False
verbose = False


@contextmanager
def cd(path):
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_cwd)


def sh(command):
    try:
        if verbose:
            print('$ %s' % command)
        return subprocess.check_output(
            command.split()).decode('utf-8').rstrip()
    except Exception as e:
        return None


def ask_if_change(name, expected, command_read, command_set):
    current = sh(command_read)
    if current != expected:
        print('%s Before:' % name)
        print(current)
        print('%s After:' % name)
        print(expected)
        global always_yes
        if always_yes:
            sh(command_set)
        else:
            ans = input('Do you wish to proceed(y/n/a):')
            if ans == 'a':
                always_yes = True
            if ans != 'n':
                sh(command_set)
                print('Command %s succeeded' % command_set)
    else:
        print('%s is already configured to TUNA mirrors' % name)


def homebrew():
    repo = sh('brew --repo')
    if repo:
        with cd(repo):
            ask_if_change(
                'Homebrew repo',
                'https://%s/git/homebrew/brew.git' % mirror_root,
                'git remote get-url origin',
                'git remote set-url origin https://%s/git/homebrew/brew.git' %
                mirror_root)


def main():
    parser = argparse.ArgumentParser(
        description='Use TUNA mirrors everywhere when applicable')
    parser.add_argument(
        '-v', '--verbose', help='verbose output', action='store_true')
    parser.add_argument(
        '-y',
        '--yes',
        help='always answer yes to questions',
        action='store_true')
    args = parser.parse_args()
    global verbose
    verbose = args.verbose
    global always_yes
    always_yes = args.yes

    homebrew()


if __name__ == "__main__":
    main()
