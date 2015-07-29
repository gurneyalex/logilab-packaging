#!/usr/bin/env python
# pylint: disable=W0404,W0622,W0704,W0613,W0152
# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of logilab-packaging.
#
# logilab-packaging is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option) any
# later version.
#
# logilab-packaging is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with logilab-packaging.  If not, see <http://www.gnu.org/licenses/>.
"""Generic Setup script, takes package info from __pkginfo__.py file.
"""
__docformat__ = "restructuredtext en"

from setuptools import setup, find_packages
from io import open
from os import path

here = path.abspath(path.dirname(__file__))

pkginfo = {}
with open(path.join(here, '__pkginfo__.py')) as f:
    exec(f.read(), pkginfo)

with open(path.join(here, 'README'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name=pkginfo['distname'],
    version=pkginfo['version'],
    description=pkginfo['description'],
    long_description=long_description,
    url=pkginfo['web'],
    author=pkginfo['author'],
    author_email=pkginfo['author_email'],
    license=pkginfo['license'],

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ],

    packages=find_packages(exclude=['contrib', 'docs', 'test*']),
    install_requires=pkginfo['install_requires'],
    scripts=pkginfo['scripts'],
    data_files = pkginfo['data_files'],
    namespace_packages=['logilab'],
)
