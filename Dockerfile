FROM python:3.10

RUN apt update && apt upgrade -y
RUN apt install -y python3-pip

COPY ./ /app
WORKDIR /app

RUN pip install -r requirements.txt
WORKDIR /app/app
EXPOSE 8888
ENTRYPOINT ["bash", "run_server.sh"]
