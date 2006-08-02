# Copyright (c) 2000-2003 LOGILAB S.A. (Paris, FRANCE).
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
"""USAGE: checkdistribution <source_directory> <distribution_directory>
"""

__revision__ = "$Id $"

import sys
import getopt
from os.path import join, exists
from os import listdir

from logilab.devtools.lib import TextReporter
REPORTER = TextReporter()

UNAUTHORIZED = ['debian', 'CVS', 'announce.txt', 'COPYING']
REQUIRED = ['__init__.py']

def check_bin(s_dir, d_dir):
    """check all files in the 'bin' directory are present and executable
    """
    errors = []
    for filename in listdir(s_dir):
        if filename == 'CVS':
            continue
        if not exists(join(d_dir, filename)):
            errors.append('missing file bin/%s' % filename)
    return errors


def run(args):
    """check a source (.tar.gz) distribution
    """
    opts, args = getopt.getopt(args, 'h', 'help')
    if opts:
        print __doc__
        return
    s_dir = args[0]
    d_dir = args[1]
    errors = []
    globs = globals()
    for filename in listdir(s_dir):
        if globs.has_key('check_%s' % filename):
            errors += globs['check_%s' % filename](join(s_dir, filename),
                                                   join(d_dir, filename))
        if exists(join(d_dir, filename)):
            if filename in UNAUTHORIZED:
                errors.append('%s should not be distributed' % filename)
        try:
            REQUIRED.remove(filename)
        except ValueError:
            continue
    for filename in REQUIRED:
        errors.append('%s is required' % filename)
    if errors:
        for msg in errors:
            print msg
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
