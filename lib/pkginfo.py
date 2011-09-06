# Copyright (c) 2003 Sylvain Thenault (thenault@gmail.com)
# Copyright (c) 2003-2010 Logilab (contact@logilab.fr)
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
# 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.
"""handle package information contained in the __pkginfo__.py file and / or
deduced from the package content.
"""

import os
import re
import tempfile
import shutil
from urllib2 import urlopen, HTTPError
from os.path import join, split, exists
from imp import find_module, load_module
from commands import getstatusoutput
from time import time, localtime
from stat import S_IWRITE

from logilab.common.fileutils import lines, ensure_fs_mode
from logilab.common.shellutils import find
from logilab.common.deprecation import deprecated

import logilab.devtools
from logilab.devtools.lib import TextReporter
from logilab.devtools.lib.utils import SGMLCatalog, get_scripts, glob_match
from logilab.devtools import BASE_EXCLUDE

try:
    from scriptfoundry.snakespell import iSpell
    def spell_check(text, dictionary='american', ignore=()):
        """spell the given text and return a list of possibly misspelled words
        """
        spell = iSpell('-d %s' % dictionary)
        spell.check(text)
        words = [mistake.getWord() for mistake in spell.getMistakes()]
        return [w for w in words if not w.lower() in ignore]
except:
    def spell_check(text, dictionary=None, ignore=()):
        """spell the given text and return a list of possibly misspelled words
        """
        return []

TEMPLATE_DIR = join(logilab.devtools.__path__[0], 'templates')

STD_DOCS = ('README', 'README.txt', 'ChangeLog',
            'TODO', 'TODO.txt',
            'INSTALL', 'INSTALL.txt')
SPEC_FILES = ('MANIFEST.in', 'setup.py', 'setup.cfg',
              'AUTHORS', 'DEPENDS', 'RECOMMENDS', 'SUGGESTS') + STD_DOCS
SPEC_DIRS = ('doc', 'docs', 'bin', 'dtd', 'elisp', 'examples', 'man', 'xsl')


_LICENSES_FILE = {}
_LICENSES_TEXT = {}

def get_known_licenses():
    """get identifier for licenses defined in a special resource directory"""
    # FIXME load additional licences and their content from a directory (or a list of
    # directory given by an environment variable
    if _LICENSES_FILE:
        result = _LICENSES_FILE.keys()
    else:
        result = []
        licenses_dir = join(TEMPLATE_DIR, 'licenses')
        for license_file in os.listdir(licenses_dir):
            if license_file.endswith('.txt') and not license_file.startswith('full'):
                assert os.path.isfile(os.path.join(licenses_dir, 'full_'+license_file)), "No full text available for %s"%license_file
                license_id = license_file[:-4].upper()
                result.append(license_id)
                _LICENSES_FILE[license_id] = join(licenses_dir, license_file)
    result.sort()
    return result

# write pkg info file #########################################################

def pkginfo_save(pkginfo, modifs):
    """save modifications in the <modifs> dictionary to a __pkginfo__ file
    (path given by the <pkginfo> string)
    """
    tmpfile = tempfile.mktemp()
    stream = open(tmpfile, 'w')
    try:
        # replace existants values
        for line in open(pkginfo, 'r'):
            key = line.split('=')[0].strip()
            # FIXME: multilines value
            if modifs.has_key(key):
                if modifs[key] is not None:
                    stream.write('%s = %r\n' % (key, modifs[key]))
                del modifs[key]
            else:
                stream.write(line)
        # add missing  values
        for key, value in modifs.items():
            stream.write('%s = %r\n' % (key, value))
        stream.close()
        ensure_fs_mode(pkginfo, S_IWRITE)
        # FIXME: fix perms if necessary
        shutil.move(tmpfile, pkginfo)
    except:
        os.remove(tmpfile)
        raise

# try to get correct / default values pkg info fields #########################

def get_license_text(license_id):
    """return the text of the license with the given identifier (gpl, zpl...)
    """
    license_id = license_id.upper()
    try:
        return _LICENSES_TEXT[license_id]
    except KeyError:
        if not _LICENSES_FILE:
            get_known_licenses()
        license_text = open(_LICENSES_FILE[license_id]).read()
        _LICENSES_TEXT[license_id] = license_text
        return license_text

def get_default_scripts(pkginfo):
    """return a list of executable scripts"""
    return get_scripts(pkginfo.base_directory, include_bat=0)

def get_default_elisp_files(pkginfo):
    """return elisp files if found"""
    return glob_match('elisp/*.el', pkginfo.base_directory)

def get_default_elisp_startup(pkginfo):
    """return elisp startup files if it exists"""
    elisp_startup = join('elisp', 'startup')
    if exists(join(pkginfo.base_directory, elisp_startup)):
        return elisp_startup
    else:
        return None

def get_default_dtd_files(pkginfo):
    """return dtd files if found"""
    return glob_match('dtd/*.dtd', pkginfo.base_directory)

def get_default_catalog(pkginfo):
    """return path of the sgml catalog if it exists"""
    catalog = join(pkginfo.base_directory, 'dtd', 'catalog')
    return exists(catalog) and join('dtd', 'catalog') or None

def get_default_xslt_files(pkginfo):
    """return xsl files if found"""
    result = glob_match(join('xsl', '*.xsl'), pkginfo.base_directory)
    result += glob_match(join('xsl', '*.xslt'), pkginfo.base_directory)
    return result

def get_default_man_files(pkginfo):
    """return a dictionary of man pages
    FIXME: revoir structure dictionaire !
    """
    result = {}
    try:
        for fname in os.listdir(join(pkginfo.base_directory, 'man')):
            if fname[-2:] in ('.1', '.2', '.3', '.4', '.5',
                          '.6', '.7', '.8', '.9'):
                result[fname[:-2]] = (join('man', fname), fname[-1])
    except OSError:
        pass
    return result

def get_default_license_text(pkginfo):
    """return the default license text
    It may have be set by the license hook
    """
    if hasattr(pkginfo, 'license_text'):
        return pkginfo.license_text
    return

def get_default_depends(pkginfo):
    """return the lines in the DEPENDS file if it exists, else an empty list
    """
    return _get_lines(pkginfo, 'DEPENDS')

def get_default_recommends(pkginfo):
    """return the lines in the RECOMMENDS file if it exists, else an empty list
    """
    return _get_lines(pkginfo, 'RECOMMENDS')

def get_default_suggests(pkginfo):
    """return the lines in the SUGGESTS file if it exists, else an empty list
    """
    return _get_lines(pkginfo, 'SUGGESTS')

def get_default_arch_dep(pkginfo):
    return pkginfo.ext_modules and True or False

def get_default_handler(pkginfo):
    """return the default debian handler (python-standalone if there is some
    scripts detected, else, python-library
    """
    archdep = pkginfo.architecture_dependent and 'dep' or 'indep'
    if pkginfo.scripts:
        return 'python-%s-standalone' % archdep
    return 'python-%s-library' % archdep

def get_default_documentation(pkginfo):
    """search documentation files not in html format"""
    return _get_files(pkginfo, ('doc', 'docs',),
                      exclude_exts=('.html', '.htm', '.css', '.png', '.gif'),
                      exclude_dirs=('html',))

def get_default_html_documentation(pkginfo):
    """search documentation files in html format"""
    for directory in ('doc', 'docs'):
        html_doc_dir = join(directory, 'html')
        if exists(join(pkginfo.base_directory, html_doc_dir)):
            return [join(html_doc_dir, '*')]
    return _get_files(pkginfo, ('doc', 'docs',),
                      include_exts=('.html', '.htm', '.css', '.png', '.gif'))

def get_default_examples_dir(pkginfo):
    """search a directory containing examples"""
    if exists(join(pkginfo.base_directory, 'examples')):
        return 'examples'
    else:
        return None

def get_default_test_dir(pkginfo):
    """search a directory containing tests"""
    dirname = pkginfo.base_directory
    for test_dir_name in ('test', 'tests'):
        if exists(join(dirname, test_dir_name)):
            return test_dir_name
    return None

def _get_lines(pkginfo, fname):
    """return the lines in the given file (relatvie to the package's base dir)
    if it exists, else an empty list
    """
    filename = join(pkginfo.base_directory, fname)
    if exists(filename):
        return lines(filename, '#')
    return []

def _get_files(pkginfo, directories, include_exts=(), exclude_exts=None,
               exclude_dirs=()):
    """return files matching or excluding a set of extensions, in the first
    existing directory
    """
    cwd = os.getcwd()
    os.chdir(pkginfo.base_directory)
    exclude_dirs += BASE_EXCLUDE
    try:
        for directory in directories:
            if exists(directory):
                return find(directory,
                            include_exts,
                            exclude_exts,
                            exclude_dirs)
        return []
    finally:
        os.chdir(cwd)

# package info fields definition ##############################################

PKGINFO = (
    ('Base information', (
        {'name': 'modname',
         'required': True,
         'help' : 'main (python) package name.'},
        {'name': 'distname',
         'help' : 'The distribution name, if different from the main package name.',
         'required': True,
         'default': None},
        {'name': 'numversion' ,
         'help' : 'version number as a tuple or list (usually a 3-uple).'},
        {'name': 'version' ,
         'required': True,
         'help' : 'version number, as a string.'},
        {'name': 'copyright' ,
         'help' : 'copyright notice.'},
        {'name': 'short_desc',
         'help': "'short_desc' must be renamed to new pkginfo 'description' attribute",
         'deprecated': True},
        {'name': 'long_desc',
         'help' : 'a long description.',
         'default': None},
        {'name': 'description',
         # FIXME disabled during package transition
         #'required': True,
         'help' : 'a one line description. It should : be less than 80 '
                  'characters, not contain the package name, start with '
                  'a minus letter and not end with a full stop.'},
        {'name': 'author',
         'required': True,
         'help' : 'package author name.'},
        {'name': 'author_email',
         'required': True,
         'help' : 'package author contact email.'},
        {'name': 'web',
         'required': True,
         'help' : 'package home page.'},
        {'name': 'ftp',
         'default' : None,
         'help' : 'package download page or ftp site.'},
        {'name': 'mailinglist',
         'default' : None,
         'help' : 'package mailing list address.'},
    )),
    ('Packaging', (
        {'name': 'subpackage_of',
         'default' : None,
         'help' : 'if the package is a subpackage, this variable handles the '
                  'primary level package name. For instance, "logilab" '
                  'subpackages should set this variable to "logilab".'},
        {'name': 'subpackage_master',
         'default' : False,
         'help' : 'if the package is a subpackage, this variable tells if this '
                  'package handles the subpackage\'s __init__ file.'},
        {'name': 'include_dirs',
         'default' : (),
         'help' : 'list of data directories to install _with_ the library. '
                  'This usually contains test data.'},
        {'name': 'scripts',
         'default' : get_default_scripts,
         'help' : 'list of executable scripts (look at the distutils setup '
                  'arguments documentation for more information).'},
        {'name': 'data_files',
         'default' : (),
         'help' : 'list of data files (look at the distutils setup arguments '
                  'documentation for more information).'},
        {'name': 'ext_modules',
         'default' : None,
         'help' : 'list of distutils Extension instances for Python C/C++ '
                  'extensions (look at the distutils setup arguments '
                  'documentation for more information.)'},
        {'name': 'license',
         'required': True,
         'default' : None,
         'help' : 'distribution license (GPL, LGPL, ZPL...).'},
        {'name': 'license_text',
         'default' : get_default_license_text,
         'help' : 'distribution license terms. You should not set it if you '
                  'have specified a known license with the "license" attribute.'
                  'Otherwise, you must set this variable.'},
        {'name': 'licence',
         'help': "'licence' must be renamed to 'license'",
         'deprecated': True},
        {'name': 'pyversions',
         'default' : ('2.5', '2.6'),
         'help' : 'list of supported Python versions'},
    )),
    ('Debian packaging', (
        {'name': 'debian_name',
         'default' : None,
         'help' : 'name of the debian package, if different from the package\'s name.'},
        {'name': 'debian_maintainer',
         'default' : None,
         'help' : 'debian maintainer, if different from the upstream author.'},
        {'name': 'debian_maintainer_email',
         'default' : None,
         'help' : 'debian maintainer email address, if different from the '
                  'upstream author email.'},
        {'name': 'debian_uploader',
         'default' : None,
         'help' : 'debian uploader, if different from the debian maintainer.'},
        {'name': 'architecture_dependent',
         'default' : get_default_arch_dep,
         'help' : 'flag indicating if the package is architecture dependent. '
                  'If not specified, this value will be guessed according to '
                  'the value of the "ext_modules" variable.'},
        {'name': 'test_directory',
         'default' : get_default_test_dir,
         'help' : 'Directory containing tests for the package. If not specified, '
                  'this value will be set to "test" or "tests" if one of those '
                  'directories exists.'
        },
        {'name': 'elisp_files',
         'default' : get_default_elisp_files,
         'help' : 'list of Emacs Lisp files. If not specified, this value will be '
                  'guessed according to the content of the optional "elisp" directory.'},
        {'name': 'elisp_startup',
         'default' : get_default_elisp_startup,
         'help' : 'elisp startup file. If not specified, this value will be '
                  'set to "elisp/startup" if it exists.'},
        {'name': 'dtd_files',
         'default' : get_default_dtd_files,
         'help' : 'list of DTD files. If not specified, this value will be '
                  'guessed according to the content of the optional "dtd" directory.'},
        {'name': 'catalog',
         'default' : get_default_catalog,
         'help' : 'SGML catalog path. If not specified, this value will be '
                  'set to "dtd/catalog" if it exists.'},
        {'name': 'xslt_files',
         'default' : get_default_xslt_files,
         'help' : 'list of XSLT files. If not specified, this value will be '
                  'guessed according to the content of the optional "xsl" directory.'},
        {'name': 'examples_directory',
         'default' : get_default_examples_dir,
         'help' : 'path of the directory containing examples files. If not '
                  'specified, this value will be set to "examples" if it exists'},
        {'name': 'doc_files',
         'default' : get_default_documentation,
         'help' : 'list of documentation files. If not specified, this value '
                  'will be set to according to the content of "doc" or "docs" '
                  'directories, if one of those exists. Note html documentation'
                  'should not be included here but in html_doc_files'},
        {'name': 'html_doc_files',
         'default' : get_default_html_documentation,
         'help' : 'list of documentation files in HTML format. If not '
                  'specified, this value will be set to according to the '
                  'content of "doc" or "docs" directories, if one of those exists.'},
        {'name': 'man_files',
         'default' : get_default_man_files,
         'help' : 'dictionary of man page files. If not specified, this value '
                  'will be guessed according to the content of the optional '
                  '"man" directory.'},
        {'name': 'depends',
         'default' : get_default_depends,
         'help' : 'packages dependencies. If not specified, this value will be '
                  'guessed according to the content of the optional "DEPENDS" file.'},
        {'name': 'recommends',
         'default' : get_default_recommends,
         'help' : 'recommended additional packages. If not specified, this '
                  'value will be guessed according to the content of the '
                  'optional "RECOMMENDS" file.'},
        {'name': 'suggests',
         'default' : get_default_suggests,
         'help' : 'suggested additional packages. If not specified, this value '
                  'will be guessed according to the content of the optional '
                  '"SUGGESTS" file.'},
        {'name': 'debian_handler',
         'default' : get_default_handler,
         'help' : 'Name of the debian package handler (python-library, '
                  'python-standalone, zope).'},
    )),
   )

PKGINFO_ATTRIBUTES = {}
for cat_name, cat_def_ in PKGINFO:
    for option_def in cat_def_:
        PKGINFO_ATTRIBUTES[option_def['name']] = option_def


class PackageInfo:
    """a class to handle package information :

    read user specified values and provide missing fields when guessable
    """

    def __init__(self, reporter=TextReporter(), directory=None,
                 info_module='__pkginfo__', init=1):
        self.reporter = reporter
        if directory:
            self.base_directory = directory
        else:
            self.base_directory = os.getcwd()
        self.info_module = info_module
        # make pylint happy be adding some default member attributes
        self.name = None
        self.version = None
        self.author = None
        self.author_email = None
        self.debian_name = None
        self.debian_maintainer = None
        self.debian_maintainer_email = None
        self.debian_uploader = None
        self.debian_handler = None
        self.architecture_dependent = None
        self.std_docs = None
        self.ext_modules = None
        self.prepare = None
        # initialize if necessary
        if init:
            self.init_from_module()
            self.initialization_end()

    def setattr(self, name, value):
        """set attribute <name> to <value>
        """
        if name == 'numversion':
            setattr(self, 'version', '.'.join([str(word) for word in value]))
        elif name == 'version':
            setattr(self, 'numversion', value.split('.'))
        elif name == 'license' and value is not None:
            try:
                self.setattr('license_text', get_license_text(value))
            except KeyError:
                msg = 'unknown license %s' % value
                self.setattr('license_text', '')
                self.reporter.warning(self.info_module, None, msg)
        elif name == 'short_desc':
            name = 'description'
        setattr(self, name, value)

    def init_from_module(self):
        """retreive pkg information from a config file and by inspecting the
        package structure
        """
        # get upstream package information for its config_module file
        imod = self.info_module
        mp_file, mp_filename, mp_desc = find_module(imod, [self.base_directory])
        info_module = load_module(imod, mp_file, mp_filename, mp_desc)
        status = 1
        for cat, cat_def in PKGINFO:
            for opt_def in cat_def:
                opt_name = opt_def['name']
                try:
                    value = getattr(info_module, opt_name)
                    self.setattr(opt_name, value)
                    if opt_def.has_key('deprecated') and opt_def.has_key('help'):
                        msg = "deprecated attribute '%s' (%s: %s)"
                        msg = msg  % (opt_name, cat, opt_def['help'])
                        config_module = imod + '.py'
                        self.reporter.warning(config_module, None, msg)
                except AttributeError:
                    if opt_def.has_key('default'):
                        value = opt_def.get('default')
                        if callable(value):
                            value = value(self)
                        self.setattr(opt_name, value)
                    if opt_def.has_key('required') and opt_def['required']:
                        msg = "missing required attribute '%s' (%s: %s)"
                        msg = msg  % (opt_name, cat, opt_def['help'])
                        config_module = imod + '.py'
                        self.reporter.error(config_module, None, msg)
                        status = 0
        # override prepare function ?
        if hasattr(info_module, 'prepare'):
            self.prepare = info_module.prepare
        return status

    def initialization_end(self):
        """notify the end of the initialization procedure"""
        # fix some info
        if not self.name:
            self.name = self.modname
        if not self.debian_name:
            if self.subpackage_of and not self.name.startswith(self.subpackage_of):
                self.debian_name = '%s-%s' % (self.subpackage_of,
                                              self.name.lower())
            else:
                self.debian_name = self.name.lower()
        if not self.debian_maintainer:
            self.debian_maintainer = self.author
        if not self.debian_maintainer_email:
            self.debian_maintainer_email = self.author_email
        # standard doc files
        self.std_docs = []
        for doc in STD_DOCS:
            if exists(join(self.base_directory, doc)):
                self.std_docs.append(doc)

    @deprecated
    def release_tag(self, version=None, branch=0):
        """return the release tag for the given or current version
        """
        if version is None:
            version = self.version
        version = version.replace('.', '_')
        if branch:
            return '%s-version-%s-branch' % (self.name, version)
        else:
            return '%s-version-%s' % (self.name, version)

    @deprecated
    def debian_release_tag(self, version=None):
        """return the release tag for the given or current version
        """
        if version is None:
            version = self.debian_version()
        version = version.replace('.', '_')
        return '%s-debian-version-%s' % (self.name, version)

    @deprecated
    def debian_version(self):
        """return current debian version
        """
        cwd = os.getcwd()
        os.chdir(self.base_directory)
        try:
            status, output = getstatusoutput('dpkg-parsechangelog')
            if status != 0:
                msg = 'dpkg-parsechangelog exited with status %s' % status
                raise Exception(msg)
            for line in output.split('\n'):
                line = line.strip()
                if line and line.startswith('Version:'):
                    return line.split(' ', 1)[1].strip()
            raise Exception('Debian version not found')
        finally:
            os.chdir(cwd)

# check package info field values #############################################

COPYRIGHT_RGX = "Copyright \(c\) (?P<from>\d{4})(?:\s*-\s*(?P<to>\d+))? LOGILAB S\.A\. \(Paris, FRANCE\), all rights reserved\."
COPYRIGHT_RGX = re.compile(COPYRIGHT_RGX)

def check_url(reporter, file, var, url):
    """Check that the given url exists by trying to open it
    """
    if url is None:
        return
    if not url:
        msg = 'no %s variable specified' % var
        reporter.warning(file, None, msg)
        return
    try:
        urlopen(url)
    except HTTPError, ex:
        msg = '%s on %s=%r' % (ex, var, url)
        reporter.warning(file, None, msg)
    except Exception, ex:
        msg = '%s on %s=%r' % (ex, var, url)
        reporter.error(file, None, msg)

def check_info_module(reporter, dirname=None, info_module='__pkginfo__'):
    """ checking package information module and source tree structure """
    if dirname is None:
        dirname = os.getcwd()
    absfile = join(dirname, info_module + '.py')
    try:
        mp_file, mp_filename, mp_desc = find_module(info_module,
                                                    [dirname])
        module = load_module(info_module, mp_file, mp_filename, mp_desc)
    except Exception, ex:
        reporter.error(absfile, None, str(ex))
        return 0

    # this will check for missing required attribute
    pi = PackageInfo(reporter, dirname, info_module, init=0)
    status = pi.init_from_module()
    pi.initialization_end()

    # check scripts
    detected_scripts = get_default_scripts(pi)
    scripts = getattr(module, 'scripts', []) or []
    if not sequence_equal(detected_scripts, scripts):
        msg = 'detected %r as default "scripts" value, found %r'
        reporter.warning(absfile, None, msg % (detected_scripts, scripts))

    # check license
    if not (getattr(module, 'license', None) or
            getattr(module, 'license_text', None)):
        msg = 'no "license" nor "license_text" attribute'
        reporter.error(absfile, None, msg)
        status = 0

    # check copyright (no more mandatory)
    copyright = getattr(module, 'copyright', '')
    if copyright:
        match = COPYRIGHT_RGX.search(copyright)
        if match:
            end = match.group('to') or match.group('from')
            thisyear = localtime(time())[0]
            if int(end) < thisyear or int(end) > thisyear+1:
                msg = 'copyright is outdated (%s)' % end
                reporter.warning(absfile, None, msg)
        else:
            msg = 'copyright doesn\'t match: %s' % repr(COPYRIGHT_RGX.pattern)
            reporter.warning(absfile, None, msg)

    # check include_dirs
    if getattr(module, 'include_dirs', None):
        for directory in module.include_dirs:
            if not exists(join(dirname, directory)):
                msg = 'include inexistant directory %r' % directory
                reporter.error(absfile, None, msg)

    # check external resources (web site and ftp)
    for ext_resources in ('web', 'ftp'):
        check_url(reporter, absfile, ext_resources, getattr(pi, ext_resources))

    # check descriptions
    if not pi.description:
        msg = 'no project description given'
        reporter.error(absfile, None, msg)
    else:
        if len(pi.description) > 80:
            msg = 'short description longer than 80 characters'
            reporter.warning(absfile, None, msg)
        desc = pi.description.lower().split()
        if pi.name.lower() in desc or pi.debian_name.lower() in desc:
            msg = 'short description contains the package name'
            reporter.warning(absfile, None, msg)
        if pi.description[0].isupper():
            msg = 'short description starts with a capitalized letter'
            reporter.warning(absfile, None, msg)
        if pi.description[-1] == '.':
            msg = 'short description ends with a period'
            reporter.warning(absfile, None, msg)
        for word in spell_check(pi.description, ignore=(pi.name.lower(),)):
            msg = 'short description contains possibly mispelled word %r' % word
            reporter.warning(absfile, None, msg)

    if pi.long_desc:
        for word in spell_check(pi.long_desc, ignore=(pi.name.lower(),)):
            msg = 'long description contains possibly mispelled word %r' % word
            reporter.warning(absfile, None, msg)
        for line in pi.long_desc.splitlines():
            if len(line) > 79:
                msg = 'long description contains lines longer than 80 characters'
                reporter.warning(absfile, None, msg)

    # check python versions format
    if not hasattr(pi.pyversions, '__iter__'):
        msg = 'pyversions attribute must be iterable (found: %s)' % pi.pyversions
        reporter.error(absfile, None, msg)
        status = 0

    # standard source tree ####################################################

    # DTDs and catalog
    detected_dtds = get_default_dtd_files(pi)
    dtds = getattr(module, 'dtd_files', None)
    if dtds is not None and not sequence_equal(detected_dtds, dtds):
        msg = 'Detected %r as default "dtd_files" value, found %r'
        reporter.warning(absfile, None, msg % (detected_dtds, dtds))
    else:
        dtds = detected_dtds
    detected_catalog = get_default_catalog(pi)
    catalog = getattr(module, 'catalog', None)
    if catalog:
        if detected_catalog and catalog != detected_catalog:
            msg = 'detected %r as default "catalog" value, found %r'
            reporter.warning(absfile, None, msg % (detected_catalog,
                                                        catalog))
        elif split(catalog)[1] != 'catalog':
            msg = 'package\'s main catalog should be named "catalog" not %r'
            reporter.error(join(dirname, 'dtd'), None,
                         msg % split(catalog)[1])
            status = 0
    else:
        catalog = detected_catalog
    cats = glob_match(join('dtd', '*.cat'))
    if cats:
        msg = 'unsupported catalogs %s' % ' '.join(cats)
        reporter.warning(join(dirname, 'dtd'), None, msg)
    if dtds:
        if not catalog:
            msg = 'package provides some DTDs but no catalog'
            reporter.error(join(dirname, 'dtd'), None, msg)
            status = 0
        else:
            # check catalog's content (i.e. dtds are listed inside)
            cat = SGMLCatalog(catalog, open(join(dirname, catalog)))
            cat.check_dtds([split(dtd)[1] for dtd in dtds], reporter)

    # FIXME: examples_directory, doc_files, html_doc_files
    # FIXME: find a generic way to checks values found in config !
    return status


def sequence_equal(list1, list2):
    """return true if both sequence contains the same elements
    """
    # FIXME return set(list1) == set(list2) ?
    if type(list1) is not type([]):
        list1 = list(list1)
    if type(list2) is not type([]):
        list2 = list(list2)
    list1.sort()
    list2.sort()
    return list1 == list2
