FROM node:22-bookworm-slim
WORKDIR /app
COPY package.json ./
COPY server.mjs ./
COPY sites ./sites
ENV PORT=5180
ENV BACKEND_URL=http://backend:8000
ENV DEFAULT_SITE_KEY=qlyc
EXPOSE 5180
CMD ["node", "server.mjs"]
