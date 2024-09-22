run app under docker: docker-compose up -d
get logs for app under docker: docker logs $(docker ps -a | grep aprv-ai | awk '{print $1}')
start app: uvicorn main:app --app-dir ./app