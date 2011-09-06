;; Copyright (c) 2000-2008 LOGILAB S.A. (Paris, FRANCE).
;; http://www.logilab.fr/ -- mailto:contact@logilab.fr

;; Provides:
;;
;;  insert-date :
;;      insert today's date under the cursor
;;  insert-warning :
;;      insert warnings under the cursor
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
51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA.
"))


(defun lglb-copyright ()
  "insert the Logilab's copyright under the cursor"
  (interactive)
  (insert "Copyright (c) " (format-time-string "%Y") " LOGILAB S.A. (Paris, FRANCE).
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

;; add default modes for tac (twisted) and old python files ;;;;;;;;;;;;;;;;;;;
(setq auto-mode-alist
      (append '(("\\.py.old$"  . python-mode)
                ("\\.tac$"  . python-mode)
                ) auto-mode-alist))

;; buffer / paragraph indentation ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
(defun buffer-indent()
  "Indente l'ensemble du buffer courant."
  (interactive)
  ;; (normal-mode)
  (save-excursion
    (mark-whole-buffer)
    (call-interactively 'indent-region)
    (save-buffer))
  
  (message "%s" "Buffer indentation completed"))

(defun para-indent()
  "Indente l'ensemble du paragraphe."
  (interactive)
  ;; (normal-mode)
  (save-excursion
    (mark-paragraph)
    (call-interactively 'indent-region)
    (save-buffer))
  (message "%s" "Paragraph indentation completed"))

; (global-set-key [(shift f9)] 'buffer-indent)
; (global-set-key [(shift f8)] 'para-indent)


;; use C style indentation for CSS ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
(defun my-css-hook ()
  (setq cssm-indent-function 'cssm-c-style-indenter)
  (local-set-key [(C-tab)] 'cssm-complete-property)
  )

(add-hook 'css-mode-hook 'my-css-hook)

; (global-set-key [(meta shift i)] 'string-rectangle)
; (global-set-key [(meta shift d)] 'delete-rectangle)
