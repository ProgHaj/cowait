#!/bin/bash

# Find the agent
agent=$(docker ps -aqf "name=agent")

# Check if agent was found
if [ -z $agent ]
then
  echo "Agent auto-discovery failed - make sure the cowait agent is running"
  exit 1
fi

# Exctract the task definition
task_definition=$(docker exec $agent bash -c 'echo "$TASK_DEFINITION"')

# Find url and token values
url=$(jq -r '.routes["/"].url' <<< $task_definition)
token=$(jq -r '.meta.http_token' <<<$task_definition)

# Construct agent URL
agent_url="$url?token=$token"

# Run
echo "Agent successfully discovered - $agent_url"
REACT_APP_AGENT_URL=$agent_url PORT=1339 react-scripts start