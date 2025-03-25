#!/usr/bin/env python3
# performance_test.py

import requests
import time
import statistics
import json
import concurrent.futures
import argparse
import os
import psutil
import matplotlib.pyplot as plt
from datetime import datetime

class FunctionPerformanceTester:
    def __init__(self, function_url, test_videos=None):
        self.function_url = function_url
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
        
    def test_cold_start(self, num_tests=3):
        """Test cold start time by forcing new container instances"""
        print("\n🧊 Testing cold start time...")
        cold_starts = []
        
        for i in range(num_tests):
            print(f"  Cold start test {i+1}/{num_tests}")
            # Force a new instance by waiting or using a unique parameter
            if i > 0:
                time.sleep(60)  # Wait for instance to be recycled (adjust based on your function idle timeout)
            
            start_time = time.time()
            response = requests.post(
                self.function_url,
                headers={"Content-Type": "application/json"},
                json={"url": self.test_videos[0], "force_cold": str(time.time())}
            )
            end_time = time.time()
            
            if response.status_code == 200:
                cold_start_time = end_time - start_time
                cold_starts.append(cold_start_time)
                print(f"  ✅ Cold start time: {cold_start_time:.4f} seconds")
            else:
                print(f"  ❌ Error during cold start test: {response.status_code}")
                print(response.text)
        
        self.results["cold_start"] = cold_starts
        return cold_starts
    
    def test_warm_start(self, num_tests=10):
        """Test warm start time with repeated requests"""
        print("\n🔥 Testing warm start time...")
        warm_starts = []
        
        # Make a request to ensure function is warmed up
        requests.post(
            self.function_url,
            headers={"Content-Type": "application/json"},
            json={"url": self.test_videos[0], "warmup": "true"}
        )
        time.sleep(1)  # Give system a moment
        
        for i in range(num_tests):
            print(f"  Warm start test {i+1}/{num_tests}")
            start_time = time.time()
            response = requests.post(
                self.function_url,
                headers={"Content-Type": "application/json"},
                json={"url": self.test_videos[0]}
            )
            end_time = time.time()
            
            if response.status_code == 200:
                warm_start_time = end_time - start_time
                warm_starts.append(warm_start_time)
                print(f"  ✅ Warm start time: {warm_start_time:.4f} seconds")
            else:
                print(f"  ❌ Error during warm start test: {response.status_code}")
        
        self.results["warm_start"] = warm_starts
        return warm_starts
    
    def test_latency(self, num_tests=10):
        """Test latency with varying video sizes"""
        print("\n⏱️ Testing latency across different video sizes...")
        latency_results = {video_url: [] for video_url in self.test_videos}
        
        for video_url in self.test_videos:
            print(f"  Testing with video: {os.path.basename(video_url)}")
            for i in range(num_tests):
                start_time = time.time()
                response = requests.post(
                    self.function_url,
                    headers={"Content-Type": "application/json"},
                    json={"url": video_url}
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    latency = end_time - start_time
                    latency_results[video_url].append(latency)
                    print(f"  ✅ Request {i+1}/{num_tests}: Latency = {latency:.4f} seconds")
                else:
                    print(f"  ❌ Error during latency test: {response.status_code}")
        
        self.results["latency"] = latency_results
        return latency_results
    
    def test_throughput(self, concurrent_requests=[1, 5, 10, 20]):
        """Test throughput with different levels of concurrency"""
        print("\n🚀 Testing throughput with concurrent requests...")
        throughput_results = {}
        
        for num_concurrent in concurrent_requests:
            print(f"  Testing with {num_concurrent} concurrent requests")
            
            # Function to make a single request
            def make_request():
                start_time = time.time()
                response = requests.post(
                    self.function_url,
                    headers={"Content-Type": "application/json"},
                    json={"url": self.test_videos[0]}
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    return end_time - start_time
                else:
                    print(f"  ❌ Error during throughput test: {response.status_code}")
                    return None
            
            # Execute concurrent requests
            start_time = time.time()
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
                results = list(executor.map(lambda _: make_request(), range(num_concurrent)))
            end_time = time.time()
            
            # Calculate throughput
            total_time = end_time - start_time
            successful_requests = sum(1 for r in results if r is not None)
            
            if successful_requests > 0:
                throughput = successful_requests / total_time
                avg_response_time = statistics.mean([r for r in results if r is not None])
                throughput_results[num_concurrent] = {
                    "requests_per_second": throughput,
                    "avg_response_time": avg_response_time,
                    "total_time": total_time
                }
                print(f"  ✅ Throughput: {throughput:.2f} requests/second")
                print(f"  ✅ Average response time: {avg_response_time:.4f} seconds")
            else:
                print("  ❌ No successful requests")
        
        self.results["throughput"] = throughput_results
        return throughput_results
    
    def test_resource_usage(self, num_tests=3):
        """Test resource usage for different video sizes"""
        print("\n💻 Testing resource usage...")
        resource_results = []
        
        for video_url in self.test_videos:
            print(f"  Testing with video: {os.path.basename(video_url)}")
            
            # Get initial resource usage
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            start_time = time.time()
            response = requests.post(
                self.function_url,
                headers={"Content-Type": "application/json", "X-Track-Resources": "true"},
                json={"url": video_url}
            )
            execution_time = time.time() - start_time
            
            if response.status_code == 200:
                # Get final resource usage
                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                
                # Try to extract resource usage from response
                try:
                    function_resources = response.json().get("resources", {})
                except (ValueError, KeyError):
                    function_resources = {}
                
                result = {
                    "video": os.path.basename(video_url),
                    "execution_time": execution_time,
                    "client_memory_used_mb": final_memory - initial_memory,
                    "function_resources": function_resources
                }
                resource_results.append(result)
                print(f"  ✅ Execution time: {execution_time:.4f} seconds")
                print(f"  ✅ Client memory used: {final_memory - initial_memory:.2f} MB")
            else:
                print(f"  ❌ Error during resource test: {response.status_code}")
        
        self.results["resource_usage"] = resource_results
        self.results["execution_time"] = [r["execution_time"] for r in resource_results]
        return resource_results
    
    def run_all_tests(self):
        """Run all performance tests"""
        self.test_cold_start()
        self.test_warm_start()
        self.test_latency()
        self.test_throughput()
        self.test_resource_usage()
        self.generate_report()
        
    def generate_report(self):
        """Generate a performance report"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "function_url": self.function_url,
            "summary": {
                "cold_start": {
                    "avg": statistics.mean(self.results["cold_start"]) if self.results["cold_start"] else None,
                    "min": min(self.results["cold_start"]) if self.results["cold_start"] else None,
                    "max": max(self.results["cold_start"]) if self.results["cold_start"] else None
                },
                "warm_start": {
                    "avg": statistics.mean(self.results["warm_start"]) if self.results["warm_start"] else None,
                    "min": min(self.results["warm_start"]) if self.results["warm_start"] else None,
                    "max": max(self.results["warm_start"]) if self.results["warm_start"] else None
                },
                "execution_time": {
                    "avg": statistics.mean(self.results["execution_time"]) if self.results["execution_time"] else None,
                    "min": min(self.results["execution_time"]) if self.results["execution_time"] else None,
                    "max": max(self.results["execution_time"]) if self.results["execution_time"] else None
                }
            },
            "detailed_results": self.results
        }
        
        # Save report to file
        report_file = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📊 Performance report saved to {report_file}")
        
        # Generate some visualizations
        self._generate_visualizations()
        
        return report
    
    def _generate_visualizations(self):
        """Generate visualization charts for the performance results"""
        # Cold vs Warm Start Times
        plt.figure(figsize=(12, 6))
        plt.boxplot([self.results["cold_start"], self.results["warm_start"]], labels=["Cold Start", "Warm Start"])
        plt.title("Cold Start vs Warm Start Times")
        plt.ylabel("Time (seconds)")
        plt.savefig("start_times_comparison.png")
        
        # Throughput
        if self.results["throughput"]:
            concurrency = list(self.results["throughput"].keys())
            throughput = [self.results["throughput"][c]["requests_per_second"] for c in concurrency]
            
            plt.figure(figsize=(12, 6))
            plt.plot(concurrency, throughput, marker='o')
            plt.title("Throughput vs Concurrency")
            plt.xlabel("Concurrent Requests")
            plt.ylabel("Requests per Second")
            plt.grid(True)
            plt.savefig("throughput_analysis.png")
        
        # Latency by Video Size
        if self.results["latency"]:
            plt.figure(figsize=(12, 6))
            video_labels = [os.path.basename(url) for url in self.results["latency"].keys()]
            latencies = [self.results["latency"][url] for url in self.results["latency"].keys()]
            
            plt.boxplot(latencies, labels=video_labels)
            plt.title("Latency by Video Size")
            plt.ylabel("Time (seconds)")
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig("latency_by_video_size.png")
        
        print("📈 Visualization charts have been generated.")


def main():
    parser = argparse.ArgumentParser(description='Test the performance of an OpenFaaS function')
    parser.add_argument('--url', type=str, default='http://127.0.0.1:8080/function/video-preview',
                        help='URL of the function to test')
    parser.add_argument('--videos', type=str, nargs='+',
                        help='List of video URLs to test with')
    
    args = parser.parse_args()
    
    tester = FunctionPerformanceTester(args.url, args.videos)
    tester.run_all_tests()


if __name__ == "__main__":
    main()