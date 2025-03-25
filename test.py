#!/usr/bin/env python3
# lambda_performance_test.py

import boto3
import time
import statistics
import json
import concurrent.futures
import argparse
import os
import psutil
import matplotlib.pyplot as plt
from datetime import datetime
import requests

class LambdaPerformanceTester:
    def __init__(self, input_bucket, output_bucket, test_videos=None):
        self.s3_client = boto3.client('s3')
        self.lambda_client = boto3.client('lambda')
        self.logs_client = boto3.client('logs')
        
        self.input_bucket = input_bucket
        self.output_bucket = output_bucket
        
        self.test_videos = test_videos or [
            "https://video-preview.se-sto-1.linodeobjects.com/input/videoplayback.mp4", # small video (~10MB)
            "https://video-preview.se-sto-1.linodeobjects.com/input/Medium.mp4",  # Medium video (~50MB)
            "https://video-preview.se-sto-1.linodeobjects.com/input/Large.mp4", # Large video (~100MB)
        ]
        
        self.results = {
            "cold_start": [],
            "warm_start": [],
            "latency": [],
            "throughput": {},
            "execution_time": [],
            "resource_usage": []
        }
        
    def upload_video_and_wait_for_preview(self, video_path, wait_for_output=True):
        """Upload a video to S3 and wait for the preview to be generated"""
        video_name = os.path.basename(video_path)
        output_key = f"previews/{os.path.splitext(video_name)[0]}_prev.mp4"
        
        # Upload the video to trigger Lambda
        start_time = time.time()
        print(f"  Uploading {video_name} to {self.input_bucket}...")
        with open(video_path, 'rb') as f:
            self.s3_client.upload_fileobj(f, self.input_bucket, video_name)
        
        # Wait for the preview to appear in the output bucket
        if wait_for_output:
            print(f"  Waiting for preview {output_key} in {self.output_bucket}...")
            preview_found = False
            max_wait_time = 300  # 5 minutes max wait
            wait_start = time.time()
            
            while not preview_found and (time.time() - wait_start < max_wait_time):
                try:
                    self.s3_client.head_object(Bucket=self.output_bucket, Key=output_key)
                    preview_found = True
                except Exception:
                    time.sleep(1)
            
            if preview_found:
                end_time = time.time()
                processing_time = end_time - start_time
                print(f"  ✅ Preview generated in {processing_time:.2f} seconds")
                return processing_time
            else:
                print(f"  ❌ Preview not found after waiting {max_wait_time} seconds")
                return None
        
        return None
    
    def test_cold_start(self, num_tests=3):
        """Test cold start time by forcing new lambda instances"""
        print("\n🧊 Testing cold start time...")
        cold_starts = []
        
        for i in range(num_tests):
            print(f"  Cold start test {i+1}/{num_tests}")
            # Force a new instance by waiting long enough for the Lambda to be recycled
            if i > 0:
                time.sleep(600)  # Wait 10 minutes to ensure Lambda is recycled
            
            processing_time = self.upload_video_and_wait_for_preview(self.test_videos[0])
            if processing_time:
                cold_starts.append(processing_time)
        
        self.results["cold_start"] = cold_starts
        return cold_starts
    
    def test_warm_start(self, num_tests=10):
        """Test warm start time with repeated requests"""
        print("\n🔥 Testing warm start time...")
        warm_starts = []
        
        # First upload to ensure Lambda is warm
        print("  Warming up Lambda...")
        self.upload_video_and_wait_for_preview(self.test_videos[0])
        time.sleep(3)  # Brief pause
        
        for i in range(num_tests):
            print(f"  Warm start test {i+1}/{num_tests}")
            processing_time = self.upload_video_and_wait_for_preview(self.test_videos[0])
            if processing_time:
                warm_starts.append(processing_time)
            time.sleep(3)  # Brief pause between tests
        
        self.results["warm_start"] = warm_starts
        return warm_starts
    
    def test_latency(self, num_tests=10):
        """Test latency with varying video sizes"""
        print("\n⏱️ Testing latency across different video sizes...")
        latency_results = {video_path: [] for video_path in self.test_videos}
        
        for video_path in self.test_videos:
            video_name = os.path.basename(video_path)
            print(f"  Testing with video: {video_name}")
            
            for i in range(num_tests):
                print(f"  Test {i+1}/{num_tests}")
                processing_time = self.upload_video_and_wait_for_preview(video_path)
                if processing_time:
                    latency_results[video_path].append(processing_time)
                time.sleep(3)  # Brief pause between tests
        
        self.results["latency"] = latency_results
        return latency_results
    
    def test_throughput(self, concurrent_uploads=[1, 5, 10, 20]):
        """Test throughput with different levels of concurrency"""
        print("\n🚀 Testing throughput with concurrent uploads...")
        throughput_results = {}
        
        for num_concurrent in concurrent_uploads:
            print(f"  Testing with {num_concurrent} concurrent uploads")
            
            # Function to upload a video and track time
            def upload_video():
                return self.upload_video_and_wait_for_preview(self.test_videos[0], wait_for_output=True)
            
            # Execute concurrent uploads
            start_time = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
                results = list(executor.map(lambda _: upload_video(), range(num_concurrent)))
            end_time = time.time()
            
            # Calculate throughput
            total_time = end_time - start_time
            successful_uploads = sum(1 for r in results if r is not None)
            
            if successful_uploads > 0:
                throughput = successful_uploads / total_time
                avg_processing_time = statistics.mean([r for r in results if r is not None])
                throughput_results[num_concurrent] = {
                    "videos_per_second": throughput,
                    "avg_processing_time": avg_processing_time,
                    "total_time": total_time
                }
                print(f"  ✅ Throughput: {throughput:.2f} videos/second")
                print(f"  ✅ Average processing time: {avg_processing_time:.2f} seconds")
            else:
                print("  ❌ No successful uploads")
        
        self.results["throughput"] = throughput_results
        return throughput_results
    
    def get_lambda_metrics(self):
        """Get Lambda metrics from CloudWatch"""
        print("\n📊 Retrieving Lambda metrics...")
        # This is a simplified placeholder - actual implementation would use the CloudWatch API
        # to get memory usage, execution duration, etc.
        return {"memory": "N/A", "duration": "N/A"}
    
    def run_all_tests(self):
        """Run all performance tests"""
        print(f"Starting performance tests for Lambda processing videos from {self.input_bucket} to {self.output_bucket}")
        self.test_warm_start(num_tests=3)  # Reduced number for faster testing
        self.test_latency(num_tests=2)     # Reduced number for faster testing
        self.test_throughput(concurrent_uploads=[1, 2])
        self.generate_report()
    
    def generate_report(self):
        """Generate a performance report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "input_bucket": self.input_bucket,
            "output_bucket": self.output_bucket,
            "summary": {
                "warm_start": {
                    "avg": statistics.mean(self.results["warm_start"]) if self.results["warm_start"] else None,
                    "min": min(self.results["warm_start"]) if self.results["warm_start"] else None,
                    "max": max(self.results["warm_start"]) if self.results["warm_start"] else None
                }
            },
            "detailed_results": self.results
        }
        
        # Add cold start data if available
        if self.results["cold_start"]:
            report["summary"]["cold_start"] = {
                "avg": statistics.mean(self.results["cold_start"]),
                "min": min(self.results["cold_start"]),
                "max": max(self.results["cold_start"])
            }
        
        # Save report to file
        report_file = f"lambda_performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📊 Performance report saved to {report_file}")
        
        # Generate visualizations
        self._generate_visualizations()
        
        return report
    
    def _generate_visualizations(self):
        """Generate visualization charts for the performance results"""
        # Processing Time by Video Size
        if self.results["latency"]:
            plt.figure(figsize=(12, 6))
            
            video_sizes = []
            avg_times = []
            
            for video_path, times in self.results["latency"].items():
                if times:
                    video_name = os.path.basename(video_path)
                    video_sizes.append(video_name)
                    avg_times.append(statistics.mean(times))
            
            plt.bar(video_sizes, avg_times)
            plt.title("Processing Time by Video Size")
            plt.xlabel("Video")
            plt.ylabel("Average Processing Time (seconds)")
            plt.savefig("processing_time_by_size.png")
        
        # Cold vs Warm Start Times
        if self.results["cold_start"] and self.results["warm_start"]:
            plt.figure(figsize=(8, 6))
            plt.boxplot([self.results["cold_start"], self.results["warm_start"]], 
                        labels=["Cold Start", "Warm Start"])
            plt.title("Cold Start vs Warm Start Times")
            plt.ylabel("Time (seconds)")
            plt.savefig("start_times_comparison.png")
        
        # Throughput
        if self.results["throughput"]:
            concurrency = list(self.results["throughput"].keys())
            throughput = [self.results["throughput"][c]["videos_per_second"] for c in concurrency]
            
            plt.figure(figsize=(10, 6))
            plt.plot(concurrency, throughput, marker='o')
            plt.title("Throughput vs Concurrency")
            plt.xlabel("Concurrent Uploads")
            plt.ylabel("Videos Processed per Second")
            plt.grid(True)
            plt.savefig("throughput.png")

    def test_resource_usage(self, num_tests=3):
        """Test resource usage during function execution"""
        print("\n💻 Testing resource usage...")
        resource_results = []
        
        for i in range(num_tests):
            print(f"  Resource test {i+1}/{num_tests}")
            # Choose a medium-sized video for resource tests
            video_url = self.test_videos[min(1, len(self.test_videos)-1)]
            
            # Record initial memory usage
            initial_process = psutil.Process(os.getpid())
            initial_memory = initial_process.memory_info().rss / 1024 / 1024  # Convert to MB
            initial_cpu_percent = psutil.cpu_percent(interval=None)
            
            # Start timing
            start_time = time.time()
            
            # Make request with resource metrics flag
            response = requests.post(
                self.function_url,
                headers={"Content-Type": "application/json"},
                json={"url": video_url, "include_metrics": "true"}
            )
            
            # End timing
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Measure final resource usage
            final_memory = initial_process.memory_info().rss / 1024 / 1024  # Convert to MB
            final_cpu_percent = psutil.cpu_percent(interval=None)
            
            if response.status_code == 200:
                # Try to get function-side metrics if available
                function_resources = {}
                try:
                    response_data = response.json()
                    if 'metrics' in response_data:
                        function_resources = response_data['metrics']
                except (ValueError, KeyError):
                    # Function might not return metrics
                    pass
                
                # Store results
                result = {
                    "timestamp": datetime.now().isoformat(),
                    "video": os.path.basename(video_url),
                    "execution_time": execution_time,
                    "client_memory_used_mb": final_memory - initial_memory,
                    "client_cpu_percent": final_cpu_percent - initial_cpu_percent,
                    "function_resources": function_resources
                }
                resource_results.append(result)
                print(f"  ✅ Execution time: {execution_time:.4f} seconds")
                print(f"  ✅ Client memory used: {final_memory - initial_memory:.2f} MB")
                print(f"  ✅ Client CPU usage: {final_cpu_percent - initial_cpu_percent:.2f}%")
                if function_resources:
                    print(f"  ✅ Function memory used: {function_resources.get('memory_used_mb', 'N/A')} MB")
                    print(f"  ✅ Function execution time: {function_resources.get('execution_time_ms', 'N/A')} ms")
            else:
                print(f"  ❌ Error during resource test: {response.status_code}")
                print(response.text)
        
        self.results["resource_usage"] = resource_results
        self.results["execution_time"] = [r["execution_time"] for r in resource_results]
        return resource_results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Performance testing for Lambda video processing")
    parser.add_argument("--input-bucket", required=True, help="S3 bucket for input videos")
    parser.add_argument("--output-bucket", required=True, help="S3 bucket for output previews")
    parser.add_argument("--video-folder", default="./test_videos", help="Folder containing test videos")
    args = parser.parse_args()
    
    # Find test videos in the specified folder
    test_videos = [os.path.join(args.video_folder, f) for f in os.listdir(args.video_folder) 
                  if f.endswith(('.mp4', '.MP4'))]
    
    if not test_videos:
        print(f"No test videos found in {args.video_folder}. Please add some .mp4 files.")
        exit(1)
    
    # Sort by file size (smallest to largest)
    test_videos.sort(key=lambda f: os.path.getsize(f))
    
    print(f"Found {len(test_videos)} test videos: {[os.path.basename(v) for v in test_videos]}")
    
    tester = LambdaPerformanceTester(
        input_bucket=args.input_bucket,
        output_bucket=args.output_bucket,
        test_videos=test_videos
    )
    tester.run_all_tests()