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
import sys
import stat
import re
import commands
import logging
import subprocess
from os.path import basename, join, exists, isdir, isfile
from pprint import pformat

from logilab.common.compat import set
from logilab.common.fileutils import ensure_fs_mode

from logilab.devtools.lib.pkginfo import check_url as _check_url, spell_check, get_default_scripts, sequence_equal
from logilab.devtools.lib.manifest import (get_manifest_files, read_manifest_in,
                                           match_extensions, JUNK_EXTENSIONS)

from logilab.devtools import templates
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import cond_exec, confirm
from logilab.devtools.lgp.exceptions import LGPException

CHANGEFILE='ChangeLog'
MANDATORY_SETUP_FIELDS = ('name', 'version', 'author', 'author_email', 'license',
                          'copyright', 'short_desc', 'long_desc')

OK, NOK = 1, 0
CHECKS = { 'default'    : ['debian_dir', 'debian_rules', 'debian_copying',
                           'debian_source_value',
                           'debian_changelog', 'package_info', 'readme',
                           'changelog', 'bin', 'tests_directory', 'setup_file',
                           'repository', 'copying', 'documentation',
                           'homepage', 'builder', 'keyrings', 'announce',
                           'release_number', 'manifest_in', 'include_dirs',
                           'scripts', 'pydistutils', 'debian_maintainer',
                           'debian_uploader'],
           'setuptools' : [],
           'pkginfo'    : [],
           'makefile'   : ['makefile'],
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
        return 1
    except LGPException, exc:
        logging.critical(exc)
        return 1


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
                 'metavar' : "<comma separated names of check functions>",
                 'help': "force the inclusion of other check functions"
                }),
               ('exclude',
                {'type': 'csv',
                 'dest': 'exclude_checks',
                 'short': 'e',
                 'metavar' : "<comma separated names of check functions>",
                 'help': "force the exclusion of other check functions"
                }),
               ('set',
                {'type': 'csv',
                 'dest': 'set_checks',
                 'default' : CHECKS['default'],
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

        assert self.config.set_checks, 'set_checks should never be empty here'

        try:
            try:
                if self.config.set_checks:
                    checks = []
                    for check in self.config.set_checks:
                        checks.append(check)
                    #self.logger.debug("active checks: %s" % ','.join(checks))

                if self.config.include_checks is not None:
                    for check in self.config.include_checks:
                        #self.logger.debug("include check: %s" % check)
                        checks.append(check)
                if self.config.exclude_checks is not None:
                    for check in self.config.exclude_checks:
                        #self.logger.debug("exclude check: %s" % check)
                        checks.remove(check)
                self.checklist = [globals()["check_%s" % name] for name in checks]
            except ValueError, err:
                raise KeyError(check)
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
        all_checks = self.get_checklist(all=True)
        checks     = self.get_checklist()
        if len(checks)==0:
            print "No available check."
        else:
            print "You can use the --set, --exclude or --include options\n"
            msg = "Current active checks"
            print msg; print len(msg) * '='
            for check in checks:
                print "%-25s: %s" % (check.__name__[6:], check.__doc__)
            msg = "Other available checks"
            print "\n" + msg; print len(msg) * '='
            for check in (set(all_checks) - set(checks)):
                print "%-25s: %s" % (check.__name__[6:], check.__doc__)



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
    """check the mandatory keyrings for debian and ubuntu in /usr/share/keyrings/"""
    if isfile("/usr/share/keyrings/ubuntu-archive-keyring.gpg") and \
       isfile("/usr/share/keyrings/debian-archive-keyring.gpg"):
        return OK
    return NOK

def check_pydistutils(checker):
    """check a .pydistutils.cfg file in your home firectory"""
    if isfile(os.path.join(os.environ['HOME'], '.pydistutils.cfg')):
        checker.logger.error('your ~/.pydistutils.cfg conflicts with distutils commands')
        return NOK
    return OK

def check_builder(checker):
    """check if the builder has been changed"""
    debuilder = os.environ.get('DEBUILDER') or False
    if debuilder:
        checker.logger.warn('you have set a different builder in DEBUILDER. Unset it if in doubt')
    return OK

def check_debian_dir(checker):
    """check the debian* directory """
    checker.current_distrib = "unstable"
    debian_dir = checker.get_debian_dir()
    return isdir(debian_dir)

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
                            "Source filed value in your debian/control (%s)"
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
            checker.logger.info('Default distribution value should be "unstable" in your debian changelog')
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
    """the upstream README file is missing"""
    if not isfile('README'):
        checker.logger.warn(check_readme.__doc__)
    return OK

def check_changelog(checker):
    """the upstream ChangeLog file is missing"""
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
    """run the unit tests """
    testdirs = ('test', 'tests')
    for testdir in testdirs:
        if isdir(testdir):
            cond_exec('pytest', confirm=True, retry=True)
            break
    return OK

def check_setup_file(checker):
    """check the setup.[py|mk] file """
    return isfile('setup.py') or isfile('setup.mk')

def check_makefile(checker):
    """check makefile file and expected targets (project, version)"""
    status = OK
    setup_file = checker.config.setup_file
    status = status and isfile(setup_file)
    for cmd in ['%s project', '%s version']:
        cmd %= setup_file
        if not subprocess.call(cmd.split()):
            checker.logger.error("%s not a valid command" % cmd)
        status = NOK
    return status

def check_homepage(checker):
    """check the homepage field"""
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
        # FIXME
        # should be a clean target in setup.mk for example
        # and isfile('doc/Makefile') or isfile('doc/makefile'):
        #if confirm('build documentation ?'):
        #os.chdir('doc')
        #status = cond_exec('make', retry=True)
        pass
    else:
        checker.logger.warn("documentation directory not found")
    return status

def check_repository(checker):
    """check repository status (not up-to-date) """
    try:
        from logilab.devtools.vcslib import get_vcs_agent
        vcs_agent = get_vcs_agent(checker.config.pkg_dir)
        if vcs_agent:
            result = vcs_agent.not_up_to_date(checker.config.pkg_dir)
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

def check_include_dirs(checker):
    """check include_dirs declared in setup file"""
    if hasattr(checker, "_package") and hasattr(checker._package, 'include_dirs'):
        for directory in checker._package.include_dirs:
            if not exists(directory):
                msg = 'include inexistant directory %r' % directory
                checker.logger.error(msg)
                return NOK
    return OK

def check_debsign(checker):
    """Hint: you can add DEBSIGN_KEYID to your environment and use a gpg-agent to sign directly"""
    if 'DEBSIGN_KEYID' not in os.environ:
        logging.info(check_debsign.__doc__)
        return
    return OK

def check_scripts(checker):
    """check scripts declared in setup file"""
    if hasattr(checker, "_package") and hasattr(checker._package, 'scripts'):
        detected_scripts = get_default_scripts(checker._package)
        scripts = getattr(checker._package, 'scripts', [])
        if not sequence_equal(detected_scripts, scripts):
            msg = 'detected %r as default "scripts" value, found %r' % (detected_scripts, scripts)
            checker.logger.warn(msg)
            return NOK
    return OK

def check_package_info(checker):
    """check package information"""
    status = OK
    if hasattr(checker, "_package") and checker.package_format == "PackageInfo":
        pi = checker._package
    else:
        return status

    for field in MANDATORY_SETUP_FIELDS:
        if not hasattr(pi, field):
            checker.logger.error("%s field missing" % field)
            status = NOK
        if field == "long_desc":
            for word in spell_check(pi.long_desc, ignore=(pi.name.lower(),)):
                msg = 'possibly mispelled word %r' % word
                checker.logger.warn(msg)
            for line in pi.long_desc.splitlines():
                if len(line) > 79:
                    msg = 'long description contains lines longer than 80 characters'
                    checker.logger.warn(msg)
        elif field == "short_desc":
            if len(pi.short_desc) > 80:
                msg = 'short description longer than 80 characters'
                checker.logger.warn(msg)
            desc = pi.short_desc.lower().split()
            if pi.name.lower() in desc or checker.get_upstream_name().lower() in desc:
                msg = 'short description contains the package name'
                checker.logger.warn(msg)
            if pi.short_desc[0].isupper():
                msg = 'short description starts with a capitalized letter'
                checker.logger.warn(msg)
            if pi.short_desc[-1] == '.':
                msg = 'short description ends with a period'
                checker.logger.warn(msg)
            for word in spell_check(pi.short_desc, ignore=(pi.name.lower(),)):
                msg = 'possibly mispelled word %r' % word
                checker.logger.warn(msg)
    return status



# ===============================
#
# Not implemented check functions
#
# ===============================

def check_shebang(checker):
    """check #! signature for shell and python script (not implemented)"""
    # TODO make a test with file utility and check #!/bin/... or #!/usr/bin/env python
    raise NotImplementedError("use best practises")

def check_deprecated(checker):
    """check attributes in deprecation (not implemented)"""
    raise NotImplementedError("use right pylint options")

def check_pylint(checker):
    """check with pylint (not implemented) """
    raise NotImplementedError("use right pylint options")

def check_dtd_and_catalogs(checkers):
    """check dtd and catalogs (not implemented) """
    raise NotImplementedError("dtd_and_catalog needs to be fixed !")
#    # DTDs and catalog
#    detected_dtds = get_default_dtd_files(pi)
#    dtds = getattr(module, 'dtd_files', None)
#    if dtds is not None and not sequence_equal(detected_dtds, dtds):
#        msg = 'Detected %r as default "dtd_files" value, found %r'
#        reporter.warning(absfile, None, msg % (detected_dtds, dtds))
#    else:
#        dtds = detected_dtds
#    detected_catalog = get_default_catalog(pi)
#    catalog = getattr(module, 'catalog', None)
#    if catalog:
#        if detected_catalog and catalog != detected_catalog:
#            msg = 'Detected %r as default "catalog" value, found %r'
#            reporter.warning(absfile, None, msg % (detected_catalog,
#                                                        catalog))
#        elif split(catalog)[1] != 'catalog':
#            msg = 'Package\'s main catalog should be named "catalog" not %r'
#            reporter.error(join(dirname, 'dtd'), None,
#                         msg % split(catalog)[1])
#            status = 0
#    else:
#        catalog = detected_catalog
#    cats = glob_match(join('dtd', '*.cat'))
#    if cats:
#        msg = 'Unsupported catalogs %s' % ' '.join(cats)
#        reporter.warning(join(dirname, 'dtd'), None, msg)
#    if dtds:
#        if not catalog:
#            msg = 'Package provides some DTDs but no catalog'
#            reporter.error(join(dirname, 'dtd'), None, msg)
#            status = 0
#        else:
#            # check catalog's content (i.e. dtds are listed inside)
#            cat = SGMLCatalog(catalog, open(join(dirname, catalog)))
#            cat.check_dtds([split(dtd)[1] for dtd in dtds], reporter)
#            
#    # FIXME: examples_directory, doc_files, html_doc_files
#    # FIXME: find a generic way to checks values found in config !
#    return status

def check_copyright_header(checker):
    """check copyright year (not implemented) """
    raise NotImplementedError("year could be updated automatically by templating")
#    match = COPYRIGHT_RGX.search(copyright)
#    if match:
#        end = match.group('to') or match.group('from')
#        thisyear = localtime(time())[0]
#        if int(end) < thisyear:
#            msg = 'Copyright is outdated (%s)' % end
#            reporter.warning(absfile, None, msg)
#        else:
#            msg = 'Copyright doesn\'t match %s' % COPYRIGHT_RGX.pattern
#            reporter.warning(absfile, None, msg)

def check_web_and_ftp(checker):
    """check web and ftp external resources (not implemented)"""
    raise NotImplementedError("unrelated if new package !")
#   # check web site and ftp
#   _check_url(reporter, absfile, 'web', pi.web)
#   _check_url(reporter, absfile, 'ftp', pi.ftp)

