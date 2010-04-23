# Logilab lgp configuration file for pbuilder.
# Copyright (c) 2003-2009 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr

# The file in /usr/share/pbuilder/pbuilderrc is the default template.
# /etc/pbuilderrc is the one meant for editing.
#
# Read pbuilderrc.5 document for notes on specific options.

# This file is largely inspired by:
#     https://wiki.ubuntu.com/PbuilderHowto
# Thanks a lot, guys !


# Declaration of lgp suites file location
LGP_SUITES=${LGP_SUITES:-'/etc/lgp/suites'}

DEBIAN_SUITES=${DEBIAN_SUITES:-$(grep -B2 '^Keyring: debian' $LGP_SUITES | sed -n 's/\(Suite: \)//p')}
UBUNTU_SUITES=${UBUNTU_SUITES:-$(grep -B2 '^Keyring: ubuntu' $LGP_SUITES | sed -n 's/\(Suite: \)//p')}

# *** NEEDS REFACTORING ***
# FIXME Use same format with MIRRORSITE and DEBIAN_MIRRORSITE + UBUNTU_MIRRORSITE
# FIXME support of old DEBIAN_MIRROR and UBUNTU_MIRROR ?
# FIXME Manage OTHERMIRROR only by DEBIAN_SOURCESLIST settings
# FIXME rename DEBIAN_MIRROR to DEBIAN_MIRRORSITE without change it
# FIXME make a function here instead of multiple greps
# FIXME check repo availability before adding it ?
if echo "$DEBIAN_SUITES" | grep -q "^$DIST$"; then
    DEBIAN_MIRRORSITE="http://$DEBIAN_MIRROR/debian/"
    MIRRORSITE=${DEBIAN_MIRRORSITE}
    COMPONENTS=${DEBIAN_COMPONENTS}
    eval "OTHERMIRROR=\"$(grep -v '#' $DEBIAN_SOURCESLIST | tr '\n' '|')\""
    [[ -f $DEBIAN_SOURCESLIST.$DIST ]] && OTHERMIRROR=$(grep -v '#' $DEBIAN_SOURCESLIST.$DIST | tr '\n' '|')
    OTHERMIRROR=${OTHERMIRROR:-$DEBIAN_OTHERMIRROR}
elif echo "$UBUNTU_SUITES" | grep -q "^$DIST$"; then
    UBUNTU_MIRRORSITE="http://$UBUNTU_MIRROR/ubuntu/"
    MIRRORSITE=${UBUNTU_MIRRORSITE}
    COMPONENTS=${UBUNTU_COMPONENTS}
    eval "OTHERMIRROR=\"$(grep -v '#' $UBUNTU_SOURCESLIST | tr '\n' '|')\""
    [[ -f $UBUNTU_SOURCESLIST.$DIST ]] && OTHERMIRROR=$(grep -v '#' $UBUNTU_SOURCESLIST.$DIST | tr '\n' '|')
    OTHERMIRROR=${OTHERMIRROR:-$UBUNTU_OTHERMIRROR}
else
    echo "Distribution '$DIST' cannot be found in \"/etc/lgp/suites\""
    echo "Edit this file if you want create a new unlisted distribution"
    echo "This error occured in pbuilder set up"
    exit 3
fi

# *** DEPRECATED ***
# Note: files matching *_SOURCESLIST.${DIST} in the same directory can be used
#       to override generic values
# ... or set theses variables in a sources.list format (see pbuilder man page)
# They will be used in the distribution image to fetch developped packages
#DEBIAN_OTHERMIRROR=
#UBUNTU_OTHERMIRROR=

# Set a default distribution if none is used.
#: ${DIST:="$(lsb_release --short --codename)"}
#: ${DIST:="unstable"}
# Optionally use the changelog of a package to determine the suite to use if none set
# Will use generic 'unstable' distribution name
#if [ -z "${DIST}" ] && [ -r "debian/changelog" ]; then
#	DIST=$(dpkg-parsechangelog | awk '/^Distribution: / {print $2}')
#	# Use the unstable suite for Debian experimental packages.
#	if [ "${DIST}" == "experimental" -o \
#		 "${DIST}" == "UNRELEASED" -o \
#		 "${DIST}" == "DISTRIBUTION" ]; then
#		DIST="unstable"
#	fi
#	echo "Retrieve distribution from debian/changelog: $DIST"
#fi

#export DEBIAN_BUILDARCH=athlon
##############################################################################

# Don't use DISTRIBUTION directly
DISTRIBUTION="${DIST}"

# We always define an architecture to the host architecture if none set.
# Note that you can set your own default in /etc/lgp/pbuilderrc.local
# (i.e. ${ARCH:="i386"}).
: ${ARCH:="$(dpkg --print-architecture)"}
NAME="${DIST}"

DEBOOTSTRAP=${DEBOOTSTRAP:-"cdebootstrap"}

DEBOOTSTRAPOPTS=()
DEBOOTSTRAPOPTS=("--include" "sysv-rc" "${DEBOOTSTRAPOPTS[@]}")
DEBOOTSTRAPOPTS=("--include" "libc6" "${DEBOOTSTRAPOPTS[@]}")
case "${DEBOOTSTRAP}" in
	"debootstrap")
		DEBOOTSTRAPOPTS=("--variant=buildd" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--verbose" "${DEBOOTSTRAPOPTS[@]}")
		;;
	"cdebootstrap")
		DEBOOTSTRAPOPTS=("--flavour=build" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--debug" "-v" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--allow-unauthenticated" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--suite-config=${LGP_SUITES}")
		;;
esac

if [ -n "${ARCH}" ]; then
	NAME="$NAME-$ARCH"
	DEBOOTSTRAPOPTS=("--arch" "$ARCH" "${DEBOOTSTRAPOPTS[@]}")
fi
#echo "D: $DEBOOTSTRAP ${DEBOOTSTRAPOPTS[@]}"

# Don't use BASETGZ directly
# Set the BASETGZ using lgp IMAGE environment variable
: ${IMAGE:="/var/cache/lgp/buildd/$NAME.tgz"}
BASETGZ=${IMAGE}
if [ ! -d $(dirname $BASETGZ) ]; then
	echo "Error: parent directory '$(dirname $BASETGZ)' has not been fully created" >/dev/stderr
	exit 2
fi
if [ ! -r ${BASETGZ} -a "$PBCURRENTCOMMANDLINEOPERATION" != "create" ]; then
	echo "Error: pbuilder image '$BASETGZ' has not been created" >/dev/stderr
	exit 2
fi

USEPROC=yes
USEDEVPTS=yes
USEDEVFS=no

# BINDMOUNTS is a space separated list of things to mount inside the chroot.
# Don't use array aggregation here
BINDMOUNTS="/sys"
if [ "$PBCURRENTCOMMANDLINEOPERATION" == "login" -o "$PBCURRENTCOMMANDLINEOPERATION" == "scripts" ]; then
	# Default value set to be used by hooks
	export BUILDRESULT="${HOME}/dists/${DIST}"
fi
if [ -d "${BUILDRESULT}" ]; then
	BINDMOUNTS="${BINDMOUNTS} $BUILDRESULT"
fi

# FIXME pbuilder.local has not $NAME defined
#APTCACHE="/var/cache/pbuilder/$NAME/aptcache/"

#REMOVEPACKAGES="lilo bash"
REMOVEPACKAGES="lilo"
#EXTRAPACKAGES=gcc3.0-athlon-builder

# Use DEBOOTSTRAPOPTS instead ?
# "debconf: delaying package configuration, since apt-utils is not installed"
EXTRAPACKAGES="apt-utils nvi"

# command to satisfy build-dependencies; the default is an internal shell
# implementation which is relatively slow; there are two alternate
# implementations, the "experimental" implementation,
# "pbuilder-satisfydepends-experimental", which might be useful to pull
# packages from experimental or from repositories with a low APT Pin Priority,
# and the "aptitude" implementation, which will resolve build-dependencies and
# build-conflicts with aptitude which helps dealing with complex cases but does
# not support unsigned APT repositories
PBUILDERSATISFYDEPENDSCMD="/usr/lib/pbuilder/pbuilder-satisfydepends"

#Command-line option passed on to dpkg-buildpackage.
#DEBBUILDOPTS will be overriden by lgp
#PDEBUILD_PBUILDER=pbuilder
#USE_PDEBUILD_INTERNAL=yes

# pdebuild wants invoke debsign command after building
# We use pdebuild only for package debugging. Say 'no' (or commented) here.
#AUTO_DEBSIGN=no

# Hooks directory for pbuilder
# Force an alternate value of hookdir since hooks can be sensitive
HOOKDIR=${HOOKDIR:+"/var/lib/lgp/hooks"}

# APT configuration files directory
_APTCONFDIR="/etc/lgp/apt.conf.d"
if [[ -n "$(ls $_APTCONFDIR 2>/dev/null)" ]]; then
	APTCONFDIR=$_APTCONFDIR
fi

# the username and ID used by pbuilder, inside chroot. Needs fakeroot, really
#BUILDUSERID=$SUDO_UID
BUILDUSERID=1234
#BUILDUSERNAME=$SUDO_USER
BUILDUSERNAME=pbuilder
BUILDRESULTUID=$SUDO_UID

# Set the PATH I am going to use inside pbuilder
#export PATH="/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/X11R6/bin"

# SHELL variable is used inside pbuilder by commands like 'su'; and they need sane values
export SHELL="/bin/sh"

# enable pkgname-logfile
#PBUILDER_BUILD_LOGFILE="${BUILDRESULT}/"$(basename "${PACKAGENAME}" .dsc)"${PKGNAME_LOGFILE_EXTENTION}"
PKGNAME_LOGFILE_EXTENTION="_${ARCH}_${DIST}.lgp-build"
PKGNAME_LOGFILE=yes

# for pbuilder debuild
BUILDSOURCEROOTCMD="fakeroot"
PBUILDERROOTCMD="sudo"

# No debconf interaction with user by default
export DEBIAN_FRONTEND=${DEBIAN_FRONTEND:="noninteractive"}
