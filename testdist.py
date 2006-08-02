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
"""distribution test tools"""

import os

from logilab.devtools.lib.utils import exec_continue

def add_options(parser):
    parser.usage = 'lgp test [options] <.deb> ...'
    parser.min_args = 1
    parser.max_args = 2**16
    parser.add_option('-D', '--no-linda', help='do not run linda',
                      action="store_false", default=True, dest="linda")
    parser.add_option('-T', '--no-lintian', help='do not run lintian',
                      action="store_false", default=True, dest="lintian")
    parser.add_option('-P', '--no-piuparts', help='do not run piuparts',
                      action="store_false", default=True, dest="piuparts")

    
def run(options, args):
    for pkg in args:
        if options.lintian:
            exec_continue('lintian -i %s' % pkg)
        if options.linda:
            exec_continue('linda -i %s' % pkg)
    if options.piuparts:
        print '+' * 72
        print 'piuparts %s' % ' '.join(args)
        os.system('sudo piuparts -p %s' % ' '.join(args))

