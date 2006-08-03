# -*- coding: iso-8859-1 -*-

import os, os.path as osp
import sys
from stat import ST_MTIME, S_IWUSR
from cStringIO import StringIO
from logilab.common.shellutils import cp

from logilab.devtools import TEMPLATE_DIR
from logilab.devtools.lib import TextReporter
from logilab.devtools.lib.utils import cond_exec, confirm
from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lib.changelog import ChangeLog

ADDITIONAL_DESCR="""LOGILAB provides services in the fields of XML techniques and advanced
computing (implementation of intelligent agents, knowledge management,
natural language processing, statistical analysis, data mining, etc.),
and also trainings on Python, XML, UML, Object Oriented design, design
patterns use and other cutting edge topics. To know more about
Logilab, visit http://www.logilab.com/.

Logilab is also a strong supporter of the Free Software movement, and an
active member of the Python and Debian communities. Logilab's open 
source projects can be found on http://www.logilab.org/."""

SEPARATOR = '+' * 72

def install_copying(license):
    """ensure COPYING is up to date"""
    license_file = osp.join(TEMPLATE_DIR, 'licenses', 'full_%s.txt' % license)
    if osp.isfile(license_file) and confirm('COPYING file checking ?'):
        if osp.isfile('COPYING'):
            # update COPYING file if needed
            if os.stat(license_file)[ST_MTIME] > os.stat('COPYING')[ST_MTIME]:
                cp(license_file, 'COPYING')
            else:
                print "COPYING file is up to date"
        else:
            cp(license_file, 'COPYING')


def runtests(projdir=os.getcwd()):
    """runs unit tests"""
    if osp.isdir('test'):
        os.chdir('test')
        cond_exec('python runtests.py', confirm=True, retry=True)
        os.chdir(projdir)

def close_changelog(projdir=os.getcwd()):
    """closes the projects's ChangeLog"""
    if osp.isfile('ChangeLog') and confirm('close ChangeLog ?'):
        # chmod u+w ChangeLog
        os.system('chmod 664 ChangeLog')
        # os.system('changelog close')
        chlg = ChangeLog('ChangeLog')
        try:
            chlg.close(projdir)
        except Exception, exc:
            print "An error occured while closing Changelog:", exc
            if not confirm('Continue ?'):
                sys.exit(1)


def build_documentation(projdir=os.getcwd()):
    """builds the project's documentation"""
    if osp.isdir('doc') and (osp.isfile('doc/makefile') or osp.isfile('doc/Makefile')) and \
           confirm('build documentation ?'):
        os.chdir('doc')
        cond_exec('make', retry=True)
        os.chdir(projdir)


def make_announce(pkginfo, filename):
    if osp.isfile('announce.txt') and confirm('generate announce in %s ?' % filename):
        stream = StringIO()
        chglog = ChangeLog('ChangeLog')
        chglog.extract(stream=stream)
        whatsnew = stream.getvalue()
        values = dict(CHANGELOG=whatsnew, VERSION=pkginfo.version,
                      WEB=pkginfo.web, FTP=pkginfo.ftp,
                      MAILINGLIST=pkginfo.mailinglist,
                      LONG_DESC=pkginfo.long_desc, DISTNAME=pkginfo.name,
                      ADDITIONAL_DESCR=ADDITIONAL_DESCR)
        template = file('announce.txt').read()
        announce = file(filename, 'w')
        announce.write(template % values)
        announce.close()


DEFAULT_ACTIONS = ('pylint', 'copying', 'checkpackage',
                   'runtests', 'changelog', 'doc', 'announce')

def add_options(parser):
    parser.usage = """lgp prepare [options] [<project_dir>]
if <project_dir> is omitted, the current directory will be used

possible actions are: %s
""" % ', '.join(DEFAULT_ACTIONS)
    parser.add_option('-o', '--only', action="append", dest="only",
                      help="perform only that action (this option can be passed several times)",
                      metavar='<ACTIONS>', default=[])
    parser.max_args = 1


def run(options, args):
    projdir = osp.abspath(args and args[0] or os.getcwd())
    distdir = osp.abspath(osp.join(os.getcwd(), '..', 'dist'))
    os.chdir(projdir)
    if osp.isfile('__init__.py'):
        pkgtype = 'python'
    else:
        pkgtype = 'formation'
    try:
        pkginfo = PackageInfo(TextReporter(sys.stderr), projdir)
    except ImportError, exc:
        sys.stderr.write("%r does not appear to be a valid package " % projdir)
        sys.stderr.write("(no __pkginfo__ found)\n")
        return
    actions = options.only or DEFAULT_ACTIONS
    if pkgtype == 'python':
        if 'pylint' in actions:
            # run pylint
            print SEPARATOR
            cond_exec('pylint --ignore doc %s' % projdir, confirm=True, retry=True)
        # update COPYING (license) file
        if pkginfo.license and 'copying' in actions:
            print SEPARATOR
            install_copying(pkginfo.license)
        # checkpackage
        if 'checkpackage' in actions:
            print SEPARATOR
            cond_exec('lgp check', confirm=True, retry=True)
    else:
        # formation check only release number
        if 'checkpackage' in actions:
            print SEPARATOR
            cond_exec('lgp check -o release_number', confirm=True, retry=True)
    if 'runtests' in actions:
        # run unit tests
        print SEPARATOR
        runtests()
    if 'changelog' in actions:
        # close project's ChangeLog
        print SEPARATOR
        close_changelog()
    if 'doc' in actions:
        # builds the documentation
        print SEPARATOR
        build_documentation()
    if 'announce' in actions:
        # prepare ANNOUNCE file
        if pkgtype == 'python':
            print SEPARATOR
            filename = '%s/%s.announce' % (distdir, pkginfo.name)
            make_announce(pkginfo, filename)
