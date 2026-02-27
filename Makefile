.PHONY: install run clean help

help:
	@echo "LocalManus — local agentic AI"
	@echo ""
	@echo "  make install   Install dependencies into .venv"
	@echo "  make run       Start the server (http://localhost:7860)"
	@echo "  make clean     Remove .venv and workspace sessions"

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip -q
	.venv/bin/pip install -r requirements.txt
	@echo ""
	@echo "Done. Copy .env.example to .env and edit as needed."
	@echo "Then: make run"

run:
	@if [ ! -d .venv ]; then echo "Run 'make install' first."; exit 1; fi
	.venv/bin/python3 main.py

clean:
	rm -rf .venv workspace/__* workspace/[0-9a-f]*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
