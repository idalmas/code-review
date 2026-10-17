# Sandbox image for rendering PR components. Runs untrusted PR code: the backend starts it
# with no secrets, all capabilities dropped, resource limits, and no network while rendering.
FROM mcr.microsoft.com/playwright:v1.64.1-noble
RUN npm install -g pnpm@10.28.0 yarn@1.22.22 && npm cache clean --force
WORKDIR /renderer
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts && npm cache clean --force
COPY . .
ENV HOME=/tmp
USER pwuser
