FROM node:20-alpine AS build
WORKDIR /opt/archai
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm install
COPY apps/web ./
RUN npm run build
FROM node:20-alpine
WORKDIR /opt/archai
ENV NODE_ENV=production
COPY --from=build /opt/archai ./
USER 10001
EXPOSE 3000
CMD ["npm", "run", "start"]
