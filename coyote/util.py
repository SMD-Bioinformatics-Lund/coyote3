import os
from copy import deepcopy

from flask import current_app as app

"""
List of util functions, mostly shared across
CDM main, trends and API blueprints.
"""


def assay_config(assay_name: str = None) -> dict:
    conf = app.config["ASSAYS"]
    if assay_name is not None:
        conf = conf[assay_name]

    return deepcopy(conf)


def table_config() -> dict:
    conf = app.config["TABLE"]
    return deepcopy(conf)


def cutoff_config(assay_name, sample_type=None) -> dict:
    try:
        conf = app.config["CUTOFFS"][assay_name]
        if sample_type is not None:
            conf = conf.get(sample_type)
    except KeyError:
        err = f"No cutoffs defined for assay:{assay_name}"
        if sample_type is not None:
            err += f"/sample_type:{sample_type}"
        app.logger.debug(err)
        return {}
    return deepcopy(conf)


def assay_info_vars(assay_name) -> list:
    assay = assay_config(assay_name)
    info = assay.get("sample_info")
    return info


def assay_qc_vars(assay_name) -> list:
    assay = assay_config(assay_name)
    qc = assay.get("sample_qc")
    return qc


def assays_in_assay_group(assay_name: str) -> list:
    return assay_config(assay_name).get("include_assays")





def has_subtypes(assay_name) -> bool:
    assay_conf = assay_config(assay_name)
    return "subtypes" in assay_conf


def get_sample_subtypes(assay_name: str) -> list:
    """
    Get list of available subtypes for assay defined in assays.config
    """
    assay = assay_config(assay_name)
    subtypes = assay.get("subtypes", {})
    subtypes = subtypes.get("subtype_names", None)
    return subtypes


def subtype_id_var(assay_name) -> list:
    if not has_subtypes(assay_name):
        return None

    assay_conf = assay_config(assay_name)

    if "subtype_id_col" not in assay_conf:
        config_path = app.config["PATH_ASSAY_CONFIG"]
        raise AttributeError(
            f"Error in assay config: {config_path}. "
            "subtypes enabled but no subtype_id_col "
            f"defined for {assay_name}."
        )

    return assay_conf["subtype_id_col"]


def assay_exists(assay_name: str) -> bool:
    """Check if assay defined in config"""
    conf = assay_config()
    return assay_name in conf


def assay_names_for_db_query(assay_category_name):
    # Ignore _restored
    assay_names = assay_config(assay_category_name.removesuffix("_restored")).get("include_assays")
    if assay_category_name.endswith("_restored"):
        assay_names = [f"{assay_name}_restored" for assay_name in assay_names]

    return assay_names


def get_active_branch_name():
    """
    Get curr checked out git branch name. Used to display version name
    in debug mode.

    Credit: https://stackoverflow.com/a/62724213
    """
    from pathlib import Path

    head_dir = Path(".git/HEAD")

    if not os.path.exists(head_dir):
        return "unknown branch"

    with head_dir.open("r") as f:
        content = f.read().splitlines()

        for line in content:
            if line[0:4] == "ref:":
                return line.partition("refs/heads/")[2]
