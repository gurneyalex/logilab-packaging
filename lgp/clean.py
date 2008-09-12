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
""" lgp clean [options]

    Clean project's directory
"""
__docformat__ = "restructuredtext en"

import os
import os.path
from logilab.devtools.lgp.utils import confirm, cond_exec


def run(args):
    """ Main function of lgp clean command """

    patterns = ['*~', '*.pyc', '*.pyo', '*.o', '\#*', '.\#*']
    search = ' -o '.join(['-name "%s" '%item for item in patterns])
    os.system('find . "(" %s ")" -a -ls' % search)
    if confirm("nettoyage du répertoire de travail ?"):
        os.system('find . "(" %s ")" -a -exec rm -f \{\} \; 2>/dev/null' % search)
    if os.path.isdir('doc') and os.path.isfile('doc/makefile'):
        if confirm("nettoyage du répertoire de documentation ?"):
        os.chdir('doc')
        cond_exec('make clean', retry=True)

