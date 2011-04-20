Tag your project
================

Template format
---------------

Lgp will be able to substitute some string format when tagging:

- $project : project name
- $version : current upstream version
- $debian_revision : current increment of the Debian version
- $debian_version : full Debian version (upstream version + $debian_revision)
- $distrib : Debian-compatible distribution name
- $arch : Debian-compatible architecture

Example
'''''''

::

    % lgp tag my-version-$version


Alias some tags
---------------

You can aliases long tags as follows in your `/etc/lgp/lgprc`::

     [LGP-TAG]
 
     # tag format examples
     upstream=$project-version-$version
     debian=$project-debian-version-$debian_version
     debian_revision=debrevision-$debian_revision
 
     # Logilab policy
     logilab=upstream, debian
 
     # list of tag templates to apply by default
     # '$version' is used by default if not defined
     default=logilab

Default entry will be use when no parameter is given on command-line.

For instance, with the above configuration for the `cubicweb-tag`__ project::

     % lgp tag --verbose
     ...
     D:tag: detected alias 'logilab' expanded to '['upstream', ' debian']'
     D:tag: detected alias 'upstream' expanded to '['$project-version-$version']'
     D:tag: detected alias 'debian' expanded to '['$project-debian-version-$debian_version']'
     D:tag: run command: hg tag cubicweb-tag-version-1.7.0
     I:tag: add tag to repository: cubicweb-tag-version-1.7.0
     D:tag: run command: hg tag cubicweb-tag-debian-version-1.7.0-1
     I:tag: add tag to repository: cubicweb-tag-debian-version-1.7.0-1
 


The only benefit to have separated aliases instead of a raw config line:

    default=$project-version-$version,$project-debian-version-$debian_version

is to be able to run `lgp tag` on specific alias if need::

     % lgp tag upstream
     I:tag: add tag to repository: cubicweb-tag-version-1.7.0
     % lgp tag debian
     I:tag: add tag to repository: cubicweb-tag-debian-version-1.7.0-1



__ https://www.cubicweb.org/project/cubicweb-tag
