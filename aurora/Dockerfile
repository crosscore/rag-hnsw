# aurora/Dockerfile

FROM postgres:latest

RUN apt-get update && apt-get install -y \
    postgresql-server-dev-all \
    gcc \
    git \
    make \
    tzdata \
    && cd /tmp \
    && git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git \
    && cd pgvector \
    && make \
    && make install \
    && cd / \
    && rm -rf /tmp/pgvector \
    && apt-get remove -y postgresql-server-dev-all gcc git make \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Tokyo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN echo "alias ls='ls --color=auto'" >> ~/.bashrc && \
    echo "alias ll='ls -alF'" >> ~/.bashrc && \
    echo "export PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '" >> ~/.bashrc

RUN echo "CREATE EXTENSION IF NOT EXISTS vector;" > /docker-entrypoint-initdb.d/10-create-extension.sql
