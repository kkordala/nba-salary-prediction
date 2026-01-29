FROM apache/spark:3.4.1

# Install python + pip as root
USER root

RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Install python libraries needed for your Spark app
RUN pip install pyspark kafka-python

# Switch back to spark user (important!)
USER spark

# Make sure spark binaries are available
ENV PATH="/opt/spark/bin:${PATH}"
