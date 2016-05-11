## Help for API administrator

### Performing a new release

#### Development-side steps

To release a new version of the server first create a new release from the
folder where development has taken place. (In all the following steps replace
X.X with the version number of the release.)

```bash
git tag -a vX.X -m "Version description." -s
git push origin vX.X
```

#### Server-side steps

First check out the repository from GitHub (and also check out the dependent
repositories from GitHub):

```bash
cd /raid/www/bmrbapi/
git clone --recursive https://github.com/uwbmrb/BMRB-API.git vX.X
cd vX.X
git checkout tags/vX.X -b vX.X
cd ..
ln -snf vX.X/ current
```

Then set up the symlinks:

```bash
cd /raid/www/webapi/html/
ln --symbolic /raid/www/bmrbapi/vX.X/server/html/ vX.X
```

Finally, add the relevant entries to the Apache configuration file
`releases.conf` in `apache_config_dir/includes/`
