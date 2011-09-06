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

Example
'''''''

::

    % lgp tag -t 'my-version-$version'
    I:tag: add tag to repository: my-version-0.55.2


Alias some tags
---------------

You can aliases long tags as follows in your `/etc/lgp/lgprc`::

     [TAG]
     
     # tag format examples
     upstream=$project-version-$version
     debian=$project-debian-version-$debian_version
     debian_revision=debrevision-$debian_revision
     
     # Logilab policy
     logilab=$upstream,$debian
     
     # list of tag templates to apply by default
     # '$version' is used by default if not defined
     template=$logilab


Default entry will be use when no parameter is given on command-line.
Here, the default behaviour will be to expand '$logilab' template.

For instance, with the above configuration for the `logilab-common`__ project::

     % lgp tag --verbose
     ...
     D:tag: processing... '$logilab'
     I:tag: template '$logilab' expanded to: '$upstream, $debian'
     D:tag: pending templates:
     * $upstream
     * $debian
     D:tag: processing... '$upstream'
     I:tag: template '$upstream' expanded to: '$project-version-$version'
     D:tag: pending templates:
     * $debian
     * $project-version-$version
     D:tag: processing... '$debian'
     I:tag: template '$debian' expanded to: '$project-debian-version-$debian_version'
     D:tag: pending templates:
     * $project-version-$version
     * $project-debian-version-$debian_version
     D:tag: processing... '$project-version-$version'
     D:tag: run command: hg tag logilab-common-version-0.55.2
     I:tag: add tag to repository: logilab-common-version-0.55.2
     D:tag: processing... '$project-debian-version-$debian_version'
     D:tag: run command: hg tag logilab-common-debian-version-0.55.2-1
     I:tag: add tag to repository: logilab-common-debian-version-0.55.2-1


The only benefit to have separated aliases instead of a raw config line:

    default=$project-version-$version, $project-debian-version-$debian_version

is to be able to run `lgp tag` on specific alias if need::

     % lgp tag -t '$upstream'
     I:tag: add tag to repository: logilab-common-version-0.55.2
     % lgp tag -t '$debian'
     I:tag: add tag to repository: logilab-common-debian-version-0.55.2-1



__ http://www.logilab.org/project/logilab-common
