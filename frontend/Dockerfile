FROM node:22-slim AS build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/frontend/dist /usr/share/nginx/html
RUN printf '%s\n' \
    'server {' \
    '  listen 8080;' \
    '  server_name _;' \
    '  root /usr/share/nginx/html;' \
    '  index index.html;' \
    '  location /assets/ {' \
    '    try_files $uri =404;' \
    '    add_header Cache-Control "public, max-age=31536000, immutable";' \
    '  }' \
    '  location / {' \
    '    try_files $uri $uri/ /index.html;' \
    '  }' \
    '}' > /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
