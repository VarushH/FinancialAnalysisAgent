import boto3

cloudwatch = boto3.client("cloudwatch")

def publish_metric(name: str, value: float):
    """
    Publishes custom CloudWatch metrics.
    """
    cloudwatch.put_metric_data(
        Namespace="FinancialMultiAgent",
        MetricData=[
            {
                "MetricName": name,
                "Value": value,
                "Unit": "Count"
            }
        ]
    )
