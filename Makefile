__VERSION__ = "0.9.11"

bump:
	bump2version --current-version $(__VERSION__) patch Makefile custom_components/easee/const.py

lint:
	black custom_components
	flake8 --ignore=E501,E231 custom_components

install_dev:
	pip install -r requirements-dev.txt
