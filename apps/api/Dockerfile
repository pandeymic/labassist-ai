FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY tsconfig.json ./
COPY src ./src
COPY migrations ./migrations
RUN npm run build
FROM node:20-alpine
WORKDIR /app
COPY --from=build /app ./
EXPOSE 4000
CMD ["sh", "-c", "npm run db:migrate && npm run db:seed && npm start"]
