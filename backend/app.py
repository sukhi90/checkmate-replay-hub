import json

def lambda_handler(event, context):
    print("Received event: " + json.dumps(event, indent=2))
    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        'body': json.dumps({
            'message': 'Hello from Checkmate Replay Hub Backend!',
            'status': 'success'
        })
    }
