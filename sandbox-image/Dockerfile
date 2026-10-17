# Sandbox image: renders PR components and runs generated stress tests. Runs untrusted PR
# code, so the backend starts it with no secrets, all capabilities dropped, resource limits,
# and no network except while installing dependencies.
FROM python:3.13-slim AS uv
RUN pip install --no-cache-dir uv==0.11.32

FROM mcr.microsoft.com/playwright:v1.64.1-noble
# uv manages Python virtualenvs for Python projects (the image has python3 but no pip).
COPY --from=uv /usr/local/bin/uv /usr/local/bin/uv
RUN npm install -g pnpm@10.28.0 yarn@1.22.22 && npm cache clean --force
WORKDIR /sandbox
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts && npm cache clean --force
COPY . .
# Caches and any Python that uv downloads live in the mounted job folder, so the offline
# run step can still use what the networked install step fetched.
ENV HOME=/tmp UV_CACHE_DIR=/work/.cache/uv UV_PYTHON_INSTALL_DIR=/work/.cache/python
USER pwuser
