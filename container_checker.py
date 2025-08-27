import argparse
import os
import requests
import json
from datetime import datetime
from urllib.parse import urlparse
import glob

# This script checks the availability and last published date of container images
# from various registries, including Docker Hub, GitHub Container Registry,
# and Codeberg Container Registry.

TARGET_DIRECTORY = '.'

def get_docker_hub_auth_token():
    """Fetches a Docker Hub authentication token."""
    url = "https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/ubuntu:pull"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()['token']
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Docker Hub token: {e}")
        return None

def check_image_availability(image_name, github_token=None, codeberg_token=None, print_payload=False):
    """
    Checks the availability and last published date of a container image.
    Supports Docker Hub, GHCR, and Codeberg.
    """
    availability_status = "Not Found"
    last_published_date = "N/A"
    
    # Pre-parse the image name to determine the registry
    registry = "docker.io"
    path = image_name
    
    if '/' in image_name:
        parts = image_name.split('/')
        # Check if the first part is a known registry
        if parts[0].endswith('.io') or parts[0].endswith('.org'):
            registry = parts[0]
            path = '/'.join(parts[1:])
        
    print(f"Checking {image_name}...")

    try:
        # --- Docker Hub Logic ---
        if registry == "docker.io":
            # For official images like `python`, use library/python
            if '/' not in image_name:
                path = f"library/{path}"
            
            token = get_docker_hub_auth_token()
            if not token:
                print("Skipping Docker Hub check due to failed authentication.")
                return image_name, "Error", "N/A"
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.docker.distribution.manifest.v2+json"
            }
            url = f"https://registry-1.docker.io/v2/{path}/manifests/latest"
            
            response = requests.head(url, headers=headers, timeout=10)
            if print_payload:
                print(f"API Payload (HEAD): {response.headers}")

            if response.status_code == 200:
                availability_status = "Available"
                if "Docker-Content-Digest" in response.headers:
                    # Get image digest to fetch manifest
                    digest = response.headers["Docker-Content-Digest"]
                    manifest_url = f"https://registry-1.docker.io/v2/{path}/manifests/{digest}"
                    manifest_response = requests.get(manifest_url, headers=headers, timeout=10)
                    if print_payload:
                        print(f"API Payload (GET): {manifest_response.json()}")
                    
                    if manifest_response.status_code == 200:
                        manifest_data = manifest_response.json()
                        if 'history' in manifest_data and manifest_data['history']:
                            last_layer = json.loads(manifest_data['history'][0]['v1Compatibility'])
                            created_str = last_layer.get('created', 'N/A')
                            if created_str != 'N/A':
                                created_date = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                                last_published_date = created_date.strftime("%Y-%m-%d")

        # --- GitHub Container Registry (GHCR) Logic ---
        elif registry == "ghcr.io":
            if not github_token:
                print("Skipping GHCR check: No GitHub token provided.")
                availability_status = "Auth Required"
            else:
                url = f"https://ghcr.io/v2/{path}/manifests/latest"
                headers = {
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.docker.distribution.manifest.v2+json"
                }
                response = requests.head(url, headers=headers, timeout=10)
                if print_payload:
                    print(f"API Payload (HEAD): {response.headers}")
                
                if response.status_code == 200:
                    availability_status = "Available"
                # Last Published Date is complex to get directly
                last_published_date = "N/A (Complex API)"

        # --- Codeberg Container Registry Logic ---
        elif registry == "codeberg.org":
            if not codeberg_token:
                print("Skipping Codeberg check: No JWT token provided.")
                availability_status = "Auth Required"
            else:
                url = f"https://codeberg.org/v2/{path}/manifests/latest"
                headers = {
                    "Authorization": f"Bearer {codeberg_token}",
                    "Accept": "application/vnd.docker.distribution.manifest.v2+json"
                }
                response = requests.head(url, headers=headers, timeout=10)
                if print_payload:
                    print(f"API Payload (HEAD): {response.headers}")
                
                if response.status_code == 200:
                    availability_status = "Available"
                # Last Published Date is complex to get directly
                last_published_date = "N/A (Complex API)"

        # --- Unknown Registry Logic ---
        else:
            availability_status = "Unknown Registry"
            last_published_date = "N/A"

    except requests.exceptions.RequestException as e:
        availability_status = f"Error: {e}"

    return image_name, availability_status, last_published_date

def get_images_from_json():
    """Parses JSON files in the target directory to extract unique image:tag combinations."""
    images = set()
    print(f"Scanning JSON files in {TARGET_DIRECTORY}...")
    json_files = glob.glob(os.path.join(TARGET_DIRECTORY, '*.json'))
    
    for filename in json_files:
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Recursively search for 'image' and 'tag' keys
                    def find_images(obj):
                        if isinstance(obj, dict):
                            if 'image' in obj and 'tag' in obj:
                                images.add(f"{obj['image']}:{obj['tag']}")
                            for key, value in obj.items():
                                find_images(value)
                        elif isinstance(obj, list):
                            for item in obj:
                                find_images(item)
                    find_images(data)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read or parse {filename}. Error: {e}")
            
    if not images:
        print("No image:tag combinations found in JSON files.")
    else:
        print("\nFound the following unique image:tag combinations:")
        for img in sorted(list(images)):
            print(f"- {img}")
    
    return list(images)

def print_results(results, output_format):
    """Prints the results in the specified format."""
    if output_format == 'json':
        output_data = [
            {"image": r[0], "status": r[1], "last_published": r[2]}
            for r in results
        ]
        print(json.dumps(output_data, indent=4))
    
    elif output_format == 'html':
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Container Image Availability Report</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <style>
                body {
                    font-family: 'Inter', sans-serif;
                }
            </style>
        </head>
        <body class="bg-gray-100 p-8">
            <div class="max-w-4xl mx-auto bg-white rounded-lg shadow-xl p-6">
                <h1 class="text-3xl font-bold text-center mb-6 text-gray-800">Container Image Availability Report</h1>
                <div class="overflow-x-auto rounded-lg">
                    <table class="min-w-full bg-white border border-gray-200">
                        <thead class="bg-blue-600 text-white">
                            <tr>
                                <th class="py-3 px-4 text-left font-semibold">Image</th>
                                <th class="py-3 px-4 text-left font-semibold">Status</th>
                                <th class="py-3 px-4 text-left font-semibold">Last Published</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        for image, status, date in results:
            status_class = "text-green-600 font-medium" if status == "Available" else "text-red-600 font-medium"
            html_content += f"""
                            <tr class="border-t border-gray-200 hover:bg-gray-50">
                                <td class="py-3 px-4 text-gray-700 font-mono">{image}</td>
                                <td class="py-3 px-4 {status_class}">{status}</td>
                                <td class="py-3 px-4 text-gray-500">{date}</td>
                            </tr>
            """
        html_content += """
                        </tbody>
                    </table>
                </div>
            </div>
        </body>
        </html>
        """
        print(html_content)

    elif output_format == 'markdown':
        print("| Image | Status | Last Published |")
        print("|---|---|---|")
        for image, status, date in results:
            print(f"| {image} | {status} | {date} |")
    
    else:  # 'console' is the default
        print("-" * 50)
        print("Image Availability Report")
        print("-" * 50)
        print(f"{'Image':<40} | {'Status':<15} | {'Last Published'}")
        print("-" * 50)
        for image, status, date in results:
            print(f"{image:<40} | {status:<15} | {date}")
        print("-" * 50)

def main():
    """Main function to parse arguments and run the checks."""
    parser = argparse.ArgumentParser(description="Check singlecontainer image availability.")
    parser.add_argument("-i", "--image", type=str,
                        help="Check a single image. Ignores JSON files.")
    parser.add_argument("-g", "--github-token", type=str,
                        help="GitHub Personal Access Token for ghcr.io authentication.")
    parser.add_argument("-c", "--codeberg-token", type=str,
                        help="Codeberg JWT token for codeberg.org authentication.")
    parser.add_argument("-p", "--print-payload", action="store_true",
                        help="Print the raw API payloads for debugging.")
    parser.add_argument("-o", "--output-format", choices=['console', 'json', 'html', 'markdown'],
                        default='console', help="Output format for the results.")

    args = parser.parse_args()
    
    # Use command-line argument if provided, otherwise check environment variables
    github_token = args.github_token or os.environ.get("GITHUB_TOKEN")
    codeberg_token = args.codeberg_token or os.environ.get("CODEBERG_TOKEN")

    images_to_check = []
    if args.image:
        image_to_process = args.image
        if ':' not in image_to_process:
            image_to_process += ':latest'
        images_to_check.append(image_to_process)
    else:
        images_to_check = get_images_from_json()

    if not images_to_check:
        print("No images to check. Exiting.")
        return

    results = []
    for image in images_to_check:
        results.append(check_image_availability(image, github_token, codeberg_token, args.print_payload))
    
    print_results(results, args.output_format)

if __name__ == "__main__":
    main()
