MKHTML=mkdoc
MKHTMLOPTS=--doctype book --param toc.section.depth=2  --target html --stylesheet single-file
SRC=.

TXTFILES:= $(wildcard *.txt)
TARGET := $(TXTFILES:.txt=.html)

all: ${TARGET}

%.html: %.txt
	${MKHTML} ${MKHTMLOPTS} $<

clean:
	rm -f *.html
