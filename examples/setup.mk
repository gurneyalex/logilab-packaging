NAME:=$(shell basename $(shell pwd))
#NAME:=$(shell sed -ne 's/^Source: \(.*\)/\1/p' debian/control | tr -d '\n')
VERSION=0.0.1
DIST_DIR=~/dist
EXCLUDE_FILES=-X "./debian" -X ".hg*" -X "setup.mk"

ARCHIVE_FORMAT=tgz
TAG=tip


default:
	@echo "Name: $(NAME)"
	@echo "Version: $(VERSION)"

changelog:
	#

dist-gzip: changelog
	@mkdir -p ${DIST_DIR}
	hg archive -t ${TAG} ${EXCLUDE_FILES} -t ${ARCHIVE_FORMAT} ${DIST_DIR}/${NAME}-${VERSION}.tar.gz

clean:
	#hg clean
