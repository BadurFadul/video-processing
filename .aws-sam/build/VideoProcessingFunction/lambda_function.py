import os
import logging
import tempfile
import urllib
import ffmpeg
import boto3

from preview import generate_video_preview, calculate_sample_seconds

s3_client = boto3.client('s3')

samples = int(os.getenv("samples", "4"))
sample_duration = int(os.getenv("sample_duration", "2"))
scale = os.getenv("scale")
format = os.getenv("format", "mp4")

s3_output_prefix = os.getenv("s3_output_prefix", "output")
debug = os.getenv("debug", "false").lower() == "true"

def lambda_handler(event, context):
    s3_bucket_name = event['Records'][0]['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')

    # Extract the file name and add "_prev" suffix
    file_name, file_ext = os.path.basename(key).split(".")
    output_key = os.path.join(s3_output_prefix, file_name + "_prev." + format)
    out_file = tempfile.NamedTemporaryFile(delete=True)
    
    # Create a temporary file for downloaded input
    tmp_input_file = os.path.join('/tmp', os.path.basename(key))
    
    try:
        # Download file to local temporary storage instead of using presigned URL
        logging.info(f"Downloading file {key} from bucket {s3_bucket_name}")
        s3_client.download_file(s3_bucket_name, key, tmp_input_file)
    except Exception as e:
        logging.error("Failed to download input file")
        raise e

    try:
        # Use local file path instead of S3 URL
        probe = ffmpeg.probe(tmp_input_file)
        video_duration = float(probe["format"]["duration"])
    except ffmpeg.Error as e:
        logging.error("failed to get video info")
        logging.error(e.stderr)
        raise e
    finally:
        # Try to ensure we always log the error details
        if 'e' in locals() and hasattr(e, 'stderr'):
            logging.error(e.stderr)

    # Calculate sample_seconds based on the video duration, sample_duration and number of samples
    sample_seconds = calculate_sample_seconds(video_duration, samples, sample_duration)

    # Generate video preview
    try:
        # Use local file instead of URL
        generate_video_preview(tmp_input_file, out_file.name, sample_duration, sample_seconds, scale, format, quiet=not debug)
    except Exception as e:
        logging.error("failed to generate video preview")
        raise e

    # Upload video file to S3 bucket.
    try:
        output_bucket = os.getenv("output_bucket")
        s3_client.upload_file(out_file.name, output_bucket, output_key)
    except Exception as e:
        logging.error("failed to upload video preview")
        raise e
    
    # Clean up temporary files
    try:
        if os.path.exists(tmp_input_file):
            os.remove(tmp_input_file)
    except Exception as e:
        logging.warning(f"Failed to clean up temporary file: {e}")
    
    # Return success response
    return {
        'statusCode': 200,
        'body': {
            'message': 'Video preview generated successfully',
            'input_key': key,
            'output_key': output_key,
            'bucket': s3_bucket_name
        }
    }

