# Logilab lgp configuration file for pbuilder.
# Copyright (c) 2003-2011 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# The file in /usr/share/pbuilder/pbuilderrc is the default template.
# This file /etc/lgp/pbuilderrc is related to lgp
# /etc/lgp/pbuilderrc.local is the one meant for editing.

#Command-line option passed on to dpkg-buildpackage.
#DEBBUILDOPTS will be overriden by lgp

is_pure_debian() {
	DEBSCRIPT="/usr/share/debootstrap/scripts/$1"
	test -f $DEBSCRIPT
	test "$(basename $(readlink -f $DEBSCRIPT))" = "sid"
	return $?
}

merge_lgp_sources_list() {
	SOURCESLIST=$1
	if [ -f $SOURCESLIST.$DIST ]; then
		sed "s/\${DIST}/${DIST}/g" $SOURCESLIST.$DIST
	elif [ -f $SOURCESLIST ]; then
		sed "s/\${DIST}/${DIST}/g" $SOURCESLIST
	fi
}

DEBOOTSTRAP=${DEBOOTSTRAP:-"debootstrap"}
: ${DEBOOTSTRAPOPTS:-()}
case "${DEBOOTSTRAP}" in
	"debootstrap")
		DEBOOTSTRAPOPTS=("--verbose" "${DEBOOTSTRAPOPTS[@]}")
		;;
	"cdebootstrap")
		#DEBOOTSTRAPOPTS=("--include" "sysv-rc" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--flavour=build" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--debug" "-v" "${DEBOOTSTRAPOPTS[@]}")
		DEBOOTSTRAPOPTS=("--allow-unauthenticated" "${DEBOOTSTRAPOPTS[@]}")
		;;
esac

# command to satisfy build-dependencies; the default is an internal shell
# implementation which is relatively slow; there are two alternate
# implementations, the "experimental" implementation,
# "pbuilder-satisfydepends-experimental", which might be useful to pull
# packages from experimental or from repositories with a low APT Pin Priority,
# and the "aptitude" implementation, which will resolve build-dependencies and
# build-conflicts with aptitude which helps dealing with complex cases but does
# not support unsigned APT repositories
#PBUILDERSATISFYDEPENDSCMD="/usr/lib/pbuilder/pbuilder-satisfydepends"
#PBUILDERSATISFYDEPENDSOPT=('--check-key')

if is_pure_debian $DIST; then
	MIRRORSITE=${DEBIAN_MIRRORSITE}
	COMPONENTS=${DEBIAN_COMPONENTS}
	export LGP_OTHERMIRRORS="$(merge_lgp_sources_list $DEBIAN_SOURCESLIST)"
else
	MIRRORSITE=${UBUNTU_MIRRORSITE}
	COMPONENTS=${UBUNTU_COMPONENTS}
	DEBOOTSTRAPOPTS=("${DEBOOTSTRAPOPTS[@]}" "--keyring=/usr/share/keyrings/ubuntu-archive-keyring.gpg")
	export LGP_OTHERMIRRORS="$(merge_lgp_sources_list $UBUNTU_SOURCESLIST)"
fi

# Note: don't use DISTRIBUTION directly
DISTRIBUTION="${DIST}"
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
#fi

# XXX We always define an architecture to the host architecture if none set.
# Note that you can set your own default in /etc/lgp/pbuilderrc.local
# (i.e. ${ARCH:="i386"}).
: ${ARCH:="$(dpkg --print-architecture)"}

NAME="${DIST}"

if [ "$PBCURRENTCOMMANDLINEOPERATION" = "create" -a -n "${ARCH}" ]; then
	NAME="$NAME-$ARCH"
	DEBOOTSTRAPOPTS=("--arch" "$ARCH" "${DEBOOTSTRAPOPTS[@]}")
fi

if [ "$PBCURRENTCOMMANDLINEOPERATION" = "create" -o "$PBCURRENTCOMMANDLINEOPERATION" = "update" ]; then
	echo "D: $DEBOOTSTRAP ${DEBOOTSTRAPOPTS[@]} ${DIST}"
fi

# Don't use BASETGZ directly
# XXX Set the BASETGZ using lgp IMAGE environment variable
: ${IMAGE:="/var/cache/lgp/buildd/$NAME.tgz"}
BASETGZ=${IMAGE}

USEPROC=yes
USEDEVPTS=yes
USEDEVFS=no

# Using environmental variables for running pbuilder for specific distribution
# http://www.netfort.gr.jp/~dancer/software/pbuilder-doc/pbuilder-doc.html#ENVVARDISTRIBUTIONSWITCH
APTCACHE="/var/cache/pbuilder/${DIST}/aptcache/"

# 26. Using tmpfs for buildplace ($BUILDPLACE)
# http://www.netfort.gr.jp/~dancer/software/pbuilder-doc/pbuilder-doc.html#tmpfsforpbuilder
# To improve speed of operation, it is possible to use tmpfs for pbuilder build location.
# Mount tmpfs to /var/cache/pbuilder/build, and set APTCACHEHARDLINK to no
if mountpoint $BUILDPLACE >/dev/null; then
	APTCACHEHARDLINK="no"
else
	: ${APTCACHEHARDLINK:="yes"}
fi

# BINDMOUNTS is a space separated list of things to mount inside the chroot.
BINDMOUNTS="${BINDMOUNTS} /sys /dev"

# "debconf: delaying package configuration, since apt-utils is not installed"
EXTRAPACKAGES="apt-utils"

# Hooks directory for pbuilder
# Force an alternate value of hookdir since hooks can be sensitive
HOOKDIR=${HOOKDIR:+"/var/lib/lgp/hooks"}

# APT configuration files directory
_APTCONFDIR="/etc/lgp/apt.conf.d"
if [[ -n "$(ls $_APTCONFDIR 2>/dev/null)" ]]; then
	APTCONFDIR=$_APTCONFDIR
fi

# The username and uid to be used inside chroot.
# It should ideally not collide with other uid outside the chroot
# to avoid chroot user having access to outside processes
#BUILDUSERID=$SUDO_UID
#BUILDUSERID=1234
#BUILDUSERNAME=$SUDO_USER
#BUILDUSERNAME=pbuilder
#BUILDRESULTUID=$SUDO_UID

BUILD_LOG_EXT=".lgp-build.log"
PKGNAME_LOGFILE_EXTENTION="_${ARCH}_${DIST}$BUILD_LOG_EXT"
PKGNAME_LOGFILE=yes

# No debconf interaction with user by default
export DEBIAN_FRONTEND=${DEBIAN_FRONTEND:="noninteractive"}

# Set PATH used inside pbuilder image
#export PATH="/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/X11R6/bin"
# SHELL variable is used inside pbuilder by commands like 'su'; and they need sane values
export SHELL="/bin/sh"
export TERM=linux
