MKHTML=mkdoc
MKHTMLOPTS=--doctype book --param toc.section.depth=2  --target html --stylesheet single-file
SRC=.

TXTFILES:= $(wildcard *.txt)
XMLFILES:= $(wildcard *.xml)
TARGET := $(TXTFILES:.txt=.html) $(XMLFILES:.xml=.html)

all: ${TARGET}

%.html: %.txt
	${MKHTML} ${MKHTMLOPTS} $<

%.html: %.xml
	${MKHTML} ${MKHTMLOPTS} $<

clean:
	rm -f *.html
