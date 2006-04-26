;; Copyright (c) 2000-2003 LOGILAB S.A. (Paris, FRANCE).
;; http://www.logilab.fr/ -- mailto:contact@logilab.fr

;; Provides:
;;
;;  insert-date :
;;      insert today's date under the cursor
;;  insert-warning :
:			       ;      insert warnings under the cursor
;;  insert-gpl :  
;;      insert the GPL terms under the cursor
;;  insert-revision :  
;;      insert the __revision__ variable under the cursor
;;  insert-docstring :  
;;      insert a docstring under the cursor
;;
;;  lglb-copyright :  
;;      insert the Logilab's copyright under the cursor
;;  lglb-header-gpl :  
;;      insert the Logilab's standard header for GPLed files at the beginning
;;      of the current buffer
;;  lglb-header-closed :
;;      insert the Logilab's standard header for non GPLed files at the 
;;      beginning of the current buffer
;;

(defun insert-warning ()
  "insert warnings under the cursor"
  (interactive)
  (progn
    (insert "/!\\  /!\\")
    (backward-char 4))
  )


(defun insert-today-date ()
  "insert today's date under the cursor"
  (interactive)
  (insert (format-time-string "%Y/%m/%d"))
  )


(defun insert-gpl ()
  "insert the GPL terms under the cursor"
  (interactive)
  (insert "This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc.,
59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
"))


(defun lglb-copyright ()
  "insert the Logilab's copyright under the cursor"
  (interactive)
  (insert "Copyright (c) 2000-2003 LOGILAB S.A. (Paris, FRANCE).
http://www.logilab.fr/ -- mailto:contact@logilab.fr
"))


;; python specific ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
(defun logilab-python-hook ()

  (defun insert-revision ()
    "insert the __revision__ variable under the cursor"
    (interactive)
    (insert "
__revision__ = \"$Id: \
$\"\n")
    )


  (defun insert-docstring ()
    "insert a docstring under the cursor"
    (interactive)
    (progn
      (insert "\"\"\"\n")
      (save-excursion
	(insert "\n\"\"\"\n"))
      )
    )


  (defun lglb-header-gpl ()
    "insert the Logilab's standard header for GPLed files at the beginning
    of the current buffer"
    (interactive)
    (progn
      (beginning-of-buffer)
      (let 
	  ((here (point)))
	(lglb-copyright)
	(insert "\n")
	(insert-gpl)
	(comment-region here (point)))
      (insert-docstring)
      (save-excursion
	(forward-line 2)
	(insert-revision))
      )
    )


  (defun lglb-header-closed ()
    "insert the Logilab's standard header for non GPLed files at the 
   beginning of the current buffer"
    (interactive)
    (progn
      (beginning-of-buffer)
      (let 
	  ((here (point)))
	(lglb-copyright)
	(comment-region here (point)))
      (insert-docstring)
      (save-excursion
	(forward-line 2)
	(insert-revision))
      )
    )

  ;; add shortcuts in the global keymap ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
  (local-set-key "\C-cg" 'lglb-header-gpl)
  (local-set-key "\C-cc" 'lglb-header-closed)
  (local-set-key "\C-cd" 'insert-docstring)
)


;; add shortcuts in the global keymap ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
(global-set-key "\C-cw" 'insert-warning)
(global-set-key "\C-cr" 'insert-revision)
(global-set-key "\C-ct" 'insert-today-date)


;; register hooks ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
(add-hook 'python-mode-hook 'logilab-python-hook)

