# Single image running BOTH Node and Python.
#
# server.js spawns the Python eval pipeline via child_process, so both runtimes
# must live in one container. A Dockerfile gives explicit control over this dual
# stack — Railway's auto-builders (Railpack / Nixpacks) each only fully provision
# one language's runtime, which left either `node` or `pip` missing.
FROM node:20-slim

# Python 3 + pip for eval_pipeline (numpy/scipy/scikit-learn/matplotlib/anthropic).
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Node deps (cached unless package files change).
COPY package.json package-lock.json ./
RUN npm ci

# Python deps. --break-system-packages: install into the system interpreter
# (Debian marks it externally-managed/PEP 668); fine inside a container.
COPY requirements.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# App source.
COPY . .

ENV PYTHON_BIN=python3
# Railway injects PORT; server.js falls back to 3000 locally.
EXPOSE 3000
CMD ["node", "server.js"]
