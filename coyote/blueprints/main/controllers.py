import logging
from pprint import pformat

import pymongo
from flask_pymongo import ObjectId

from coyote.extensions import store
from coyote.util import assay_config, assay_info_vars, assay_qc_vars, table_config

logger = logging.getLogger(__name__)


def samples():
    runs = store.runs_collection.find({"hidden": {"$ne": 1}}).sort("run_date", -1)
    return runs


