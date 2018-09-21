#!/bin/bash

# Pull down the newest devel version
cd /websites/webapi/wsgi/releases/devel/
git pull -q
git submodule update --recursive -q

# Update the symlink to point to the newest version
cd /websites/webapi/wsgi/releases/
rm current
ln --symbolic -T `ls -d */ | tail -1` current

# Update the HTML folder
cd /websites/webapi/html/
find -type l -delete
rm index.html

# Manually include the first server version
echo "WSGIScriptAlias /v1/rest    \${releases_path}/v1/server/wsgi/restapi.py" > /websites/webapi/wsgi/releases/releases.conf
echo "WSGIScriptAlias /v1/jsonrpc \${releases_path}/v1/server/wsgi/jsonapi.py" >> /websites/webapi/wsgi/releases/releases.conf

# Generate the new configurations
for D in ../wsgi/releases/*/; do
    export base=`basename ${D}`
    ln --symbolic -T ${D}/server/html $base
    echo "<a href='$base/'>$base</a><br>" >> index.html

    echo "WSGIDaemonProcess $base python-home=\${releases_path}/$base/server/wsgi/env" >> /websites/webapi/wsgi/releases/wsgi_process_groups.conf

    cat >> /websites/webapi/wsgi/releases/releases.conf << EOF

WSGIDaemonProcess $base python-home=\${releases_path}/$base/server/wsgi/env
WSGIProcessGroup $base
WSGIApplicationGroup %{GLOBAL}
<Location /$base>
        WSGIProcessGroup $base
</Location>
WSGIScriptAlias /$base         \${releases_path}/$base/server/wsgi/restapi.py
EOF

    #echo "WSGIScriptAlias /$base         \${releases_path}/$base/server/wsgi/restapi.py" >> /websites/webapi/wsgi/releases/releases.conf
done

# Restart apache
sudo /root/send_HUP_to_apache.sh &> /dev/null

# Run the tests
errors=0
#for D in ../wsgi/releases/*/; do
#    ${D}/server/wsgi/utils/test.py "http://webapi-master.bmrb.wisc.edu/`basename ${D}`"
#    if [ $? -ne 0 ]
#    then
#        errors=$((errors+1))
#    fi
#done

if [ $errors -ne 0 ] && [ "$1" != "-force" ]
then
    echo "Not syncing because at least one error happened."
else
    if [ "$1" == "-force" ] && [ $errors -ne 0 ]
    then
        echo "Syncing despite errors because of -force option."
    fi
    # Sync the wsgi and html directories
    rsync -aq --no-motd --delete /websites/webapi/html/ rsync://web@webapi:/html/
    rsync -aq --no-motd --delete /websites/webapi/wsgi/ rsync://web@webapi:/wsgi/
fi
