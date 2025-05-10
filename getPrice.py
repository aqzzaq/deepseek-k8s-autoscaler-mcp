import boto3
from google.oauth2 import service_account
from google.cloud import billing_v1
import json
import requests

# Azure Configuration
AZURE_INSTANCE_TYPE = "Standard_B2s_v2"
AZURE_SKU_NAME = "B2s v2"
AZURE_PRODUCT_NAME = "Virtual Machines Bsv2 Series"
AZURE_REGION= "eastus"


# AWS Configuration
AWS_ACCESS_KEY = ""
AWS_SECRET_KEY = ""
AWS_REGION = "us-east-1"
AWS_INSTANCE_TYPE = "t2.medium"

# GCP Configuration 
GCP_PROJECT = ""
GCP_INSTANCE_TYPE = "e2-micro"
GCP_CREDENTIALS_PATH = ""
GCP_BILLING_SERVICE_ID = ""

def get_aws_price():
    """Fixed AWS Price List API response parsing"""
    try:
        session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )

        pricing = session.client('pricing')
        response = pricing.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
                {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': AWS_INSTANCE_TYPE},
                {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': 'US East (N. Virginia)'},
                {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
                {'Type': 'TERM_MATCH', 'Field': 'marketoption', 'Value': 'OnDemand'},
                {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
                {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'}
             #   {'Type': 'TERM_MATCH', 'Field': 'capacitystatus"', 'Value': 'Used'}
            ]
        )
       # print(response)
        price_data = json.loads(response['PriceList'][0])
        on_demand = price_data['terms']['OnDemand']
        price_dimensions = next(iter(on_demand.values()))['priceDimensions']
        return float(next(iter(price_dimensions.values()))['pricePerUnit']['USD'])

    except (KeyError, json.JSONDecodeError) as e:
        print(f"AWS Data Error: {str(e)}")
        return None

def get_azure_price():
    api_url = "https://prices.azure.com/api/retail/prices"
    query = (
        f"armRegionName eq '{AZURE_REGION}' "
        f"and armSkuName eq '{AZURE_INSTANCE_TYPE}' "
        f"and priceType eq 'Consumption' "
        f"and meterName eq '{AZURE_SKU_NAME}' "
        f"and productName eq '{AZURE_PRODUCT_NAME}' "
    )
    response = requests.get(api_url, params={'$filter': query})
    #print(response.text)
    json_data = json.loads(response.text)
    price_data = json_data['Items'][0]
    return float(price_data['retailPrice'])
   


def get_gcp_price():
    """Updated for Cloud Billing API v1 with ServicesClient"""
    try:

        credentials = service_account.Credentials.from_service_account_file(GCP_CREDENTIALS_PATH)
        client = billing_v1.CloudCatalogClient(credentials=credentials)
        
        # List SKUs for Compute Engine service[1,8](@ref)
        skus = client.list_skus(parent=f"services/{GCP_BILLING_SERVICE_ID}")
        for sku in skus:
            if "E2" in sku.description and sku.category.usage_type == "OnDemand" and "us-central1" in sku.service_regions:
               # print(sku)
                return sku.pricing_info[0].pricing_expression.tiered_rates[0].unit_price.nanos * 1e-9
        return None

    except Exception as e:
        print(f"GCP API Error: {str(e)}")
        return None

# ========================
# COMPARISON LOGIC
# ========================

def compare_prices():
    """Safe price formatting with type validation"""
    prices = {
        'AWS': get_aws_price(),
        'Azure': get_azure_price(),
        'GCP': get_gcp_price()
    }

    print("\nCurrent Hourly Prices:")
    for provider, price in prices.items():
        # Handle None and numeric formatting[9,10](@ref)
        formatted_price = f"{price:.4f}" if isinstance(price, (float, int)) else "N/A"
        print(f"{provider}: ${formatted_price}/hr")

    valid_prices = {k:v for k,v in prices.items() if v is not None}
    if valid_prices:
        cheapest = min(valid_prices, key=valid_prices.get)
        return f"\nCheapest Provider: {cheapest} (${valid_prices[cheapest]:.4f}/hr)"
    return "\nNo valid pricing data available"

if __name__ == "__main__":
    print(compare_prices())