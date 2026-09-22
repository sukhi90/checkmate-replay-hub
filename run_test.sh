#!/bin/bash
clear
echo "Sending isolated request directly to the LOCAL Python Backend..."

curl -i -X POST "localhost/submissions" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","fileName":"partie.txt"}'
