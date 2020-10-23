__VERSION__ = "0.9.21"

bump:
	bump2version --allow-dirty --current-version $(__VERSION__) patch Makefile custom_components/easee/const.py

lint:
	black custom_components
	flake8 custom_components

install_dev:
	pip install -r requirements-dev.txt
