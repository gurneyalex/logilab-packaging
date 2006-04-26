# Copyright (c) 2003-2004 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"""debianize handler for zope package

WARNING: this file contains some tabulations to be inserted in debian/rules,
         don't untabify this file !
"""

__revision__ = '$Id: zope_pkg.py,v 1.5 2005-12-28 18:34:50 syt Exp $'

from os.path import join

from logilab.devtools import TEMPLATE_DIR, stp
from logilab.devtools.debhdlrs import get_long_descr
from logilab.devtools.debhdlrs.python_pkg import PythonDepStandaloneHandler

class ZopeHandler(PythonDepStandaloneHandler):
    """debian package handler for a zope product"""
    
    def __init__(self, pkginfo, replace_func, empty_func):
        PythonDepStandaloneHandler.__init__(self, pkginfo, replace_func, empty_func)
        if not 'zope' in self.pkginfo.depends:
            # FIXME : why did I add the test below ??
            #if self.pkginfo.architecture_dependant: 
            self.pkginfo.depends.insert(0, 'zope (>= 2.6.2)')
            #else:
            #    self.pkginfo.depends.insert(0, 'zope')
        self.pkginfo.pyversions = ['2.2']
        
    def file_callbacks(self):
        """return debian files with their callback associated"""
        return PythonDepStandaloneHandler.file_callbacks(self) + \
               [
            ('postinst', self.postinst),
            ('prerm', self.prerm),
            ('config', self.config),
            ('templates', self.templates),
            ('dirs', self._std_dirs),            
            ('docs', self._std_docs),            
            ('examples', self._std_examples),
            ]
    
    def python_file_callbacks(self):
        """return debian files depending on python version, with their
        callback associated
        """
        return []
    
    def rules(self, stream):
        """create the "rules" file for zope packages"""
        pkginfo = self.pkginfo
        debian_name = pkginfo.debian_name
        patterns = self.base_rules()
        ignore = r'''
                            -path './debian/*' -or \
                            -path './build/*' -or \
                            -path './doc/*' -or \
                            -path './docs/*' -or \
                            -path '*/CVS/*' -or \
                            -name 'build-stamp' -or \
                            -iname 'authors*' -or \
                            -iname 'license.txt' -or \
                            -name 'ChangeLog*' -or \
                            -name 'README*' -or \
                            -name 'INSTALL*' -or \
                            -name 'TODO*' -or \
                            -name 'COPYING*' -or \
                            -name 'MANIFEST*' -or \
                            -name 'DEPENDS' -or \
                            -name 'RECOMMENDS' -or \
                            -name 'SUGGESTS' -or \
                            -name '.cvsignore' \
'''
        if pkginfo.test_directory:
            ignore += r'''			-or -path './%s/*' \
            ''' % pkginfo.test_directory
        patterns['INSTALL_PYTHON'] = r'''
	find . -type f -not \( \%s		\) -exec install -D --mode=644 {} debian/%s/usr/lib/zope/lib/python/Products/%s/{} \;''' % (
            ignore, pkginfo.debian_name, pkginfo.modname)
        # scripts
        if pkginfo.scripts:
            print 'XXXFIXME: alternatives are not handled'
        stp.parse_stream(open(join(TEMPLATE_DIR, 'rules')),
                         patterns, stream)

    def control(self, stream):
        """create the "control" file for zope packages"""
        pkginfo = self.pkginfo
        normalized_desc = get_long_descr(pkginfo)
        patterns = {
            'BUILD_DEPENDENCIES': '',
            'SHORT_DESCRIPTION':  pkginfo.short_desc,
            'LONG_DESCRIPTION':   normalized_desc,
            'SECTION' : 'web',
            }
        deps, expand = self.expand_dependancies()
        if expand:
            deps = deps % (self.pkginfo.pyversions[0] * expand)
        patterns['DEPENDENCIES'] = deps
        self.base_control(stream, patterns)
        stream.write(self.test_control())
        
    def test_dependancies(self):
        return '%s (= ${Source-Version})' % self.main_package_name()

    def postinst(self, stream):
        """create the "postinst" files for zope packages"""
        stream.write(open(join(TEMPLATE_DIR, 'zope.postinst')).read())

    def config(self, stream):
        """create the "config" files for zope packages"""
        stream.write(open(join(TEMPLATE_DIR, 'zope.config')).read())

    def templates(self, stream):
        """create the "template" files for zope packages"""
        patterns = {'PACKAGE' : self.pkginfo.debian_name}
        stp.parse_stream(open(join(TEMPLATE_DIR, 'zope.templates')),
                         patterns, stream)

    def prerm(self, stream):
        """create the "prerm" files for zope packages"""
        stream.write(open(join(TEMPLATE_DIR, 'zope.prerm')).read())
