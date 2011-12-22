# -*- coding: utf-8 -*-
#
# Copyright (c) 2003-2011 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.

import os
import stat
import re
import sys
import commands
import logging
import itertools
import subprocess
from os.path import basename, join, exists, isdir, isfile
from glob import glob

from logilab.devtools import BASE_EXCLUDE, __path__
from logilab.devtools.lgp import LGP, LGP_CONFIG_FILE, utils
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException
from logilab.devtools.lib.changelog import CHANGEFILE
from logilab.devtools.lib.manifest import (get_manifest_files, read_manifest_in,
                                           match_extensions, JUNK_EXTENSIONS)


OK, NOK = 1, 0
CHECKS = {'debian'    : set(['debian_dir', 'debian_rules', 'debian_copying',
                             'debian_source_value', 'debian_env',
                             'debian_changelog', 'debian_homepage', 'debian_maintainer']),
          'default'   : set(['builder',  'bin', 'release_number']),
          'distutils' : set(['manifest_in', 'pydistutils',]),
          'pkginfo'   : set(['debsign', 'package_info',
                             'pkginfo_copyright', 'tests_directory',
                             'readme', 'changelog']),
          'makefile'  : set(['makefile']),
          'cubicweb'  : set(), # XXX test presence of a ['migration_file'], for the current version
         }

# avoid warning from continuous integration report
if os.environ.get('APYCOT_ROOT'):
    # XXX check if a tty instead ?
    CHECKS['debian'].remove("debian_env")

REV_LINE = re.compile('__revision__.*')


def is_executable(filename):
    """return true if the file is executable"""
    mode = os.stat(filename)[stat.ST_MODE]
    return bool(mode & stat.S_IEXEC)

def make_executable(filename):
    """make a file executable for everybody"""
    mode = os.stat(filename)[stat.ST_MODE]
    os.chmod(filename, mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

def normalize_version(version):
    """remove trailing .0 in version if necessary (i.e. 1.1.0 -> 1.1, 2.0.0 -> 2)
    """
    if isinstance(version, basestring):
        version = tuple( int(num) for num in version.split('.'))
    while version and version[-1] == 0:
        version = version[:-1]
    return version

def _check_sh(checker, sh_file):
    """ check executable script files """
    status = OK
    data = open(sh_file).read()
    if data[:2] != '#!':
        checker.logger.error('script %s doesn\'t starts with "#!"' % sh_file)
        status = NOK
    if not is_executable(sh_file):
        make_executable(sh_file)
    cmd = '%s --help' % sh_file
    cmdstatus, _ = commands.getstatusoutput(cmd)
    if cmdstatus:
        checker.logger.error('%s returned status %s' % (cmd, cmdstatus))
        status = NOK
    return status

def _check_template(checker, filename, templatename):
    """check a file is similar to a reference template """
    if not exists(filename):
        checker.logger.warn('%s missing' % filename)
        return NOK
    template = open(join(__path__[0], 'templates', templatename)).read()
    template = REV_LINE.sub('', template)
    actual = open(filename).read()
    actual = REV_LINE.sub('', actual)
    if actual != template:
        checker.logger.warn('%s does not match the template' % filename)
    return OK

def _check_bat(checker, bat_file):
    """try to check windows .bat files
    """
    status = OK
    f = open(bat_file)
    data = f.read().strip()
    if not data[:11] == '@python -c ':
        msg = "unrecognized command %s" % data[:11]
        checker.logger.warn(bat_file, None, msg)
        return status
    if data[-26:] == '%1 %2 %3 %4 %5 %6 %7 %8 %9':
        command = data[1:-26]
    elif data[-2:] == '%*':
        command = data[1:-2]
    else:
        command = data
        checker.logger.error(bat_file, None, "forget arguments")
        status = NOK
    error = os.popen3('%s --help' % command)[2].read()
    if error:
        checker.logger.error(bat_file, None,
                       "error while executing (%s):\n%s"%(command, error))
        status = NOK
    return status


@LGP.register
class Checker(SetupInfo):
    """Check project in the current working directory.

    Just run: 'lgp check --list' for available checkers

    You can add the [CHECK] section in /etc/lgp/lgprc
    """
    name = "check"
    options = SetupInfo.options + [
               ('include',
                {'type': 'csv',
                 'dest': 'include_checks',
                 'short': 'i',
                 'metavar': "<comma separated names of check functions>",
                 'help': "force the inclusion of other check functions",
                 'default': [],
                }),
               ('exclude',
                {'type': 'csv',
                 'dest': 'exclude_checks',
                 'short': 'e',
                 'metavar' : "<comma separated names of check functions>",
                 'help': "force the exclusion of other check functions",
                 'default': [],
                }),
               ('set',
                {'type': 'csv',
                 'dest': 'set_checks',
                 'short': 's',
                 'metavar' : "<comma separated names of check functions>",
                 'help': "set a specific check functions list",
                 'default': [],
                }),
               ('list',
                {'action': 'store_true',
                 'dest' : "list_checks",
                 'short': 'l',
                 'help': "return a list of all available check functions"
                }),
              ]
    checklist = []
    counter = 0

    def run(self, args):
        if self.config.list_checks:
            self.list_checks()
            return 0
        self.start_checks()
        # Return the number of invalid tests
        return self.errors()

    def errors(self):
        return len(self.get_checklist())-self.counter

    def get_checklist(self, all=False):
        if all:
            return [funct for (name, funct) in globals().items() if name.startswith('check_')]
        try:
            checks = CHECKS['default']

            # we try to compile a coherent set of checks to apply
            if os.path.exists('setup.py'):
                checks.update(CHECKS['distutils'])
            if os.path.exists('__pkginfo__.py'):
                checks.update(CHECKS['pkginfo'])
            if os.path.exists('debian'):
                checks.update(CHECKS['debian'])
            if self.config.set_checks:
                checks = set()

            for c in itertools.chain(self.config.set_checks,
                                     self.config.include_checks):
                if c in CHECKS:
                    checks.update(CHECKS[c])
                else:
                    checks.add(c)
            for c in self.config.exclude_checks:
                if c in CHECKS:
                    checks.difference_update(CHECKS[c])
                else:
                    if c in checks:
                        checks.remove(c)
            self.checklist = [globals()["check_%s" % name] for name in checks]
        except KeyError, err:
            msg = "check function or category %s was not found. Use lgp check --list"
            raise LGPException(msg % str(err))
        return self.checklist

    def start_checks(self):
        checklist = self.get_checklist()
        self.logger.debug('applied checklist chain: %s'
                          % [f.__name__ for f in checklist])
        for func in self.checklist:
            loggername = func.__name__
            loggername = loggername.replace('_', '.', 1)
            self.logger = logging.getLogger(loggername)

            result = func(self)
            # result possible values:
            #   negative -> error occured !
            #   NOK: use a generic report function
            #   OK/None: add to counter
            if result == NOK :
                self.logger.error(func.__doc__)
            elif result is None or result > 0:
                self.counter += 1

    # TODO dump with --help and drop the command-line option
    def list_checks(self):
        def title(msg):
            print >> sys.stderr, "\n", msg, "\n", len(msg) * '='
        all_checks = self.get_checklist(all=True)
        checks     = self.get_checklist()
        if len(checks)==0:
            print >> sys.stderr, "No available check."
        else:
            print >> sys.stderr, "You can use check function names or categories with --set, --exclude or --include options"
            title("Current active checks")
            for check in checks:
                print >> sys.stderr, "%-25s: %s" % (check.__name__[6:], check.__doc__)
            title("Available categories")
            for cat, values in CHECKS.items():
                print >> sys.stderr, "%-10s: %s" % (cat, ", ".join(values))
            title("Inactive checks")
            for check in (set(all_checks) - set(checks)):
                print >> sys.stderr, "%-25s: %s" % (check.__name__[6:], check.__doc__)



# ========================================================
#
# Check functions collection starts here
# TODO make a package to add easily external checkers
# TODO instead of OK/NOK
#
# IMPORTANT ! all checkers should return a valid status !
# Example: OK, NOK or None
#
# ========================================================
def check_keyrings(checker):
    """check the mandatory keyrings for ubuntu in /usr/share/keyrings/"""
    msg = ""
    if not isfile("/usr/share/keyrings/debian-archive-keyring.gpg"):
        msg = "no keyring for debian in /usr/share/keyrings/ (debian-archive-keyring)"
    if not isfile("/usr/share/keyrings/ubuntu-archive-keyring.gpg"):
        msg = "no keyring for ubuntu in /usr/share/keyrings/ (ubuntu-archive-keyring)"
    if msg:
        checker.logger.warn(msg)
        checker.logger.info("you haven't installed archive keyring for ubuntu distributions")
        checker.logger.info("you can download it from http://fr.archive.ubuntu.com/ubuntu/pool/main/u/ubuntu-keyring")
        checker.logger.info("then copy keyring file into /usr/share/keyrings/ directory")
        checker.logger.info("example: wget -O /usr/share/keyrings/ubuntu-archive-keyring.gpg ftp://ftp.archive.ubuntu.com/ubuntu/project/ubuntu-archive-keyring.gpg")
    return OK

def check_debian_env(checker):
    """check usefull DEBFULLNAME and DEBEMAIL env variables"""
    email = os.environ.get('DEBEMAIL', os.environ.get('EMAIL', ""))
    name  = os.environ.get('DEBFULLNAME', os.environ.get('NAME'))
    if not email:
        checker.logger.warn('to update changelog, please define DEBEMAIL or EMAIL environ variable')
    # If DEBEMAIL or MAIL has the form "name <email>", then the maintainer
    # name will also be taken from here if neither DEBFULLNAME nor NAME is set.
    if not name and '<' not in email:
        checker.logger.warn('to update changelog, please define DEBFULLNAME or NAME environ variable')
    return OK

def check_pydistutils(checker):
    """check a .pydistutils.cfg file in home firectory"""
    if isfile(join(os.environ['HOME'], '.pydistutils.cfg')):
        checker.logger.warn('your ~/.pydistutils.cfg can conflict with distutils commands')
    return OK

def check_builder(checker):
    """check if the builder has been changed"""
    if os.environ.get('DEBUILDER'):
        checker.logger.warn('you have manually set a builder in DEBUILDER. Unset it if in doubt')
    return OK

def check_debian_dir(checker):
    """check the debian directory and debian/control file"""
    return isdir("debian") and isfile(join("debian","control"))

def check_debian_rules(checker):
    """check the debian*/rules file (filemode should be "+x")"""
    debian_dirs = glob("debian.*")
    debian_dirs.append('debian')
    for debian_dir in debian_dirs:
        rules = join(debian_dir, 'rules')
        if isfile(rules):
            if not is_executable(rules):
                msg = "check the '%s' file (filemode should be '+x')"
                checker.logger.warn(msg % rules)
            break
    else:
        checker.logger.warn('check the debian/rules file')
    return OK

def check_debian_copying(checker):
    """check debian/copyright file"""
    return isfile(join('debian', 'copyright'))

def check_debian_source_value(checker):
    """check debian source field value"""
    upstream_name = checker.get_upstream_name()
    debian_name   = checker.get_debian_name()
    if upstream_name != debian_name:
        checker.logger.warn("upstream project name (%s) is different from the "
                            "Source field value in your debian/control (%s)"
                            % (upstream_name, debian_name))
    return OK

def check_debian_changelog(checker, debian_dir=None):
    """check debian changelog error cases"""
    if debian_dir is None:
        debian_dirs = glob("debian.*")
        debian_dirs.append('debian')
    else:
        debian_dirs = [debian_dir]
    for debian_dir in debian_dirs:
        CHANGELOG = join(debian_dir, 'changelog')
        if isfile(CHANGELOG):
            # verify if changelog is closed
            cmd = "sed -ne '/^ -- $/p' %s" % CHANGELOG
            _, output = commands.getstatusoutput(cmd)
            if output:
                msg = "missing attribution trailer line. '%s' is not properly closed" % CHANGELOG
                checker.logger.warn(msg)
                return
            # consider UNRELEASED as problematic only if not on first line
            cmd = "sed -ne '2,${/UNRELEASED/p}' %s" % CHANGELOG
            _, output = commands.getstatusoutput(cmd)
            if output:
                checker.logger.debug('UNRELEASED keyword found in debian changelog')
            cmd = "sed -ne '/DISTRIBUTION/p' %s" % CHANGELOG
            _, output = commands.getstatusoutput(cmd)
            if output:
                checker.logger.error("old DISTRIBUTION keyword found in %s" % CHANGELOG)
            # check project name coherency
            if checker.get_debian_name() != utils._parse_deb_project():
                msg = "project name mismatch: debian/control says '%s' and debian/changelog says '%s'"
                checker.logger.error(msg % (checker.get_debian_name(), utils._parse_deb_project()))
            # check maintainer field
            cmd = "dpkg-parsechangelog -l%s | awk '/^Maintainer/ { $1 = \"\"; print }'"
            _, maintainer = commands.getstatusoutput(cmd % CHANGELOG)
            for d in [debian_dir, "debian"]:
                cmd = 'grep "%s" %s' % (maintainer.strip(), join(d, "control"))
                cmdstatus, _ = commands.getstatusoutput(cmd)
                if not cmdstatus: break
            else:
                checker.logger.warn("'%s' not found in Uploaders field"
                                    % maintainer.strip())
            # final check with Debian utility
            cmd = "dpkg-parsechangelog -l%s >/dev/null" % CHANGELOG
            _, output = commands.getstatusoutput(cmd)
            if output:
                checker.logger.error(output)
        else:
            if debian_dir == "debian":
                checker.logger.error("no debian*/changelog file found")

def check_debian_maintainer(checker):
    """check Maintainer field in debian/control file"""
    status = OK
    cmd = "awk '/^Maintainer/ { $1 = \"\"; print}' debian/control"
    cmdstatus, output = commands.getstatusoutput(cmd)
    if output.strip() != 'Logilab S.A. <contact@logilab.fr>':
        checker.logger.info("Maintainer value can be 'Logilab S.A. <contact@logilab.fr>'")
    return status

def check_readme(checker):
    """upstream README file is missing"""
    if not isfile('README'):
        checker.logger.warn(check_readme.__doc__)
    return OK

def check_changelog(checker):
    """upstream ChangeLog file is missing"""
    status = OK
    if not isfile(CHANGEFILE):
        checker.logger.warn(check_changelog.__doc__)
    else:
        cmd = "grep -E '^[[:space:]]+--[[:space:]]+$' %s" % CHANGEFILE
        status, _ = commands.getstatusoutput(cmd)
        if not status:
            checker.logger.warn("%s doesn't seem to be closed" % CHANGEFILE)
    return status

def check_copying(checker):
    """check upstream COPYING file """
    if not isfile('COPYING'):
        checker.logger.warn(check_copying.__doc__)
    return OK

def check_tests_directory(checker):
    """check your tests? directory """
    if not (isdir('test') or isdir('tests')):
        checker.logger.warn(check_tests_directory.__doc__)
    return OK

def check_run_tests(checker):
    """run unit tests"""
    testdirs = ('test', 'tests')
    for testdir in testdirs:
        if isdir(testdir):
            os.system('pytest')
    return OK

def check_makefile(checker):
    """check makefile file and expected targets (project, version)"""
    status = OK
    setup_file = checker.config.setup_file
    status = status and setup_file and isfile(setup_file)
    if status:
        for cmd in ['%s project', '%s version']:
            cmd %= setup_file
            if subprocess.call(cmd.split()):
                checker.logger.error("%s not a valid command" % cmd)
            status = NOK
    return status

def check_debian_homepage(checker):
    """check the debian homepage field"""
    status, _ = commands.getstatusoutput('grep ^Homepage debian/control')
    if not status:
        status, _ = commands.getstatusoutput('grep "Homepage: http://www.logilab.org/projects" debian/control')
        if not status:
            checker.logger.warn('rename "projects" to "project" in the "Homepage:" value in debian/control')
    else:
        checker.logger.warn('add a valid "Homepage:" field in debian/control')
    return OK

def check_bin(checker):
    """check executable script files in bin/ """
    status = OK
    if not exists('bin/'):
        return status
    for filename in os.listdir('bin/'):
        if filename in BASE_EXCLUDE:
            continue
        if filename[-4:] == '.bat':
            continue
        sh_file = join('bin/', filename)
        bat_file = sh_file + '.bat'
        if not exists(bat_file):
            checker.logger.warn('no %s file' % basename(bat_file))
        elif filename[-4:] == '.bat':
            _status = _check_bat(checker, bat_file)
            status = status and _status
        _status = _check_sh(checker, sh_file)
        status = status and _status
    return status

def check_documentation(checker):
    """check project's documentation"""
    status = OK
    if isdir('doc'):
        os.system('cd doc && make')
    else:
        checker.logger.warn("documentation directory not found")
    return status

def check_release_number(checker):
    """check the versions coherence between upstream and debian/changelog"""
    try:
        checker._check_version_mismatch()
    except LGPException, err:
        checker.logger.critical(err)
    return OK

def check_manifest_in(checker):
    """to correct unmatched files, please include or exclude them in MANIFEST.in"""
    status = OK
    dirname = checker.config.pkg_dir
    absfile = join(dirname, 'MANIFEST.in')
    # return immediatly if no file available
    if not isfile(absfile):
        return status

    # check matched files
    should_be_in = get_manifest_files(dirname=dirname)
    matched = set(read_manifest_in(None, dirname=dirname))
    for path in should_be_in:
        if path in matched:
            matched.remove(path)
        else:
            checker.logger.warn('%s unmatched' % path)
            # FIXME keep valid status till ``#2888: lgp check ignore manifest # "prune"``
            # path command not resolved
            # See http://www.logilab.org/ticket/2888
            #status = NOK
    # check garbage
    for filename in matched:
        if match_extensions(filename, JUNK_EXTENSIONS):
            checker.logger.warn('a junk extension is matched: %s' % filename)
    return status

def check_debsign(checker):
    """check requirements (~/.devscripts or gpg-agent) to sign packages"""
    if not getattr(checker.config, 'sign', True):
        return OK

    if not os.path.exists(os.path.expanduser("~/.devscripts")):
        msg = "please, export your DEBSIGN_KEYID in ~/.devscripts (read `debsign` manual)"
        checker.logger.error(msg)
        return NOK
    if 'GPG_AGENT_INFO' not in os.environ:
        checker.logger.warning('enable your gpg-agent to sign packages automatically')
        return NOK
    return OK

def check_package_info(checker):
    """check package information"""
    status = OK
    if hasattr(checker, "_package") and checker.package_format == "PackageInfo":
        if subprocess.call(['python', '__pkginfo__.py']):
            checker.logger.warn('command "python __pkginfo__.py" returns errors')
    else:
        return status

    # check mandatory attributes defined by pkginfo policy
    from logilab.devtools.lib.pkginfo import check_info_module
    class Reporter(object):
        def warning(self, path, line, msg):
            checker.logger.warn(msg)
        def error(self, path, line, msg):
            checker.logger.error(msg)
        def info(self, path, line, msg):
            checker.logger.info(msg)
        def fatal(self, path, line, msg):
            checker.logger.fatal(msg)
    return check_info_module(Reporter())

def check_pkginfo_copyright(checker):
    """check copyright header"""
    cmd = 'grep -EHnori "copyright.*[[:digit:]]{4}-.* LOGILAB S.A." * | grep -v $(date +%Y)'
    grep = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = grep.communicate()
    if out:
        checker.logger.warn(out.strip())
        checker.logger.warn('check copyright header of these previous files')
    if err:
        checker.logger.warn(err.strip())
    if grep.wait() >= 2:
        checker.logger.error('grep failed with exit status %d' % grep.wait())
        return NOK
    return OK
