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
__all__ = ('check_info_module', 'check_release_number', 'check_manifest_in',
           'check_bin', 'check_test', 'check_setup_py', 'check_announce')

import sys
import os
import stat
import re
import commands
from os.path import basename, join, exists, isdir, isfile
from pprint import pprint

from logilab.common.compat import set
from logilab.common.fileutils import ensure_fs_mode

from logilab.devtools.vcslib import get_vcs_agent, BASE_EXCLUDE

from logilab.devtools import templates
from logilab.devtools.lgp.changelog import ChangeLog, ChangeLogNotFound, \
     find_ChangeLog
from logilab.devtools.lgp.setupinfo import SetupInfo
from logilab.devtools.lgp.utils import get_distributions, get_architectures
from logilab.devtools.lgp.utils import cond_exec


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
    status = 1
    data = open(sh_file).read()
    if data[:2] != '#!':
        checker.logger.error('script %s doesn\'t starts with "#!"' % sh_file)
        status = 0
    if not is_executable(sh_file):
        make_executable(sh_file)
    cmd = '%s --help' % sh_file
    cmdstatus, output = commands.getstatusoutput(cmd)
    if cmdstatus:
        checker.logger.error('%r returned status %s, ouput:\n%s' % (cmd, cmdstatus, output))
        status = 0
    return status

def _check_template(checker, filename, templatename):
    """check a file is similar to a reference template """
    if not exists(filename):
        checker.logger.warn('%s missing' % filename)
        return 0
    template = open(join(templates.__path__[0], templatename)).read()
    template = REV_LINE.sub('', template)
    actual = open(filename).read()
    actual = REV_LINE.sub('', actual)
    if actual != template:
        checker.logger.warn('%s does not match the template' % filename)
    return 1

def _check_bat(checker, bat_file):
    """try to check windows .bat files
    """
    status = 1
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
        status = 0
    error = os.popen3('%s --help' % command)[2].read()
    if error:
        checker.logger.error(bat_file, None,
                       "error while executing (%s):\n%s"%(command, error))
        status = 0
    return status


def run(args):
    """ Main function of lgp check command """
    checker = Checker(args)
    try :
        distributions = get_distributions(checker.config.distrib)

        if checker.config.list_checks:
            checker.list_checks()

        checker.start_checks()

        # Return the number of invalid tests
        return len(checker.get_checklist())-checker.counter

    except Exception, exc:
        checker.logger.critical(exc)
        return 1


class Checker(SetupInfo):
    """ Package checker class

    Specific options are added. See lgp check --help
    """
    checklist = []
    counter = 0
    name = "lgp-check"
    options = (('distrib',
                {'type': 'choice',
                 'choices': get_distributions(),
                 'dest': 'distrib',
                 #'default' : 'sid',
                 'metavar' : "<distribution>",
                 'help': "the distribution targetted (e.g. etch, lenny, sid). Use 'all' for all known distributions"
                }),
               ('includes',
                {'type': 'csv',
                 'dest': 'includes_checks',
                 #'default' : [],
                 'metavar' : "<comma separated names of check functions>",
                 'help': "force the inclusion of other check functions"
                }),
               ('excludes',
                {'type': 'csv',
                 'dest': 'excludes_checks',
                 #'default' : [],
                 'metavar' : "<comma separated names of check functions>",
                 'help': "force the exclusion of other check functions"
                }),
               ('list',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "list_checks",
                 'help': "return a list of all available check functions"
                }),
               ('only',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "only_one_check",
                 'help': "run only one single test (not available)"
                }),
               ('repare',
                {'action': 'store_true',
                 'default': False,
                 'dest' : "repare_attempt",
                 'help': "try to repare detected problems (not available)"
                }),
              ),

    def __init__(self, args):
        # Retrieve upstream information
        super(Checker, self).__init__(arguments=args, options=self.options, usage=__doc__)
        # FIXME logilab.common.configuration doesn't like default values :-(
        # FIXME Duplicated code between commands
        # Be sure to have absolute path here
        if self.config.distrib is None:
            self.config.distrib = 'sid'

    def get_checklist(self, all=False):
        checks = ['debian_dir', 'debian_rules', 'debian_copying', 'debian_changelog',
                  'readme', 'changelog', 'bin', 'tests_directory', 'setup_py', 'repository']
        if self._package == "pkginfo":
            checks += ['info_module', 'release_number', 'manifest_in', 'announce']
        elif self._package == "setuptools":
            checks += ['changelog',]
        elif self._package == "makefile":
            checks += ['makefile',]

        if self.config.includes_checks is not None:
            for check in self.config.includes_checks:
                checks.append(check)
        if self.config.excludes_checks is not None:
            for check in self.config.excludes_checks:
                checks.remove(check)
        if all:
            return [funct for (name, funct) in globals().items() if name.startswith('check_')]
        else:
            self.checklist = [globals()["check_%s" % name] for name in checks]
        return self.checklist

    def start_checks(self):
        for func in self.get_checklist():
            result = func(self)
            if result:
                self.logger.info(func.__doc__)
            else:
                self.logger.error(func.__doc__)
            self.counter += result
            if self.config.only_one_check:
                break

    def list_checks(self):
        all_checks = self.get_checklist(all=True)
        checks     = self.get_checklist()
        if len(checks)==0:
            print "No available check."
        else:
            print "You can use the --excludes or --includes options\n"
            msg = "Current checks"
            print msg; print len(msg) * '='
            for check in checks:
                print "%-25s: %s" % (check.__name__[6:], check.__doc__)
            msg = "Other available checks"
            print "\n" + msg; print len(msg) * '='
            for check in (set(all_checks) - set(checks)):
                print "%-25s: %s" % (check.__name__[6:], check.__doc__)
        sys.exit()



# ======================================
#
# Check functions collection starts here
#
# ======================================

def check_debian_dir(checker):
    """ check the debian* directory """
    debian_dir = checker.get_debian_dir()
    return os.path.isdir(debian_dir)

def check_debian_rules(checker):
    """ check the debian*/rules file (filemode) """
    debian_dir = checker.get_debian_dir()
    status = 1
    status = status and os.path.isfile(debian_dir + '/rules')
    status = status and is_executable(debian_dir + '/rules')
    return status

def check_debian_copying(checker):
    """ check debian*/copyright file """
    debian_dir = checker.get_debian_dir()
    return os.path.isfile(debian_dir + '/copyright')

def check_debian_changelog(checker):
    """ check debian*/changelog file """
    debian_dir = checker.get_debian_dir()
    return os.path.isfile(debian_dir + '/changelog')

def check_readme(checker):
    """ check the upstream README[.txt] file """
    return isfile('README') or isfile('README.txt')

def check_changelog(checker):
    """ check the upstream ChangeLog """
    # see preparedist.py:close_changelog
    # TODO --repare
    status = 1
    status = status and isfile('ChangeLog')
    cmd = "grep -E '^[[:space:]]+--' ChangeLog"
    cmdstatus, output = commands.getstatusoutput(cmd)
    print cmdstatus, output
    status = status and not cmdstatus
    return status

def check_copying(checker):
    """ check copyright file """
    # see preparedist.py:install_copying
    # TODO --repare
    return os.path.isfile('COPYING')

def check_tests_directory(checker):
    """ check the tests? directory """
    return isdir('test') or isdir('tests')

def check_run_tests(checker):
    """ run the unit tests """
    testdirs = ('test', 'tests')
    for testdir in testdirs:
        if os.path.isdir(testdir):
            os.chdir(testdir)
            cond_exec('pytest', confirm=True, retry=True)
            break
    return 1

def check_setup_py(checker):
    """ check the setup.py file """
    return isfile('setup.py')

def check_makefile(checker):
    """ check makefile file and dependencies """
    status = 1
    status = status and os.path.isfile("Makefile")
    #status = status and _check_make_dependencies()
    return status

def check_announce(checker):
    """ checking the announce.txt file """
    # TODO --repare
    return isfile('announce.txt')

def check_bin(checker):
    """ check executable script files in bin/ """
    status = 1
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
    """ check build of project's documentation"""
    if osp.isdir('doc') and (osp.isfile('doc/makefile') or osp.isfile('doc/Makefile')) and \
           confirm('build documentation ?'):
        os.chdir('doc')
        cond_exec('make', retry=True)
    return 0

def check_repository(checker):
    """ check repository status (modified files) """
    try:
        vcs_agent = get_vcs_agent(checker.config.pkg_dir)
        result = vcs_agent.not_up_to_date(checker.config.pkg_dir)
        if result:
            return 0
    except NotImplementedError:
        checker.logger.warn("the vcs agent isn't yet supported")
    return 1

def check_pylint(checker):
    """ check with pylint """
    'pylint --ignore doc %s'
    return 0




###############################################################################
        

REV_LINE = re.compile('__revision__.*')
    
def check_release_number(checker, dirname, info_module='__pkginfo__'):
    """ check inconsistency with release number """
    try:
        pi = PackageInfo(checker, dirname, info_module=info_module)
    except ImportError:
        return 0
    version = normalize_version(pi.version)
    status = 1
    try:
        cl_version = ChangeLog(find_ChangeLog(dirname)).get_latest_revision()
        cl_version = normalize_version(cl_version)
        if cl_version != version:
            msg = 'Version inconsistency : found %s in ChangeLog \
(reference is %s)'
            checker.logger.error('ChangeLog', None, msg % (cl_version, version))
            status = 0
    except ChangeLogNotFound:
        checker.logger.warn('ChangeLog', None, 'Missing file')
    if exists(join(dirname, 'debian')):
        if not exists(join(dirname, 'debian', 'changelog')):
            checker.logger.error('debian/changelog', None, 'Missing file')
            status = 0
        else:
            deb_version = pi.debian_version()
            deb_version = normalize_version(deb_version.split('-', 1)[0])
            if deb_version != version:
                msg = 'Version inconsistency : found %s in debian/changelog \
(reference is %s)'
                checker.logger.error('debian/changelog', None,
                               msg % (deb_version, version))
                status = 0
    return status

#def check_manifest_in(reporter, dirname=os.getcwd(),
#                      info_module=None, # avoid pb with check_package
#                      junk_extensions=JUNK_EXTENSIONS):
#    """checks MANIFEST.in file"""
#    status = 1
#    # check matched files
#    should_be_in = get_manifest_files(dirname=dirname)
#    matched = read_manifest_in(reporter, dirname=dirname)
#    absfile = join(dirname, 'MANIFEST.in')
#    for path in should_be_in:
#        try:
#            i = matched.index(path)
#            matched.pop(i)
#        except ValueError:
#            reporter.error(absfile, None, '%s is not matched' % path)
#            status = 0
#    # check garbage
#    for filename in matched:
#        if match_extensions(filename, junk_extensions):
#            reporter.warning(absfile, None, 'match %s' % filename)
#    return status

#from logilab.devtools.lib.pkginfo import PackageInfo, check_info_module
#def check_info_module(reporter,
#                      dirname=os.getcwd(), info_module='__pkginfo__'):
#    """ checking package information module and source tree structure """
#    absfile = join(dirname, info_module + '.py')
#    try:
#        mp_file, mp_filename, mp_desc = find_module(info_module,
#                                                    [dirname])
#        module = load_module(info_module, mp_file, mp_filename, mp_desc)
#    except Exception, ex:
#        reporter.error(absfile, None, str(ex))
#        return 0
#    # this will check for missing required attribute
#    pi = PackageInfo(reporter, dirname, info_module, init=0)
#    status = pi.init_from_module()
#    pi.initialization_end()
#    
#    # check package name
###     if not getattr(module, 'name', None) and \
###            not getattr(module, 'modname', None):
###         msg = 'No required "name" nor "modname" attribute'
###         reporter.error(info_module, None, msg)
###         status = 0
#        
#    # check scripts
#    detected_scripts = get_default_scripts(pi)
#    scripts = getattr(module, 'scripts', []) or []
#    if not sequence_equal(detected_scripts, scripts):
#        msg = 'Detected %r as default "scripts" value, found %r'
#        reporter.warning(absfile, None, msg % (detected_scripts, scripts))

#    # check license
#    if not (getattr(module, 'license', None) or
#            getattr(module, 'license_text', None)):
#        msg = 'No "license" nor "license_text" attribute'
#        reporter.error(absfile, None, msg)
#        status = 0

#    # check copyright
#    copyright = getattr(module, 'copyright', '') 
#    if not copyright:
#        msg = 'No copyright notice'
#        reporter.error(absfile, None, msg)
#        status = 0
#    else:
#        match = COPYRIGHT_RGX.search(copyright)
#        if match:
#            end = match.group('to') or match.group('from')
#            thisyear = localtime(time())[0]
#            if int(end) < thisyear:
#                msg = 'Copyright is outdated (%s)' % end
#                reporter.warning(absfile, None, msg)
#                
#        else:
#            msg = 'Copyright doesn\'t match %s' % COPYRIGHT_RGX.pattern
#            reporter.warning(absfile, None, msg)
#            
#    # check include_dirs
#    if getattr(module, 'include_dirs', None):
#        for directory in module.include_dirs:
#            if not exists(join(dirname, directory)):
#                msg = 'Include inexistant directory %r' % directory
#                reporter.error(absfile, None, msg)

#    # check web site and ftp
#    check_url(reporter, absfile, 'web', pi.web)
#    check_url(reporter, absfile, 'ftp', pi.ftp)

#    # check descriptions
#    if not pi.short_desc:
#        msg = 'No short description'
#        reporter.error(absfile, None, msg)
#    else:
#        if len(pi.short_desc) > 80:
#            msg = 'Short description longer than 80 characters'
#            reporter.error(absfile, None, msg)
#        desc = pi.short_desc.lower().split()
#        if pi.name.lower() in desc or pi.debian_name.lower() in desc:
#            msg = 'Short description contains the package name'
#            reporter.error(absfile, None, msg)
#        if pi.short_desc[0].isupper():
#            msg = 'Short description starts with a capitalized letter'
#            reporter.error(absfile, None, msg)
#        if pi.short_desc[-1] == '.':
#            msg = 'Short description ends with a period'
#            reporter.error(absfile, None, msg)
#        for word in spell_check(pi.short_desc, ignore=(pi.name.lower(),)):
#            msg = 'Possiply mispelled word %r' % word
#            reporter.warning(absfile, None, msg)
#            
#    if not pi.long_desc:
#        msg = 'No long description'
#        reporter.error(absfile, None, msg)
#    else:
#        for word in spell_check(pi.long_desc, ignore=(pi.name.lower(),)):
#            msg = 'Possiply mispelled word %r' % word
#            reporter.warning(absfile, None, msg)
#        for line in pi.long_desc.splitlines():
#            if len(line) > 79:
#                msg = 'Long description contains lines longer than 80 characters'
#                reporter.warning(absfile, None, msg)
#        
#    # standard source tree ####################################################
#    
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
#    
