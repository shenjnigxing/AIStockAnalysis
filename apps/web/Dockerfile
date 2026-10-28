FROM node:22-alpine
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web /app
# Copying sources must not retain a host build, dependency directory or secret.
EXPOSE 3000
CMD ["node", "node_modules/next/dist/bin/next", "dev", "-H", "0.0.0.0", "-p", "3000"]
