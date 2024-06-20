from flask import current_app as app
import re

def build_fusion_query(sample_settings, groups) -> dict:
    """_summary_
    This function processes RNA samples and groups, and results in the samples with the fusion events

    Args:
        sample_settings (dict): A dictionary containing settings for the sample. This might include parameters like sample size, sample type, and other relevant configurations.
        groups (list): The group information from the sample

    Returns:
        dict: _description_
    """

    