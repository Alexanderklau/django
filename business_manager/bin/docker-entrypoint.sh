#!/bin/bash
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++#
##
##   @DESCRIPTION : Microservice
##   @NAME        : docker-entrypoint.sh
##   @VERSION     : 1.0.0
##   @CREATE      : 2017-01-16 17:39:11
##   @UPDATE      : 2017-01-16 17:39:11
##   @MAINTAINER  : colin.lee<likunyao@rongshutong.com>
##
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++#
set -e

### constant
WORKDIR=/app
OK="\033[32m [OK] \033[0m"
ERROR="\033[31m [ERROR] \033[0m"

gen_thrift() {
    thrift_file_path=`find /app -name "*.thrift"`
    if [ -z "$thrift_file_path" ]; then
        echo -e " - $OK no thrift file find, skip..."
        return
    fi
    for tfile in $thrift_file_path; do
        tpath=`dirname $tfile`
        tname=`basename $tfile`
        cd $tpath && thrift --gen py $tname
        if [ $? == 0 ]; then
            echo -e " - $OK generate => $tfile"
        else
            echo -e " - $ERROR generate => $tfile"
        fi
    done
}

gen_proto() {
    proto_path=`find /app -type d -name "pb"`
    if [ -z "$proto_path" ]; then
        echo -e " - $OK no proto file find, skip..."
        return
    fi
    for ppath in $proto_path; do
        cd $ppath && protoc --python_out=./ ./*.proto
        if [ $? == 0 ]; then
            echo -e " - $OK generate => $ppath"
        else
            echo -e " - $ERROR generate => $ppath"
        fi
    done
}
gen_config() {
    # settings.py
    echo -e " - configurating: config.template"
    envsubst > $WORKDIR/conf/settings.py.ctmpl <  $WORKDIR/conf/settings.py.ctmpl.template

    # consul
    echo -e " - configurating: consul.hcl"
    envsubst > $WORKDIR/conf/consul.hcl < $WORKDIR/conf/consul.hcl.template

    # suppervisor
    echo -e " - configurating: supervisor"
    cp $WORKDIR/conf/supervisord.conf /etc
    chmod 644 /etc/supervisord.conf

    # permission
    echo -e " - configurating: permission"
    mkdir -p /data/logs
    chown -R worker:worker /app /data
}

init() {

    echo -e "*** STEP: generate thrift file..."
    gen_thrift
    echo -e "*** STEP: generate proto file..."
    gen_proto
    echo -e "*** STEP: generate config file..."
    gen_config

}

## run command
# check for the expected command
if [ "$1" = 'supervisord' ]; then
    # run command
    init
    # use gosu to drop to a non-root user
    echo -e "*** STEP: running supervisor..."
    exec gosu worker "$@"
fi

# else default to run whatever the user wanted like "bash"
exec "$@"
