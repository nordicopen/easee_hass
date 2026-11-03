lint:
	ruff check custom_components --fix

install_dev:
	pip install -r requirements-dev.txt

# Normal version bump
bump:
	bumpver update --patch --no-fetch

# Start beta track
bump_beta:
	bumpver update --no-fetch --patch --tag=beta --tag-num

bump_next_beta:
	bumpver update --no-fetch --tag-num

# Final release bump if beta versions have been released
bump_final:
	bumpver update --no-fetch --tag=final

# Show current version
show_version:
	bumpver show --no-fetch
