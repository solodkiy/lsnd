all: USAGE SMTPHelp

USAGE: lsnd.py
	./lsnd.py --help > USAGE
SMTPHelp: lsnd.py
	./lsnd.py --smtphelp > SMTPHelp

publish: lsnd.py USAGE SMTPHelp
	cd .. && tar --exclude ".*" -czvf lsnd.tgz lsnd \
	    && scp lsnd.tgz sverige:html
	ssh sverige "cd html && tar -xzvf lsnd.tgz && mv lsnd.tgz lsnd"
	git push gitorious
