FROM python:3.5-slim

RUN useradd fishroom
USER fishroom

# COPY fishroom /data/fishroom
COPY requirements.txt /data/requirements.txt

USER root

# RUN echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ jessie main contrib non-free" > /etc/apt/sources.list && \
# 	echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ jessie-backports main contrib non-free" >> /etc/apt/sources.list && \
# 	echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian/ jessie-updates main contrib non-free" >> /etc/apt/sources.list && \
# 	echo "deb http://mirrors.tuna.tsinghua.edu.cn/debian-security/ jessie/updates main contrib non-free" >> /etc/apt/sources.list

# RUN echo "[global]" > /etc/pip.conf && \
# 	echo "index-url=https://pypi.tuna.tsinghua.edu.cn/simple" >> /etc/pip.conf

RUN apt-get update && \
	apt-get install -y libmagic1 libjpeg62-turbo libjpeg-dev libpng-dev libwebp-dev zlib1g zlib1g-dev gcc mime-support

RUN python3 -m ensurepip && \
	pip3 install --upgrade pip setuptools 


RUN pip3 install pillow && \
	pip3 install -r /data/requirements.txt

RUN apt-get remove -y libjpeg-dev libpng-dev libwebp-dev zlib1g-dev gcc && \
	apt-get autoremove -y && \
	apt-get clean all

WORKDIR /data
USER fishroom
