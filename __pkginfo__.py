# Copyright (c) 2003-2015 LOGILAB S.A. (Paris, FRANCE).
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
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.
"""logilab.packaging packaging information"""

modname = 'packaging'
distname = 'logilab-packaging'
numversion = (1, 3, 0)
version = '.'.join([str(num) for num in numversion])

license = 'GPL'
author = "Logilab"
author_email = "contact@logilab.fr"

description = "tools used at Logilab to create debian packages"
web = "http://www.logilab.org/project/logilab-packaging"
mailinglist = "mailto://python-projects@lists.logilab.org"

scripts = [
    'bin/lgp',
    ]

from os.path import join, isdir, dirname
from os import listdir

if '__file__' in locals():
    here = dirname(__file__)
else:
    here = '.'

def listfiles(path):
    return [join(here, path, x) for x in listdir(join(here, path))
            if not isdir(join(here, path, x))]

data_files = [('etc/lgp', listfiles('etc/lgp')),
              ('etc/lgp/hooks', listfiles('etc/lgp/hooks')),
              ('etc/lgp/scripts', listfiles('etc/lgp/scripts')),
              ]

# python-debian needs chardet but doesn't seem to declare the dependency
install_requires = ['setuptools', 'logilab-common', 'python-debian', 'chardet']
