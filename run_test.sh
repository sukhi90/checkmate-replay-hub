#!/bin/bash
clear
echo "Sending isolated request directly to the LOCAL Python Backend..."

curl -i -X POST "http://127.0.0" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","fileName":"partie.txt"}'
