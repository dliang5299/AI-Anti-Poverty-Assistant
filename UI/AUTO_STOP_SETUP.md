# Auto-Stop EC2 Instance on Inactivity

## Quick Setup Options

### Option 1: AWS Instance Scheduler (Easiest - Recommended)

**Automatically stops instance on schedule (e.g., nights/weekends)**

1. **AWS Console → Systems Manager → Quick Setup**
   - Select "Instance Scheduler"
   - Schedule: Stop at 10 PM daily, start at 8 AM
   - Attach to your EC2 instance

2. **Cost:** FREE

**Pros:**
- No code needed
- AWS managed
- Reliable

**Cons:**
- Schedule-based, not activity-based

---

### Option 2: Activity-Based Auto-Stop Script

**Stops instance when no requests for X minutes**

#### Setup on EC2:

```bash
# 1. SSH into your EC2 instance
ssh -i benefitsflow-key.pem ec2-user@<YOUR-EC2-IP>

# 2. Install AWS CLI (if not installed)
sudo yum install -y aws-cli

# 3. Configure AWS credentials (need IAM role with ec2:StopInstances permission)
# OR attach IAM role to EC2 instance with permission:
# {
#   "Effect": "Allow",
#   "Action": ["ec2:StopInstances"],
#   "Resource": "arn:aws:ec2:*:*:instance/*",
#   "Condition": {"StringEquals": {"ec2:ResourceTag/Owner": "your-username"}}
# }

# 4. Create the script
cat > ~/auto-stop.sh << 'EOF'
#!/bin/bash
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)

# Check last activity (simple: check if any HTTP requests in last 30 min)
LAST_ACTIVITY=$(docker logs --since 30m benefitsflow 2>/dev/null | wc -l)

if [ "$LAST_ACTIVITY" -eq "0" ]; then
    echo "$(date): No activity for 30 min, stopping instance"
    aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --region "$REGION"
fi
EOF

chmod +x ~/auto-stop.sh

# 5. Run as cron job (check every 15 minutes)
(crontab -l 2>/dev/null; echo "*/15 * * * * /home/ec2-user/auto-stop.sh >> /home/ec2-user/auto-stop.log 2>&1") | crontab -
```

**Cons:**
- Instance must be running to check (can't detect inactivity while stopped)
- Need IAM permissions
- More complex

---

### Option 3: CloudWatch + Lambda (Most Reliable)

**Monitor app metrics and auto-stop when inactive**

1. **Create Lambda function** to stop instance after inactivity
2. **CloudWatch alarm** triggers Lambda
3. **Monitor:** HTTP requests per minute = 0 for 30 minutes

**Pros:**
- Works even if instance is running but idle
- More reliable

**Cons:**
- More setup complexity
- Need Lambda + CloudWatch knowledge

---

### Option 4: Manual Stop (Simplest - Recommended for Now)

**Just stop manually when done working**

```bash
# AWS Console:
# EC2 → Instances → Select instance → Stop instance

# Or via CLI:
aws ec2 stop-instances --instance-ids <INSTANCE-ID>
```

**Pros:**
- Zero setup
- Full control
- No surprises

**Cons:**
- Remember to stop manually
- ~$0.10/month storage still charged

---

## Recommendation

**For now:** Use **manual stop** (Option 4). It's free tier eligible (750 hrs/month), so you have plenty of time.

**Later:** Add **Instance Scheduler** (Option 1) if you want automation without complexity.

**Cost impact:** 
- Manual stop when done: ~$0.10/month storage
- Auto-stop on schedule: Same cost, just automatic

---

## Setup Instance Scheduler (5 minutes)

1. **Go to:** AWS Systems Manager → Quick Setup
2. **Select:** Instance Scheduler
3. **Configure:**
   - **Schedule name:** `weekdays-only`
   - **Stop time:** `20:00 UTC` (adjust for your timezone)
   - **Start time:** `08:00 UTC`
   - **Days:** Monday-Friday (or all days)
4. **Select your EC2 instance**
5. **Done!** Instance auto-stops/starts on schedule

---

## Alternative: Simple Timer Script

If you just want to stop after X hours of running:

```bash
# On your local machine, run:
aws ec2 stop-instances --instance-ids <INSTANCE-ID> --region us-west-2
```

Or use Windows Task Scheduler / macOS cron to run this command at a specific time.

---

## Bottom Line

**Easiest:** Just manually stop when done → **$0.10/month** when stopped  
**Automated:** Instance Scheduler → **Same cost**, but automatic  
**Smart:** Lambda + CloudWatch → More complex, but activity-based

**Recommendation:** Start with manual, add Instance Scheduler later if you want automation.
