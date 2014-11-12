# Copyright (c) 2003-2014 LOGILAB S.A. (Paris, FRANCE).
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
numversion = (1, 0, 0)
version = '.'.join([str(num) for num in numversion])

license = 'GPL'
author = "Logilab"
author_email = "contact@logilab.fr"

description = "tools used at Logilab to create debian packages"
web = "http://www.logilab.org/project/logilab-packaging"
mailinglist = "mailto://python-projects@lists.logilab.org"

subpackage_of = 'logilab'

from os.path import join, isdir

include_dirs = ['templates', join('test', 'data')]

scripts = [
    'bin/lgp',
    ]

install_requires = ['logilab-common']
