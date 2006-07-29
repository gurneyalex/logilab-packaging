#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
#
# Copyright (c) 2004 LOGILAB S.A. (Paris, FRANCE).
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
from logilab.devtools.lib.utils import cond_exec, cond_continue

def usage(status=0):
    """print usage and exit with the given status"""
    print "USAGE: makedistrib <source_directory> <bdist_wininst|sdist|deb>"
    print "if the second argument is omitted, default is deb"
    print
    print __doc__
    sys.exit(status)
    
def run(args=None):
    args = args or sys.argv[1:]
    if '--help' in args or '-h' in args:
        usage( )
    if not args or len(args) > 2:
        usage(1)
    package_dir = args[0]
    pkgname = basename(package_dir)
    vcs_agent = get_vcs_agent(package_dir)
    print '+' * 72
    if cond_exec("vérifier que l'entrepôt est à jour"):
        try:
            result = vcs_agent.not_up_to_date(package_dir)
            if result:
                print '\n'.join(["%s: %s"%r for r in result])
                cond_continue()
        except NotImplementedError:
            print 'pas encore supporté par cet agent de controle'
    print '+' * 72
    if cond_exec("vérifier qu'aucun fichier n'est en édition"):
        try:
            result = vcs_agent.edited(package_dir)
            if result:
                print '\n'.join(result)
                cond_continue()
        except NotImplementedError:
            print 'pas encore supporté par cet agent de controle'
    print '+' * 72
    print "nettoyage du répertoire de travail"
    os.system('rm -f *~ \#* .\#* */*~ */\#* */.\#* */*/*~ */*/\#* */*/.\#* 2>/dev/null')
    print '+' * 72
    print "génération du paquet"
    target = len(args) == 2 and args[1] or 'deb'
    status = os.system('buildpackage %s %s' % (package_dir, target))
    if status == 0:
        print '+' * 72
        if target == "deb" and cond_exec("lancement de piuparts sur les paquets générés"):
            print 'buildeb --piuparts %s %s' % (package_dir, 'dist')
            os.system('buildeb --piuparts %s %s' % (package_dir, 'dist'))
    print '+' * 72
    tag_package(package_dir, vcs_agent)

if __name__ == '__main__':
    run()
 
