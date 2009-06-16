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
"""
logilab.devtools packaging information
"""


modname = 'devtools'
distname = 'logilab-devtools'
numversion = (0, 15, 0)
version = '.'.join([str(num) for num in numversion])

license = 'GPL'
copyright = '''Copyright (c) 2003-2008 LOGILAB S.A. (Paris, FRANCE).
http://www.logilab.fr/ -- mailto:contact@logilab.fr'''

author = "Logilab"
author_email = "contact@logilab.fr"

short_desc = "set of development tools used at Logilab"
long_desc = """Set of tools which aims to help the developpement process, including :
* standard for zope and python packages
* tools to check and build source and/or debian packages
* python coverage tool
* cvs/svn utilities
"""
web = "http://www.logilab.org/project/devtools"
ftp = "ftp://ftp.logilab.org/pub/devtools"
mailinglist = "mailto://python-projects@lists.logilab.org"

subpackage_of = 'logilab'

from os.path import join

include_dirs = ['templates', join('test', 'data')]

scripts = [
    # vcslib
    'bin/vcpull',
    'bin/cvslog',
    'bin/cvstatus',
    'bin/hgstatus',
    # pycovergae
    'bin/pycoverage',
    # logilab-packaging
    'bin/changelog',
    'bin/update_gettext',
    'bin/lgp',
    'bin/vbuild',
    'bin/lsprofcalltree',
    ] 

