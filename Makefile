.PHONY: install install-dev demo test lint doctor

install:
	python3 -m pip install -e ".[demo,preview]"

install-dev:
	python3 -m pip install -e ".[demo,preview,dev]"

demo:
	./draw demo out/cvpr_demo.pptx --png out/cvpr_demo.png --force

test:
	python3 -m pytest

lint:
	python3 -m ruff check pptdraw tests

doctor:
	./draw doctor
