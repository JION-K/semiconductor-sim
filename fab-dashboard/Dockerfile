FROM node:20-alpine

WORKDIR /app

COPY package*.json /app/
RUN npm install

COPY . /app

CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173", "--force"]
