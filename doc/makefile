MKHTML=mkdoc
MKHTMLOPTS=--doctype book --param toc.section.depth=2  --target html --stylesheet standard
SRC=.

TXTFILES:= $(wildcard *.txt)
XMLFILES:= $(wildcard *.xml)
TARGET := $(TXTFILES:.txt=.html) $(XMLFILES:.xml=.html)

all: ${TARGET}

%.html: %.txt
	${MKHTML} ${MKHTMLOPTS} $<

%.html: %.xml
	${MKHTML} ${MKHTMLOPTS} $<

apydoc:
	epydoc -o apidoc --html -v --graph all --no-private --exclude="__pkginfo__" --exclude="setup" -n "Logilab's devtools library" ../

clean:
	rm -rf apidoc
	rm -f *.html
