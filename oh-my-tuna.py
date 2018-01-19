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
import argparse
import re
from six.moves import input
import platform
from contextlib import contextmanager

mirror_root = "mirrors.tuna.tsinghua.edu.cn"
always_yes = False
verbose = False

os_release_regex = re.compile(r"^ID=\"?([^\"\n]+)\"?$", re.M)


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
        if isinstance(command, str):
            command = command.split()
        return subprocess.check_output(command).decode('utf-8').rstrip()
    except Exception as e:
        return None


def user_prompt():
    global always_yes
    if always_yes:
        return True

    ans = input('Do you wish to proceed(y/n/a):')
    if ans == 'a':
        always_yes = True
    return ans != 'n'


def ask_if_change(name, expected, command_read, command_set):
    current = sh(command_read)
    if current != expected:
        print('%s Before:' % name)
        print(current)
        print('%s After:' % name)
        print(expected)
        if user_prompt():
            sh(command_set)
            print('Command %s succeeded' % command_set)
            return True
        else:
            return False
    else:
        print('%s is already configured to TUNA mirrors' % name)
        return True


def get_linux_distro():
    os_release = sh('cat /etc/os-release')
    if not os_release:
        return None
    match = re.findall(os_release_regex, os_release)
    if len(match) != 1:
        return None
    return match[0]


def set_env(key, value):
    shell = os.environ.get('SHELL').split('/')[-1]
    if shell == 'bash' or shell == 'sh':
        with open(os.path.expanduser('~/.profile'), 'a') as f:
            f.write('export %s=%s\n' % (key, value))
    elif shell == 'zsh':
        with open(os.path.expanduser('~/.zprofile'), 'a') as f:
            f.write('export %s=%s\n' % (key, value))
    else:
        print('Please set %s=%s' % (key, value))


def remove_env(key):
    shell = os.environ.get('SHELL').split('/')[-1]
    if shell == 'bash' or shell == 'sh':
        pattern = "^export %s=" % key
        profile = "~/.profile"
    elif shell == 'zsh':
        pattern = "^export %s=" % key
        profile = "~/.zprofile"
    if pattern:
        profile = os.path.expanduser(profile)
        if platform.system() == 'Darwin': # TODO: More BSD systems
            sed = ['sed', '-i', "", "/%s/d" % pattern, profile]
        else:
            sed = ['sed', '-i', "/%s/d" % pattern, profile]
        return sh(sed)
    else:
        print('Please remove environment variable %s' % key)



class Base(object):
    """
    Name of this mirror/module
    """

    @staticmethod
    def name():
        raise NotImplementedError

    """
    Returns whether this mirror is applicable
    """

    @staticmethod
    def is_applicable():
        return False

    """
    Returns whether this mirror is already up
    """

    @staticmethod
    def is_online():
        raise NotImplementedError

    """
    Activate this mirror
    Returns True if this operation is completed, False otherwise
    Caller should never invoke this method when is_online returns True
    """

    @staticmethod
    def up():
        raise NotImplementedError

    """
    Deactivate this mirror
    Returns True if this operation is completed, False otherwise
    Caller should never invoke this method when is_online returns False
    """

    @staticmethod
    def down():
        raise NotImplementedError

    """
    Print a log entry with the name of this mirror/module
    """

    @classmethod
    def log(cls, msg):
        print('[%s]: %s' % (cls.name(), msg))


class ArchLinux(Base):
    @staticmethod
    def name():
        return 'Arch Linux'

    @staticmethod
    def is_applicable():
        return os.path.isfile(
            '/etc/pacman.d/mirrorlist') and get_linux_distro() == 'arch'

    @staticmethod
    def is_online():
        mirror_re = re.compile(
            r" *Server *= *(http|https)://%s/archlinux/\$repo/os/\$path\n" %
            mirror_root, re.M)
        ml = open('/etc/pacman.d/mirrorlist', 'r')
        lines = ml.readlines()
        result = map(lambda l: re.match(mirror_re, l), lines)
        result = any(result)
        ml.close()
        return result

    @staticmethod
    def up():
        # Match commented or not
        mirror_re = re.compile(
            r" *(# *)?Server *= *(http|https)://%s/archlinux/\$repo/os/\$path\n"
            % mirror_root, re.M)
        banner = '# Generated and managed by the awesome oh-my-tuna\n'
        target = "Server = https://%s/archlinux/$repo/os/$path\n\n" % mirror_root

        print(
            'This operation will insert the following line into the beginning of your pacman mirrorlist:\n%s'
            % target[:-2])
        if not user_prompt():
            return False

        ml = open('/etc/pacman.d/mirrorlist', 'r')
        lines = ml.readlines()

        # Remove all
        lines = filter(lambda l: re.match(mirror_re, l) is None, lines)

        # Remove banner
        lines = filter(lambda l: l != banner, lines)

        # Finish reading
        lines = list(lines)

        # Remove padding newlines
        k = 0
        while k < len(lines) and lines[k] == '\n':
            k += 1

        ml.close()
        ml = open('/etc/pacman.d/mirrorlist', 'w')
        # Add target
        ml.write(banner)
        ml.write(target)
        ml.writelines(lines[k:])
        ml.close()
        return True

    @staticmethod
    def down():
        print(
            'This action will comment out TUNA mirrors from your pacman mirrorlist, if there is any.'
        )
        if not user_prompt():
            return False

        # Simply remove all matched lines
        mirror_re = re.compile(
            r" *Server *= *(http|https)://%s/archlinux/\$repo/os/\$path\n" %
            mirror_root, re.M)

        ml = open('/etc/pacman.d/mirrorlist', 'r')
        lines = ml.readlines()
        lines = list(
            map(lambda l: l if re.match(mirror_re, l) is None else '# ' + l,
                lines))
        ml.close()
        ml = open('/etc/pacman.d/mirrorlist', 'w')
        ml.writelines(lines)
        ml.close()
        return True


class Homebrew(Base):
    @staticmethod
    def name():
        return 'Homebrew'

    @staticmethod
    def is_applicable():
        return sh('brew --repo') is not None

    @staticmethod
    def is_online():
        repo = sh('brew --repo')
        with cd(repo):
            repo_online = sh('git remote get-url origin'
                      ) == 'https://%s/git/homebrew/brew.git' % mirror_root
        if repo_online:
            return os.environ.get('HOMEBREW_BOTTLE_DOMAIN') == 'https://%s/homebrew-bottles' % mirror_root
        return False


    @staticmethod
    def up():
        repo = sh('brew --repo')
        with cd(repo):
            ask_if_change(
                'Homebrew repo',
                'https://%s/git/homebrew/brew.git' % mirror_root,
                'git remote get-url origin',
                'git remote set-url origin https://%s/git/homebrew/brew.git' %
                mirror_root)
        for tap in ('homebrew-core', 'homebrew-python', 'homebrew-science'):
            tap_path = '%s/Library/Taps/homebrew/%s' % (repo, tap)
            if os.path.isdir(tap_path):
                with cd(tap_path):
                    ask_if_change(
                        'Homebrew tap %s' % tap,
                        'https://%s/git/homebrew/%s.git' % (mirror_root, tap),
                        'git remote get-url origin',
                        'git remote set-url origin https://%s/git/homebrew/%s.git'
                        % (mirror_root, tap))
        set_env('HOMEBREW_BOTTLE_DOMAIN', 'https://%s/homebrew-bottles' % mirror_root)
        return True

    @staticmethod
    def down():
        repo = sh('brew --repo')
        with cd(repo):
            sh('git remote set-url origin https://github.com/homebrew/brew.git'
               )
            for tap in ('homebrew-core', 'homebrew-python',
                        'homebrew-science'):
                tap_path = '%s/Library/Taps/homebrew/%s' % (repo, tap)
                if os.path.isdir(tap_path):
                    with cd(tap_path):
                        sh('git remote set-url origin https://github.com/homebrew/%s.git'
                           % tap)
            sh('git remote get-url origin'
                      ) == 'https://github.com/homebrew/brew.git'
        return remove_env('HOMEBREW_BOTTLE_DOMAIN')


class CTAN(Base):
    @staticmethod
    def name():
        return 'CTAN'

    @staticmethod
    def is_applicable():
        return sh('tlmgr --version') is not None

    @staticmethod
    def is_online():
        return sh(
            'tlmgr option repository'
        ) == 'Default package repository (repository): https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet'

    @staticmethod
    def up():
        return ask_if_change(
            'CTAN mirror',
            'Default package repository (repository): https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet',
            'tlmgr option repository',
            'tlmgr option repository https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet'
        )


class Ubuntu(Base):
    @staticmethod
    def build_template(mirror):
        repos = ['', '-updates', '-security', '-backports']
        release = sh('lsb_release -sc')
        lines = ['deb %s/ubuntu %s%s main multiverse universe restricted\n' % (mirror, release, repo) for repo in repos]
        tmpl = ''.join(lines)
        return tmpl

    @staticmethod
    def name():
        return 'Ubuntu'

    @staticmethod
    def is_applicable():
        return os.path.isfile(
            '/etc/apt/sources.list') and get_linux_distro() == 'ubuntu'

    @staticmethod
    def is_online():
        with open('/etc/apt/sources.list', 'r') as sl:
            content = sl.read();
            return content == Ubuntu.build_template('https://' + mirror_root)

    @staticmethod
    def up():
        print('This operation will move your current sources.list to sources.on-my-tuna.bak.list,\n' + \
              'and use TUNA apt source instead.')
        if not user_prompt():
            return False
        if os.path.isfile('/etc/apt/sources.list'):
            sh('cp /etc/apt/sources.list /etc/apt/sources.oh-my-tuna.bak.list')
        with open('/etc/apt/sources.list', 'w') as sl:
            sl.write(Ubuntu.build_template('https://' + mirror_root))
        return True

    @staticmethod
    def down():
        print('This operation will copy sources.on-my-tuna.bak.list to sources.list if there is one,\n' + \
              'otherwise build a new sources.list with archive.ubuntu.com as its mirror root.')
        if not user_prompt():
            return False
        if os.path.isfile('/etc/apt/sources.oh-my-tuna.bak.list'):
            if sh('cp /etc/apt/sources.oh-my-tuna.bak.list /etc/apt/sources.list') is not None:
                return True
        with open('/etc/apt/sources.list', 'w') as sl:
            sl.write(Ubuntu.build_template('http://archive.ubuntu.com'))
        return True


MODULES = [ArchLinux, Homebrew, CTAN, Ubuntu]


def main():
    parser = argparse.ArgumentParser(
        description='Use TUNA mirrors everywhere when applicable')
    parser.add_argument(
        'subcommand',
        nargs='?',
        metavar='SUBCOMMAND',
        choices=['up', 'down', 'status'],
        default='up')
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

    if args.subcommand == 'up':
        for m in MODULES:
            if m.is_applicable():
                if not m.is_online():
                    m.log('Activating...')
                    try:
                        result = m.up()
                        if not result:
                            m.log('Operation cancled')
                        else:
                            m.log('Mirror has been activated')
                    except NotImplementedError:
                        m.log(
                            'Mirror doesn\'t support activation. Please activate manually'
                        )

    if args.subcommand == 'down':
        for m in MODULES:
            if m.is_applicable():
                if m.is_online():
                    m.log('Deactivating...')
                    try:
                        result = m.down()
                        if not result:
                            m.log('Operation cancled')
                        else:
                            m.log('Mirror has been deactivated')
                    except NotImplementedError:
                        m.log(
                            'Mirror doesn\'t support deactivation. Please deactivate manually'
                        )

    if args.subcommand == 'status':
        for m in MODULES:
            if m.is_applicable():
                if m.is_online():
                    m.log('Online')
                else:
                    m.log('Offline')


if __name__ == "__main__":
    main()
