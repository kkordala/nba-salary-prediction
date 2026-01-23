command prompt:

cd do /docker 

docker-compose up --build -d

jeszcze to 

docker exec -it kafka kafka-topics --create --topic raw-events --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1


docker exec -it kafka kafka-topics --create --topic processed-events --bootstrap-server kafka:9092 --partitions 1 --replication-factor 1

potem

docker exec -it spark spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 /home/jovyan/work/spark_streaming.py

UI
http://127.0.0.1:5005/

po restarcie jeśli nie działa
docker exec -it spark rm -rf /home/jovyan/work/checkpoints