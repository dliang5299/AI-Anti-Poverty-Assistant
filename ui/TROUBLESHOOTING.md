# Troubleshooting Guide for EC2 Deployment

## Common Issues and Fixes

### 1. Images Not Loading

**Symptoms:** Images show as broken/placeholder icons

**Fix:**
- Images are now properly mounted at `/images` in `serve_frontend.py`
- Verify images exist in container: `docker exec -it <container-name> ls -la /ui/images/`
- Check browser console for 404 errors on image requests
- Ensure Dockerfile copies the `ui` folder correctly (should include `images/` subfolder)

### 2. "Backend API not available" Error

**Symptoms:** Red error banner saying "Backend API not available. Please start the FastAPI server."

**Causes & Fixes:**

#### A. RAG Service URL Not Configured
On **Instance 1** (UI instance), check your `.env` file:
```bash
# Should have:
RAG_SERVICE_URL=http://[INSTANCE-2-PRIVATE-IP]:8000

# Example:
RAG_SERVICE_URL=http://172.31.20.8:8000
```

**To fix:**
1. Get Instance 2's private IP from AWS Console
2. SSH into Instance 1
3. Edit `.env` file: `nano .env`
4. Add/update: `RAG_SERVICE_URL=http://[INSTANCE-2-PRIVATE-IP]:8000`
5. Restart container: `docker restart <container-name>`

#### B. RAG Service Not Running on Instance 2
Check if RAG service is running:
```bash
# On Instance 2
docker ps  # Should see rag-service container
docker logs rag-service  # Check for errors
```

**To fix:**
1. SSH into Instance 2
2. Check container: `docker ps -a`
3. If not running: `docker start rag-service`
4. If container doesn't exist, rebuild:
   ```bash
   cd AI-Anti-Poverty-Assistant
   docker build -f Dockerfile.api -t benefitsflow-rag .
   docker run -d -p 8000:8000 --name rag-service --env-file .env --restart unless-stopped benefitsflow-rag
   ```

#### C. Security Group Issues
Instance 1 cannot reach Instance 2's port 8000.

**To fix:**
1. Go to AWS Console → EC2 → Security Groups
2. Find Instance 2's security group
3. Add inbound rule:
   - Type: Custom TCP
   - Port: 8000
   - Source: Instance 1's security group (or Instance 1's private IP)

### 3. Container Not Starting

**Symptoms:** `docker ps` shows container as "Exited" or keeps restarting

**Debug:**
```bash
# Check logs
docker logs <container-name>

# Common issues:
# - Missing .env file
# - Wrong file paths
# - Port already in use
# - Missing dependencies
```

**Fix:**
1. Check logs for specific error
2. Verify `.env` file exists and has correct values
3. Check if port is in use: `sudo netstat -tulpn | grep 8501` (UI) or `grep 8000` (RAG)
4. Rebuild container if needed

### 4. API Calls Failing

**Symptoms:** Chat messages don't get responses, or errors in browser console

**Debug:**
1. Open browser console (F12)
2. Check Network tab for failed requests
3. Look for CORS errors or 404/500 errors

**Common fixes:**
- Verify `RAG_SERVICE_URL` is correct in `.env`
- Check that Instance 2's RAG service is accessible: `curl http://[INSTANCE-2-IP]:8000/health`
- Check CORS settings (should allow all origins in current setup)

### 5. Environment Variables Not Loading

**Symptoms:** Code uses default values instead of `.env` values

**Fix:**
- Ensure `.env` file is in the same directory as `docker run` command
- Use `--env-file .env` flag when running container
- Check file permissions: `chmod 644 .env`
- Verify variable names match exactly (case-sensitive)

## Quick Health Checks

### On Instance 1 (UI):
```bash
# Check container is running
docker ps | grep benefitsflow

# Check logs
docker logs benefitsflow

# Test API endpoint
curl http://localhost:8501/api/health

# Check environment variables
docker exec benefitsflow env | grep RAG_SERVICE_URL
```

### On Instance 2 (RAG):
```bash
# Check container is running
docker ps | grep rag-service

# Check logs
docker logs rag-service

# Test RAG endpoint
curl http://localhost:8000/health

# Test from Instance 1 (replace with Instance 1's private IP)
curl http://[INSTANCE-1-IP]:8501
```

## Verification Steps

1. **Instance 2 RAG Service:**
   ```bash
   curl http://localhost:8000/health
   # Should return: {"service": "ok", ...}
   ```

2. **Instance 1 UI Service:**
   ```bash
   curl http://localhost:8501/health
   # Should return: {"status": "healthy", ...}
   ```

3. **Connection from Instance 1 to Instance 2:**
   ```bash
   # On Instance 1
   curl http://[INSTANCE-2-PRIVATE-IP]:8000/health
   # Should return: {"service": "ok", ...}
   ```

4. **Browser:**
   - Open: `http://[INSTANCE-1-PUBLIC-IP]:8501`
   - Check browser console (F12) for errors
   - Try sending a chat message
   - Check Network tab for API calls

## Still Having Issues?

1. Check Docker logs: `docker logs <container-name>`
2. Check system logs: `journalctl -u docker` (if using systemd)
3. Verify security groups allow traffic
4. Ensure IAM roles have correct permissions
5. Check AWS Secrets Manager if using it for API keys

