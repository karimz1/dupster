FROM mcr.microsoft.com/devcontainers/python:3.11


ENV VENV=/opt/venv
RUN python -m venv "$VENV" \
 && "$VENV/bin/pip" install --no-cache-dir -U pip setuptools wheel
ENV PATH="$VENV/bin:$PATH"
ENV PIP_REQUIRE_VIRTUALENV=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && rm -f /tmp/requirements.txt

RUN if id -u vscode >/dev/null 2>&1; then chown -R vscode:vscode "$VENV"; fi