# Step-by-Step EC2 Deployment (t3.micro - Cost Optimized)

## Phase 1: Launch EC2 Instance

### 1. Go to AWS Console → EC2 → Launch Instance

**Name:** `benefitsflow-ui`

**Application and OS Images (Amazon Machine Image):**
- **Amazon Linux 2023 AMI** (free tier eligible)

**Instance type:**
- **t3.micro** (750 hours/month free for 12 months, then ~$7-8/month)
- If free tier expired, still only ~$7-8/month

**Key pair (login):**
- Create new key pair: `benefitsflow-key` (save `.pem` file securely!)
- Or use existing key pair

**Network settings:**
- Allow SSH traffic from: **My IP** (or your IP)
- **Add security group rule:**
  - Type: **Custom TCP**
  - Port: **8000**
  - Source: **Anywhere (0.0.0.0/0)** (for web access)

**Configure storage:**
- 8 GB (gp3) - Free tier eligible

**Advanced details:**
- (Optional) Add user data script to auto-install Docker (see below)

### 2. Click "Launch Instance"

**IMPORTANT:** Save your:
- **Public IPv4 address** (e.g., `54.123.45.67`)
- **Key pair file** (e.g., `benefitsflow-key.pem`)

---

## Phase 2: SSH and Setup

### 3. SSH into your instance

**Windows (PowerShell):**
```powershell
# Navigate to where your .pem file is
cd C:\path\to\your\key

# SSH into EC2
ssh -i benefitsflow-key.pem ec2-user@<YOUR-EC2-IP>
```

**First time?** You might need to:
```powershell
# Fix permissions (if needed)
icacls benefitsflow-key.pem /inheritance:r
icacls benefitsflow-key.pem /grant:r "%USERNAME%:R"
```

### 4. Install Docker and Git

Once SSH'd in, run:

```bash
# Update system
sudo yum update -y

# Install Docker
sudo yum install -y docker git
sudo systemctl start docker
sudo systemctl enable docker  # Auto-start on reboot
sudo usermod -aG docker ec2-user

# Install Docker Compose (optional, for easier management)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Log out and back in for group changes
exit
```

**Re-SSH:**
```bash
ssh -i benefitsflow-key.pem ec2-user@<YOUR-EC2-IP>
```

### 5. Clone Your Repo

```bash
# Clone your repository
git clone https://github.com/dliang5299/AI-Anti-Poverty-Assistant.git
cd AI-Anti-Poverty-Assistant/UI
```

---

## Phase 3: Deploy Your App

### 6. Build and Run Docker Container

```bash
# Build the image
docker build -t benefitsflow-ui .

# Run the container (detached, auto-restart on reboot)
docker run -d \
  -p 8000:8000 \
  --name benefitsflow \
  --restart unless-stopped \
  benefitsflow-ui

# Check if it's running
docker ps
docker logs benefitsflow
```

### 7. Test Your App

Visit in browser: `http://<YOUR-EC2-IP>:8000`

Should see your BenefitsFlow UI!

---

## Phase 4: Save Money - Stop/Start Instance

### Stop Instance (When Not Using)

**AWS Console:**
- EC2 → Instances → Select `benefitsflow-ui`
- Instance state → **Stop instance**

**Or via CLI:**
```bash
aws ec2 stop-instances --instance-ids <INSTANCE-ID>
```

**Cost while stopped:** **~$0.10/month** (storage only)

### Auto-Stop Options

**Option A: AWS Instance Scheduler (Recommended)**
- AWS Console → Systems Manager → Quick Setup → Instance Scheduler
- Set schedule: Stop at 10 PM, start at 8 AM
- **FREE and automatic!**

**Option B: Manual Stop (Simplest)**
- Just stop when done working
- See `AUTO_STOP_SETUP.md` for activity-based auto-stop scripts

### Start Instance (When Needed)

**AWS Console:**
- EC2 → Instances → Select `benefitsflow-ui`
- Instance state → **Start instance**
- Wait ~30 seconds for it to boot

**Your Docker container will auto-start** (because of `--restart unless-stopped`)

**Access again:** `http://<YOUR-EC2-IP>:8000` (IP might change, check console)

---

## Phase 5: Update Your App

When you make code changes:

```bash
# SSH into instance
ssh -i benefitsflow-key.pem ec2-user@<YOUR-EC2-IP>

# Pull latest code
cd AI-Anti-Poverty-Assistant
git pull

# Rebuild and restart
cd UI
docker stop benefitsflow
docker rm benefitsflow
docker build -t benefitsflow-ui .
docker run -d -p 8000:8000 --name benefitsflow --restart unless-stopped benefitsflow-ui
```

---

## Optional: Auto-Start Docker on Instance Boot

Create a startup script so Docker container auto-starts even after instance reboot:

```bash
# Create startup script
cat > ~/start-benefitsflow.sh << 'EOF'
#!/bin/bash
cd /home/ec2-user/AI-Anti-Poverty-Assistant/UI
docker start benefitsflow || docker run -d -p 8000:8000 --name benefitsflow --restart unless-stopped benefitsflow-ui
EOF

chmod +x ~/start-benefitsflow.sh

# Add to crontab for auto-start on boot
(crontab -l 2>/dev/null; echo "@reboot /home/ec2-user/start-benefitsflow.sh") | crontab -
```

---

## Troubleshooting

### Can't access app?
- Check security group allows port **8000** from **0.0.0.0/0**
- Check Docker is running: `docker ps`
- Check logs: `docker logs benefitsflow`

### Container not starting?
```bash
# Check what went wrong
docker logs benefitsflow

# Try running manually to see errors
docker run -p 8000:8000 benefitsflow-ui
```

### IP changed after stop/start?
- EC2 public IPs change when you stop/start
- Check new IP in EC2 console
- Or use **Elastic IP** (free if attached to running instance) to get permanent IP

---

## Cost Breakdown

- **t3.micro running 24/7:** ~$7-8/month
- **t3.micro running 8 hours/day:** ~$2-3/month
- **Stopped instance:** $0 + $0.10/month storage
- **Free tier (first 12 months):** 750 hours/month free = **$0 if <750 hrs/month**

**Pro tip:** Stop instance when not developing/testing to maximize savings!

---

## Next: Connect to Teammate's RAG

When their RAG service (`app/04_RAG_service.py`) is deployed, update your `fastapi_backend.py` to call their endpoint via HTTP.

See `INTEGRATION_GUIDE_FOR_DERIC.md` for details.
