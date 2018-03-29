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
import errno
import argparse
import re
import platform
from contextlib import contextmanager

try:
   input = raw_input
except NameError:
   pass

try:
    import configparser
except ImportError:
    import ConfigParser as configparser


mirror_root = "mirrors.tuna.tsinghua.edu.cn"
host_name = "tuna.tsinghua.edu.cn"
always_yes = False
verbose = False
is_global = True

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
        return subprocess.check_output(command, stderr=subprocess.STDOUT).decode('utf-8').rstrip()
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
        sh(sed)
        return True
    else:
        print('Please remove environment variable %s' % key)
        return False


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise



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
    def log(cls, msg, level='i'):
        levels = "viodwe" # verbose, info, ok, debug, warning, error
        assert level in levels

        global verbose
        if level == 'v' and verbose:
            return

        color_prefix = {
            'v': '',
            'i': '',
            'o': '\033[32m',
            'd': '\033[34m',
            'w': '\033[33m',
            'e': '\033[31m'
        }
        if color_prefix[level]:
            color_suffix = '\033[0m'
        else:
            color_suffix = ''

        print('%s[%s]: %s%s' % (color_prefix[level], cls.name(), msg, color_suffix))


class Pypi(Base):
    mirror_url = 'https://pypi.%s/simple' % host_name

    """
    Reference: https://pip.pypa.io/en/stable/user_guide/#configuration
    """
    @staticmethod
    def config_files():
        system = platform.system()
        if system == 'Darwin':
            return ('$HOME/Library/Application Support/pip/pip.conf', '$HOME/.pip/pip.conf')
        elif system == 'Windows':
            return ('%APPDATA%\pip\pip.ini', '~\pip\pip.ini')
        elif system == 'Linux':
            return ('$HOME/.config/pip/pip.conf', '$HOME/.pip/pip.conf')


    @staticmethod
    def name():
        return "pypi"


    @staticmethod
    def is_applicable():
        global is_global
        if is_global:
            # Skip if in global mode
            return False
        return sh('pip') is not None or sh('pip3') is not None


    @staticmethod
    def is_online():
        pattern = re.compile(r' *index-url *= *%s' % Pypi.mirror_url)
        config_files = Pypi.config_files()
        for conf_file in config_files:
            if not os.path.exists(os.path.expandvars(conf_file)):
                continue
            with open(os.path.expandvars(conf_file)) as f:
                for line in f:
                    if pattern.match(line):
                        return True
        return False


    @staticmethod
    def up():
        config_file = os.path.expandvars(Pypi.config_files()[0])
        config = configparser.ConfigParser()
        if os.path.exists(config_file):
            config.read(config_file)
        if not config.has_section('global'):
            config.add_section('global')
        if not os.path.isdir(os.path.dirname(config_file)):
            mkdir_p(os.path.dirname(config_file))
        config.set('global', 'index-url', Pypi.mirror_url)
        with open(config_file, 'w') as f:
            config.write(f)
        return True


    @staticmethod
    def down():
        config_files = map(os.path.expandvars, Pypi.config_files())
        config = configparser.ConfigParser()
        for path in config_files:
            if not os.path.exists(path):
                continue
            config.read(path)
            try:
                if config.get('global', 'index-url') == Pypi.mirror_url:
                    config.remove_option('global', 'index-url')
                with open(path, 'w') as f:
                    config.write(f)
            except (configparser.NoOptionError, configparser.NoSectionError):
                pass
        return True


class ArchLinux(Base):
    @staticmethod
    def name():
        return 'Arch Linux'

    @staticmethod
    def is_applicable():
        global is_global
        if not is_global:
            return False
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
        global is_global
        if not is_global:
            return False
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
        # Works both in global mode or local mode
        return sh('tlmgr --version') is not None

    @staticmethod
    def is_online():
        global is_global
        base = "tlmgr"
        if not is_global:
            # Setup usertree first
            sh("tlmgr init-usertree")
            base += " --usermode"

        return sh(
            '%s option repository' % base
        ) == 'Default package repository (repository): https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet'

    @staticmethod
    def up():
        global is_global
        base = "tlmgr"
        if not is_global:
            base += " --usermode"

        return ask_if_change(
            'CTAN mirror',
            'Default package repository (repository): https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet',
            '%s option repository' % base,
            '%s option repository https://mirrors.tuna.tsinghua.edu.cn/CTAN/systems/texlive/tlnet' % base
        )


class Anaconda(Base):
    url_free = 'https://%s/anaconda/pkgs/free/' % mirror_root
    url_main = 'https://%s/anaconda/pkgs/main/' % mirror_root


    @staticmethod
    def name():
        return "Anaconda"


    @staticmethod
    def is_applicable():
        # Works both in global mode and local mode
        return sh('conda -V') is not None


    @staticmethod
    def is_online():
        cmd = 'conda config --get channels'
        global is_global
        if is_global:
            cmd += ' --system'

        channels = sh(cmd).split('\n')
        in_channels = 0
        for line in channels:
            if Anaconda.url_free in line:
                in_channels += 1
            elif Anaconda.url_main in line:
                in_channels += 1
        return in_channels == 2


    @staticmethod
    def up():
        basecmd = 'conda config'
        global is_global
        if is_global:
            basecmd += ' --system'
        sh ("%s --add channels %s" % (basecmd, Anaconda.url_free))
        sh ("%s --add channels %s" % (basecmd, Anaconda.url_main))
        return True

    @staticmethod
    def down():
        basecmd = 'conda config'
        global is_global
        if is_global:
            basecmd += ' --system'
        sh ("%s --remove channels %s" % (basecmd, Anaconda.url_free))
        sh ("%s --remove channels %s" % (basecmd, Anaconda.url_main))
        return True


class Debian(Base):
    pools = "main contrib non-free"
    default_sources = {
            'http://deb.debian.org/debian': ['', '-updates'],
            'http://security.debian.org/debian-security': ['main', 'contrib', 'non-free'],
            }

    @staticmethod
    def build_mirrorspec():
        return {
                'https://' + mirror_root + '/debian': ['', '-updates'],
                'https://' + mirror_root + '/debian-security': ['/updates'],
            }

    @classmethod
    def build_template(cls, mirrorspecs):
        release = sh('lsb_release -sc')
        lines = ['%s %s %s%s %s\n' % (repoType, mirror, release, repo, cls.pools)
                    for mirror in mirrorspecs
                    for repo in mirrorspecs[mirror]
                    for repoType in ['deb', 'deb-src']]
        tmpl = ''.join(lines)
        return tmpl

    @staticmethod
    def name():
        return 'Debian'

    @staticmethod
    def is_applicable():
        global is_global
        if not is_global:
            return False
        return os.path.isfile(
            '/etc/apt/sources.list') and get_linux_distro() == 'debian'

    @classmethod
    def is_online(cls):
        with open('/etc/apt/sources.list', 'r') as sl:
            content = sl.read();
            return content == cls.build_template(cls.build_mirrorspec())

    @classmethod
    def up(cls):
        print('This operation will move your current sources.list to sources.on-my-tuna.bak.list,\n' + \
              'and use TUNA apt source instead.')
        if not user_prompt():
            return False
        if os.path.isfile('/etc/apt/sources.list'):
            sh('cp /etc/apt/sources.list /etc/apt/sources.oh-my-tuna.bak.list')
        with open('/etc/apt/sources.list', 'w') as sl:
            sl.write(cls.build_template(cls.build_mirrorspec()))
        return True

    @classmethod
    def down(cls):
        print('This operation will copy sources.on-my-tuna.bak.list to sources.list if there is one,\n' + \
              'otherwise build a new sources.list with archive.ubuntu.com as its mirror root.')
        if not user_prompt():
            return False
        if os.path.isfile('/etc/apt/sources.oh-my-tuna.bak.list'):
            if sh('cp /etc/apt/sources.oh-my-tuna.bak.list /etc/apt/sources.list') is not None:
                return True
        with open('/etc/apt/sources.list', 'w') as sl:
            sl.write(cls.build_template(cls.default_sources))
        return True


class Ubuntu(Debian):
    default_sources = { 'http://archive.ubuntu.com/ubuntu': ['', '-updates', '-security', '-backports'] }
    pools = "main multiverse universe restricted"

    @staticmethod
    def build_mirrorspec():
        return {
                'https://' + mirror_root + '/ubuntu': ['', '-updates', '-security', '-backports'],
            }

    @staticmethod
    def name():
        return 'Ubuntu'

    @staticmethod
    def is_applicable():
        global is_global
        if not is_global:
            return False
        return os.path.isfile(
            '/etc/apt/sources.list') and get_linux_distro() == 'ubuntu'


MODULES = [ArchLinux, Homebrew, CTAN, Pypi, Anaconda, Debian, Ubuntu]


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
    parser.add_argument(
        '-g',
        '--global',
        dest='is_global',
        help='apply system-wide changes. This option may affect applicability of some modules.',
        action='store_true')

    args = parser.parse_args()
    global verbose
    verbose = args.verbose
    global always_yes
    always_yes = args.yes
    global is_global
    is_global = args.is_global

    if args.subcommand == 'up':
        for m in MODULES:
            if m.is_applicable():
                if not m.is_online():
                    m.log('Activating...')
                    try:
                        result = m.up()
                        if not result:
                            m.log('Operation cancled', 'w')
                        else:
                            m.log('Mirror has been activated', 'o')
                    except NotImplementedError:
                        m.log(
                            'Mirror doesn\'t support activation. Please activate manually'
                        , 'e')

    if args.subcommand == 'down':
        for m in MODULES:
            if m.is_applicable():
                if m.is_online():
                    m.log('Deactivating...')
                    try:
                        result = m.down()
                        if not result:
                            m.log('Operation cancled', 'w')
                        else:
                            m.log('Mirror has been deactivated', 'o')
                    except NotImplementedError:
                        m.log(
                            'Mirror doesn\'t support deactivation. Please deactivate manually'
                        , 'e')

    if args.subcommand == 'status':
        for m in MODULES:
            if m.is_applicable():
                if m.is_online():
                    m.log('Online', 'o')
                else:
                    m.log('Offline')


if __name__ == "__main__":
    main()
