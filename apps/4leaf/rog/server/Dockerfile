# Isolated 4LEAF ChatTown authority; only Node's standard library is needed.
FROM node:22-alpine
WORKDIR /app
COPY apps/4leaf/rog/server/central.cjs ./central.cjs
ENV NODE_ENV=production PORT=10000 HOST=0.0.0.0 \
    LEAF_CENTRAL_ORIGINS=https://koith.github.io \
    LEAF_CENTRAL_STORAGE=/var/lib/4leaf/chat-state.json
RUN mkdir -p /var/lib/4leaf && chown -R node:node /var/lib/4leaf
USER node
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD node -e "fetch('http://127.0.0.1:'+(process.env.PORT||10000)+'/api/health').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "central.cjs"]
