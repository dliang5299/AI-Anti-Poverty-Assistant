# Quick Start: Deploy BenefitsFlow UI to AWS

## Fastest Method: Elastic Beanstalk (5 minutes)

### Prerequisites:
- AWS CLI configured (`aws configure`)
- EB CLI installed: `pip install awsebcli`

### Steps:

```bash
# 1. Navigate to UI folder
cd UI

# 2. Initialize Elastic Beanstalk
eb init -p python-3.11 benefitsflow-ui --region us-west-2

# 3. Create and deploy
eb create benefitsflow-prod

# 4. Your app is live!
eb open
```

That's it! Your app will be available at: `http://benefitsflow-prod.elasticbeanstalk.com`

---

## Alternative: Manual EC2 (10 minutes)

### 1. Launch EC2 Instance:
- **AMI**: Amazon Linux 2023
- **Instance Type**: t3.small (or t3.medium)
- **Security Group**: 
  - Port 8000 (HTTP) from Anywhere (0.0.0.0/0)
  - Port 22 (SSH) from your IP

### 2. SSH into instance:
```bash
ssh -i your-key.pem ec2-user@<your-ec2-ip>
```

### 3. Install Docker and Git:
```bash
sudo yum update -y
sudo yum install -y docker git
sudo systemctl start docker
sudo usermod -aG docker ec2-user
newgrp docker  # Refresh group membership
```

### 4. Clone and deploy:
```bash
git clone https://github.com/dliang5299/AI-Anti-Poverty-Assistant.git
cd AI-Anti-Poverty-Assistant/UI

# Build and run
docker build -t benefitsflow-ui .
docker run -d -p 8000:8000 --name benefitsflow --restart unless-stopped benefitsflow-ui
```

### 5. Access your app:
Visit: `http://<your-ec2-ip>:8000`

---

## Update Your App (After Code Changes)

### Elastic Beanstalk:
```bash
cd UI
eb deploy
```

### EC2:
```bash
# SSH into instance
ssh ec2-user@<your-ec2-ip>

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

## Test Locally First (Before AWS)

```bash
cd UI
docker build -t benefitsflow-ui .
docker run -p 8000:8000 benefitsflow-ui
```

Then visit: `http://localhost:8000`

---

## Troubleshooting

- **Can't access app**: Check security group allows port 8000
- **502 errors**: Check logs with `eb logs` (EB) or `docker logs benefitsflow` (EC2)
- **CORS errors**: Already handled, but check `allow_origins` in `fastapi_backend.py` if needed

---

## Next Steps

When your teammate's RAG system is ready:
1. Update `fastapi_backend.py` to connect to their RAG service
2. Redeploy with `eb deploy` or rebuild Docker container
3. Done!

See `INTEGRATION_GUIDE_FOR_DERIC.md` for integration details.
