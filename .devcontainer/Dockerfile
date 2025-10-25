FROM mcr.microsoft.com/devcontainers/python:3.11

# Create and use a venv
ENV VENV=/opt/venv
RUN python -m venv "$VENV" \
 && "$VENV/bin/pip" install --no-cache-dir -U pip setuptools wheel
ENV PATH="$VENV/bin:$PATH"
ENV PIP_REQUIRE_VIRTUALENV=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Install deps (great for Docker layer caching)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && rm -f /tmp/requirements.txt

# Optional: ensure the devcontainer user can add packages interactively
RUN if id -u vscode >/dev/null 2>&1; then chown -R vscode:vscode "$VENV"; fi