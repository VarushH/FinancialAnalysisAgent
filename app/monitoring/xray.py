from aws_xray_sdk.core import xray_recorder, patch_all

patch_all()

def trace_subsegment(name: str):
    """
    Creates X-Ray subsegment for tracing.
    """
    return xray_recorder.in_subsegment(name)
