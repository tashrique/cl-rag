#!/bin/bash
# Docker container debugging script
# Run this inside the container to check connectivity and configuration

echo "===== Docker Container Debug Information ====="
echo

echo "### Environment Variables ###"
echo "HOST: $HOST"
echo "PORT: $PORT"
echo "PYTHONPATH: $PYTHONPATH"
echo "GEMINI_API_KEY set: $(if [ -n "$GEMINI_API_KEY" ]; then echo "Yes"; else echo "No"; fi)"
echo "PINECONE_API_KEY set: $(if [ -n "$PINECONE_API_KEY" ]; then echo "Yes"; else echo "No"; fi)"
echo

echo "### Network Information ###"
echo "Container IP addresses:"
ip addr | grep "inet " | awk '{print $2}'
echo
echo "DNS configuration:"
cat /etc/resolv.conf
echo

echo "### Testing External Connectivity ###"
echo "Testing connectivity to api.pinecone.io:"
curl -s -o /dev/null -w "%{http_code}" https://api.pinecone.io || echo "Failed to connect"
echo
echo "Testing connectivity to Google API:"
curl -s -o /dev/null -w "%{http_code}" https://generativelanguage.googleapis.com || echo "Failed to connect"
echo

echo "### Application Status ###"
echo "Running processes:"
ps aux
echo
echo "Open ports:"
netstat -tulpn 2>/dev/null || echo "netstat not available, trying ss" && ss -tulpn
echo

echo "### File Structure ###"
echo "Directory structure:"
ls -la /app
echo
echo "Source directory:"
ls -la /app/src
echo

echo "### Application Configuration ###"
echo "FastAPI Routes Configuration:"
grep -r "include_router" /app/src || echo "No router inclusion found"
echo
grep -r "app.include_router" /app/src || echo "No app.include_router found"
echo

echo "===== End of Debug Information =====" 