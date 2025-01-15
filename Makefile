__VERSION__ = "0.9.67"

old_bump:
	bump2version --allow-dirty --current-version $(__VERSION__) patch Makefile custom_components/easee/const.py custom_components/easee/manifest.json

lint:
	ruff check custom_components --fix

install_dev:
	pip install -r requirements-dev.txt

bump:
	bumpver update --patch --no-fetch

bump_minor:
	bumpver update minor --no-fetch

bump_major:
	bumpver update major --no-fetch

bump_dev:
	bumpver update --no-fetch --patch --tag=dev --tag-num

bump_beta:
	bumpver update --no-fetch --patch --tag=beta --tag-num

bump_next_pre:
	bumpver update --no-fetch --tag-num

bump_final:
	bumpver update --no-fetch --tag=final
