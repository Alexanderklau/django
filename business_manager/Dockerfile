#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++#
##
##   @DESCRIPTION : Microservice For bsmserver
##   @NAME        : Dockerfile
##   @VERSION     : 1.0.0
##   @CREATE      : 2017-01-16 15:44:06
##   @UPDATE      : 2017-02-09 15:41:06
##   @MAINTAINER  : colin.lee<likunyao@rongshutong.com>
##
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++#

FROM hub.rongshutong.com/common/python:alpine

WORKDIR /app

RUN mkdir -p /data

### install consul-template
RUN set -ex ;\
    apk add --no-cache --no-cache supervisor ;\
    ## install consul-template
    wget -q -O - http://rst-public.oss-cn-hangzhou.aliyuncs.com/docker/consul-template_0.18.0_linux_amd64.tgz | tar zxf - ;\
    mv consul-template /usr/local/bin

ADD . /app
RUN cp ./bin/docker-entrypoint.sh /entrypoint.sh

VOLUME ["/data"]

EXPOSE 9001

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord"]
