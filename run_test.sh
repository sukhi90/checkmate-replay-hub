#!/bin/bash
clear
echo "Sending isolated request directly to the NEW AWS API Gateway..."

curl -i -X POST "https://sve3f9df5j://amazonaws.com" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","fileName":"partie.txt"}'
