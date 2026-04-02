FROM python:3.14-alpine
WORKDIR /opt/wsgi

RUN apk update && \
    apk --no-cache add \
        bash \
        ca-certificates \
        git \
        openjdk8-jre \
        perl \
        postgresql-libs \
        wget \
        pcre \
        postgresql-client && \
    apk --no-cache add --virtual .build-deps \
        gcc \
        musl-dev \
        postgresql-dev \
        python3-dev \
        make \
        zlib-dev \
        g++ \
        linux-headers \
        pcre-dev && \
    update-ca-certificates && \
    apk --update add tzdata && \
    cp /usr/share/zoneinfo/America/Chicago /etc/localtime && \
    apk del tzdata && \
    pip install --upgrade pip setuptools && \
    rm -r /root/.cache

COPY ./wsgi/bmrbapi/reloaders/molprobity_binary /opt/wsgi/bmrbapi/reloaders/molprobity_binary
RUN cd /opt/wsgi/bmrbapi/reloaders/molprobity_binary && make

COPY ./wsgi/bmrbapi/submodules/fasta36 /opt/wsgi/bmrbapi/submodules/fasta36
RUN sed -i 's/-DPOSIX_C_SOURCE=2/-DPOSIX_C_SOURCE=2 -D_GNU_SOURCE/' /opt/wsgi/bmrbapi/submodules/fasta36/make/Makefile.linux64_sse2 && \
    cd /opt/wsgi/bmrbapi/submodules/fasta36/src && make -f ../make/Makefile.linux64_sse2 all

COPY wsgi/requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip wheel
RUN pip install uwsgi -r /tmp/requirements.txt

COPY ./wsgi /opt/wsgi/

COPY wsgi.conf /opt/wsgi/wsgi.conf

CMD [ "uwsgi", "--ini", "/opt/wsgi/wsgi.conf" ]
