# -*- coding: iso-8859-1 -*-
#
# Copyright (c) 2004-2006 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""make a distribution for a logilab python package after some checks
"""

__revision__ = '$Id: makedistrib.py,v 1.4 2006-02-10 15:09:15 syt Exp $'

import sys
import os
from os.path import basename

from logilab.devtools.vcslib import get_vcs_agent
from logilab.devtools.tagpackage import tag_package
from logilab.devtools.lib.utils import confirm, cond_exec
from logilab.devtools.buildeb import lint

SEPARATOR = '+' * 72

def add_options(parser):
    parser.usage = 'lgp make [options] <project_dir> ...'
    #print "USAGE: makedistrib <source_directory> <bdist_wininst|sdist|deb>"

def run(options, args):
    package_dir = args[0]
    pkgname = basename(package_dir)
    vcs_agent = get_vcs_agent(package_dir)

    # check vcs up to date
    print SEPARATOR
    if confirm("vérifier que l'entrepôt est à jour ?"):
        try:
            result = vcs_agent.not_up_to_date(package_dir)
            if result:
                print '\n'.join(["%s: %s"%r for r in result])
                if not confirm('Continue ?'):
                    return 0
        except NotImplementedError:
            print 'pas encore supporté par cet agent de controle'

    # check no file in edition
    print SEPARATOR
    if confirm("vérifier qu'aucun fichier n'est en édition ?"):
        try:
            result = vcs_agent.edited(package_dir)
            if result:
                print '\n'.join(result)
                if not confirm('Continue ?'):
                    return 0
        except NotImplementedError:
            print 'pas encore supporté par cet agent de controle'

    # clean
    print SEPARATOR
    print "nettoyage du répertoire de travail"
    os.system('rm -f *~ \#* .\#* */*~ */\#* */.\#* */*/*~ */*/\#* */*/.\#* 2>/dev/null')

    # build
    print SEPARATOR
    print "génération du paquet"
    target = (len(args) == 2) and args[1] or 'deb'
    if os.system('buildpackage %s %s' % (package_dir, target)):
        return 1

    # lintian
    print SEPARATOR
    if target == "deb" and confirm("lancement de lintian sur les paquets générés ?"):
        lint('lintian -i', package_dir, 'dist')

    # linda
    print SEPARATOR
    if target == "deb" and confirm("lancement de linda sur les paquets générés ?"):
        lint('linda -i', package_dir, 'dist')

    # piuparts
    print SEPARATOR
    if target == "deb" and confirm("lancement de piuparts sur les paquets générés ?"):
        print 'buildeb --piuparts %s %s' % (package_dir, 'dist')
        os.system('buildeb --piuparts %s %s' % (package_dir, 'dist'))
    print SEPARATOR

    tag_package(package_dir, vcs_agent)

 
