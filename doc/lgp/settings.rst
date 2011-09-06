Settings
========

Debian and Ubuntu sources.list management
-----------------------------------------

In some situations, we want to add extra sources.list entries to the chroot.
For example, you want to use acceptance repositories when you build some binary packages.
So, some (build-)dependencies can be found easily.

Lgp can use sources.list template files with simple scheme to add extra repos.

/etc/lgp/sources.list.debian:
    for generic Debian distribution

/etc/lgp/sources.list.debian.${DIST}:
    specific file for the Debian ${DIST} distribution

/etc/lgp/sources.list.ubuntu:
    for generic Ubuntu distribution

/etc/lgp/sources.list.ubuntu.${DIST}:
    specific file for the Ubuntu ${DIST} distribution

Example: you can find the template used at logilab in:
    /usr/share/doc/logilab-packaging/examples/sources.list.debian

::

    # Logilab acceptance repository (http://www.logilab.org/card/LogilabDebianRepository)
    #deb http://download.logilab.org/acceptance ${DIST}/

As you can see, you can use the ${DIST} variable in the template files
instead of a fixed codename. It will be substitued automatically by lgp when
creating or updating an image (chroot).

The entries found by lgp will be aggregated in the /etc/apt/sources.list/lgp.list
file into the chroot. This action is performed by the `E00lgpmirrors` hook.

