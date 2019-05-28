FROM python:3.7

COPY configs/requirements.txt /tmp/
RUN pip install --no-cache -r /tmp/requirements.txt

RUN useradd --create-home appuser
WORKDIR /opt/wsgi
USER appuser

COPY ./wsgi /opt/wsgi/

ARG configfile
ENV configfile=${configfile:-./docker.conf}
COPY ${configfile} /opt/wsgi/wsgi.conf

CMD [ "uwsgi", "--ini", "/opt/wsgi/wsgi.conf" ]
