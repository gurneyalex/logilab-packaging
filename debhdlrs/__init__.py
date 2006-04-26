# Copyright (c) 2003-2006 LOGILAB S.A. (Paris, FRANCE).
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
"""abstract package information handlers for debianize

WARNING: this file contains some tabulations to be inserted in debian/rules,
         don't untabify this file !
"""

__revision__ = '$Id: __init__.py,v 1.19 2006-02-10 15:09:16 syt Exp $'

from __future__ import nested_scopes 

import sys
import os
import re
import shutil
import tempfile
from os.path import join, exists, basename
from imp import find_module, load_module
from cStringIO import StringIO

from logilab.common.fileutils import export
from logilab.common.textutils import normalize_paragraph

from logilab.devtools import TEMPLATE_DIR, stp


class EmptyFile(Exception):
    """Exception raised when a file is empty, and so should not be created"""

def dh_wrap(content, stream):
    stp.parse_stream(open(join(TEMPLATE_DIR, 'debhelper')),
                     {'CONTENT': content}, stream)
        


def replace(tmp_file, dest_file):
    """interactivly replace the old file with the new file according to
    user decision
    """
    if exists(dest_file):
        p_output = os.popen('diff -u %s %s' % (dest_file, tmp_file), 'r')
        diffs = p_output.read()
        if diffs:
            print '*'*30, dest_file
            print 
            print diffs
            action = raw_input('Replace (N/y/q) ? ').lower()
            if action == 'y':
                try:
                    shutil.copyfile(tmp_file, dest_file)
                except IOError:
                    os.system('cvs edit %s'%dest_file)
                    shutil.copyfile(tmp_file, dest_file)
                print '** REPLACED'
            elif action == 'q':
                sys.exit(0)
            else:
                print '** KEEP CURRENT VERSION'
        else:
            print '** NO CHANGES IN', dest_file
    else:
        shutil.copyfile(tmp_file, dest_file)
        print '** CREATED FILE', dest_file
        
    os.remove(tmp_file)

def empty(dest_file):
    """helper function for files to remove according to user decision"""
    if exists(dest_file):
        print '*'*30, dest_file
        action = raw_input('Supprimer (N/y/q) ? ')
        if action == 'y':
            os.remove(dest_file)
            print '** REMOVED'
        elif action == 'q':
            sys.exit(0)
        else:
            print '** KEEP CURRENT VERSION'


FTP_RGX = re.compile('ftp://(?P<site>[^/]+)(?P<dir>/.*)')

def normalize_description(string):
    """normalize a description string for control files (ie add spaces and
    dots where required)
    """
    normalized_desc = []
    for line in string.split('\n'):
        line = line.strip()
        if line:
            if line.startswith('* '):
                normalized_desc.append('  %s' % line)
            else:
                normalized_desc.append(' %s' % line)
        elif normalized_desc and normalized_desc[-1] != ' .':
            normalized_desc.append(' .')
    return '\n'.join(normalized_desc)

def get_long_descr(pkginfo, addons=''):
    """get the long description for the given package"""
    desc = pkginfo.long_desc
    if addons:
        desc += '\n\n%s' % addons
    if pkginfo.web:
        desc += '\n\nHomepage: %s' % pkginfo.web
    return normalize_description(desc)
    
def dir_filter(paths):
    """remove directories from file names"""
    return [basename(path) for path in paths]

# Utilities for package preparation ###########################################


class DebianizerHandler(object):
    """Base handler for debianizing
    """
    def __init__(self, pkginfo, replace_func, empty_func):
        super(DebianizerHandler, self).__init__()
        self.pkginfo = pkginfo
        self.file_replace = replace_func
        self.empty_file = empty_func

    def expand_template(self, patterns, template, stream=None):
        """expand a template using given patterns. If a stream, the result
        content will be written in it as a debhelper script.
        
        Return the result content.
        """
        content_stream = StringIO()
        stp.parse_stream(open(join(TEMPLATE_DIR, template)),
                         patterns, content_stream)
        content = content_stream.getvalue() or ''
        if stream:
            dh_wrap(content, stream)
        return content
    
    def main_package_name(self):
        """return the package name for the main package (non source)"""
        return self.pkginfo.debian_name

    def common_package_name(self):
        """return the package name for common files (data, sgml, elisp...)"""
        return '%s-common' % self.pkginfo.debian_name

    def test_package_name(self):
        """return the package name for test files"""
        return '%s-test' % self.main_package_name()

    def file_callbacks(self):
        """return debian files with their callback associated"""
        addons_package = self.common_package_name()
        test_package = self.test_package_name()
        return [
            ('control', self.control),
            ('rules', self.rules),            
            ('copyright', self.copyright),
            ('watch', self.watch),
            
            ('%s.postinst' % addons_package, self.common_postinst),
            ('%s.prerm' % addons_package, self.common_prerm),
            ('%s.dirs' % addons_package, self.common_dirs),
            ('%s.install' % addons_package, self.common_install),
            ('%s.emacsen-install' % addons_package, self.common_emacsen_install),
            ('%s.emacsen-remove' % addons_package, self.common_emacsen_remove),
            ('%s.emacsen-startup' % addons_package, self.common_emacsen_startup),
            
            ('%s.dirs' % test_package, self.test_dirs),
            ]

    def update_debian_files(self, debian_dir):
        """create / update debian configuration files"""
        # create debian directory if it doesn't exist
        if not exists(debian_dir):
            os.mkdir(debian_dir)
        # FIXME: are we removing tmp files ???
        for filename, handler in self.file_callbacks():
            tmp_file = tempfile.mktemp()
            stream = open(tmp_file, 'w')
            try:
                handler(stream)
                stream.close()
                dest_file = join(debian_dir, filename)
                self.file_replace(tmp_file, dest_file)
                if filename == 'rules':
                    os.chmod(dest_file, 0777)
            except EmptyFile:
                self.empty_file(join(debian_dir, filename))
        
        
    def export_debian(self, archive, destdir):
        os.system('cd .. ; tar czf %s %s' % (archive, basename(os.getcwd())))
        export('.', destdir)
        # export debian directory
        export('debian', '%s/debian' % destdir)
        
    def prepare_debian(self, orig=1):
        """prepare a directory to build a debian package"""
        pkginfo = self.pkginfo
        if pkginfo.prepare:
            return pkginfo.prepare(pkginfo, orig)
        version = pkginfo.version
        debname = pkginfo.debian_name
        destdir = '../%s-%s'% (debname, version)
        archive = '%s-%s.tar.gz' % (pkginfo.name, version)
        # export upstream directory
        if exists(destdir):
            shutil.rmtree(destdir)
        _out = sys.stdout
        sys.stdout = sys.stderr
        try:
            self.export_debian(archive, destdir)
            # make the .orig.tar.gz if necessary
            if orig:
                shutil.copy('../%s' % archive,
                            '../%s_%s.orig.tar.gz' % (debname, version))
        finally:
            sys.stdout = _out
        return destdir
    
    def control(self, stream):
        raise NotImplementedError()
    
    def rules(self, stream):
        raise NotImplementedError()
    
    BINARY_INDEP = """\
# Build architecture-independent files here.
binary-indep: build install
	dh_testdir 
	dh_testroot 
	dh_install -i
	%(GZIP_CHANGELOG)s
	dh_installchangelogs -i
	dh_installexamples -i
	dh_installdocs -i %(STD_DOCS)s
	dh_installman -i%(INSTALL_EMACS)s
	dh_link -i
	dh_compress -i -X.py -X.ini -X.xml -Xtest
	dh_fixperms -i
	dh_installdeb -i
	dh_gencontrol -i 
	dh_md5sums -i
	dh_builddeb -i"""
    
    BINARY_ARCH = """\
# Build architecture-dependent files here.
binary-arch: build install
	dh_testdir 
	dh_testroot 
	dh_install -a
	dh_strip -a
	dh_link -a
	dh_compress -a -X.py -X.ini -X.xml -Xtest
	dh_fixperms -a
	dh_installdeb -a
	dh_gencontrol -a
	dh_md5sums -a
	dh_builddeb -a"""
    
    def base_rules(self):
        """return the common patterns for the "rules" file"""
        pkginfo = self.pkginfo
        # initial patterns
        patterns = {'BINARY_ARCH':       '',
                    'RULE_HEAD':         '',
                    'GZIP_CHANGELOG' :   '',
                    'STD_DOCS':          ' '.join(pkginfo.std_docs),
                    'SUBPACKAGE_INIT':   '',
                    'ARCH':              '',
                    'BUILD_PYTHON':      '',
                    'INSTALL_PYTHON':    '',
                    'INSTALL_TEST':      '',
                    'INSTALL_ALT':       '',
                    'INSTALL_EMACS':     '',
                    'INSTALL_ELISP':     '',
                    'INSTALL_MAN':       ''}
        # architecture
        if pkginfo.architecture_dependant:
            patterns['BINARY_TARGET'] = 'binary-indep binary-arch'
            patterns['BINARY_ARCH'] = self.BINARY_ARCH
        else:
            patterns['BINARY_TARGET'] = 'binary-indep'
        # emacs
        if pkginfo.elisp_files:
            pkg = self.common_package_name()
            patterns['INSTALL_EMACS'] = """
	dh_installemacsen"""
            patterns['INSTALL_ELISP'] = """
	install -m 644 %s debian/%s/usr/share/emacs/site-lisp/%s/""" % (
                ' '.join(pkginfo.elisp_files), pkg, pkg)
        # Changelog
        if 'ChangeLog' in pkginfo.std_docs:
            pkginfo.std_docs.remove('ChangeLog')
            pkginfo.std_docs.append('changelog.gz')
            patterns['GZIP_CHANGELOG'] = 'gzip -9 -c ChangeLog > changelog.gz'
            patterns['STD_DOCS'] = ' '.join(pkginfo.std_docs)
        # tests
        if pkginfo.test_directory:
            dest = 'debian/%s/usr/share/doc/%s/test' % (self.test_package_name(),
                                                        self.main_package_name())
            patterns['INSTALL_TEST'] = r'''
	# install tests
	(cd %s && find . -type f -not \( -path '*/CVS/*' -or -name '*.pyc' \) -exec install -D --mode=644 {} ../%s/{} \;)''' % (
                pkginfo.test_directory, dest)
        # binary indep (last because it may needs some patterns defined above)
        patterns['BINARY_INDEP'] = self.BINARY_INDEP % patterns
        return patterns

    def base_control(self, stream, patterns):
        """initialize the "control" file"""
        pkginfo = self.pkginfo
        package_name = self.main_package_name()
        common_pkg = self.common_package_name()
        maintainer = 'Maintainer: %s <%s>' % (pkginfo.debian_maintainer,
                                              pkginfo.debian_maintainer_email)
        if pkginfo.debian_uploader:
            maintainer += '\nUploaders: %s' % pkginfo.debian_uploader
        patterns.update({
            'MAINTAINER':    maintainer,
            'SOURCEPACKAGE': pkginfo.debian_name,
            'PACKAGE':       self.main_package_name(),
            })
        # additional packages for dtd, elisp or data?
        if (pkginfo.dtd_files or pkginfo.catalog or pkginfo.xslt_files 
            or pkginfo.elisp_files or pkginfo.elisp_startup 
            or pkginfo.data_files) and common_pkg != package_name:
            pkginfo.depends.append('%s (>= ${Source-Version})' % common_pkg)
            patterns['DEPENDENCIES'] += ', %s' % common_pkg
            depends, descr = self.common_deps(pkginfo)
            depends = depends and '\nDepends: %s' % ', '.join(depends) or ''
            norm_desc = get_long_descr(pkginfo,
"""This package provides files shared by %s across different python
 versions:
%s
""" % (pkginfo.name, '\n'.join(descr)))
            addons = '''Package: %s
Architecture: all%s
Description: shared data for the %s package
%s

''' % (common_pkg, depends, pkginfo.debian_name, norm_desc)
        else:
            addons = ''
        stp.parse_stream(open(join(TEMPLATE_DIR, 'control')),
                         patterns, stream)
        stream.write(addons)

    def common_deps(self, pkginfo):
        depends = []
        descr = []
        if pkginfo.dtd_files or pkginfo.catalog or pkginfo.xslt_files:
            depends.append('sgml-base')
            descr.append('* SGML DTDs and catalog')
        if pkginfo.elisp_files or pkginfo.elisp_startup:
            depends.append('emacsen-common')
            descr.append('* Emacs lisp libraries')
        if pkginfo.data_files:
            descr.append('* Shared data')
        return depends, descr
    
    def copyright(self, stream):
        """create the "copyright" file for all packages"""
        pkginfo = self.pkginfo
        download = pkginfo.ftp and 'It was downloaded from %s' % pkginfo.ftp or ''
        if not download:
            download = pkginfo.web and 'It was downloaded from %s' % pkginfo.web
        patterns = {
            'DEBIANIZER':         pkginfo.debian_maintainer,
            'DEBIANIZER_EMAIL':   pkginfo.debian_maintainer_email,
            'UPSTREAM_AUTHOR':    '%s <%s>' % (pkginfo.author,
                                               pkginfo.author_email),
            'UPSTREAM_FTP':       download,
            'COPYRIGHT':          pkginfo.copyright,
            'LICENSE' :           pkginfo.license_text,
            }
        stp.parse_stream(open(join(TEMPLATE_DIR, 'copyright')),
                         patterns, stream)

    def watch(self, stream):
        """create the "watch" file for all packages"""
        pkginfo = self.pkginfo
        if pkginfo.ftp is None:
            raise EmptyFile()
        match = FTP_RGX.match(pkginfo.ftp)
        if match is None:
            print 'Unable to match FTP site %s'% pkginfo.ftp
            raise EmptyFile()
        patterns = {
    #        'FTPSITE' : match.group('site'),
            'FTPDIR' : pkginfo.ftp,
            'SOURCEPACKAGE' : pkginfo.name
            }
        stp.parse_stream(open(join(TEMPLATE_DIR, 'watch')),
                         patterns, stream)


    def common_dirs(self, stream, raise_if_empty=True):
        """create the "dir" file for -common packages"""
        pkginfo = self.pkginfo
        if not (pkginfo.dtd_files or pkginfo.catalog or pkginfo.xslt_files
                or pkginfo.elisp_files):
            if raise_if_empty:
                raise EmptyFile()
            return
        if pkginfo.elisp_files:
            stream.write('usr/share/emacs/site-lisp/\n')
            elisp_pkg = self.common_package_name()
            stream.write('usr/share/emacs/site-lisp/%s\n' % elisp_pkg)
        if pkginfo.dtd_files or pkginfo.xslt_files:
            debname = self.main_package_name()
            stream.write('usr/share/sgml/%s\n' % debname)
            if pkginfo.dtd_files:
                stream.write('usr/share/sgml/%s/dtd\n' % debname)
            if pkginfo.xslt_files:
                stream.write('usr/share/sgml/%s/stylesheet\n' % debname)


    def common_install(self, stream):
        """create the "install" file for -sgml packages"""
        pkginfo = self.pkginfo
        writed = False
        if pkginfo.dtd_files:
            for dtd in pkginfo.dtd_files:
                stream.write('%s usr/share/sgml/%s/dtd\n' % (
                    dtd, pkginfo.debian_name))
            writed = True
        if pkginfo.catalog:
            stream.write('%s usr/share/sgml/%s\n' % (
                pkginfo.catalog, pkginfo.debian_name))
            writed = True
        if pkginfo.xslt_files:
            for xslt in pkginfo.xslt_files:
                stream.write('%s usr/share/sgml/%s/stylesheet\n' % (
                    xslt, pkginfo.debian_name))
            writed = True
        if not writed:
            raise EmptyFile()

    def common_prerm(self, stream=None):
        """create the "prerm" files for -common packages"""
        # catalog
        if not self.pkginfo.catalog:
            if stream:
                raise EmptyFile()
            return ''
        debname = self.main_package_name()
        patterns = {'DEBNAME' : debname,
                    'CATALOG' : '%s/catalog' % debname}
        return self.expand_template(patterns, 'sgml.prerm', stream)
            
    def common_postinst(self, stream=None):
        """create the "postinst" files for -common packages"""
        # catalog
        if not self.pkginfo.catalog:
            if stream:
                raise EmptyFile()
            return ''
        debname = self.main_package_name()
        patterns = {'DEBNAME' : debname,
                    'CATALOG' : '%s/catalog' % debname}
        return self.expand_template(patterns, 'sgml.postinst', stream)

    def common_emacsen_install(self, stream):
        """create the "emacsen-install" file for -common packages"""
        pkginfo = self.pkginfo
        if not pkginfo.elisp_files:
            raise EmptyFile()
        patterns = {'PACKAGE': self.common_package_name()}
        stp.parse_stream(open(join(TEMPLATE_DIR, 'elisp.emacsen-install')),
                         patterns, stream)

    def common_emacsen_remove(self, stream):
        """create the "emacsen-remove" file for -elisp packages"""
        pkginfo = self.pkginfo
        if not pkginfo.elisp_files:
            raise EmptyFile()
        patterns = {'PACKAGE': self.common_package_name()}
        stp.parse_stream(open(join(TEMPLATE_DIR, 'elisp.emacsen-remove')),
                         patterns, stream)

    def common_emacsen_startup(self, stream):
        """create the "emacsen-startup" file for -elisp packages"""
        pkginfo = self.pkginfo
        if not pkginfo.elisp_startup:
            raise EmptyFile()
        patterns = {'PACKAGE': self.common_package_name()}
        stp.parse_stream(open(pkginfo.elisp_startup), patterns, stream)

    def test_control(self):
        test_package = self.test_package_name()
        debname = self.main_package_name()
        if not self.pkginfo.test_directory or test_package == debname:
            return ''
        depends = self.test_dependancies()
        return '''Package: %s
Architecture: all
Depends: %s
Description: %s\'s test files
%s
''' % (test_package, depends, debname, normalize_paragraph(
    """This package contains test files shared by the %s package. It isn\'t
necessary to install this package unless you want to execute or look at
the tests.""" % debname, indent=' ', line_len=74))

    def test_dirs(self, stream, raise_if_empty=True):
        """create the "dirs" file for -test packages"""
        pkginfo = self.pkginfo
        if pkginfo.test_directory:
            debname = self.main_package_name()
            stream.write('usr/share/doc/%s\n' % debname)
            stream.write('usr/share/doc/%s/test\n' % debname)
        elif raise_if_empty:
            raise EmptyFile()


    def _std_dirs(self, stream, package=None):
        """create the "dirs" file for all packages"""
        pkginfo = self.pkginfo
        if package is None:
            package = pkginfo.main_package_name()
        base_doc = 'usr/share/doc/%s' % package
        stream.write('%s\n' % base_doc)

    def _std_docs(self, stream, package=None):
        """create the .docs file for a package"""
        pkginfo = self.pkginfo
        if not (pkginfo.html_doc_files or pkginfo.doc_files):
            raise EmptyFile()
        if pkginfo.html_doc_files:
            stream.write('\n'.join(pkginfo.html_doc_files) + '\n')
        if pkginfo.doc_files:
            stream.write('\n'.join(pkginfo.doc_files) + '\n')
            
    def _std_examples(self, stream, package=None):
        """create the .examples file for a package"""
        if self.pkginfo.examples_directory:
            stream.write(self.pkginfo.examples_directory + '/*\n')
        else:
            raise EmptyFile()



def get_package_handler(pkginfo, replace_func=replace, empty_func=empty):
    """return the debian package handler for this package"""
    try:
        return PKG_HANDLERS[pkginfo.debian_handler](pkginfo, replace_func, empty_func)
    except KeyError:
        raise Exception('Unknown debian package handler %s' 
                        % pkginfo.debian_handler)
    
from logilab.devtools.debhdlrs.python_pkg import \
     PythonDepLibraryHandler, PythonIndepLibraryHandler, \
     PythonDepStandaloneHandler, PythonIndepStandaloneHandler
from logilab.devtools.debhdlrs.zope_pkg import ZopeHandler

PKG_HANDLERS = {
    'python-library' : PythonDepLibraryHandler, # bw compat
    'python-standalone' : PythonDepStandaloneHandler, # bw compat
    'python-dep-library' : PythonDepLibraryHandler,
    'python-indep-library' : PythonIndepLibraryHandler,
    'python-dep-standalone' : PythonDepStandaloneHandler,
    'python-indep-standalone' : PythonIndepStandaloneHandler,
    'zope' : ZopeHandler,    
    }

