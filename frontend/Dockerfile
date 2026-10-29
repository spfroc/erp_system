FROM node:22-alpine

WORKDIR /app

# Alpine 默认无 tzdata；仅设 TZ=Asia/Shanghai 会回落到 UTC
RUN apk add --no-cache tzdata \
  && cp /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
  && echo Asia/Shanghai >/etc/timezone
ENV TZ=Asia/Shanghai

COPY package*.json ./
RUN npm install -g npm@11 && npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
