# Copyright (c) 2003-2010 LOGILAB S.A. (Paris, FRANCE).
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
"""logilab.devtools packaging information"""

modname = 'devtools'
distname = 'logilab-devtools'
numversion = (0, 17, 5)
version = '.'.join([str(num) for num in numversion])

license = 'GPL'
author = "Logilab"
author_email = "contact@logilab.fr"

description = "set of development tools used at Logilab"
web = "http://www.logilab.org/project/logilab-devtools"
ftp = "ftp://ftp.logilab.org/pub/devtools"
mailinglist = "mailto://python-projects@lists.logilab.org"

subpackage_of = 'logilab'

from os.path import join

include_dirs = ['templates', join('test', 'data')]

scripts = [
    # logilab-packaging
    'bin/changelog',
    'bin/update_gettext',
    'bin/lgp',
    'bin/lsprofcalltree',
    ]

install_requires = ['logilab-common']

