FROM ubuntu:focal

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Ljubljana

# Install common dependencies
RUN set -ex \
    && apt-get update --fix-missing \
    && apt-get upgrade -y \
    && apt-get install -y   apt-utils \
                            nano \
                            git \
                            python3-pip\
    && apt-get clean -y

# Install Python3 packages
RUN set -ex \
    && pip3 install     pyzmq

RUN mkdir logatec-experiment

WORKDIR /root/logatec-experiment

# Copy logatec-experiment into container
COPY ./ ./

# Expose ports for ZMQ communication
EXPOSE 5561
EXPOSE 5562
EXPOSE 5563

# Start the python script
CMD ["python3", "monitor/ECMS_controller.py"]

# Local test:
# docker build -t controller -f monitor/docker/Dockerfile .
# docker run -p 5561:5561 -p 5562:5562 -p 5563:5563 -e DEVICE_NUM=1 -e RADIO_TYPE=test_type controller