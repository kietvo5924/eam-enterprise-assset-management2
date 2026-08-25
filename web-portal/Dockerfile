FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose Vite default dev port
EXPOSE 5173

# Run Vite dev server, host 0.0.0.0 is needed for Docker port mapping to work
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
