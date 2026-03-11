FROM node:20-alpine
WORKDIR /home/app
COPY package*.json ./
RUN npm install
COPY ./ ./
RUN addgroup -S appgroup && adduser -S appuser -G appgroup && chown -R appuser:appgroup /home/app
USER appuser
EXPOSE 3000
