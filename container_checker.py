# A program to extract image and tag information from JSON configuration files,
# including checks for image availability on Docker Hub.

import os
import json
import requests
from tabulate import tabulate
import argparse

# The default directory to search for JSON files.
TARGET_DIRECTORY = './configs'
# The file to exclude from processing.
EXCLUSION_FILE = 'root.json'

def parse_image(image_str, tag_from_json=None):
    """
    Parses an image string to extract the image name and tag (container version).
    Assumes "latest" if no tag is specified.

    Args:
        image_str (str): The full image string, e.g., 'ubuntu:20.04' or 'myrepo/myimage' or `ghcr.io/myrepo/myimage'.

    Returns:
        tuple: A tuple containing registry (str), owner (str), container (str), tag (str).
    """

    # Determine version 'tag' in case it is part of the image, if none then default to 'latest'
    if ':' in image_str:
        image_name, tag = image_str.rsplit(':', 1)
    elif tag_from_json is None:
        image_name = image_str
        tag = 'latest'
    else:
        image_name = image_str
        tag = tag_from_json

    # Split remaining image_name into registry, owner, container for most flexibility across registry APIs
    parts = image_name.split("/", 1)
    if len(parts) == 2 and ("." in parts[0]):
        registry = parts[0]
        remainder = parts[1]
    else:
        # Default to Docker Hub
        registry = "docker.io"
        remainder = image_name

    # Docker Hub official images do not have a user/repo prefix
    if '/' not in image_name:
        container = remainder
        owner = 'library'
        return registry, owner, container,tag
    else:
        # Split image into owner & container
        parts = remainder.split("/", 1)
        owner = parts[0]
        container = parts[1]
        return registry, owner, container, tag

def check_docker_hub_image(owner, image_name, tag, print_payload=False):
    """
    Checks Docker Hub for image availability and last published date.

    Args:
        owner (str): Typically, the repository owner
        image_name (str): The name of the Docker image (e.g., 'nginx', 'myimage').
        tag (str): The specific tag (version) to check.
        print_payload (bool): If True, prints the request headers and payload.

    Returns:
        dict: A dictionary with 'available' (bool or str) and 'last_published' (str).
    """
    # Docker Hub official images do not have a user/repo prefix
    # if '/' not in image_name:
    #     image_name = f"library/{image_name}"

    api_url = f"https://hub.docker.com/v2/repositories/{owner.lower()}/{image_name.lower()}/tags/{tag}"

    if print_payload:
        print(f"Docker Hub API URL: {api_url}")

    try:
        response = requests.get(api_url, timeout=5)
        response.raise_for_status()

        data = response.json()
        
        # Check if the API response contains a 'last_updated' field, which
        # indicates the specific tag exists.
        if 'last_updated' in data:
            return {"available": True, "last_published": data.get('last_updated')}
        else:
            return {"available": False, "last_published": "N/A"}
            
    except requests.exceptions.HTTPError as e:
        # 404 Not Found means the image or tag does not exist
        if e.response.status_code == 404:
            return {"available": False, "last_published": "N/A"}
        return {"available": "Error", "last_published": "N/A"}
    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not check Docker Hub for '{image_name}': {e}")
        return {"available": "Unknown", "last_published": "N/A"}

def check_ghcr_image(owner, image_name, tag, github_token=None, print_payload=False):
    """
    Checks GitHub Container Registry.
    Args:
        owner (str): Typically, the repository owner
        image_name (str): The name of the Docker image (e.g., 'nginx', 'myimage').
        tag (str): The specific tag (version) to check.
        github_token(str): requires classic Personal Access Token, not base64 encoded.
        print_payload (bool): If True, prints the request headers and payload.

    Returns:
        dict: A dictionary with 'available' (bool or str) and 'last_published' (str).

    Requires a GitHub access token with 'read:packages' scope.
    Caveat, it will not consider the version without more complications
    so using github API and not OCI version.
    """
    
    
    api_url = f"https://api.github.com/users/{owner}/packages/container/{image_name}"
    # future, if OCI API is ever more thoroughly implemented, switch over
    # api_url = f"https://ghcr.io/v2/{path}/manifests/{tag}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json"
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        data = response.json()

        if print_payload:
            print(f"API Payload (HEAD): {response.headers}")
            print(f"Body: {response.json()}")
            print (data)

        if 'updated_at' in data:
            return {"available": True, "last_published": data.get('updated_at')}
        else:
            return {"available": False, "last_published": "N/A"}

    except requests.exceptions.HTTPError as e:
        # 404 Not Found means the image or tag does not exist
        if e.response.status_code == 404:
            return {"available": False, "last_published": "N/A"}
        return {"available": "Error", "last_published": "N/A"}
    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not check ghcr.io registry for '{image_name}': {e}")
        return {"available": "Unknown", "last_published": "N/A"}

    # return {"available": "Not Implemented", "last_published": "N/A"}

def check_codeberg_image(owner, image_name, tag, codeberg_token=None, print_payload=False):
    """
    Checks GitHub Container Registry.
    Args:
        owner (str): Typically, the repository owner
        image_name (str): The name of the Docker image (e.g., 'nginx', 'myimage').
        tag (str): The specific tag (version) to check.
        codeberg_token(str): currently does not require a token, might in the future.
        print_payload (bool): If True, prints the request headers and payload.

    Returns:
        dict: A dictionary with 'available' (bool or str) and 'last_published' (str).
    
    Codeberg's registry is based on Gitea's API.
    """
    
    api_url = f"https://codeberg.org/api/v1/packages/{owner}/container/{image_name}/{tag}"
    

    headers = {
        # "Authorization": f"Bearer {codeberg_token}",
        "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.github+json, application/json"
    }
    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        data = response.json()

        if print_payload:
            print(f"API Payload (HEAD): {response.headers}")
            print(f"Body: {data}")

        if 'created_at' in data:
            return {"available": True, "last_published": data.get('created_at')}
        else:
            return {"available": False, "last_published": "N/A"}

    except requests.exceptions.HTTPError as e:
        # 404 Not Found means the image or tag does not exist
        if e.response.status_code == 404:
            return {"available": False, "last_published": "N/A"}
        return {"available": "Error", "last_published": "N/A"}
    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not check codeberg.org registry for '{image_name}': {e}")
        return {"available": "Unknown", "last_published": "N/A"}

        # return {"available": "Not Implemented", "last_published": "N/A"}

def check_image_repository(image_str, tag_from_json=None, github_token=None, codeberg_token=None, print_payload=False):
    """
    Determines the repository and checks image availability and last published date.
    This function acts as a dispatcher based on the image name's prefix.
    Args:
        image_str (str): image string extracted from <image> in Rockon json file.
        tag_from_json (str): if tag existed in json file it should be populated, otherwise optional.
        github_token (str): Github PAT token, if any image is from the github container registry.
        codeberg_token (str): Codeberg API token, currently not required to inspect containers on the registry.
        print_payload (bool): If True, prints the request headers and payload.
    """
    registry, owner, image_name, tag_to_check = parse_image(image_str, tag_from_json)
    # tag_to_check = tag_from_json if tag_from_json is not None else inferred_tag

    # temporarily: github token is not encoded
    # github_token = ''
    # codeberg_token = ''   

    if registry.startswith('ghcr.io'):
        if github_token is None:
            print("Warning: GitHub token not provided. Checks for ghcr.io images may be inaccurate.")
        return check_ghcr_image(owner, image_name, tag_to_check, github_token, print_payload)
    elif registry.startswith('codeberg.org'):
        return check_codeberg_image(owner, image_name, tag_to_check, codeberg_token, print_payload)
    # Insert conditions here for any other container registries. If API tokens are required, then assign interfaces
    else:
        # Assume Docker Hub for all other image names, including those with a slash
        return check_docker_hub_image(owner, image_name, tag_to_check, print_payload)

def process_json_files(directory, github_token, codeberg_token, print_payload):
    """
    Reads JSON files from a specified directory, extracts image and tag
    information, and returns the data as a list of dictionaries.

    Args:
        directory (str): The path to the directory containing the JSON files.

    Returns:
        list: A list of dictionaries, where each dictionary represents a row
              in the final table.
    """
    extracted_data = []

    # Check if the target directory exists
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' not found.")
        return extracted_data

    # Iterate over all files in the directory
    for filename in os.listdir(directory):
        # Skip the exclusion file and files that are not JSON
        if filename == EXCLUSION_FILE or not filename.endswith('.json'):
            continue

        file_path = os.path.join(directory, filename)
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

                # The file identifier is the top-level key.
                file_identifier = list(data.keys())[0]

                # Access the containers dictionary
                containers = data.get(file_identifier, {}).get('containers', {})

                # Iterate through each container within the 'containers' key
                for container_name, container_details in containers.items():
                    image = container_details.get('image')
                    tag = container_details.get('tag')

                    # Only process if an image is found
                    if image:
                        # Use the dispatcher function to check the repository
                        repo_info = check_image_repository(image, tag, github_token, codeberg_token, print_payload)
                        
                        # Set the tag for the output table, using 'latest' if none is found
                        display_tag = tag if tag is not None else 'latest'

                        extracted_data.append({
                            "Rockon": file_identifier,
                            "image": image,
                            "tag": display_tag,
                            "image:tag": f"{image}:{display_tag}",
                            "Availability": repo_info.get("available"),
                            "Last Published": repo_info.get("last_published")[:10] # truncate to yyy-mm-dd only
                        })

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from file '{filename}': {e}")
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found at '{file_path}'.")
        except Exception as e:
            print(f"An unexpected error occurred while processing '{filename}': {e}")

    return extracted_data

def get_images_from_json(directory):
    """
    Reads JSON files to extract all unique image:tag combinations before network calls.
    """
    images = set()

    if not os.path.isdir(directory):
        return images

    for filename in os.listdir(directory):
        if filename == EXCLUSION_FILE or not filename.endswith('.json'):
            continue

        file_path = os.path.join(directory, filename)
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
                def find_images_recursive(obj):
                    if isinstance(obj, dict):
                        image = obj.get('image')
                        tag = obj.get('tag')
                        if image:
                            display_tag = tag if tag is not None and tag != '' else 'latest'
                            images.add(f"{image}:{display_tag}")
                        for value in obj.values():
                            find_images_recursive(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            find_images_recursive(item)

                find_images_recursive(data)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Warning: Could not read or parse {filename}. Error: {e}")

    return sorted(list(images))

def print_results(results, output_format):
    
    # sort by earliest last publishing/change date
    results.sort(key=lambda x: (x["Last Published"], x["Rockon"]))

    """Prints the results in the specified format."""
    if output_format == 'json':
        output_data = [
            {"rockon": r['Rockon'], "image": r['image:tag'], "version": r['tag'], "status": r['Availability'], "last_published": r['Last Published']}
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
                                <th class="py-3 px-4 text-left font-semibold">Rockon</th>
                                <th class="py-3 px-4 text-left font-semibold">Image</th>
                                <th class="py-3 px-4 text-left font-semibold">Version</th>
                                <th class="py-3 px-4 text-left font-semibold">Status</th>
                                <th class="py-3 px-4 text-left font-semibold">Last Published</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        for r in results:
            image_name = r['image:tag']
            status = r['Availability']
            date = r['Last Published']
            rockon_name = r['Rockon']
            version = r['tag']
            status_class = "text-green-600 font-medium" if status == "Available" else "text-red-600 font-medium"
            html_content += f"""
                            <tr class="border-t border-gray-200 hover:bg-gray-50">
                                <td class="py-3 px-4 text-gray-700">{rockon_name}</td>
                                <td class="py-3 px-4 text-gray-700 font-mono">{image_name}</td>
                                <td class="py-3 px-4 text-gray-700">{version}</td>
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
        print("| Rockon | Image | Version | Status | Last Published |")
        print("|---|---|---|---|---|")
        for r in results:
            print(f"| {r['Rockon']} | {r['image:tag']} | {r['tag']} | {r['Availability']} | {r['Last Published']} |")

    else:  # 'console' is the default
        if results:
            # Reformat results for tabulate
            formatted_results = [
                (r['Rockon'], r['image:tag'], r['tag'], r['Availability'], r['Last Published']) for r in results
            ]
            print(tabulate(formatted_results, headers=["Rockon", "Image", "Version", "Status", "Last Published"], tablefmt="pipe"))
        else:
            print("No data extracted. Please check the directory and file contents.")


def main():
    """Main function to parse arguments and run the checks."""
    parser = argparse.ArgumentParser(description="Check container image availability.")
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
    parser.add_argument("-d", "--directory", type=str, default=TARGET_DIRECTORY,
                        help=f"Specify the directory to scan for JSON files. Defaults to '{TARGET_DIRECTORY}'.")

    args = parser.parse_args()

    # Use command-line argument if provided, otherwise check environment variables
    github_token = args.github_token or os.environ.get("GITHUB_TOKEN")
    codeberg_token = args.codeberg_token or os.environ.get("CODEBERG_TOKEN")
    json_directory = args.directory

    results = []

    if args.image:
        print(f"Checking a single image: {args.image}")
        # Parse the single image and process it
        registry, owner, image_name, tag = parse_image(args.image)
        repo_info = check_image_repository(args.image, tag, github_token, codeberg_token, args.print_payload)
        
        display_tag = tag if tag is not None and tag != '' else 'latest'
        
        results.append({
            "Rockon": "N/A",
            "image": args.image,
            "tag": display_tag,
            "image:tag": f"{args.image}:{display_tag}",
            "Availability": repo_info.get("available"),
            "Last Published": repo_info.get("last_published")
        })

    else:
        # Default behavior: scan JSON files
        images_to_check = get_images_from_json(json_directory)
        if not images_to_check:
            print("No images to check. Exiting.")
            return

        print("\nFound the following unique image:tag combinations:")
        for img in images_to_check:
            print(f"- {img}")
        print("\n")
        
        results = process_json_files(json_directory, github_token, codeberg_token, args.print_payload)

    print_results(results, args.output_format)

if __name__ == "__main__":
    main()
