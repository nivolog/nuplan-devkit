FROM debian:latest

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV PATH /opt/conda/bin:$PATH

RUN apt-get update --fix-missing && apt-get install -y wget bzip2 ca-certificates \
    libglib2.0-0 libxext6 libsm6 libxrender1 \
    git mercurial subversion
    
RUN apt-get install -y software-properties-common \
    && apt-get update && apt-get install python3.9 \
    && apt-get install -y python3.9-dev


RUN apt-get install -y curl \
    && curl -LO http://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
    
RUN bash Miniconda3-latest-Linux-x86_64.sh -p /miniconda -b
RUN rm Miniconda3-latest-Linux-x86_64.sh
ENV PATH=/miniconda/bin:${PATH}
RUN conda update -y conda

RUN conda install -c anaconda -y python=3.9
RUN conda install -c anaconda -y \
    pip

RUN apt-get update && apt-get install -y git \
    && apt-get install --reinstall -y ca-certificates \
    && git clone https://github.com/motional/nuplan-devkit.git && cd nuplan-devkit

    
COPY run_jupyter.sh nuplan-devkit
COPY set_env.sh nuplan-devkit
