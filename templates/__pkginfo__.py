# Copyright (c) 2000-2008 LOGILAB S.A. (Paris, FRANCE).
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
%(MODNAME)s packaging information
"""

# package name
modname = '%(MODNAME)s'

# release version
numversion = [0, 1, 0]
version = '.'.join([str(num) for num in numversion])

# license and copyright
license = 'GPL'
copyright = '''Copyright (c) 2001-2008 LOGILAB S.A. (Paris, FRANCE).
http://www.logilab.fr/ -- mailto:contact@logilab.fr'''

# short and long description
short_desc = ""
long_desc = """
"""

# author name and email
author = "Logilab"
author_email = "devel@logilab.fr"

# home page
web = "http://www.logilab.org/%s" % modname

# mailing list
mailinglist = 'mailto://%s@lists.logilab.org' % modname

# download place
ftp = "ftp://ftp.logilab.org/pub/%s" % modname

# executable (include the 'bin' directory in the name)
scripts = ()

# should it be placed as a subpackage of a package such as 'logilab'
subpackage_of = None

# is there some directories to include with the source installation
include_dirs = []
