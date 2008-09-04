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
""" Announce command """

import sys
from string import Template
from cStringIO import StringIO

from logilab.devtools.lib.pkginfo import PKGINFO, PKGINFO_ATTRIBUTES
from logilab.devtools.lib.pkginfo import PackageInfo
from logilab.devtools.lib.changelog import ChangeLog
from logilab.devtools.lib import TextReporter



ANNOUNCE="""I'm pleased to announce the ${VERSION} release of ${DISTNAME}.

What's new ?
------------
${CHANGELOG}


What is ${DISTNAME} ?
------------------------
${LONG_DESC}


Home page
---------
${WEB}

Download
--------
${FTP}

Mailing list
------------
${MAILINGLIST}

${ADDITIONAL_DESCR}
"""

ADDITIONAL_DESCR="""LOGILAB provides services in the fields of XML techniques and advanced
computing (implementation of intelligent agents, knowledge management,
natural language processing, statistical analysis, data mining, etc.),
and also trainings on Python, XML, UML, Object Oriented design, design
patterns use and other cutting edge topics. To know more about
Logilab, visit http://www.logilab.com/.

Logilab is also a strong supporter of the Free Software movement, and an
active member of the Python and Debian communities. Logilab's open 
source projects can be found on http://www.logilab.org/."""


def add_options(parser):
    parser.usage = "lgp announce"


def run(pkgdir, options, args):
    """ display announce """
    try:
        out = sys.stderr
        reporter = TextReporter(out, color=out.isatty())
        pkginfo = PackageInfo(reporter, pkgdir)
        content = Template(ANNOUNCE)
        content.delimiter = '%'
        stream = StringIO()
        chglog = ChangeLog('ChangeLog')
        chglog.extract(stream=stream)
        whatsnew = stream.getvalue()
        values = dict(CHANGELOG=whatsnew, VERSION=pkginfo.version,
                      WEB=pkginfo.web, FTP=pkginfo.ftp,
                      MAILINGLIST=pkginfo.mailinglist,
                      LONG_DESC=pkginfo.long_desc, DISTNAME=pkginfo.name,
                      ADDITIONAL_DESCR=ADDITIONAL_DESCR)
        print content.substitute(values)
    except ImportError:
        sys.stderr.write("%r does not appear to be a valid package " % pkgdir)
        sys.stderr.write("(no __pkginfo__ found)\n")
        return 1
    return 0
