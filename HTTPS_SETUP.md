# HTTPS Setup Guide for BenefitsFlow

## Overview
This guide will help you set up HTTPS using Let's Encrypt (free SSL certificates) with your Nginx reverse proxy.

## Prerequisites
- Domain `benefitsflow.org` pointing to your EC2 instance (already done ✅)
- Port 443 open in your EC2 Security Group (need to add)
- SSH access to your EC2 instance

## Step 1: Update Security Group

1. Go to AWS Console → EC2 → Security Groups
2. Find your instance's security group
3. Add **Inbound Rule**:
   - **Type**: HTTPS
   - **Port**: 443
   - **Source**: 0.0.0.0/0

## Step 2: Install Certbot on EC2

SSH into your EC2 instance and run:

```bash
# For Amazon Linux 2023
sudo dnf install -y certbot

# For Ubuntu
# sudo apt-get update && sudo apt-get install -y certbot
```

## Step 3: Get SSL Certificate

Run certbot to get your certificate:

```bash
sudo certbot certonly --standalone -d benefitsflow.org -d www.benefitsflow.org
```

**Important**: This will temporarily stop Nginx to validate your domain. You'll need to:
1. Stop docker-compose: `docker-compose down`
2. Run certbot command above
3. Restart docker-compose: `docker-compose up -d`

Certificates will be saved to:
- `/etc/letsencrypt/live/benefitsflow.org/fullchain.pem`
- `/etc/letsencrypt/live/benefitsflow.org/privkey.pem`

## Step 4: Update Configuration Files

The updated `nginx.conf` and `docker-compose.yml` files are ready. You need to:

1. Copy the updated files to your EC2 instance
2. Update docker-compose.yml to mount the certificate directory
3. Restart services

## Step 5: Set Up Auto-Renewal

Let's Encrypt certificates expire every 90 days. Set up auto-renewal:

```bash
# Test renewal
sudo certbot renew --dry-run

# Add to crontab (runs twice daily, only renews if <30 days until expiry)
sudo crontab -e
# Add this line:
0 0,12 * * * certbot renew --quiet --deploy-hook "cd /home/ec2-user/AI-Anti-Poverty-Assistant && docker-compose restart nginx"
```

## Step 6: Verify HTTPS Works

After setup:
- Visit: `https://benefitsflow.org`
- Check for the padlock icon in your browser
- Test HTTP → HTTPS redirect

## Troubleshooting

**Certificate renewal fails:**
- Make sure port 80 is accessible (for validation)
- Check certbot logs: `sudo tail -f /var/log/letsencrypt/letsencrypt.log`

**Nginx can't find certificates:**
- Verify certificate paths in docker-compose.yml volume mounts
- Check file permissions: `sudo ls -la /etc/letsencrypt/live/benefitsflow.org/`

**Mixed content warnings:**
- Update any hardcoded `http://` URLs in your frontend to use `https://` or relative paths

