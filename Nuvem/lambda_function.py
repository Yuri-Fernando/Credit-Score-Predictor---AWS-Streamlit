import json
import os
import boto3
import joblib
import tempfile
from decimal import Decimal
from botocore.exceptions import ClientError

# Cache local da features list para o cold start da Lambda
FEATURES_CACHE_PATH = "/tmp/features.joblib"
features = None

# Clients AWS
s3_client = boto3.client('s3')
runtime_client = boto3.client('sagemaker-runtime')
dynamodb = boto3.resource('dynamodb')

# Variáveis de ambiente
SAGEMAKER_ENDPOINT = os.environ['SAGEMAKER_ENDPOINT']
DYNAMODB_TABLE = os.environ['DYNAMODB_TABLE']
FEATURES_S3_URI = os.environ['FEATURES_S3_URI']
MODEL_VERSION = os.environ.get('MODEL_VERSION', 'v1')

def load_features():
    global features
    if features is None:
        # Checa se features.joblib já está em cache local
        if not os.path.exists(FEATURES_CACHE_PATH):
            bucket, key = parse_s3_uri(FEATURES_S3_URI)
            s3_client.download_file(bucket, key, FEATURES_CACHE_PATH)
        features = joblib.load(FEATURES_CACHE_PATH)
    return features

def parse_s3_uri(s3_uri):
    # s3://bucket/key -> (bucket, key)
    parts = s3_uri.replace("s3://", "").split('/', 1)
    return parts[0], parts[1]

def decimal_default(obj):
    # Para JSON serializar Decimal do DynamoDB
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def lambda_handler(event, context):
    try:
        # Evento deve ser JSON com dados para inferência
        input_json = event if isinstance(event, dict) else json.loads(event)
        
        # Carrega features (cold start)
        features_list = load_features()

        # Prepara payload com ordem correta das features
        data = input_json['data']
        row = [data.get(f, 0) for f in features_list]  # preenche 0 se faltar

        payload = {
            "instances": [row]
        }
        payload_str = json.dumps(payload)

        # Chama endpoint SageMaker
        response = runtime_client.invoke_endpoint(
            EndpointName=SAGEMAKER_ENDPOINT,
            ContentType='application/json',
            Body=payload_str
        )

        result = json.loads(response['Body'].read())
        score = float(result['predictions'][0])

        # Salva no DynamoDB
        table = dynamodb.Table(DYNAMODB_TABLE)
        from datetime import datetime
        import uuid

        request_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        item = {
            'request_id': request_id,
            'timestamp': timestamp,
            'score': Decimal(str(score)),
            'model_version': MODEL_VERSION,
            'input': data
        }
        table.put_item(Item=item)

        # Retorna JSON limpo
        return {
            'statusCode': 200,
            'body': json.dumps({
                'request_id': request_id,
                'score': score,
                'model_version': MODEL_VERSION
            }, default=decimal_default)
        }

    except ClientError as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
    except Exception as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(e)})
        }
