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
from six.moves import input
from contextlib import contextmanager

mirror_root = "mirrors.tuna.tsinghua.edu.cn"


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
        ans = input('Do you wish to proceed(y/n):')
        if ans == 'y':
            sh(command_set)
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
    homebrew()


main()
