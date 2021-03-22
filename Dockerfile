FROM notsosuper/python-3.8

#Dependencies

RUN apt-get update \
    && apt-get install -y git \
    iputils-ping \
    && apt-get clean

# JEMALLOC

RUN wget -q https://github.com/jemalloc/jemalloc/releases/download/5.2.1/jemalloc-5.2.1.tar.bz2 \
    && tar xjf jemalloc-5.2.1.tar.bz2 \
    && cd jemalloc-5.2.1 \
    && ./configure \
    && make -j5 && make install \
    && rm -rf ../jemalloc*


WORKDIR /discord

#PyPI

COPY requirements.txt .

ARG PIPBUST=0
ARG DEV=0

RUN pip3.8 install --no-cache-dir -r requirements.txt \
    $([ -z "$DEV" ] && echo "ptvsd") \
    && rm requirements.txt

#Clean Up

RUN apt remove -y --auto-remove gcc \
    && rm -rf /usr/local/lib/python3.8/test \
    /usr/local/lib/python3.8/config-3.8m-x86_64-linux-gnu \
    /usr/share/doc \
    /usr/share/man \
    /usr/lib/gcc \
    /var/cache \
    /var/lib/apt/lists/* \
    && rm -f /usr/lib/x86_64-linux-gnu/libLLVM-4.0.so.1

#Deploy Key

ARG key_dir="/tmp/id_rsa"
COPY gh_deploy $key_dir

RUN chmod 600 $key_dir \
    && eval $(ssh-agent) \
    && echo "Host github.com" >> /etc/ssh/ssh_config \
    && echo "    IdentityFile $key_dir" >> /etc/ssh/ssh_config \
    && echo "    StrictHostKeyChecking no" >> /etc/ssh/ssh_config

#Source

ARG CACHEBUST=0

RUN git clone --depth 1 git@github.com:NotSoSuper/NotSoBot_Private.git .

#TCMALLOC

# ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libtcmalloc_minimal.so.4"
ENV LD_PRELOAD="/usr/local/lib/libjemalloc.so"

#Final

RUN mkdir /etc/service/discord /logs
COPY run.sh /etc/service/discord/run

ENTRYPOINT [ "/sbin/my_init" ]

#docker build --tag notsobot . --build-arg CACHEBUST=0