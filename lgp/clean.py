# -*- coding: utf-8 -*-
# Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr

# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.

# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
""" Clean command """

import os
import sys
from logilab.devtools.lgp.utils import confirm

def add_options(parser):
    parser.usage = "lgp clean"

def run(pkgdir, options, args):
    """ display announce """
    patterns = ['*~', '*.pyc', '*.pyo', '*.o', '\#*', '.\#*']
    search = ' -o '.join(['-name "%s" '%item for item in patterns])
    os.system('find . "(" %s ")" -a -ls' % search)
    if confirm("nettoyage du répertoire de travail ?"):
        os.system('find . "(" %s ")" -a -exec rm -f \{\} \; 2>/dev/null' % search)

# TODO make clean dans doc/
#          patterns = ['*~', '*.pyc', '*.pyo', '*.o', '\#*', '.\#*']
#           search = ' -o '.join(['-name "%s" '%item for item in patterns])
#            os.system('find . "(" %s ")" -a -exec rm -f \{\} \; 2>/dev/null' % search)

