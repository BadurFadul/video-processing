# Video Processing Application

This application creates preview clips from uploaded videos using AWS Lambda and S3.

## Prerequisites

- AWS CLI installed and configured
- AWS SAM CLI installed
- Python 3.12
- FFmpeg must be included in the Lambda deployment package

## Deployment

1. Build the application:
   ```
   sam build
   ```

2. Deploy the application:
   ```
   sam deploy --guided
   ```

3. Follow the prompts to deploy the application.

## Usage

1. Upload a video file to the input S3 bucket.
2. The Lambda function will automatically process the video and create a preview.
3. The preview will be available in the output S3 bucket.

## Parameters

- `Samples`: Number of samples to take from the video (default: 4)
- `SampleDuration`: Duration of each sample in seconds (default: 2)
- `Format`: Output video format (default: mp4)

## Cleanup

To delete the application: 