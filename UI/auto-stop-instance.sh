#!/bin/bash
# Auto-stop EC2 instance after inactivity
# Place this in your EC2 instance's home directory

# Configuration
INACTIVITY_MINUTES=30  # Stop after 30 minutes of no requests
LOG_FILE="$HOME/auto-stop.log"

# Get instance metadata
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
REGION=$(curl -s http://169.254.169.254/latest/meta-data/placement/region)

# Check if app is receiving requests (check Docker container logs)
check_activity() {
    # Get last activity time from Docker logs
    LAST_ACTIVITY=$(docker logs --since 1h benefitsflow 2>/dev/null | tail -1 | grep -o '[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}T[0-9]\{2\}:[0-9]\{2\}' | tail -1)
    
    if [ -z "$LAST_ACTIVITY" ]; then
        echo "$(date): No recent activity detected" >> "$LOG_FILE"
        return 1
    fi
    
    # Parse last activity time and compare
    LAST_EPOCH=$(date -d "$LAST_ACTIVITY" +%s 2>/dev/null)
    NOW_EPOCH=$(date +%s)
    DIFF_MINUTES=$(( (NOW_EPOCH - LAST_EPOCH) / 60 ))
    
    if [ $DIFF_MINUTES -gt $INACTIVITY_MINUTES ]; then
        echo "$(date): No activity for $DIFF_MINUTES minutes, stopping instance" >> "$LOG_FILE"
        return 1
    fi
    
    return 0
}

# Stop instance
stop_instance() {
    echo "$(date): Stopping EC2 instance $INSTANCE_ID" >> "$LOG_FILE"
    aws ec2 stop-instances --instance-ids "$INSTANCE_ID" --region "$REGION"
}

# Main loop
while true; do
    if ! check_activity; then
        stop_instance
        break
    fi
    sleep 300  # Check every 5 minutes
done
