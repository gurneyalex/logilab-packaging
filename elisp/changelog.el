(require 'add-log)

(defun my-change-log-mode-hook ()
    (pymacs-load "changelog")
    (setq fill-column 80)
    (setq change-log-font-lock-keywords
	  '(;;
	    ;; Date
	    ("^[0-9-]+"
	     (0 'change-log-date-face))
	    ;; Version number.
	    ("\\([0-9]+\.[0-9.]+\\)"
	     (1 'change-log-file-face))
	    ;; entry
	    ("^    \\(\*\\)"
	     (1 'change-log-list-face)
	     ("^      \\(.*\\)" nil nil (1 'change-log-list-face)))
	    ;; title
	    ("^\\([^ ].*\\)" (1 'change-log-acknowledgement-face)))
	  ))

(add-hook 'change-log-mode-hook 'my-change-log-mode-hook)

(setq revert-without-query (list "ChangeLog"))

(defun add-change-log-entry (&optional whoami file-name other-window new-entry)
  (let* ((defun (add-log-current-defun))
	 (version (and change-log-version-info-enabled
		       (change-log-version-number-search)))
	 (buf-file-name (if add-log-buffer-file-name-function
			    (funcall add-log-buffer-file-name-function)
			  buffer-file-name))
	 (buffer-file (if buf-file-name (expand-file-name buf-file-name)))
	 (file-name (expand-file-name
		     (or file-name (find-change-log file-name buffer-file))))
	 ;; Set ENTRY to the file name to use in the new entry.
	 (entry (add-log-file-name buffer-file file-name))
	 bound)
    (pymacs-load "changelog")
    (changelog-changelog-add file-name (if new-entry new-entry "") 1)
    ; open changelog in a buffer if necessary
    (if (or (and other-window (not (equal file-name buffer-file-name)))
	    (window-dedicated-p (selected-window)))
	(find-file-other-window file-name)
      (find-file file-name))
    (or (eq major-mode 'change-log-mode)
	(change-log-mode))
    ; find position
    (goto-char (point-max))
    (search-backward (concat "    * " (if new-entry new-entry "") "
"))
    (forward-char 6)
))

