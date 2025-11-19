# Quick Fix Commands for EC2 Instances

## On Instance 1 (UI Instance)

You're already in the right directory. Run these commands:

```bash
# 1. Pull latest code (already done, but verify)
git pull origin main

# 2. Check if .env file exists
ls -la .env

# 3. View current .env file
cat .env

# 4. Edit .env file (replace INSTANCE-2-PRIVATE-IP with actual IP)
nano .env
# Add or update this line:
# RAG_SERVICE_URL=http://172.31.20.8:8000
# (Use Instance 2's actual private IP)

# 5. Rebuild and restart UI container
docker stop benefitsflow
docker rm benefitsflow
docker build -f Dockerfile.ui -t benefitsflow-ui .
docker run -d -p 8501:8501 --name benefitsflow --env-file .env --restart unless-stopped benefitsflow-ui

# 6. Check logs
docker logs -f benefitsflow
```

## On Instance 2 (RAG Instance)

```bash
# 1. Pull latest code
cd AI-Anti-Poverty-Assistant
git pull origin main

# 2. Restart RAG container (if needed)
docker restart rag-service
docker logs -f rag-service
```

## Verify Connection

On Instance 1, test if you can reach Instance 2:

```bash
# Replace with Instance 2's private IP
curl http://172.31.20.8:8000/health
```

If this works, you should see: `{"service": "ok", ...}`

## Check Your Instance 2 Private IP

If you don't know Instance 2's private IP:
- Go to AWS Console → EC2 → Instances
- Find Instance 2 (benefitsflow-rag)
- Look at "Private IPv4 addresses" column

