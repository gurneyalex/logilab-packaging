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
"""debianize handler for python packages

WARNING: this file contains some tabulations to be inserted in debian/rules,
         don't untabify this file !
"""

__revision__ = '$Id: python_pkg.py,v 1.22 2006-02-06 15:40:36 syt Exp $'

import os
import sys
import re
import shutil
import tempfile
from os.path import join, exists
from imp import find_module, load_module

from logilab.common.fileutils import export

from logilab.devtools import TEMPLATE_DIR, stp
from logilab.devtools.debhdlrs import EmptyFile, DebianizerHandler, dir_filter, \
     get_long_descr

ALT_PRIORITY = {
    '2.1' : 10,
    '2.2' : 30,
    '2.3' : 50,
    '2.4' : 40,
    }


def _preprocess_deps(dependencies):
    """preprocess dependencies for the default python package"""
    depends = []
    for dep in dependencies:
        if dep in ('python', 'python-optik'):
            continue
        if dep.find('(python)') > -1:
            dep = dep.replace('(python)', '').strip()
        depends.append(dep)
    return depends

def _python_dependencies(dependencies, expand=0, dep_type=None):
    """parse dependencies and add %s where the python version should be
    inserted
    return a dependencies string with the number of place where the python
    version should be inserted
    """
    result = []
    for dependency in dependencies:
        if dependency.startswith('python-') or dependency == 'python':
            result.append('python%%s%s' % dependency[6:])
            expand += 1
        elif dependency.endswith('-python'):
            result.append('%s-python%%s' % dependency[:-7])
            expand += 1            
        elif dependency.find('(python)') > -1:
            dependency = dependency.replace('(python)', '').strip()
            result.append('python%%s-%s' % dependency)
            expand += 1
        else:
            result.append(dependency)
    result = ', '.join(result)
    if dep_type is not None:
        result = '\n%s: %s' % (dep_type, result)
    return result, expand

#def tabify(string):
#    return '\n'.join(['\t%s' % line for line in string.splitlines()])    


class PythonMixIn(object):
    """a mixin for python package, with common functionalities of different
    python package handler
    """
    default_python = '2.3'
    next_python = '2.4'
    
    def __init__(self, pkginfo, replace_func, empty_func):
        super(PythonMixIn, self).__init__(pkginfo, replace_func, empty_func)
        if not 'python' in self.pkginfo.depends:
            self.pkginfo.depends.insert(0, 'python')
           
    def export_debian(self, archive, destdir):
        pkginfo = self.pkginfo
        debname = pkginfo.debian_name
        mp_file, mp_filename, mp_desc = find_module('setup',
                                                    [pkginfo.base_directory])
        setup = load_module('setup', mp_file, mp_filename, mp_desc)
        script_args = ('sdist', '--force-manifest')
        setup.install(script_name="setup.py", script_args=script_args)
        # extract source tarball
        os.system('tar xzf dist/%s -C ..' % archive)
        # move it move it
        os.rename('dist/%s' % archive, '../%s' % archive)
        # and rename it to match debian name if necessary
        if debname != pkginfo.name:
            os.rename('../%s-%s' % (pkginfo.name, pkginfo.version), destdir)
        # export debian directory
        export('debian', '%s/debian' % destdir)

    def test_dependancies(self):
        debname = self.pkginfo.debian_name
        # handle special dependencies on logilab-common
        if self.pkginfo.test_directory and \
               exists(join(self.pkginfo.test_directory, 'runtests.py')) \
               and debname != 'logilab-common':
            depends = ['(%s (= ${Source-Version}), python-logilab-common)'
                       % self.main_package_name()]
            depends += ['(python%s-%s (= ${Source-Version}), python%s-logilab-common)'
                        % (pyver, debname, pyver)
                        for pyver in self.pkginfo.pyversions]
        else:
            depends = ['%s (= ${Source-Version})' % self.main_package_name()]
            depends += ['python%s-%s (= ${Source-Version})' % (pyver, debname)
                        for pyver in self.pkginfo.pyversions]            
        return ' | '.join(depends)
        
    def _rule_python_install(self, pkginfo, package, pkg_dir, python='python'):
        result = '''
	%s setup.py -q install_lib --no-compile --install-dir=%s
	%s setup.py -q install_headers --install-dir=debian/%s/usr/include/''' % (
                python, pkg_dir, python, package)
        if pkginfo.scripts:
            result += '''
	%s setup.py -q install_scripts --install-dir=debian/%s/usr/bin/''' % (
                python, package)
        if pkginfo.subpackage_of:
            pkg_dir = '%s/%s' % (pkg_dir, pkginfo.subpackage_of)
            if not pkginfo.subpackage_master:
                result += '''
	# remove sub-package __init__ file (created by another package)
	rm %s/__init__.py''' % pkg_dir
        if pkginfo.test_directory:
            lib_dir = '%s/%s' % (pkg_dir, pkginfo.modname)
            result += '''
	# remove test directory (installed in in the doc directory)
	rm -rf %s/%s''' % (lib_dir, pkginfo.test_directory)
        return result
    
    def _control_python(self, stream, short_desc, long_desc, build_require):
        pkginfo = self.pkginfo
        patterns = {
            'SHORT_DESCRIPTION':  short_desc,
            'LONG_DESCRIPTION':   long_desc,
            'SECTION' :           'python',
            }
        if pkginfo.data_files:
            build_require.append('python')
        patterns['BUILD_DEPENDENCIES'] = ', %s' % ', '.join(build_require)
        patterns['DEPENDENCIES'] = self._control_python_default_deps(pkginfo)
        self.base_control(stream, patterns)
        stream.write(self.test_control())

    def _dirs_python(self, stream, sitepkg, package):
        pkginfo = self.pkginfo
        stream.write('%s\n' % sitepkg)
        if pkginfo.subpackage_of:
            subpkg = pkginfo.subpackage_of
            stream.write('%s/%s\n' % (sitepkg, subpkg))
            stream.write('%s/%s/%s\n' % (sitepkg, subpkg, pkginfo.modname))
        else:
            stream.write('%s/%s\n' % (sitepkg, pkginfo.modname))
        self._std_dirs(stream, package)


class PythonLibraryMixIn(object):
    """a mixin for library package, prepending python- to the main package name
    """
    #def __init__(self, pkginfo, replace_func, empty_func):
    #    super(PythonLibraryMixIn, self).__init__(pkginfo, replace_func, empty_func)

    def main_package_name(self):
        """return the package name for the main package (non source)"""
        return 'python-' + self.pkginfo.debian_name

    
class PythonDepStandaloneHandler(PythonMixIn, DebianizerHandler):
    """package information for a package conforming to doc/standard_source_tree

    the package is a python dependant standalone program
    """

    def python_file_callbacks(self):
        """return debian files depending on python version, with their
        callback associated
        """
        return [
            ('dirs', self.python_dirs),
            ('postinst', self.python_postinst),
            ('prerm', self.python_prerm),
            ('postrm', self.python_postrm),
            ('manpages', self.python_manpages),
            ('docs', self._std_docs),
            ('examples', self._std_examples),
            ]
        
    def update_debian_files(self, debian_dir):
        """create / update debian configuration files"""
        DebianizerHandler.update_debian_files(self, debian_dir)
        pyversions = self.pkginfo.pyversions
        for suffix, handler in self.python_file_callbacks():
            for pyver in pyversions:
                filename = 'python%s-%s.%s' % (pyver, self.pkginfo.debian_name, suffix)
                tmp_file = tempfile.mktemp()
                stream = open(tmp_file, 'w')
                try:
                    handler(stream, pyver)
                    stream.close()
                    self.file_replace(tmp_file, join(debian_dir, filename))
                except EmptyFile:
                    self.empty_file(join(debian_dir, filename))
        

    def rules(self, stream):
        """create the "rules" file for python packages"""
        pkginfo = self.pkginfo
        debian_name = pkginfo.debian_name
        patterns = self.base_rules()
        patterns['RULE_HEAD'] = 'PYVERSIONS=%s' % ' '.join(pkginfo.pyversions)
        for pyver in pkginfo.pyversions:
            python = 'python%s' % pyver
            package = '%s-%s' % (python, debian_name)
            pkg_dir = 'debian/%s/usr/lib/python%s/site-packages' % (package, pyver)
            patterns['INSTALL_PYTHON'] += self._rule_python_install(pkginfo, package, pkg_dir, python)
        # data
        if pkginfo.data_files:
            patterns['INSTALL_PYTHON'] += '''
	python setup.py -q install_data --install-dir=debian/%s/usr/
            ''' % self.common_package_name()

        patterns['BUILD_PYTHON'] = '''
	for v in $(PYVERSIONS) ; do \\
		python$$v setup.py -q build ; \\
	done'''
        # alternatives
        if pkginfo.scripts:
            lbuf = []
            write = lbuf.append
            for alt in dir_filter(pkginfo.scripts):
                write('		i=$$PYTMP/usr/bin/%s ; \\' % alt)
                write(
'''		if head -1 $$i | grep "^#! */usr/bin" | grep "python" >/dev/null ; then \\
			sed "s@^#! */usr/bin/env \+python\$$@#!/usr/bin/$$PYTHON@;s@^#! */usr/bin/python\$$@#!/usr/bin/$$PYTHON@" <$$i >$$i.$$PYTHON; \\
			rm $$i ; \\
		else \\
			mv $$i $$i.$$PYTHON ; \\
		fi ; \\''')
                write('		chmod a+x $$i.$$PYTHON ; \\')
                if pkginfo.man_files.has_key(alt):
                    manfile, section = pkginfo.man_files[alt]
                    write('		cp %s man/%s.$$PYTHON.%s ; \\' % (manfile, alt,
                                                                          section))

            patterns['INSTALL_ALT'] = """
	for v in $(PYVERSIONS) ; do \\
		PYTHON=python$$v ; \\
		PYTMP="debian/$$PYTHON-%s" ; \\
%s
	done""" % (debian_name, '\n'.join(lbuf))
        stp.parse_stream(open(join(TEMPLATE_DIR, 'rules')), patterns, stream)

    def _control_python_default_deps(self, pkginfo):
        """return dependancies for the main package"""
        result = ''
        for dep_type in ('recommends', 'suggests'):
            deps = getattr(pkginfo, dep_type)
            if deps:
                result += '%s: %s\n' % (dep_type.capitalize(),
                                        ', '.join(_preprocess_deps(deps)))
        debname = pkginfo.debian_name
        result += ('Depends: python (>= %s), python (<< %s), '
                   'python%s-%s (>= ${Source-Version})' % (self.default_python,
                                                           self.default_python,
                                                           self.next_python,
                                                           debname))
        if len(pkginfo.depends) > 1:
            depends = _preprocess_deps(pkginfo.depends)
            if depends: # preprocess_deps may have removed some dependencies...
                result += ', %s' % ', '.join(depends)
        return result
    
    def control(self, stream):
        """create the "control" file for python packages"""
        pkginfo = self.pkginfo
        normalized_desc = get_long_descr(pkginfo, """\
This package is an empty dummy package that always depends on a package built
for Debian\'s default Python version.""")
        pyversions = pkginfo.pyversions
        assert self.default_python in pyversions, \
                   'Default python version %s not supported !' % self.default_python
        build_require = ['python%s-dev' % pyver for pyver in pyversions]
        self._control_python(stream, pkginfo.short_desc + ' [dummy package]',
                             normalized_desc, build_require)
        package_name = self.main_package_name()
        deps, expand = self.expand_dependancies()
        if pkginfo.architecture_dependant:
            arch = 'any'
        else:
            arch = 'all'
        normalized_desc = get_long_descr(pkginfo, 'This package is built with Python %s.')
        for pyver in pyversions:
            if expand:
                v_add_ons = deps % ((pyver,) * expand)
            else:
                v_add_ons = deps
            pyver_as_tuple = tuple(map(int, pyver.split('.'))) 
            if pyver_as_tuple >= (2, 3):
                if v_add_ons.find('python%s-optik' % pyver) != -1:
                    rgx = re.compile(r',\s*python%s-optik[^,\n]*' % pyver)
                    v_add_ons = rgx.sub('', v_add_ons)
                if v_add_ons.find('python%s-xmlbase' % pyver) != -1:
                    rgx = re.compile(r',\s*python%s-xmlbase[^,\n]*' % pyver)
                    v_add_ons = rgx.sub('', v_add_ons)
            stream.write('''
Package: python%s-%s
Architecture: %s%s
Description: %s [built for python%s]
%s
''' % (pyver, pkginfo.debian_name, arch, v_add_ons,
       pkginfo.short_desc, pyver, normalized_desc % pyver))

    def expand_dependancies(self):
        pkginfo = self.pkginfo
        add_ons = ''
        if pkginfo.depends:
            depends, expand = _python_dependencies(pkginfo.depends,
                                                   dep_type='Depends')
            add_ons += depends
        if pkginfo.recommends:
            recommends, expand = _python_dependencies(pkginfo.recommends, expand,
                                                      dep_type='Recommends')
            add_ons += recommends
        if pkginfo.suggests:
            suggests, expand = _python_dependencies(pkginfo.suggests, expand,
                                                    dep_type='Suggests')
            add_ons += suggests
        return add_ons, expand
    
        
    def python_postinst(self, stream, pyver):
        """create the "postinst" files for python packages"""
        pkginfo = self.pkginfo
        content = ''
        if pkginfo.scripts:
            # install alternatives
            lbuf = []
            write = lbuf.append
            for alt in dir_filter(pkginfo.scripts):
                priority = ALT_PRIORITY[pyver]
                if pkginfo.man_files.has_key(alt):
                    section = pkginfo.man_files[alt][1]
                    data = {'alt': alt,
                            'manfile': '%s.%s.gz' % (alt, section),
                            'section': section,
                            'priority': priority}
                    write('''    update-alternatives --install /usr/bin/%(alt)s %(alt)s /usr/bin/%(alt)s.python$VERSION %(priority)s \\
--slave /usr/share/man/man%(section)s/%(manfile)s %(manfile)s \
/usr/share/man/man%(section)s/%(alt)s.python$VERSION.%(section)s''' % data)
                else:
                    write('    update-alternatives --install /usr/bin/%s %s /usr/bin/%s.python$VERSION %s' % (
                        alt, alt, alt, priority))
            content = """
## Alternatives

if [ "$1" = "configure" ]; then
    # update-alternatives on things that collide
%s
fi""" % ('\n'.join(lbuf))
        # subpackage of something ?
        base_dir = '/usr/lib/python%s/site-packages' % pyver
        subpkg = pkginfo.subpackage_of
        if subpkg:
            base_dir = '%s/%s' % (base_dir, subpkg)
            base_file = '%s/__init__.py' % base_dir
            content += '''
echo "__path__ += ['/usr/lib/site-python/%s/']" > %s
''' % (base_file, subpkg, base_file)
        patterns = {'PYVER':        pyver,
                    'PACKAGEDIR' :  '%s/%s' % (base_dir, pkginfo.modname),
                    'CONTENT' :     content}
        stp.parse_stream(open(join(TEMPLATE_DIR, 'python.postinst')),
                         patterns, stream)



    def python_prerm(self, stream, pyver):
        """create the "prerm" files for python packages"""
        pkginfo = self.pkginfo
        patterns = {'PACKAGE': 'python%s-%s' % (pyver, pkginfo.debian_name),
                    'ALTERNATIVES' : ''}
        # alternatives
        if pkginfo.scripts:
            patterns['ALTERNATIVES'] = """
## Alternatives

if [ $1 != "upgrade" ]; then
    # Remove alternatives
    for i in %s ; do
        update-alternatives --remove $i /usr/bin/$i.python%s
    done
fi""" % (' '.join(dir_filter(pkginfo.scripts)), pyver)
        stp.parse_stream(open(join(TEMPLATE_DIR, 'python.prerm')),
                         patterns, stream)

    def python_postrm(self, stream, pyver):
        """create the "postrm" files for python packages"""
        raise EmptyFile()
##         pkginfo = self.pkginfo
##         if not pkginfo.subpackage_of:
##             raise EmptyFile()
##         package_dir = '/usr/lib/python%s/site-packages/%s' % (pyver, pkginfo.subpackage_of)
##         script = 'if [ -n "`ls %s | grep -v __init__.py`" ] ; then rm -rf %s ; fi' % (
##             package_dir, package_dir)
##         patterns = {'CONTENT': script}
##         stp.parse_stream(open(join(TEMPLATE_DIR, 'debhelper')),
##                          patterns, stream)

    def python_dirs(self, stream, pyver):
        """create the .dirs file for python packages"""
        sitepkg = 'usr/lib/python%s/site-packages' % pyver
        package = 'python%s-%s' % (pyver, self.pkginfo.debian_name)
        self._dirs_python(stream, sitepkg, package)

    def python_manpages(self, stream, pyver):
        """create the .manpages file for python packages"""
        pkginfo = self.pkginfo
        if not pkginfo.man_files:
            raise EmptyFile()
        altmanpages = {}
        for alt in dir_filter(pkginfo.scripts):
            try:
                section = pkginfo.man_files[alt][1]
                altmanpages[alt] = 1
                stream.write('man/%s.python%s.%s\n' % (alt, pyver, section))
            except KeyError:
                continue
        for name, manpage_def in pkginfo.man_files.items():
            if not altmanpages.has_key(name):
                stream.write('%s\n' % manpage_def[0])

                
class PythonIndepStandaloneHandler(PythonMixIn, DebianizerHandler):
    """package information for a package conforming to doc/standard_source_tree

    the package is a python independant standalone program (install in
    /usr/lib/site-python instead of /usr/lib/pythonX.X/site-packages
    """
    
    def file_callbacks(self):
        this_package = self.main_package_name()
        return [
            ('control', self.control),
            ('rules', self.rules),
            ('copyright', self.copyright),
            ('watch', self.watch),
            
            ('%s.dirs' % this_package, self.dirs),
            ('%s.postinst' % this_package, self.postinst),
            ('%s.prerm' % this_package, self.prerm),
            ('%s.postrm' % this_package, self.postrm),
            ('%s.manpages' % this_package, self.manpages),
            ('%s.docs' % this_package, self._std_docs),
            ('%s.examples' % this_package, self._std_examples),
            ('%s.install' % this_package, self.common_install),
            ('%s.emacsen-install' % this_package, self.common_emacsen_install),
            ('%s.emacsen-remove' % this_package, self.common_emacsen_remove),
            ('%s.emacsen-startup' % this_package, self.common_emacsen_startup),
            ]

    def rules(self, stream):
        """create the "rules" file for python packages"""
        pkginfo = self.pkginfo
        debian_name = self.main_package_name()
        patterns = self.base_rules()
        pkg_dir = 'debian/%s/usr/lib/site-python' % (debian_name)
        patterns['INSTALL_PYTHON'] += self._rule_python_install(pkginfo, debian_name, pkg_dir)
        # data
        if pkginfo.data_files:
            patterns['INSTALL_PYTHON'] += '''
	python setup.py -q install_data --install-dir=debian/%s/usr/
            ''' % self.common_package_name()
        patterns['BUILD_PYTHON'] = '''
	python setup.py -q build'''
        # scripts
        if pkginfo.scripts:
            lbuf = []
            write = lbuf.append
            for alt in dir_filter(pkginfo.scripts):
                script = 'debian/%s/usr/bin/%s' % (debian_name, alt)
                write(
'''	if head -1 %s | grep "^#! */usr/bin" | grep "python" >/dev/null ; then \\
		sed -i "s@^#! */usr/bin/env \+python\$$@#!/usr/bin/python@" %s; \\
	fi
	chmod a+x %s''' % (script, script, script))
            patterns['INSTALL_ALT'] = '\n' + '\n'.join(lbuf)
        stp.parse_stream(open(join(TEMPLATE_DIR, 'rules')), patterns, stream)

    def _control_python_default_deps(self, pkginfo):
        """return dependancies for the main package"""
        result = ''
        for dep_type in ('recommends', 'suggests'):
            deps = getattr(pkginfo, dep_type)
            if deps:
                result += '%s: %s\n' % (dep_type.capitalize(),
                                        ', '.join(_preprocess_deps(deps)))
        result += 'Depends: python'
        if len(pkginfo.depends) > 1:
            depends = _preprocess_deps(pkginfo.depends)
            if depends: # preprocess_deps may have removed some dependencies...
                result += ', %s' % ', '.join(depends)
        common_deps = self.common_deps(pkginfo)[0]
        if common_deps:
            result += ', %s' % ', '.join(common_deps)
        if pkginfo.pyversions:
            provides = ', '.join(['python%s-%s' % (pyver, pkginfo.debian_name)
                                  for pyver in pkginfo.pyversions])
            result += '\nProvides: %s\nConflicts: %s\nReplaces: %s' % (
                provides, provides, provides)
        return result
    
    def control(self, stream):
        """create the "control" file for python packages"""
        pkginfo = self.pkginfo
        normalized_desc = get_long_descr(pkginfo)
        self._control_python(stream, pkginfo.short_desc, normalized_desc,
                             ['python-dev'])
        
    def postinst(self, stream):
        """create the "postinst" files for python packages"""
        pkginfo = self.pkginfo
        content = self.common_postinst()
        base_dir = '/usr/lib/site-python'
        # subpackage of something ?
        subpkg = pkginfo.subpackage_of
        if subpkg:
            base_dir = '%s/%s' % (base_dir, subpkg)
##             content += '''
## touch %s/__init__.py
## ''' % base_dir
        patterns = {'PYVER':        self.default_python,
                    'PACKAGEDIR' :  '%s/%s' % (base_dir, pkginfo.modname),
                    'CONTENT' :     content}
        self.expand_template(patterns, 'python.postinst', stream)


    def prerm(self, stream):
        """create the "prerm" files for python packages"""
        content = self.common_prerm()
        patterns = {'PACKAGE': self.main_package_name(),
                    'CONTENT' : content}
        self.expand_template(patterns, 'python.prerm', stream)

    def postrm(self, stream):
        """create the "postrm" files for python packages"""
        raise EmptyFile()
##         pkginfo = self.pkginfo
##         if not pkginfo.subpackage_of:
##             raise EmptyFile()
##         package_dir = '/usr/lib/site-python/%s' % (pkginfo.subpackage_of)
##         script = 'if [ -n "`ls %s | grep -v __init__.py`" ] ; then rm -rf %s ; fi' % (
##             package_dir, package_dir)
##         patterns = {'CONTENT': script}
##         stp.parse_stream(open(join(TEMPLATE_DIR, 'debhelper')),
##                          patterns, stream)
        
    def dirs(self, stream):
        """create the .dirs file for python packages"""
        self._dirs_python(stream, 'usr/lib/site-python',
                          self.main_package_name())
        self.common_dirs(stream, raise_if_empty=False)
        self.test_dirs(stream, raise_if_empty=False)

    def manpages(self, stream):
        """create the .manpages file for python packages"""
        pkginfo = self.pkginfo
        if not pkginfo.man_files:
            raise EmptyFile()
        altmanpages = {}
        for alt in dir_filter(pkginfo.scripts):
            try:
                section = pkginfo.man_files[alt][1]
                altmanpages[alt] = 1
                stream.write('man/%s.%s\n' % (alt, section))
            except KeyError:
                continue
        for name, manpage_def in pkginfo.man_files.items():
            if not altmanpages.has_key(name):
                stream.write('%s\n' % manpage_def[0])

    def common_package_name(self):
        """return the package name for common files (data, sgml, elisp...)"""
        return self.main_package_name()

    def test_package_name(self):
        """return the package name for test files"""
        return self.main_package_name()

    
class PythonDepLibraryHandler(PythonLibraryMixIn, PythonDepStandaloneHandler):
    """package information for a package conforming to doc/standard_source_tree

    the package is a python library
    """

class PythonIndepLibraryHandler(PythonLibraryMixIn, PythonIndepStandaloneHandler):
    """package information for a package conforming to doc/standard_source_tree

    the package is a python library
    """
