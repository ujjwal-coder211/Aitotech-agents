# ===========================================================
#  Next.js dashboard के लिए Docker image (standalone output)।
#  Railway पर इस service की Root Directory = "dashboard" set करें।
#  (या इससे आसान: dashboard को Vercel पर deploy करें — README देखें।)
# ===========================================================
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
# standalone build सिर्फ ज़रूरी files रखता है
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["sh", "-c", "node server.js"]
