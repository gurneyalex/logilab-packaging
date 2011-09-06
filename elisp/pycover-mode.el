;;; BASED ON diff-mode.el --- A mode for viewing/editing context diffs

;; Copyright (C) 1998, 1999, 2000, 2001  Free Software Foundation, Inc.
;; Copyright (C) 2005-2008 LOGILAB S.A. (Paris, FRANCE).
;; http://www.logilab.fr/ -- mailto:contact@logilab.fr

;; Author: Stefan Monnier <monnier@cs.yale.edu>
;; Keywords: patch diff

;; GNU Emacs is free software; you can redistribute it and/or modify
;; it under the terms of the GNU General Public License as published by
;; the Free Software Foundation; either version 2, or (at your option)
;; any later version.

;; GNU Emacs is distributed in the hope that it will be useful,
;; but WITHOUT ANY WARRANTY; without even the implied warranty of
;; MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
;; GNU General Public License for more details.

;; You should have received a copy of the GNU General Public License
;; along with GNU Emacs; see the file COPYING.  If not, write to the
;; Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
;; Boston, MA 02110-1301 USA

;; Code:

(eval-when-compile (require 'cl))


(defgroup pycover-mode ()
  "Major mode for viewing/editing pycovers"
  :version "21.1"
  :group 'tools
  :group 'pycover)

(defcustom pycover-default-read-only t
  "If non-nil, `pycover-mode' buffers default to being read-only."
  :type 'boolean
  :group 'pycover-mode)

(defcustom pycover-jump-to-old-file nil
  "*Non-nil means `pycover-goto-source' jumps to the old file.
Else, it jumps to the new file."
  :group 'pycover-mode
  :type '(boolean))


(defvar pycover-mode-hook nil
  "Run after setting up the `pycover-mode' major mode.")

(defvar pycover-outline-regexp
  "\\([*+][*+][*+] [^0-9]\\|@@ ...\\|\\*\\*\\* [0-9].\\|--- [0-9]..\\)")

;;;;
;;;; keymap, menu, ...
;;;;

(easy-mmode-defmap pycover-mode-shared-map
  '(
    ("K" . diff-file-kill)
    ;; From compilation-minor-mode.
    ("}" . diff-file-next)
    ("{" . diff-file-prev)
    ("\C-m" . pycover-goto-source)
    ([mouse-2] . pycover-mouse-goto-source)
    ("o" . pycover-goto-source)		;other-window
    (" " . scroll-up)
    ("\177" . scroll-down)
    ;; Our very own bindings.
    ("r" . pycover-restrict-view)
    ("R" . pycover-reverse-direction))
  "Basic keymap for `pycover-mode', bound to various prefix keys.")

(easy-mmode-defmap pycover-mode-map
  `(("\e" . ,pycover-mode-shared-map)
    ;; From compilation-minor-mode.
    ("\C-c\C-c" . pycover-goto-source)
    ;; Misc operations.
    ("\C-c\C-s" . pycover-split-hunk))
  "Keymap for `pycover-mode'.  See also `pycover-mode-shared-map'.")

(easy-menu-define pycover-mode-menu pycover-mode-map
  "Menu for `pycover-mode'."
  '("Pycover"
    ["Jump to Source"		pycover-goto-source	t]
    ["-----" nil nil]
    ["Reverse direction"	pycover-reverse-direction	t]
    ;;["Fixup Headers"		diff-fixup-modifs	(not buffer-read-only)]
    ))

(defcustom pycover-minor-mode-prefix "\C-c="
  "Prefix key for `pycover-minor-mode' commands."
  :group 'pycover-mode
  :type '(choice (string "\e") (string "C-c=") string))

(easy-mmode-defmap pycover-minor-mode-map
  `((,pycover-minor-mode-prefix . ,pycover-mode-shared-map))
  "Keymap for `pycover-minor-mode'.  See also `pycover-mode-shared-map'.")


;;;;
;;;; font-lock support
;;;;
(defface pycover-changed-face
  '((((type tty pc) (class color) (background light))
     (:foreground "magenta" :bold t :italic t))
    (((type tty pc) (class color) (background dark))
     (:foreground "yellow" :bold t :italic t))
    (t ()))
  "`pycover-mode' face used to highlight changed lines."
  :group 'pycover-mode)
(defvar pycover-changed-face 'pycover-changed-face)


(defface pycover-skipped-face
  '((t (:italic t :foreground "dark grey")))
  "`pycover-mode' face used to highlight skipped lines. (e.g comments)"
  :group 'pycover-mode)
(defvar pycover-skipped-face 'pycover-skipped-face)


;; FIXME I can't make this face work properly
(defface pycover-tested-face
  ;; '((t (:inherit pycover-changed-face)))
  '((t (:foreground "dark green" :bold t)))
  "`pycover-mode' face used to highlight tested lines."
  :group 'pycover-mode)
(defvar pycover-tested-face 'pycover-tested-face)
;; (set-face-foreground 'pycover-tested-face "green")

(defface pycover-untested-face
  ;; '((t (:inherit pycover-changed-face)))
  '((t (:foreground "red" :bold t)))
  "`pycover-mode' face used to highlight untested lines."
  :group 'pycover-mode)
(defvar pycover-untested-face 'pycover-untested-face)

;; (set-face-foreground 'pycover-untested-face "red")


(defvar pycover-font-lock-keywords
  '(("^\\!.*\n" . pycover-untested-face)
    ("^>.*\n" . pycover-tested-face)
    ("^[^>!]*\n" . pycover-skipped-face)))

(defconst pycover-font-lock-defaults
  '(pycover-font-lock-keywords t nil nil nil (font-lock-multiline . nil)))

;;;;
;;;; Movement
;;;;


;; (defun diff-beginning-of-file ()
;;   (beginning-of-line)
;;   (unless (looking-at diff-file-header-re)
;;     (forward-line 2)
;;     (condition-case ()
;; 	(re-search-backward diff-file-header-re)
;;       (error (error "Can't find the beginning of the file")))))

;; (defun diff-end-of-file ()
;;   (re-search-forward "^[-+#!<>0-9@* \\]" nil t)
;;   (re-search-forward "^[^-+#!<>0-9@* \\]" nil 'move)
;;   (beginning-of-line));


(defun pycover-count-matches (re start end)
  (save-excursion
    (let ((n 0))
      (goto-char start)
      (while (re-search-forward re end t) (incf n))
      n)))


;;;;
;;;; jump to other buffers
;;;;

(defun pycover-mouse-goto-source (event)
  "Run `pycover-goto-source' for the diff at a mouse click."
  (interactive "e")
  (save-excursion
    (mouse-set-point event)
    (message "Not implemented yed")
    (pycover-goto-source)))


;;;; 
;;;; Conversion functions

;;;###autoload
(define-derived-mode pycover-mode fundamental-mode "Diff"
  "Major mode for viewing pycover files."
  (set (make-local-variable 'font-lock-defaults) pycover-font-lock-defaults)
  (set (make-local-variable 'outline-regexp) pycover-outline-regexp)
  ;;(set (make-local-variable 'imenu-generic-expression)
  ;; pycover-imenu-generic-expression)


  (when (and (> (point-max) (point-min)) pycover-default-read-only)
    (toggle-read-only t))
  ;; Neat trick from Dave Love to add more bindings in read-only mode:
  (add-to-list (make-local-variable 'minor-mode-overriding-map-alist)
  	       (cons 'buffer-read-only pycover-mode-shared-map))
  )

;;;###autoload
;; (define-minor-mode pycover-minor-mode
;;   "Minor mode for viewing/editing context diffs.
;; \\{pycover-minor-mode-map}"
;;   nil " Diff" nil
;;   ;; FIXME: setup font-lock
;;   ;; setup change hooks
;;   (if (not pycover-update-on-the-fly)
;;       (add-hook 'write-contents-hooks 'pycover-write-contents-hooks)
;;     (make-local-variable 'pycover-unhandled-changes)
;;     (add-hook 'after-change-functions 'pycover-after-change-function nil t)
;;     (add-hook 'post-command-hook 'pycover-post-command-hook nil t)))



;; (defsubst pycover-xor (a b) (if a (not b) b))

(defun pycover-goto-source (&optional other-file)
  "Jump to the corresponding source line.
`pycover-jump-to-old-file' (or its opposite if the OTHER-FILE prefix arg
is given) determines whether to jump to the old or the new file.
If the prefix arg is bigger than 8 (for example with \\[universal-argument] \\[universal-argument])
  then `pycover-jump-to-old-file' is also set, for the next invocations."
  (interactive "P")
  ;; When pointing at a removal line, we probably want to jump to
  ;; the old location, and else to the new (i.e. as if reverting).
  ;; This is a convenient detail when using smerge-diff.
  (message "Not Implemented Yet !")
  )
(add-to-list 'auto-mode-alist '(",cover$" . pycover-mode))

;; provide the package
(provide 'pycover-mode)

