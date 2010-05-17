#!/usr/bin/env python
# Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
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
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
""" lgp check [options]

    Provides functions to check a debian package for a python package
    depending of the setup format.

    Examples for pkginfo: correctness of __pkginfo__.py, release number
    consistency, MANIFEST.in matches what is int the directory, scripts in
    bin have a --help option and .bat equivalent, execute tests, setup.py
    matches devtools template, announce matches template too.

    You can use a setup.cfg file with the [LGP-CHECK] section
"""
__docformat__ = "restructuredtext en"


import os
import stat
import re
import commands
import logging
from subprocess import call, check_call, CalledProcessError
from os.path import basename, join, exists, isdir, isfile
from pprint import pformat

from logilab.common.compat import set

from logilab.devtools.lib.changelog import CHANGEFILE
from logilab.devtools.lib.manifest import (get_manifest_files, read_manifest_in,
                                           match_extensions, JUNK_EXTENSIONS)

from logilab.devtools import templates
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.exceptions import LGPException


OK, NOK = 1, 0
CHECKS = { 'debian'    : set(['debian_dir', 'debian_rules', 'debian_copying',
                          'debian_source_value', 'debian_env', 'debian_uploader',
                          'debian_changelog', 'debian_homepage']),
           'default'   : set(['builder', 'readme', 'changelog', 'bin', 'tests_directory',
                          'repository', 'release_number', 'manifest_in', 'pydistutils']),
           'setuptools' : set(),
           'pkginfo'    : set(['package_info', 'announce']),
           'makefile'   : set(['makefile']),
           'cubicweb'   : set(), # XXX test presence of a ['migration_file'], for the current version
         }

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
    template = open(join(templates.__path__[0], templatename)).read()
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


def run(args):
    """ Main function of lgp check command """
    try :
        checker = Checker(args)
        if checker.config.list_checks:
            checker.list_checks()
            return 0

        checker.start_checks()

        # Return the number of invalid tests
        return checker.errors()

    except NotImplementedError, exc:
        logging.error(exc)
        return 2
    except LGPException, exc:
        logging.critical(exc)
        return exc.exitcode()


class Checker(SetupInfo):
    """Lgp checker class

    Specific options are added. See lgp check --help
    """
    checklist = []
    counter = 0
    name = "lgp-check"
    options = (('include',
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
                 'help': "set a specific check functions list"
                }),
               ('list',
                {'action': 'store_true',
                 'dest' : "list_checks",
                 'short': 'l',
                 'help': "return a list of all available check functions"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Checker, self).__init__(arguments=args, options=self.options, usage=__doc__)

    def errors(self):
        return len(self.get_checklist())-self.counter

    def get_checklist(self, all=False):
        if all:
            return [funct for (name, funct) in globals().items() if name.startswith('check_')]
        try:
            checks = CHECKS['default']
            if os.path.exists('__pkginfo__.py'):
                checks.update(CHECKS['pkginfo'])
            if os.path.exists('debian'):
                checks.update(CHECKS['debian'])
            if self.config.set_checks:
                checks = set(self.config.set_checks)
            checks.update(self.config.include_checks)
            checks -= set(self.config.exclude_checks)
            self.checklist = [globals()["check_%s" % name] for name in checks]
        except KeyError, err:
            raise LGPException("The check %s was not found. Use lgp check --list" % str(err))
        return self.checklist

    def start_checks(self):
        for func in self.get_checklist():
            loggername = func.__name__
            loggername = loggername.replace('_',':', 1)
            self.logger = logging.getLogger(loggername)

            result = func(self)
            # result possible values:
            #   negative -> error occured !
            #   NOK: use a generic report function
            #   OK : add to counter
            if result == NOK :
                self.logger.error(func.__doc__)
            elif result>0:
                self.counter += 1

    # TODO dump with --help and drop the command-line option
    def list_checks(self):
        import sys
        all_checks = self.get_checklist(all=True)
        checks     = self.get_checklist()
        if len(checks)==0:
            print >>sys.stderr, "No available check."
        else:
            print >>sys.stderr, "You can use the --set, --exclude or --include options\n"
            msg = "Current active checks"
            print >>sys.stderr, msg; print >>sys.stderr, len(msg) * '='
            for check in checks:
                print >>sys.stderr, "%-25s: %s" % (check.__name__[6:], check.__doc__)
            msg = "Other available checks"
            print >>sys.stderr, "\n" + msg; print >>sys.stderr, len(msg) * '='
            for check in (set(all_checks) - set(checks)):
                print >>sys.stderr, "%-25s: %s" % (check.__name__[6:], check.__doc__)



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
        checker.logger.info(msg)
    return OK

def check_debian_env(checker):
    """check usefull DEBFULLNAME and DEBEMAIL env variables"""
    if 'DEBFULLNAME' not in os.environ or  'DEBEMAIL' not in os.environ:
        checker.logger.warn('you should define DEBFULLNAME and DEBEMAIL in your shell rc file')
    return OK

def check_pydistutils(checker):
    """check a .pydistutils.cfg file in home firectory"""
    if isfile(os.path.join(os.environ['HOME'], '.pydistutils.cfg')):
        checker.logger.warn('your ~/.pydistutils.cfg can conflict with distutils commands')
    return OK

def check_builder(checker):
    """check if the builder has been changed"""
    debuilder = os.environ.get('DEBUILDER') or False
    if debuilder:
        checker.logger.warn('you have set a different builder in DEBUILDER. Unset it if in doubt')
    return OK

def check_debian_dir(checker):
    """check the debian directory"""
    return isdir('debian')

def check_debian_rules(checker):
    """check the debian*/rules file (filemode) """
    debian_dir = checker.get_debian_dir()
    status = OK
    status = status and isfile(os.path.join(debian_dir, 'rules'))
    status = status and is_executable(os.path.join(debian_dir, 'rules'))
    return status

def check_debian_copying(checker):
    """check debian*/copyright file"""
    debian_dir = checker.get_debian_dir()
    return isfile(os.path.join(debian_dir,'copyright'))

def check_debian_source_value(checker):
    """check debian source field value"""
    upstream_name = checker.get_upstream_name()
    debian_name   = checker.get_debian_name()
    if upstream_name != debian_name:
        checker.logger.warn("upstream project name (%s) is different from the "
                            "Source field value in your debian/control (%s)"
                            % (upstream_name, debian_name))
    return OK

def check_debian_changelog(checker):
    """your debian changelog contains error(s)"""
    debian_dir = checker.get_debian_dir()
    CHANGELOG = os.path.join(debian_dir, 'changelog')
    status = OK
    if isfile(CHANGELOG):
        cmd = "sed -ne '/UNRELEASED/p' %s" % CHANGELOG
        _, output = commands.getstatusoutput(cmd)
        if output:
            status = NOK
            checker.logger.error('UNRELEASED keyword in debian changelog')
        cmd = "sed -ne '/DISTRIBUTION/p' %s" % CHANGELOG
        _, output = commands.getstatusoutput(cmd)
        if output:
            checker.logger.warn("some distributions are not valid images:\n%s" % output)
        cmd = "dpkg-parsechangelog | head -n1 | cut -d' ' -f2"
        _, output = commands.getstatusoutput(cmd)
        if checker.get_debian_name() != output:
            msg = 'source package names differs between debian/changelog and debian/control: %s, %s'
            checker.logger.error(msg % (output, checker.get_debian_name()))
            status = NOK
        cmd = "dpkg-parsechangelog >/dev/null"
        _, output = commands.getstatusoutput(cmd)
        if output:
            status = NOK
            checker.logger.error(output)
    return status

def check_debian_maintainer(checker):
    """check Maintainer field in debian/control file"""
    status = OK
    cmd = "grep '^Maintainer' debian/control | cut -d' ' -f2- | tr -d '\n'"
    cmdstatus, output = commands.getstatusoutput(cmd)
    if output.strip() != 'Logilab S.A. <contact@logilab.fr>':
        checker.logger.info("Maintainer value can be 'Logilab S.A. <contact@logilab.fr>'")
    return status

def check_debian_uploader(checker):
    """check Uploaders field in debian/control file"""
    status = OK
    cmd = "dpkg-parsechangelog | grep '^Maintainer' | cut -d' ' -f2- | tr -d '\n'"
    _, output = commands.getstatusoutput(cmd)
    cmd = 'grep "%s" debian/control' % output
    cmdstatus, _ = commands.getstatusoutput(cmd)
    if cmdstatus:
        # FIXME
        #checker.logger.error("'%s' is not found in Uploaders field" % output)
        #status = NOK
        checker.logger.warn("'%s' is not found in Uploaders field" % output)
        checker.logger.warn(check_debian_uploader.__doc__)
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
        checker.logger.warn(check_copying.__doc__)
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
            if not call(cmd.split()):
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

def check_announce(checker):
    """check the announce.txt file """
    if not (isfile('announce.txt') and isfile('NEWS')) :
        checker.logger.debug('announce file not present (NEWS or announce.txt)')
    return OK

def check_bin(checker):
    """check executable script files in bin/ """
    BASE_EXCLUDE = ('CVS', '.svn', '.hg', 'bzr')
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

def check_repository(checker):
    """check repository status (if not up-to-date)"""
    try:
        from logilab.devtools.vcslib import get_vcs_agent
        vcs_agent = get_vcs_agent(checker.config.pkg_dir)
        if vcs_agent:
            result = vcs_agent.not_up_to_date(checker.config.pkg_dir)
            # filter outgoing changesets since we're testing them currently
            result = [(k,v) for (k,v) in result if k not in ('outgoing',)]
            if result:
                checker.logger.warn("vcs_agent returns:\n%s" % pformat(result))
                return NOK
    except ImportError:
        checker.logger.warn("you need to install logilab vcslib package for this check")
    except NotImplementedError:
        checker.logger.warn("the current vcs agent isn't yet supported")
    return OK

def check_release_number(checker):
    """check the versions coherence between upstream and debian/changelog"""
    status = OK
    try: 
        checker.compare_versions()
    except LGPException, err:
        checker.logger.critical(err)
        status = NOK
    return status

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
    matched = read_manifest_in(None, dirname=dirname)
    for path in should_be_in:
        try:
            i = matched.index(path)
            matched.pop(i)
        except ValueError:
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
    """Hint: you can export DEBSIGN_KEYID to your environment and use gpg-agent to sign directly"""
    if 'DEBSIGN_KEYID' not in os.environ or 'GPG_AGENT_INFO' not in os.environ:
        logging.info(check_debsign.__doc__)
        return
    return OK

def check_package_info(checker):
    """check package information"""
    status = OK
    if hasattr(checker, "_package") and checker.package_format == "PackageInfo":
        pi = checker._package
        try:
            check_call(['python', '__pkginfo__.py'])
        except CalledProcessError, err:
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
