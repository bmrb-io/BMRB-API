# Load the configuration file
import os

import simplejson as json

_querymod_dir = os.path.dirname(os.path.realpath(__file__))
_config_loc = os.path.join(_querymod_dir, "..", "..", "..", "..", "api_config.json")
if not os.path.isfile(_config_loc):
    _config_loc = os.path.join(_querymod_dir, "..", "configuration.json")
configuration = json.loads(open(_config_loc, "r").read())
