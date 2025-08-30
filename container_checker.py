# A program to extract image and tag information from JSON configuration files,
# including checks for image availability on Docker Hub.

import os
import json
import requests
import re
from tabulate import tabulate

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
    elif tag_from_json == '':
        image_name = image_str
        tag = tag_from_json
    else:
        image_name = image_str
        tag = 'latest'

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

    return {"available": "Not Implemented", "last_published": "N/A"}

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

        return {"available": "Not Implemented", "last_published": "N/A"}

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
        return check_ghcr_image(owner, image_name, tag_to_check, github_token, print_payload)
    elif registry.startswith('codeberg.org'):
        return check_codeberg_image(owner, image_name, tag_to_check, codeberg_token, print_payload)
    # Insert conditions here for any other container registries. If API tokens are required, then assign interfaces
    else:
        # Assume Docker Hub for all other image names, including those with a slash
        return check_docker_hub_image(owner, image_name, tag_to_check, print_payload)

def process_json_files(directory):
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
                        repo_info = check_image_repository(image, tag)
                        
                        # Set the tag for the output table, using 'latest' if none is found
                        display_tag = tag if tag is not None else 'latest'

                        extracted_data.append({
                            "Rockon Name": file_identifier,
                            "image": image,
                            "tag": display_tag,
                            "image:tag": f"{image}:{display_tag}",
                            "Availability": repo_info.get("available"),
                            "Last Published": repo_info.get("last_published")
                        })

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from file '{filename}': {e}")
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found at '{file_path}'.")
        except Exception as e:
            print(f"An unexpected error occurred while processing '{filename}': {e}")

    return extracted_data

if __name__ == "__main__":
    # Process the files and get the data
    data_to_display = process_json_files(TARGET_DIRECTORY)

    # Print the data as a formatted table
    if data_to_display:
        print(tabulate(data_to_display, headers="keys", tablefmt="pipe"))
    else:
        print("No data extracted. Please check the directory and file contents.")
