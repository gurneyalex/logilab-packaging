# Copyright (c) 2003 Sylvain Thenault (thenault@gmail.com)
# Copyright (c) 2003-2006 Logilab (devel@logilab.fr)
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
"""miscellaneous utilities, mostly shared by package'checkers
"""

__revision__ = '$Id: utils.py,v 1.17 2005-07-26 09:41:18 syt Exp $'

import re
import os
import glob
import sys
from os.path import basename, join, split, exists

from logilab.devtools.vcslib import BASE_EXCLUDE

PUBLIC_RGX = re.compile('PUBLIC\s+"-//(?P<group>.*)//DTD (?P<pubid>.*)//(?P<lang>\w\w)(//XML)?"\s*"(?P<dtd>.*)"')

class SGMLCatalog:
    """ handle SGML catalog information
    i.e. map dtds to their public id
    """
    def __init__(self, path, stream):
        self.path = path
        self.id = basename(path)
        self.dtds = {}
        for m in PUBLIC_RGX.finditer(stream.read()):
            dtd = m.group('dtd').split('/')[-1]
            self.dtds[dtd] = (m.group('group'), m.group('pubid'))

    def dtd_infos(self, dtd):
        """return infos for a dtd file"""
        return self.dtds[dtd]

    def check_dtds(self, dtds, reporter):
        """check given dtd files are registered"""
        for dtd in dtds:
            dtddir, dtdname = split(dtd)
            try:
                self.dtd_infos(dtdname)
            except KeyError:
                msg = 'DTD %s is not registered by the main catalog' % dtd
                reporter.log(ERROR, dtd, None, msg)

def glob_match(pattern, prefix=None):
    """return a list of files matching <pattern> from the <prefix> directory
    """
    cwd = os.getcwd()
    if prefix:
        try:
            os.chdir(prefix)
        except OSError:
            return []
    try: 
        return glob.glob(pattern)
    finally:
        if prefix:
            os.chdir(cwd)

def get_scripts(dirname, include_bat=0):
    """return a list of executable scripts
    """
    bindir = join(dirname, 'bin')
    if not exists(bindir):
        return ()
    result = []
    for filename in os.listdir(bindir):
        if filename in BASE_EXCLUDE:
            continue
        if include_bat or filename[-4:] != '.bat':
            result.append(join('bin', filename))
    return result

def cond_continue():
    """ask confirmation, quit if N"""
    try:
        answer = raw_input("Continue [y/N] ? ")
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)
    if answer.lower() in ('n', '') :
        sys.exit(0)
    
def exec_continue(cmd, separator=True):
    if separator:
        print '+'*72
        print cmd
    if os.system(cmd):
        cond_continue()
        
def exec_continue_retry(cmd):
    while True:
        status = os.system(cmd)
        if status:
            try:
                ans = raw_input('Continue? [y/N/r] ').strip().lower()
            except (EOFError, KeyboardInterrupt):
                sys.exit(0)
            if ans[0] == 'y':
                return
            elif ans[0] == 'r':
                continue
            else:
                sys.exit(0)
        else:
            return

    
def cond_exec(cmd):
    """demande confirmation, retourne 0 si oui, 1 si non"""
    try:
        answer = raw_input("Execute %s [Y/n/q] ? " % cmd)
    except (EOFError, KeyboardInterrupt):
        sys.exit(0)
    if answer == 'q':
        sys.exit(0)
    if answer == 'n':
        return False
    return True



