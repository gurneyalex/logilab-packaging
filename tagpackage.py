#!/usr/bin/env python
#
# Copyright (c) 2004-2006 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""tag a package for a distribution
"""

__revision__ = '$Id: tagpackage.py,v 1.7 2005-07-26 12:15:27 adim Exp $'

import os
import sys
from os.path import exists, abspath

from logilab.common.modutils import get_module_files

from logilab.devtools.lib.utils import cond_exec, confirm
from logilab.devtools.lib.manifest import read_manifest_in
from logilab.devtools.lib import TextReporter
from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.vcslib import get_vcs_agent


def tag_package(package_dir, vcs_agent=None):
    cwd = os.getcwd()
    package_dir = abspath(package_dir) + '/'
    os.chdir(package_dir)
    try:
        try:
            # this will try to import __pkginfo__
            pi = PackageInfo(TextReporter(sys.stderr), '.')
        except ImportError:
            print >> sys.stderr, "%r does not appear to be a valid package \
(no __pkginfo__ found)" % package_dir
            return
        vcs_agent = vcs_agent or get_vcs_agent('.')
        # conditional tagging
        release_tag = pi.release_tag()
        if confirm("Add tag %s on %s ?" % (release_tag, package_dir)):
            manifest_files = read_manifest_in(REPORTER, dirname='.',
                                              exclude_patterns=(r'/(RCS|CVS|\.svn|\.hg)/.*',
                                                                r'(.*\.pyc|.*\.pyo|.*\.html|.*\.pdf)'))
            python_files = get_module_files(package_dir)
            files = [f.replace(package_dir, '') for f in manifest_files + python_files]
            os.system(vcs_agent.tag(files, release_tag))
        package_dir = 'debian'
        if exists(package_dir):
            release_tag = pi.debian_release_tag()
            if confirm("Add tag %s on %s ?" % (release_tag, package_dir)):
                os.system(vcs_agent.tag(package_dir, release_tag))
    finally:
        os.chdir(cwd)

def add_options(parser):
    """needed by lgp.py"""
    pass

def run(pkgdir, options, args):
    tag_package(pkgdir)

