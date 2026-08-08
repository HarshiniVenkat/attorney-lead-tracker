FROM node:20-alpine

WORKDIR /app

# Dependency layer cached separately from source.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
