command prompt:

cd do /docker 

docker-compose up -d --build

potem

docker exec -it spark spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 /home/jovyan/work/spark_streaming.py

UI
http://127.0.0.1:5005/
