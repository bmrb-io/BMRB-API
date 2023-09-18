FROM alpine:3.14
WORKDIR /opt/wsgi

RUN apk update && \
    apk --no-cache add \
        bash \
        ca-certificates \
        git \
        openjdk8-jre \
        perl \
        postgresql-libs \
        python3 \
        wget \
        uwsgi-http \
        uwsgi-python3 \
        postgresql-client && \
    apk --no-cache add --virtual .build-deps \
        gcc \
        musl-dev \
        postgresql-dev \
        python3-dev \
        make \
        zlib-dev \
        g++ && \
    update-ca-certificates && \
    apk --update add tzdata && \
    cp /usr/share/zoneinfo/America/Chicago /etc/localtime && \
    apk del tzdata && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache

COPY ./wsgi/bmrbapi/reloaders/molprobity_binary /opt/wsgi/bmrbapi/reloaders/molprobity_binary
RUN cd /opt/wsgi/bmrbapi/reloaders/molprobity_binary && make

COPY ./wsgi/bmrbapi/submodules/fasta36 /opt/wsgi/bmrbapi/submodules/fasta36
RUN cd /opt/wsgi/bmrbapi/submodules/fasta36/src && make -f ../make/Makefile.linux64_sse2 all

COPY wsgi/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip wheel
RUN pip install  -r /tmp/requirements.txt

COPY ./wsgi /opt/wsgi/

COPY wsgi.conf /opt/wsgi/wsgi.conf

CMD [ "uwsgi", "--ini", "/opt/wsgi/wsgi.conf" ]
